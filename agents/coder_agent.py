"""Composition root for Module 1; future agents can call run(task)."""
from orchestration.observability import agent_span
from orchestration.graph import CoderGraph
from orchestration.memory import ConversationMemory, SemanticMemory
from tools.files import FileTools
from tools.execution import CodeRunner
from tools.registry import ToolRegistry


def build_agent(model, workspace="workspace", memory_path=".chroma", last_n=5, timeout=10):
    files = FileTools(workspace)
    return CoderGraph(model, ConversationMemory(last_n), SemanticMemory(memory_path),
                      ToolRegistry(files, CodeRunner(files, timeout=timeout)))


def execute_project_task(state, coder, session_id):
    """Consume all handoff fields and preserve prior artifacts in typed shared state."""
    import json
    from orchestration.project_state import Handoff, Progress, TaskArtifact
    handoff = Handoff.model_validate(state.handoff)
    task = state.tasks[state.current_task_index]
    if not handoff.ready or handoff != Handoff.for_task(task) or task.status != "running":
        raise ValueError("Handoff does not match the running task")
    prompt = (
        "Implement only the current handoff task in the shared project workspace, preserving completed work.\n"
        "Original requirement: " + state.original_requirement + "\n"
        "Specification: " + state.technical_spec.model_dump_json() + "\n"
        "Consume this ready handoff (including priority and acceptance criteria): "
        + handoff.model_dump_json() + "\n"
        "Accumulated source: " + json.dumps(state.code_output) + "\n"
        "Keep application modules importable and create runnable assertion scripts. "
        "The runner uses Python -I: for local imports in a test script, add "
        "str(pathlib.Path(__file__).resolve().parent) to sys.path before importing app. "
        "Read existing files before changing them. Run tests of the task's acceptance criteria."
    )
    if '/health' in state.original_requirement and '/echo' in state.original_requirement:
        from orchestration.api_fixture import FIXTURE
        prompt += "\nFlask is installed. Keep app.py importable with module-level app and use app.test_client(). Do not start a server."
        prompt += "\nDocumented local HTTP acceptance cases (use the specified content_type for malformed JSON): " + FIXTURE.read_text()
    output = coder.run(prompt, session_id=session_id)
    status = "completed" if output.task_complete else "failed"
    tasks = [t.model_copy(deep=True) for t in state.tasks]
    tasks[state.current_task_index].status = status
    code = dict(state.code_output)
    code.update(coder.tools.files.snapshot())
    return {"tasks":tasks, "current_task_index":state.current_task_index + 1,
            "handoff":handoff.model_copy(update={"ready":False}),
            "code_output":code,
            "artifacts":state.artifacts + [TaskArtifact(task_id=task.task_id, output=output)],
            "progress":state.progress + [Progress(task_id=task.task_id,status=status,
                                                  message=output.explanation)],
            "error":None if output.task_complete else output.error or "Coder task failed"}


class CoderReviser:
    """Explicit critique then revision; QA feedback is consumed through A2A payloads."""
    def __init__(self, model, files):
        self.model, self.files = model, files

    def _revise(self, source, requirement, instructions):
        import ast
        import json
        from orchestration.qa_models import Revision
        prompt = ('Revise the application according to the supplied critique or QA fix instructions. '
                  'Preserve its public interface and all requested behavior. Return complete replacement source '
                  'for changed existing application files only. Do not change tests. Make a substantive code '
                  'improvement addressing the instructions, not only comments or formatting. Return JSON: '
                  + json.dumps(Revision.model_json_schema()))
        reply = self.model.complete([{'role':'system','content':prompt}, {'role':'user','content':json.dumps({
            'requirement':requirement, 'source':source, 'instructions':instructions})}])
        revision = Revision.model_validate_json(reply.content)
        if not revision.files or not set(revision.files) <= set(source):
            raise ValueError('Revision must update existing application files')
        changed = False
        for name,code in revision.files.items():
            self.files.path(name)
            changed |= executable_ast(code) != executable_ast(source[name])
        if not changed:
            raise ValueError('Revision did not change application code')
        for name,code in revision.files.items():
            self.files.write_file(name, code)
        return {**source, **revision.files}, revision.explanation

    @agent_span("coder")
    def reflect(self, source, requirement):
        import json
        from orchestration.qa_models import Critique, ReflectionRecord
        prompt = ('Self-critique the application before QA. Identify concrete potential bugs or edge cases and '
                  'propose at least one substantive improvement within the existing interface. No private reasoning; '
                  'only concise actionable findings. Honor the requirement: do not change first-match deletion, '
                  'specified return types, or accepted values. Consider empty/singleton early returns and explicit '
                  'None checks as robustness improvements; do not propose documentation-only changes. Return JSON: '+json.dumps(Critique.model_json_schema()))
        reply = self.model.complete([{'role':'system','content':prompt}, {'role':'user','content':json.dumps({
            'requirement':requirement, 'source':source})}])
        critique = Critique.model_validate_json(reply.content)
        after, explanation = self._revise(source, requirement, critique.model_dump())
        return ReflectionRecord(critique=critique, explanation=explanation, before=source, after=after)

    @agent_span("coder")
    def fix(self, source, requirement, message):
        from orchestration.a2a import Message
        from orchestration.qa_models import QAReport, FixRecord, source_digest
        message = Message.model_validate_json(message.model_dump_json())
        if message.intent != 'fix_instruction' or message.receiver != 'coder':
            raise ValueError('Coder needs QA fix_instruction')
        report = QAReport.model_validate(message.payload)
        if report.source_digest != source_digest(source):
            raise ValueError('Fix instructions target stale code')
        after, explanation = self._revise(source, requirement, report.model_dump())
        return FixRecord(feedback=report, explanation=explanation, before=source, after=after)


def executable_ast(code):
    """Ignore comments/docstrings when deciding whether reflection changed code."""
    import ast
    class StripDocstrings(ast.NodeTransformer):
        def visit(self, node):
            node = super().visit(node)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                    node.body.pop(0)
            return node
    return ast.dump(StripDocstrings().visit(ast.parse(code)))
