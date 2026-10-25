import sys
import pytest
from tools.files import FileTools
from tools.execution import CodeRunner, bounded_process
from tools.registry import ToolRegistry

@pytest.mark.parametrize("path", ["../escape.py", "/tmp/escape.py", ".env", "a/../../x", ".git/config"])
def test_path_escape_rejected(tmp_path, path):
    files = FileTools(tmp_path/"work")
    with pytest.raises(ValueError):
        files.write_file(path, "bad")

def test_symlink_rejected(tmp_path):
    files = FileTools(tmp_path/"work")
    (files.root/"link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        files.write_file("link/out.py", "bad")
    with pytest.raises(ValueError):
        files.snapshot()

def test_read_write_and_size_limit(tmp_path):
    files = FileTools(tmp_path/"work")
    files.write_file("sub/x.py", "print(42)")
    assert files.read_file("sub/x.py") == "print(42)"
    with pytest.raises(ValueError):
        files.write_file("huge.py", "x" * 100001)

def test_unknown_arguments_rejected(tmp_path):
    files = FileTools(tmp_path/"work")
    registry = ToolRegistry(files, CodeRunner(files))
    with pytest.raises(ValueError):
        registry.dispatch("write_file", {"path": "x.py", "content": "x", "shell": True})

def test_timeout(tmp_path):
    files = FileTools(tmp_path/"work")
    files.write_file("loop.py", "while True: pass")
    result = CodeRunner(files, backend="trusted-local", timeout=0.15).run_code("loop.py")
    assert result.status == "timeout"

def test_output_limit():
    result = bounded_process([sys.executable, "-I", "-c", "while True: print('x'*1024)"], timeout=2)
    assert result.status == "output_limit"
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 65536

def test_credentials_not_in_child_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "must-not-leak")
    files = FileTools(tmp_path/"work")
    files.write_file("env.py", "import os; assert 'LLM_API_KEY' not in os.environ; print('ok')")
    result = CodeRunner(files, backend="trusted-local").run_code("env.py")
    assert result.status == "passed"

def test_no_unsafe_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.execution.shutil.which", lambda _: None)
    files = FileTools(tmp_path/"work")
    files.write_file("x.py", "print(1)")
    assert CodeRunner(files).run_code("x.py").status == "unavailable"

@pytest.mark.parametrize("name", ["exec_python", "execute_python"])
def test_exec_python_alias(tmp_path, name):
    files = FileTools(tmp_path/"work")
    files.write_file("x.py", "print(1)")
    assert getattr(CodeRunner(files, backend="trusted-local"), name)("x.py").status == "passed"


def test_docker_restrictions_and_cleanup(tmp_path, monkeypatch):
    from orchestration.models import ExecutionResult
    files = FileTools(tmp_path/"work")
    files.write_file("x.py", "print(1)")
    captured = {}
    monkeypatch.setattr("tools.execution.shutil.which", lambda _: "/usr/bin/docker")
    def run(command, **kwargs):
        captured["command"] = command
        captured["payload"] = kwargs["payload"]
        return ExecutionResult(status="timeout")
    def cleanup(command, **kwargs):
        captured["cleanup"] = command
    monkeypatch.setattr("tools.execution.bounded_process", run)
    monkeypatch.setattr("tools.execution.subprocess.run", cleanup)
    assert CodeRunner(files).run_code("x.py").status == "timeout"
    command = captured["command"]
    for flag in ["--network=none", "--read-only", "--cap-drop=ALL", "--user=65534:65534", "--pids-limit=32"]:
        assert flag in command
    assert "--volume" not in command and "-v" not in command
    name = command[command.index("--name")+1]
    assert captured["cleanup"] == ["/usr/bin/docker", "rm", "-f", name]
