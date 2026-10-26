import os
from orchestration.observability import tool_call
from collections import deque
from uuid import uuid4
import chromadb
from chromadb.config import Settings

class ConversationMemory:
    """Last N complete exchanges; the current task remains separately pinned."""
    def __init__(self, last_n=5):
        if last_n < 1:
            raise ValueError("last_n must be positive")
        self.turns = deque(maxlen=last_n)

    def add(self, request, response):
        self.turns.append((request, response))

    def messages(self):
        return [m for a, b in self.turns for m in (
            {"role": "assistant", "content": a},
            {"role": "user", "content": "Observation: " + b},
        )]

class SemanticMemory:
    """Persistent Chroma vectors. Default ONNX MiniLM embeds locally on first use.

    Inject an embedding function only for deterministic tests. Collection naming
    versions the embedding space; do not reuse with a different embedding model.
    """
    def __init__(self, path, embedding_function=None):
        if os.getenv('CHROMA_HOST'):
            self.client = chromadb.HttpClient(host=os.environ['CHROMA_HOST'],
                port=int(os.getenv('CHROMA_PORT','8000')), settings=Settings(anonymized_telemetry=False))
        else:
            self.client = chromadb.PersistentClient(
                path=str(path), settings=Settings(anonymized_telemetry=False))
        options = {} if embedding_function is None else {"embedding_function": embedding_function}
        self.collection = self.client.get_or_create_collection("coder_v1_minilm", **options)

    def store(self, text, session_id):
        from orchestration.observability import ACTIVE
        record_id = str(uuid4())
        call = lambda:self.collection.add(ids=[record_id], documents=[text[:8000]],
                                           metadatas=[{"session_id": session_id}])
        runtime = ACTIVE.get()
        return runtime.tool('memory.store',call) if runtime else call()

    @tool_call("memory.retrieve")
    def retrieve(self, query, session_id, k=3):
        if self.collection.count() == 0:
            return []
        result = self.collection.query(query_texts=[query], n_results=k,
                                       where={"session_id": session_id}, include=["documents"])
        return (result.get("documents") or [[]])[0]
