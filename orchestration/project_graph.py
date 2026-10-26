"""Sequential PM → ready handoff → Coder workflow in a single LangGraph process."""
from langgraph.graph import StateGraph, START, END
from agents.pm_agent import ProductManager
from agents.coder_agent import execute_project_task
from orchestration.project_state import ProjectState, Handoff, Progress


class ProjectWorkflow:
    def __init__(self, pm_model, coder, verifier=None, session_id='project'):
        self.pm = ProductManager(pm_model)
        self.coder = coder
        self.verifier = verifier
        self.session_id = session_id
        builder = StateGraph(ProjectState)
        builder.add_node('pm', self.pm)
        builder.add_node('prepare', self.prepare)
        builder.add_node('coder', self.code)
        builder.add_node('verify', self.verify)
        builder.add_edge(START, 'pm')
        builder.add_conditional_edges('pm', lambda s: END if s.error else 'prepare')
        builder.add_edge('prepare', 'coder')
        builder.add_conditional_edges('coder', self.route_after_coder)
        builder.add_edge('verify', END)
        self.graph = builder.compile()

    def prepare(self, state):
        task = state.tasks[state.current_task_index]
        if state.current_task_index == 0:
            handoff = state.handoff
            if handoff != Handoff.for_task(task):
                raise ValueError('Invalid initial PM handoff')
            history = state.handoff_history
        else:
            handoff = Handoff.for_task(task)
            history = state.handoff_history + [handoff]
        tasks = [t.model_copy(deep=True) for t in state.tasks]
        tasks[state.current_task_index].status = 'running'
        return {'tasks':tasks, 'handoff':handoff, 'handoff_history':history,
                'progress':state.progress + [Progress(task_id=task.task_id,status='running',
                                                     message='Coder received ready handoff')]}

    def code(self, state):
        try:
            return execute_project_task(state, self.coder, self.session_id)
        except Exception as exc:
            tasks = [t.model_copy(deep=True) for t in state.tasks]
            task = tasks[state.current_task_index]
            task.status = 'failed'
            return {'tasks':tasks, 'error':'Coder failed: '+type(exc).__name__,
                    'handoff':state.handoff.model_copy(update={'ready':False}),
                    'progress':state.progress + [Progress(task_id=task.task_id,status='failed',
                                                         message='Coder could not complete task')]}

    @staticmethod
    def route_after_coder(state):
        if state.error:
            return END
        return 'prepare' if state.current_task_index < len(state.tasks) else 'verify'

    def verify(self, state):
        if not state.tasks or any(t.status != 'completed' for t in state.tasks):
            return {'error':'Not every planned task completed'}
        if self.verifier is None:
            return {'complete':True}
        try:
            result = self.verifier(state.code_output)
            return {'verification':result, 'complete':result.status == 'passed',
                    'error':None if result.status == 'passed' else 'API acceptance fixture failed'}
        except Exception as exc:
            return {'error':'Verification failed: '+type(exc).__name__}

    def stream(self, requirement):
        for state in self.graph.stream(ProjectState(original_requirement=requirement),
                                       config={'recursion_limit':32}, stream_mode='values'):
            yield ProjectState.model_validate(state)

    def run(self, requirement):
        final = None
        for final in self.stream(requirement):
            pass
        return final


def build_project(model, workspace, memory_path, *, session_id='project', verify_api=False,
                  image='coder-python-api:module2'):
    from orchestration.graph import CoderGraph
    from orchestration.llm import SYSTEM_PROMPT
    from orchestration.memory import ConversationMemory, SemanticMemory
    from tools.files import FileTools
    from tools.registry import ToolRegistry
    from tools.execution import CodeRunner
    from orchestration.api_fixture import verify_api_source
    files = FileTools(workspace)
    system = SYSTEM_PROMPT.replace('Only Python standard library is installed\nin the execution container.',
                                   'Python standard library and Flask are installed in the execution container.')
    coder = CoderGraph(model, ConversationMemory(5), SemanticMemory(memory_path),
                       ToolRegistry(files, CodeRunner(files, image=image)), system_prompt=system)
    verifier = (lambda code: verify_api_source(code, image=image)) if verify_api else None
    return ProjectWorkflow(model, coder, verifier, session_id)
