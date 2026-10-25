from pydantic import Field
from orchestration.models import StrictModel

class PathInput(StrictModel):
    path: str = Field(min_length=1, max_length=240)

class WriteInput(PathInput):
    content: str

class ToolRegistry:
    def __init__(self, files, runner):
        self.files, self.runner = files, runner

    def dispatch(self, name, arguments):
        if name == "write_file":
            args = WriteInput.model_validate(arguments)
            return self.files.write_file(**args.model_dump())
        args = PathInput.model_validate(arguments)
        if name == "read_file":
            return {"content": self.files.read_file(args.path)}
        if name in ("run_code", "exec_python", "execute_python"):
            return self.runner.run_code(args.path).model_dump()
        raise ValueError("Unknown tool")
