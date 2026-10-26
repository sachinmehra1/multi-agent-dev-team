"""Three-agent LangGraph with pre-QA reflection and bounded A2A feedback."""
import os
from pathlib import Path
from typing import Literal
from pydantic import Field
from langgraph.graph import StateGraph, START, END
from orchestration.models import StrictModel
from orchestration.project_state import ProjectState
from orchestration.qa_models import (QAReport, QAIssue, ReflectionRecord, FixRecord,
                                     ReviewRequest, source_digest)
from orchestration.a2a import Broker, Message


class FinalReport(StrictModel):
    approved: bool
    reason: Literal['all_tests_passed', 'iteration_limit', 'workflow_error']
    qa_iterations: int
    max_qa_iterations: int
    unresolved_issues: list[QAIssue]


class TeamState(StrictModel):
    requirement: str
    project: ProjectState | None = None
    source: dict[str, str] = Field(default_factory=dict)
    acceptance_criteria: list[str] = Field(default_factory=list)
    reflection: ReflectionRecord | None = None
    fixes: list[FixRecord] = Field(default_factory=list)
    qa_reports: list[QAReport] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    qa_iterations: int = 0
    error: str | None = None
    final_report: FinalReport | None = None


def qa_limit():
    value = int(os.getenv('QA_MAX_ITERATIONS', '5'))
    if not 1 <= value <= 20:
        raise ValueError('QA_MAX_ITERATIONS must be an integer from 1 to 20')
    return value


def application_source(snapshot):
    return {name:code for name,code in snapshot.items()
            if name.endswith('.py') and not Path(name).name.startswith(('test_', '_qa_'))
            and 'tests' not in Path(name).parts and Path(name).name != 'conftest.py'}


class TeamWorkflow:
    def __init__(self, project, reviser, qa, *, max_iterations=None, task_id='project'):
        self.project, self.reviser, self.qa = project, reviser, qa
        self.limit = qa_limit() if max_iterations is None else max_iterations
        if not isinstance(self.limit, int) or isinstance(self.limit, bool) or not 1 <= self.limit <= 20:
            raise ValueError('QA iteration limit must be from 1 to 20')
        self.task_id = task_id
        self.broker = Broker()
        builder = StateGraph(TeamState)
        for name in ('generate', 'reflect', 'qa_review', 'fix', 'finalize'):
            builder.add_node(name, getattr(self, name))
        builder.add_edge(START, 'generate')
        builder.add_conditional_edges('generate', lambda s:'finalize' if s.error else 'reflect')
        builder.add_conditional_edges('reflect', lambda s:'finalize' if s.error else 'qa_review')
        builder.add_conditional_edges('qa_review', self.route)
        builder.add_conditional_edges('fix', lambda s:'finalize' if s.error else 'qa_review')
        builder.add_edge('finalize', END)
        self.graph = builder.compile()

    def generate(self, state):
        try:
            project = self.project.run(state.requirement)
            if not project.complete:
                return {'project':project, 'error':project.error or 'Initial generation failed'}
            source = application_source(project.code_output)
            if not source:
                raise ValueError('No application source produced')
            criteria = list(dict.fromkeys(project.technical_spec.acceptance_criteria +
                [c for t in project.tasks for c in t.acceptance_criteria]))
            # Generation completion is not final QA approval.
            project = project.model_copy(update={'complete':False})
            return {'project':project, 'source':source, 'acceptance_criteria':criteria}
        except Exception as exc:
            return {'error':'Generation failed: '+type(exc).__name__}

    def reflect(self, state):
        try:
            record = self.reviser.reflect(state.source, state.requirement)
            return {'reflection':record, 'source':record.after}
        except Exception as exc:
            return {'error':'Reflection failed: '+type(exc).__name__}

    def qa_review(self, state):
        iteration = state.qa_iterations + 1
        if iteration > self.limit:
            return {'error':'QA budget guard triggered'}
        try:
            request = ReviewRequest(task_id=self.task_id, requirement=state.requirement,
                acceptance_criteria=state.acceptance_criteria, source=state.source,
                source_digest=source_digest(state.source), iteration=iteration)
            response = self.broker.review(Message(sender='coder', receiver='qa', intent='review_request',
                                                 payload=request.model_dump()), self.qa)
            report = QAReport.model_validate(response.payload)
            return {'qa_reports':state.qa_reports + [report], 'qa_iterations':iteration,
                    'messages':[Message.model_validate(m) for m in self.broker.log],
                    'error':None if report.test_code else 'QA could not produce a validated test suite'}
        except Exception as exc:
            return {'qa_iterations':iteration, 'error':'QA protocol failed: '+type(exc).__name__,
                    'messages':[Message.model_validate(m) for m in self.broker.log]}

    def route(self, state):
        return 'finalize' if state.error or state.qa_reports[-1].approved or state.qa_iterations >= self.limit else 'fix'

    def fix(self, state):
        try:
            record = self.reviser.fix(state.source, state.requirement, state.messages[-1])
            return {'source':record.after, 'fixes':state.fixes + [record]}
        except Exception as exc:
            return {'error':'Coder revision failed: '+type(exc).__name__}

    def finalize(self, state):
        latest = state.qa_reports[-1] if state.qa_reports else None
        approved = bool(not state.error and latest and latest.approved and
                        latest.source_digest == source_digest(state.source))
        issues = latest.issues[:] if latest else []
        if not approved and (state.error or not issues):
            issues.append(QAIssue(location='workflow', description=state.error or 'No current QA approval',
                fix_instruction='Resolve the workflow error and rerun behavioral QA.',
                acceptance_criteria=state.acceptance_criteria or [state.requirement]))
        report = FinalReport(approved=approved, reason='all_tests_passed' if approved else
                             'workflow_error' if state.error else 'iteration_limit',
                             qa_iterations=state.qa_iterations, max_qa_iterations=self.limit,
                             unresolved_issues=issues)
        updates = {'final_report':report}
        if state.project:
            updates['project'] = state.project.model_copy(update={
                'complete':approved, 'code_output':{**state.project.code_output, **state.source}})
        return updates

    def stream(self, requirement):
        self.broker = Broker()
        self.qa.suites.clear()
        for value in self.graph.stream(TeamState(requirement=requirement),
                                       config={'recursion_limit':2*self.limit + 10}, stream_mode='values'):
            yield TeamState.model_validate(value)

    def run(self, requirement):
        final = None
        for final in self.stream(requirement):
            pass
        return final


def build_team(model, workspace, memory_path, *, session_id='module3', max_iterations=None):
    from orchestration.project_graph import build_project
    from agents.coder_agent import CoderReviser
    from agents.qa_agent import QAAgent
    from tools.pytest_runner import PytestRunner
    project = build_project(model, workspace, memory_path, session_id=session_id,
                            image='coder-python-qa:module3')
    project.coder.system_prompt = project.coder.system_prompt.replace('Python standard library and Flask are installed',
                                                                      'Python standard library and pytest are installed')
    reviser = CoderReviser(model, project.coder.tools.files)
    qa = QAAgent(model, PytestRunner(timeout=float(os.getenv('QA_TIMEOUT_SECONDS','10'))))
    return TeamWorkflow(project, reviser, qa, max_iterations=max_iterations, task_id=session_id)
