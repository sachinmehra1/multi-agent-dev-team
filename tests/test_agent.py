import json
import pytest
from pydantic import ValidationError
from orchestration.models import AgentOutput, AgentState
from tests.conftest import decision, finish

CODE = "def add(a, b):\n    return a + b\nassert add(2, 3) == 5\nassert add(-1, 1) == 0\nprint(add(2, 3))\n"

@pytest.mark.parametrize("execution_tool", ["execute_python", "exec_python", "run_code"])
def test_smoke_real_graph_chroma_and_subprocess(factory, execution_tool):
    agent, model, memory = factory([decision("write_file", path="add.py", content=CODE),
                                   decision("read_file", path="add.py"),
                                   decision(execution_tool, path="add.py"), finish()])
    output = agent.run("Write and test a Python addition function")
    assert output.task_complete
    assert output.result.stdout.strip() == "5"
    assert output.result.status == "passed"
    assert CODE in output.code
    assert output.files_written == ["add.py"]
    assert output.iterations_used == 4 and output.total_tokens == 28
    assert set(("code", "explanation", "plan", "result")) <= output.model_dump().keys()
    AgentOutput.model_validate_json(output.model_dump_json())
    assert memory.collection.count() == 3
    assert "addition" in model.messages[-1][2]["content"]

def test_retrieves_before_every_call_including_repair(factory):
    agent, model, memory = factory(["not JSON", finish(False)])
    calls = []
    original = memory.retrieve
    def retrieve(*a, **kw):
        calls.append(a)
        return original(*a, **kw)
    memory.retrieve = retrieve
    out = agent.run("sort python list")
    assert len(calls) == len(model.messages) == 2
    assert out.iterations_used == 2

def test_invalid_output_fails_after_one_retry(factory):
    agent, model, _ = factory(['{}', '{"bogus":true}', finish()])
    out = agent.run("task")
    assert out.error == "Invalid structured output after repair"
    assert len(model.messages) == 2

def test_identical_action_loop_stops_before_third_dispatch(factory):
    agent, model, memory = factory([decision("read_file", path="missing.py")]*5)
    out = agent.run("task")
    assert "Repeated" in out.error
    assert out.iterations_used == 3
    assert memory.collection.count() == 2

def test_three_action_cycle(factory):
    steps = [decision("read_file", path=f"{i}.py") for i in range(3)] * 3
    agent, model, _ = factory(steps)
    out = agent.run("task")
    assert out.iterations_used == 6
    assert "cycle" in out.error

def test_max_ten_calls(factory):
    agent, model, _ = factory([decision("read_file", path=f"{i}.py") for i in range(15)])
    out = agent.run("task")
    assert len(model.messages) == out.iterations_used == 10
    assert "Maximum" in out.error

def test_finish_on_tenth_call(factory):
    steps = [decision("read_file", path=f"{i}.py") for i in range(7)]
    steps += [decision("write_file", path="x.py", content="print(1)"), decision("run_code", path="x.py"), finish()]
    agent, _, _ = factory(steps)
    out = agent.run("task")
    assert out.task_complete and out.iterations_used == 10

def test_edits_invalidate_execution(factory):
    agent, _, _ = factory([decision("write_file", path="x.py", content="print(1)"),
        decision("run_code", path="x.py"), decision("write_file", path="x.py", content="raise Exception()"), finish()])
    out = agent.run("task")
    assert not out.task_complete and out.result.status == "not_run"

def test_failure_not_disguised_as_success(factory):
    agent, _, _ = factory([decision("write_file", path="x.py", content="assert False"),
                           decision("run_code", path="x.py"), finish()])
    out = agent.run("task")
    assert not out.task_complete and out.result.status == "failed"

def test_provider_exception_redacted(factory):
    agent, model, _ = factory([])
    def broken(messages):
        raise RuntimeError("credential-should-never-appear")
    model.complete = broken
    out = agent.run("task")
    assert "credential-should-never-appear" not in out.model_dump_json()
    assert out.iterations_used == 1

def test_memory_failure_is_structured(factory):
    agent, _, memory = factory([])
    def broken(*a, **kw):
        raise RuntimeError("internal")
    memory.retrieve = broken
    assert agent.run("task").error == "Semantic memory retrieval failed"

def test_bounds():
    with pytest.raises(ValidationError):
        AgentState(task="x", session_id="s", max_iterations=11)


def test_session_switch_clears_conversation(factory):
    agent, model, _ = factory([decision("read_file", path="first.py"), finish(False), finish(False)])
    agent.run("first session task", session_id="first")
    agent.run("second session task", session_id="second")
    assert "first session task" not in json.dumps(model.messages[-1])
    assert "first.py" not in json.dumps(model.messages[-1])


def test_execution_aliases_share_loop_guard(factory):
    steps = [decision("write_file", path="x.py", content="print(1)")]
    steps += [decision(name, path="x.py") for name in ("execute_python", "exec_python", "run_code")]
    agent, _, memory = factory(steps)
    out = agent.run("Run the script")
    assert "Repeated" in out.error
    assert out.iterations_used == 4
    assert memory.collection.count() == 3
