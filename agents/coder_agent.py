"""Composition root for Module 1; future agents can call run(task)."""
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
        "Flask is installed. Keep app.py importable with module-level app. "
        "Use app.test_client() in runnable assertion scripts; do not start a permanent HTTP server. "
        "The runner uses Python -I: for local imports in a test script, add "
        "str(pathlib.Path(__file__).resolve().parent) to sys.path before importing app. "
        "Read existing files before changing them. Run tests of the task's acceptance criteria."
    )
    if '/health' in state.original_requirement and '/echo' in state.original_requirement:
        from orchestration.api_fixture import FIXTURE
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
