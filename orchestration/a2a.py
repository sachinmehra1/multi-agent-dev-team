"""Course A2A: JSON envelopes, capability routing and correlated request/reply.

This implements the course's in-process protocol, not the external HTTP A2A standard.
"""
from queue import Queue, Empty
from uuid import uuid4, UUID
from typing import Literal
from pydantic import Field, model_validator
from orchestration.models import StrictModel
from orchestration.qa_models import ReviewRequest, QAReport


class Message(StrictModel):
    sender: Literal['coder', 'qa']
    receiver: Literal['coder', 'qa']
    intent: Literal['review_request', 'fix_instruction', 'approved']
    payload: dict
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))

    @model_validator(mode='after')
    def validate_route(self):
        UUID(self.correlation_id)
        expected = ('coder', 'qa') if self.intent == 'review_request' else ('qa', 'coder')
        if (self.sender, self.receiver) != expected:
            raise ValueError('Sender/receiver is not allowed for this intent')
        if self.intent == 'review_request':
            ReviewRequest.model_validate(self.payload)
        else:
            report = QAReport.model_validate(self.payload)
            if report.approved != (self.intent == 'approved'):
                raise ValueError('Intent conflicts with QA result')
        return self


class Broker:
    capabilities = {'qa': ['review_request'], 'coder': ['fix_instruction', 'approved']}

    def __init__(self):
        self.queues = {name: Queue() for name in self.capabilities}
        self.log = []
        self.pending = {}

    def send(self, message):
        # Real serialization boundary: no agent shares a mutable message object.
        message = Message.model_validate_json(message.model_dump_json())
        if message.intent not in self.capabilities[message.receiver]:
            raise ValueError('Unsupported receiver capability')
        if message.intent == 'review_request':
            if message.correlation_id in self.pending:
                raise ValueError('Duplicate correlation ID')
            self.pending[message.correlation_id] = (message.payload['task_id'], message.payload['source_digest'])
        else:
            expected = self.pending.get(message.correlation_id)
            actual = (message.payload['task_id'], message.payload['source_digest'])
            if expected != actual:
                raise ValueError('Unknown, stale or mismatched response')
            del self.pending[message.correlation_id]
        self.queues[message.receiver].put(message.model_dump_json())
        self.log.append(message.model_dump())

    def receive(self, agent, timeout=1):
        if agent not in self.queues:
            raise ValueError('Unknown receiver')
        try:
            return Message.model_validate_json(self.queues[agent].get(timeout=timeout))
        except Empty:
            raise TimeoutError('No protocol message received') from None

    def review(self, request, qa):
        self.send(request)
        delivered = self.receive('qa')
        self.send(qa.handle(delivered))
        response = self.receive('coder')
        if response.correlation_id != request.correlation_id:
            raise ValueError('Response correlation mismatch')
        return response
