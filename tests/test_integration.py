"""Opt-in checks: never silently download models or call a paid API during pytest."""
import os
import shutil
import subprocess
import pytest
from orchestration.memory import SemanticMemory
from tools.files import FileTools
from tools.execution import CodeRunner

@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1 with Docker and image installed")
def test_real_container_isolation(tmp_path):
    assert shutil.which("docker"), "Docker required"
    files = FileTools(tmp_path/"workspace")
    files.write_file("probe.py", """import os, pathlib, socket
assert os.getuid() == 65534
assert 'LLM_API_KEY' not in os.environ
assert not pathlib.Path('/var/run/docker.sock').exists()
try:
    pathlib.Path('/etc/blocked').write_text('x')
except OSError:
    pass
else:
    raise AssertionError('root filesystem writable')
s=socket.socket(); s.settimeout(1)
assert s.connect_ex(('1.1.1.1', 443)) != 0
print('isolated')
""")
    runner = CodeRunner(files)
    result = runner.run_code("probe.py")
    assert result.status == "passed", result
    files.write_file("loop.py", "while True: pass")
    assert CodeRunner(files, timeout=1).run_code("loop.py").status == "timeout"

@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_SEMANTIC_TESTS") != "1", reason="Set RUN_SEMANTIC_TESTS=1 to download/use MiniLM")
def test_real_semantic_retrieval(tmp_path):
    memory = SemanticMemory(tmp_path)
    memory.store("Use Python type hints and small functions.", "s")
    memory.store("The garden flowers need watering.", "s")
    found = memory.retrieve("coding style preferences for typed Python functions", "s", k=1)
    assert "type hints" in found[0]

@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM") != "1", reason="Set RUN_LIVE_LLM=1 with API configuration and Docker")
def test_live_end_to_end(tmp_path):
    from agents.coder_agent import build_agent
    from orchestration.llm import ChatModel
    model = ChatModel(os.getenv("LLM_MODEL", "gpt-4o"), os.environ["LLM_API_KEY"],
                      os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    agent = build_agent(model, tmp_path/"work", tmp_path/"chroma")
    result = agent.run("Write a Python addition function and a runnable script with assertions for 2+3 and -1+1; execute it.")
    assert result.task_complete and result.result.status == "passed", result
    from orchestration.models import AgentOutput
    assert {"code", "explanation", "plan", "result"} <= result.model_dump().keys()
    AgentOutput.model_validate_json(result.model_dump_json())
    assert result.code and result.explanation and result.plan
    actual = "\n\n".join(f"# File: {name}\n" + agent.tools.files.read_file(name)
                            for name in result.files_written)
    assert result.code == actual
    assert result.result.exit_code == 0
