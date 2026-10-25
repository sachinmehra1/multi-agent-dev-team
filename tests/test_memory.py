from orchestration.memory import ConversationMemory, SemanticMemory
from tests.conftest import TestEmbedding

def test_last_n_complete_exchanges():
    memory = ConversationMemory(2)
    for i in range(5):
        memory.add(str(i), str(i))
    assert [m["content"] for m in memory.messages()] == ["3", "Observation: 3", "4", "Observation: 4"]

def test_persistence_and_session_isolation(tmp_path):
    first = SemanticMemory(tmp_path, TestEmbedding())
    first.store("python sort preference", "alice")
    first.store("other private preference", "bob")
    reopened = SemanticMemory(tmp_path, TestEmbedding())
    assert reopened.retrieve("python", "alice") == ["python sort preference"]
    assert reopened.retrieve("python", "unknown") == []
