"""Composition root for Module 1; future agents can call run(task)."""
from orchestration.graph import CoderGraph
from orchestration.memory import ConversationMemory, SemanticMemory
from tools.files import FileTools
from tools.execution import CodeRunner
from tools.registry import ToolRegistry


def build_agent(model, workspace="workspace", memory_path=".chroma", last_n=5, timeout=10):
    files = FileTools(workspace)
    return CoderGraph(model, ConversationMemory(last_n), SemanticMemory(memory_path),
                      ToolRegistry(files, CodeRunner(files, timeout=timeout)))
