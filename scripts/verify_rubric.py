"""Opt-in live rubric evidence: real model, MiniLM/Chroma, and Docker execution.

Run from the repository root: python -m scripts.verify_rubric
Only task inputs, recalled context, short action summaries, and tool results are
saved. Keys and provider request headers are never recorded.
"""
import json
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from agents.coder_agent import build_agent
from orchestration.llm import ChatModel
from orchestration.models import AgentOutput


class ObservedModel:
    def __init__(self, model):
        self.model = model
        self.calls = []

    def complete(self, messages):
        reply = self.model.complete(messages)
        try:
            decision = json.loads(reply.content)
        except (ValueError, TypeError):
            decision = {}
        if not isinstance(decision, dict):
            decision = {}
        self.calls.append({
            "retrieved_context": json.loads(messages[2]["content"].split(": ", 1)[1]),
            "recent_buffer": messages[3:],
            "action": decision.get("action"),
        })
        return reply


def observe_tools(agent):
    records = []
    dispatch = agent.tools.dispatch
    def observed(name, arguments):
        result = dispatch(name, arguments)
        records.append({"tool": name, "arguments": arguments, "observation": result})
        return result
    agent.tools.dispatch = observed
    return records


def validate(output, agent):
    assert isinstance(output, AgentOutput)
    AgentOutput.model_validate_json(output.model_dump_json())
    assert {"code", "explanation", "plan", "result"} <= output.model_dump().keys()
    assert output.task_complete and output.result.status == "passed", output.error
    assert output.explanation and output.plan and output.code
    assert output.result.exit_code == 0
    assert 1 <= output.iterations_used <= 10
    actual = "\n\n".join(f"# File: {path}\n" + agent.tools.files.read_file(path)
                           for path in output.files_written)
    assert output.code == actual


def main():
    load_dotenv()
    model = ChatModel("gpt-4o", os.environ["LLM_API_KEY"],
                      os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    tasks = [
        "Create addition.py with add(a, b), assertions for positive and negative numbers, "
        "and REPORT_TAG = 'saras-memory-17'. Print REPORT_TAG followed by the result of add(2, 3). "
        "Use write_file, then read_file to inspect the saved source, then exec_python to run it. "
        "Return validated results only after observing successful execution.",
        "Continue the previous addition task. Recall the REPORT_TAG value from saved context. "
        "Create followup.py with that same REPORT_TAG and an addition function, assert that "
        "add(-4, -6) equals -10, and print REPORT_TAG followed by -10. Use write_file, "
        "read_file and exec_python. Confirm successful execution before finishing.",
    ]
    report = {"model": "gpt-4o", "framework": "LangGraph", "last_n": 2,
              "execution_timeout_seconds": 10, "runs": []}
    with tempfile.TemporaryDirectory(prefix="rubric-live-") as folder:
        root = Path(folder)
        for index, task in enumerate(tasks):
            observed = ObservedModel(model)
            # A fresh graph has no short-term turns; Chroma persists between runs.
            agent = build_agent(observed, root / "work", root / "chroma", last_n=2)
            assert not agent.conversation.messages()
            tools = observe_tools(agent)
            output = agent.run(task, session_id="rubric")
            validate(output, agent)
            artifacts = Path("docs/rubric-artifacts") / f"run{index + 1}"
            for name in output.files_written:
                destination = artifacts / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(agent.tools.files.read_file(name))
            print(f"Run {index + 1}: iterations={output.iterations_used}, tools={[r['tool'] for r in tools]}", flush=True)
            assert {"read_file", "write_file", "run_code"} <= {r["tool"] for r in tools}
            assert all(len(call["recent_buffer"]) <= 4 for call in observed.calls)
            assert "saras-memory-17" in output.result.stdout
            if index == 0:
                assert observed.calls[0]["retrieved_context"] == []
            else:
                assert "saras-memory-17" not in task
                assert "saras-memory-17" in json.dumps(observed.calls[0]["retrieved_context"])
                assert "-10" in output.result.stdout
            report["runs"].append({"task": task, "llm_calls": observed.calls,
                                   "tool_calls": tools, "output": output.model_dump(),
                                   "buffer_after_run": agent.conversation.messages()})
    path = Path("docs/rubric-live-evidence.json")
    path.write_text(json.dumps(report, indent=2) + "\n")
    print("PASS: two real-model tasks; all tools; persisted retrieval; bounded buffer; validated artifact-matching results")


if __name__ == "__main__":
    main()
