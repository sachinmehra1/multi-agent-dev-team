import json
import pytest
from chromadb.api.types import EmbeddingFunction
from chromadb.utils.embedding_functions import register_embedding_function
from orchestration.llm import ModelReply
from orchestration.memory import ConversationMemory, SemanticMemory
from orchestration.graph import CoderGraph
from tools.files import FileTools
from tools.execution import CodeRunner
from tools.registry import ToolRegistry

@register_embedding_function
class TestEmbedding(EmbeddingFunction):
    __test__ = False

    def __init__(self):
        pass

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return TestEmbedding()

    """Deterministic vectors for plumbing tests, NOT semantic embeddings."""
    def __call__(self, input):
        return [[float("python" in s.lower()), float("sort" in s.lower()), 1.0] for s in input]
    @staticmethod
    def name():
        return "test-only-v1"
    def embed_query(self, input):
        return self(input)

class ScriptedModel:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
        self.messages = []
    def complete(self, messages):
        self.messages.append(messages)
        item = next(self.decisions)
        return ModelReply(item if isinstance(item, str) else json.dumps(item), 7)

def decision(action, **arguments):
    return {"thought": "Perform " + action, "action": action, "arguments": arguments}

def finish(complete=True):
    return {"thought": "Report result", "action": "finish", "final": {
        "task_complete": complete, "code": "model code is not trusted", "explanation": "Implemented and checked.",
        "plan": ["Write code", "Execute assertions", "Return result"]}}

@pytest.fixture
def factory(tmp_path):
    def make(steps, backend="trusted-local", timeout=2):
        files = FileTools(tmp_path/"workspace")
        semantic = SemanticMemory(tmp_path/"chroma", TestEmbedding())
        model = ScriptedModel(steps)
        agent = CoderGraph(model, ConversationMemory(2), semantic,
                           ToolRegistry(files, CodeRunner(files, backend=backend, timeout=timeout)))
        return agent, model, semantic
    return make
