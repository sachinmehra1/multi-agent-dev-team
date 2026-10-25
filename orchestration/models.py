from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class ExecutionResult(StrictModel):
    status: Literal["not_run", "passed", "failed", "timeout", "unavailable", "output_limit"] = "not_run"
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None

class FinalAnswer(StrictModel):
    task_complete: bool
    code: str
    explanation: str = Field(min_length=1)
    plan: list[str] = Field(min_length=1)

class Decision(StrictModel):
    # A short operational summary, not private chain-of-thought.
    thought: str = Field(min_length=1, max_length=500)
    action: Literal["read_file", "write_file", "run_code", "exec_python", "finish"]
    arguments: dict = Field(default_factory=dict)
    final: FinalAnswer | None = None

    @model_validator(mode="after")
    def coherent(self):
        if (self.action == "finish") != (self.final is not None):
            raise ValueError("Only finish must include final")
        if self.action == "finish" and self.arguments:
            raise ValueError("finish arguments must be empty")
        return self

class AgentOutput(FinalAnswer):
    result: ExecutionResult
    files_written: list[str]
    iterations_used: int = Field(ge=0, le=10)
    total_tokens: int = Field(ge=0)
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)

class AgentState(BaseModel):
    task: str
    session_id: str
    iterations: int = 0
    max_iterations: int = Field(default=10, ge=1, le=10)
    actions: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    files_written: list[str] = Field(default_factory=list)
    result: ExecutionResult = Field(default_factory=ExecutionResult)
    decision: Decision | None = None
    output: AgentOutput | None = None
    error: str | None = None
    invalid_outputs: int = 0
    total_tokens: int = 0
    warnings: list[str] = Field(default_factory=list)
