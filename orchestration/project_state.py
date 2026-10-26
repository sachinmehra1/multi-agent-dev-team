"""Validated state and JSON handoffs shared by PM and Coder."""
from typing import Literal
from pydantic import Field, model_validator
from orchestration.models import StrictModel, AgentOutput, ExecutionResult


class CodingTask(StrictModel):
    task_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    priority: int = Field(ge=1, le=5)
    source_task_ids: list[str] = Field(default_factory=list)
    status: Literal['pending', 'running', 'completed', 'failed'] = 'pending'


class TechnicalSpec(StrictModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    tasks: list[CodingTask] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def unique_tasks(self):
        ids = [t.task_id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError('Task IDs must be unique')
        if any(t.status != 'pending' for t in self.tasks):
            raise ValueError('PM tasks must start pending')
        return self


class Handoff(StrictModel):
    ready: bool = True
    task_id: str
    description: str
    acceptance_criteria: list[str]
    priority: int

    @classmethod
    def for_task(cls, task):
        return cls(**task.model_dump(include={'task_id','description','acceptance_criteria','priority'}))


class Progress(StrictModel):
    task_id: str
    status: Literal['ready','running','completed','failed']
    message: str


class TaskArtifact(StrictModel):
    task_id: str
    output: AgentOutput


class ProjectState(StrictModel):
    original_requirement: str = Field(min_length=1)
    technical_spec: TechnicalSpec | None = None
    original_tasks: list[CodingTask] = Field(default_factory=list)
    tasks: list[CodingTask] = Field(default_factory=list, max_length=8)
    current_task_index: int = Field(default=0, ge=0, le=8)
    handoff: Handoff | None = None
    handoff_history: list[Handoff] = Field(default_factory=list)
    progress: list[Progress] = Field(default_factory=list)
    code_output: dict[str, str] = Field(default_factory=dict)
    artifacts: list[TaskArtifact] = Field(default_factory=list)
    verification: ExecutionResult | None = None
    complete: bool = False
    error: str | None = None
