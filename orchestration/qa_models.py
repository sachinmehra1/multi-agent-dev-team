"""Strict QA, reflection and protocol payload models."""
import hashlib
import json
from typing import Literal
from pydantic import Field, model_validator
from orchestration.models import StrictModel, ExecutionResult


def source_digest(source):
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


class QAIssue(StrictModel):
    severity: Literal['High', 'Medium', 'Low'] = 'High'
    location: str = Field(min_length=1)
    description: str = Field(min_length=1)
    fix_instruction: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)


class TestSuite(StrictModel):
    code: str = Field(min_length=1, max_length=50000)
    # Acceptance criterion -> generated pytest function names.
    coverage: dict[str, list[str]]


class QAReport(StrictModel):
    task_id: str
    source_digest: str
    approved: bool
    issues: list[QAIssue]
    execution: ExecutionResult
    tests_run: int = Field(ge=0)
    passed_tests: list[str] = Field(default_factory=list)
    test_code: str = ''
    coverage: dict[str, list[str]] = Field(default_factory=dict)
    command: list[str] = Field(default_factory=list)
    timeout_seconds: float = 10.0

    @model_validator(mode='after')
    def honest_approval(self):
        valid = self.execution.status == 'passed' and self.tests_run > 0 and not self.issues
        if self.approved != valid:
            raise ValueError('Approval must agree with actual test execution and issues')
        return self


class ReviewRequest(StrictModel):
    task_id: str
    requirement: str
    acceptance_criteria: list[str] = Field(min_length=1)
    source: dict[str, str]
    source_digest: str
    iteration: int = Field(ge=1)

    @model_validator(mode='after')
    def digest_matches(self):
        if source_digest(self.source) != self.source_digest:
            raise ValueError('Source digest mismatch')
        return self


class CritiqueItem(StrictModel):
    location: str = Field(min_length=1)
    concern: str = Field(min_length=1)
    proposed_revision: str = Field(min_length=1)


class Critique(StrictModel):
    items: list[CritiqueItem] = Field(min_length=1, max_length=8)


class Revision(StrictModel):
    explanation: str = Field(min_length=1)
    files: dict[str, str]


class ReflectionRecord(StrictModel):
    critique: Critique
    explanation: str
    before: dict[str, str]
    after: dict[str, str]


class FixRecord(StrictModel):
    feedback: QAReport
    explanation: str
    before: dict[str, str]
    after: dict[str, str]
