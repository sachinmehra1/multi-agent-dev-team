"""Docker is the security boundary; a working directory alone is not a sandbox."""
from orchestration.observability import tool_call
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from uuid import uuid4
from orchestration.models import ExecutionResult

# This bootstrap receives only source files and the selected entry point.
BOOTSTRAP = """
import json, pathlib, subprocess, sys
payload=json.load(sys.stdin)
for name, content in payload['files'].items():
    p=pathlib.Path('/work')/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
r=subprocess.run([sys.executable, '-I', payload['path']], cwd='/work', stdin=subprocess.DEVNULL)
sys.exit(r.returncode)
"""

def bounded_process(command, *, timeout, payload=None, cwd=None):
    """Drain pipes with a shared 64 KB budget and kill on timeout/overflow."""
    env = {"PATH": os.defpath, "LANG": "C.UTF-8"}
    # Docker CLI needs its normal configuration; no environment reaches the container.
    if command[0] != sys.executable:
        for key in ("HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"):
            if key in os.environ:
                env[key] = os.environ[key]
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    lock = threading.Lock()
    exceeded = threading.Event()
    def drain(stream, label):
        while data := stream.read(1024):
            with lock:
                room = 65536 - sum(map(len, chunks.values()))
                chunks[label].extend(data[:max(0, room)])
                if len(data) > room:
                    exceeded.set()
                    proc.kill()
        stream.close()
    def feed():
        try:
            proc.stdin.write(payload or b"")
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    readers = [threading.Thread(target=drain, args=(getattr(proc, label), label), daemon=True)
               for label in chunks]
    for thread in readers:
        thread.start()
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    for thread in readers:
        thread.join(timeout=1)
    status = "timeout" if timed_out else "output_limit" if exceeded.is_set() else "passed" if proc.returncode == 0 else "failed"
    with lock:
        return ExecutionResult(status=status, exit_code=proc.returncode,
                               **{k: bytes(v).decode("utf-8", errors="replace") for k, v in chunks.items()})

class CodeRunner:
    def __init__(self, files, timeout=10, image="python:3.12-slim", backend="docker"):
        if not 0 < timeout <= 60:
            raise ValueError("timeout must be > 0 and <= 60 seconds")
        if backend not in {"docker", "trusted-local"}:
            raise ValueError("Unknown execution backend")
        self.files, self.timeout, self.image, self.backend = files, timeout, image, backend

    @tool_call("run_code")
    def run_code(self, path):
        target = self.files.path(path)
        if target.suffix != ".py" or not target.is_file():
            raise ValueError("run_code needs an existing .py file")
        snapshot = self.files.snapshot()
        if self.backend == "trusted-local":
            # Explicit test-only escape hatch. Never use for untrusted model output.
            with tempfile.TemporaryDirectory() as folder:
                for name, content in snapshot.items():
                    p = Path(folder) / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content)
                return bounded_process([sys.executable, "-I", str(Path(folder)/path)],
                                       timeout=self.timeout, cwd=folder)
        docker = shutil.which("docker")
        if not docker:
            return ExecutionResult(status="unavailable", stderr="Docker is required; no unsafe fallback was used.")
        name = "coder-" + uuid4().hex
        command = [docker, "run", "--rm", "--pull=never", "--name", name, "--network=none",
                   "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                   "--user=65534:65534", "--memory=128m", "--memory-swap=128m", "--cpus=0.5",
                   "--pids-limit=32", "--ulimit", "nofile=64:64", "--ulimit", "fsize=1048576:1048576",
                   "--tmpfs", "/work:rw,noexec,nosuid,size=16m,uid=65534,gid=65534",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m,uid=65534,gid=65534",
                   "--workdir=/work", "--log-driver=none", "--entrypoint=python", "-i", self.image,
                   "-I", "-c", BOOTSTRAP]
        try:
            return bounded_process(command, timeout=self.timeout,
                                   payload=json.dumps({"files": snapshot, "path": path}).encode())
        finally:
            # Killing the CLI alone does not guarantee the container stopped.
            subprocess.run([docker, "rm", "-f", name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=False)

    exec_python = run_code

    execute_python = run_code
