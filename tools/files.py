from orchestration.observability import tool_call
from pathlib import Path

class FileTools:
    """A dedicated workspace, never the repository or a directory with secrets.

    Reject symlinks and traversal. Concurrent hostile host modifications are out
    of scope; generated code receives snapshots, never a writable host mount.
    """
    MAX_BYTES = 100_000
    MAX_FILES = 64

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name):
        if not isinstance(name, str) or not name or len(name) > 240:
            raise ValueError("Invalid workspace-relative path")
        p = Path(name)
        if p.is_absolute() or any(x in ("..", ".git") or x.startswith(".") for x in p.parts):
            raise ValueError("Absolute, hidden and traversal paths are forbidden")
        target = self.root / p
        for component in [target, *target.parents]:
            if component == self.root:
                break
            if component.is_symlink():
                raise ValueError("Symlinks are forbidden")
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Path escapes workspace")
        return target

    @tool_call("read_file")
    def read_file(self, path):
        p = self.path(path)
        with p.open("rb") as stream:
            data = stream.read(self.MAX_BYTES + 1)
        if len(data) > self.MAX_BYTES:
            raise ValueError("File exceeds 100 KB limit")
        return data.decode("utf-8")

    @tool_call("write_file")
    def write_file(self, path, content):
        if not isinstance(content, str) or len(content.encode()) > self.MAX_BYTES:
            raise ValueError("Content must be UTF-8 text <= 100 KB")
        p = self.path(path)
        if not p.exists() and sum(1 for x in self.root.rglob("*") if x.is_file()) >= self.MAX_FILES:
            raise ValueError("Workspace file limit reached")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"path": str(p.relative_to(self.root)), "bytes": len(content.encode())}

    def snapshot(self):
        files = {}
        for p in self.root.rglob("*"):
            if p.is_symlink():
                raise ValueError("Workspace contains a symlink")
            if p.is_file():
                name = p.relative_to(self.root).as_posix()
                files[name] = self.read_file(name)
                if len(files) > self.MAX_FILES or sum(len(x.encode()) for x in files.values()) > 1_000_000:
                    raise ValueError("Workspace snapshot limit exceeded")
        return files
