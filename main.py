import argparse
import json
import logging
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from agents.coder_agent import build_agent
from orchestration.llm import ChatModel
from orchestration.models import AgentOutput, ExecutionResult


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Saras AI Institute Coder Agent v1.0")
    parser.add_argument("task", help="Natural language coding task")
    parser.add_argument("--session", default="default", help="Reuse to retrieve previous Chroma memories")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.session):
        parser.error("session must be 1-64 letters, digits, underscores or hyphens")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # HTTP client logs include URLs; do not enable third-party request tracing.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        key = os.getenv("LLM_API_KEY", "")
        if not key and "api.openai.com" in base_url:
            raise ValueError("Set LLM_API_KEY in your local .env")
        agent = build_agent(ChatModel(os.getenv("LLM_MODEL", "gpt-4o"), key or "ollama", base_url),
            workspace=Path(os.getenv("WORKSPACE_DIR", "workspace"))/args.session,
            memory_path=os.getenv("CHROMA_DIR", ".chroma"),
            last_n=int(os.getenv("MEMORY_LAST_N", "5")),
            timeout=float(os.getenv("EXECUTION_TIMEOUT", "10")))
        result = agent.run(args.task, session_id=args.session)
    except Exception:
        # Avoid serializing provider exception bodies, URLs, headers or credentials.
        result = AgentOutput(task_complete=False, code="", explanation="Startup or execution failed; check configuration, dependencies and connectivity.",
            plan=["Initialize agent"], result=ExecutionResult(), files_written=[], iterations_used=0,
            total_tokens=0, error="Agent initialization or runtime failure")
    print(result.model_dump_json(indent=2))
    return 0 if result.task_complete else 1

if __name__ == "__main__":
    raise SystemExit(main())
