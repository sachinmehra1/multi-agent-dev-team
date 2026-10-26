"""Generate behavioral pytest tests, execute them, and return evidence-based fixes."""
import ast
import json
from orchestration.a2a import Message
from orchestration.qa_models import TestSuite, QAIssue, QAReport, ReviewRequest
from tools.pytest_runner import PytestRunner, PYTEST_ARGS
from orchestration.models import ExecutionResult


def validate_suite(suite, criteria):
    tree = ast.parse(suite.code)
    functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')}
    if not functions or set(suite.coverage) != set(criteria):
        raise ValueError('Tests must map every acceptance criterion')
    for names in suite.coverage.values():
        if not names or any(name not in functions for name in names):
            raise ValueError('Coverage refers to missing test functions')
    for node in functions.values():
        if not any(isinstance(n, ast.Assert) for n in ast.walk(node)):
            raise ValueError('Every test must assert behavior')
    if any(isinstance(n, ast.Attribute) and n.attr in {'skip','skipif','xfail'} for n in ast.walk(tree)):
        raise ValueError('QA tests may not skip or xfail')
    return suite


class QAAgent:
    def __init__(self, model, runner=None):
        self.model = model
        self.runner = runner or PytestRunner()
        self.suites = {}

    def suite_for(self, request):
        if request.task_id in self.suites:
            criteria, suite = self.suites[request.task_id]
            if criteria != request.acceptance_criteria:
                raise ValueError('Acceptance criteria changed during QA')
            return suite
        prompt = ('You are the QA agent. Write real pytest behavioral tests for every acceptance criterion. '
                  'Import the provided application, call its methods and assert their results or observable state. '
                  'Do not merely check code presence. Include normal, empty, missing-item, singleton and duplicate cases '
                  'where relevant. For a linked list independently exercise insert, delete, search and reverse. '
                  'Use a Python list as a reference model to compute expected remaining values after each operation. '
                  'Delete removes ONLY the first matching occurrence: other duplicates must remain. '
                  'Assert every specified return value, including reverse() is None for empty and non-empty lists. '
                  'Do not start servers, modify application code, skip, xfail, mock the application or execute shell commands. '
                  'Use only pytest and Python standard library. Each top-level test_* function needs an assert. '
                  'The coverage keys must EXACTLY match the provided acceptance criteria; values are test function names. '
                  'Return only JSON matching this schema: ' + json.dumps(TestSuite.model_json_schema()))
        reply = self.model.complete([{'role':'system','content':prompt},
                                    {'role':'user','content':request.model_dump_json()}])
        suite = validate_suite(TestSuite.model_validate_json(reply.content), request.acceptance_criteria)
        self.suites[request.task_id] = (request.acceptance_criteria[:], suite)
        return suite

    def review(self, request):
        suite = None
        try:
            suite = self.suite_for(request)
            execution, records = self.runner.run(request.source, suite.code)
        except Exception as exc:
            execution = ExecutionResult(status='failed', stderr='QA setup failed: '+type(exc).__name__)
            records = []
        issues = []
        passed = []
        ran = set()
        for record in records:
            location = record.get('nodeid', 'pytest')
            function = location.split('::')[-1].split('[')[0]
            criteria = [c for c,names in suite.coverage.items() if function in names] if suite else []
            if record.get('phase') == 'call':
                ran.add(location)
            if record.get('outcome') == 'passed' and record.get('phase') == 'call':
                passed.append(location)
            elif record.get('outcome') in {'failed', 'skipped'}:
                detail = record.get('detail') or 'Test did not pass'
                issues.append(QAIssue(location=location, description=detail,
                    fix_instruction='Revise the application to satisfy this failing assertion; keep the QA tests unchanged. '+detail,
                    acceptance_criteria=criteria or request.acceptance_criteria))
        if suite:
            passed_functions = {name.split('::')[-1].split('[')[0] for name in passed}
            for criterion,names in suite.coverage.items():
                if not any(name in passed_functions for name in names) and not issues:
                    issues.append(QAIssue(location='coverage', description='No passing behavioral test for: '+criterion,
                        fix_instruction='Provide working behavior for this acceptance criterion.', acceptance_criteria=[criterion]))
        if (execution.status != 'passed' or not ran) and not issues:
            detail = execution.stderr or execution.stdout[-3000:] or 'No behavioral tests executed'
            issues.append(QAIssue(location='pytest execution', description=detail,
                fix_instruction='Resolve the reported test execution failure without removing tests. '+detail,
                acceptance_criteria=request.acceptance_criteria))
        return QAReport(task_id=request.task_id, source_digest=request.source_digest,
                        approved=execution.status == 'passed' and bool(ran) and not issues,
                        issues=issues, execution=execution, tests_run=len(ran), passed_tests=passed,
                        test_code=suite.code if suite else '', coverage=suite.coverage if suite else {},
                        command=['python','-I','_qa_runner.py','=>','pytest',*PYTEST_ARGS],
                        timeout_seconds=float(self.runner.timeout))

    def handle(self, message):
        message = Message.model_validate_json(message.model_dump_json())
        if message.sender != 'coder' or message.receiver != 'qa' or message.intent != 'review_request':
            raise ValueError('QA accepts only Coder review_request')
        report = self.review(ReviewRequest.model_validate(message.payload))
        return Message(sender='qa', receiver='coder',
                       intent='approved' if report.approved else 'fix_instruction',
                       payload=report.model_dump(), correlation_id=message.correlation_id)
