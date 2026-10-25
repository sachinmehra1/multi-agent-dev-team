# Multi-Agent Development Team — Coder Agent v1.0

Saras AI Institute · Build Autonomous Multi-Agent Systems · Module 1.

## Module 1 submission hub

The four official lab forks are completed and tested:

| Lab | Repository | Results |
|---|---|---|
| 1.1 | [Memory](https://github.com/sachinmehra1/Multi-agents-lab-1-1-memory) | 5 offline tests + live recall passed |
| 1.2 | [Tools](https://github.com/sachinmehra1/Multi-agents-lab-1-2-tools) | 24 tests + live demo passed |
| 1.3 | [ReACT Coder](https://github.com/sachinmehra1/Multi-agents-lab-1-3-react-coder) | 24 supplied tests including live + 3 regression tests passed |
| 1.4 | [LangGraph / AutoGen / CrewAI](https://github.com/sachinmehra1/Multi-agents-lab-1-4-langgraph-autogen-crewai) | 29 live tests + 9 artifact tests passed |

**Submit this repository URL:** https://github.com/sachinmehra1/multi-agent-dev-team

[Lab evidence and reproduction notes](docs/course-labs.md) ·
[Actual framework comparison](https://github.com/sachinmehra1/Multi-agents-lab-1-4-langgraph-autogen-crewai/blob/main/comparison/results.json)

Live labs used the owner's OpenAI account directly. No user keys are included.
LMS submission remains pending.

## Standalone Coder Agent

A single LangGraph Coder agent accepts a natural-language Python task, writes files,
executes them in a restricted container, and returns Pydantic-validated JSON.
The PM and QA modules are explicitly reserved for Modules 2 and 3.

**Delivery status:** implemented, tested locally, and published at
https://github.com/sachinmehra1/multi-agent-dev-team. LMS submission remains pending.
The standalone implementation and the official lab forks have separate test evidence.
See [submission instructions](docs/submission.md) and [test evidence](docs/verification.md).
The live GPT-4o + Chroma + Docker addition task passed; its actual result is in
[the live run record](docs/live-addition-output.json).

## Setup

Use Python 3.12, Git and Docker Engine/Desktop (Linux containers).

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
```

Set `LLM_API_KEY` in your local `.env`. Default model: `gpt-4o`, as specified in the
course guide. Do not paste credentials into source files, prompts, logs or Git.
Alternatively use a running Ollama server with an installed JSON-capable model:
set `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL` to its exact model name,
and `LLM_API_KEY=ollama`. Provider/model availability must be verified in your account.
The adapter uses the OpenAI-compatible chat endpoint via HTTP and validates responses
locally, so model-provided JSON is never trusted without validation.

```bash
docker pull python:3.12-slim
python main.py "Write a Python function to sort numbers, add assertions for empty and duplicate inputs, and execute it."
```

First use downloads Chroma's local ONNX MiniLM embedding model (~80 MB). Subsequent
runs use its cache. Chroma data persists in `.chroma/`; generated files live under
`workspace/<session>/`. Do not use a workspace containing credentials or personal files.
Use `--session lesson1` on later invocations to retrieve that session's prior context.
The sliding conversation window is in-process; semantic memory survives restarts.
A graph instance is single-user and sequential, not thread-safe.

JSON goes to stdout; metadata-only JSON events go to stderr. Exit 0 means the agent
reported completion with a successful latest execution; exit 1 means incomplete or
failed. Successful execution is evidence of passing the generated checks, not a proof
that arbitrary requirements are correct. Review generated code before relying on it.

## Required repository structure

```text
multi-agent-dev-team/
├── agents/                 # coder_agent.py; reserved pm_agent.py, qa_agent.py
├── tools/                  # confined file I/O, bounded Docker subprocess, registry
├── orchestration/          # LangGraph, Pydantic state/output, LLM, two-layer memory
├── tests/                  # smoke, failures, memory, opt-in integrations
├── docs/                   # architecture, requirements, verification, submission
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── main.py
└── README.md
```

## Design decisions

- **LangGraph:** explicit `think → act → think` graph with a finalization node makes
  budgets, transitions and failure behavior visible. It is the actual runtime,
  not an optional import or a mock framework.
- **Memory:** a deque retains the last N complete decision/observation exchanges
  (default 5). The task and system instructions remain pinned. Chroma embeds and
  retrieves the top 3 matching records before **every** model call, including a
  validation retry. Task context and observations are stored after each tool call.
  Session metadata filters prevent retrieval across sessions; switching session
  clears the in-process conversation. Retrieved content is explicitly untrusted.
- **ReACT:** each response supplies a short operational `thought`, a typed action
  and typed arguments. These are action summaries, not private reasoning traces.
  The actual action summaries form the returned execution plan.
- **Guards:** at most 10 total model calls; a malformed response gets one repair
  within that budget. The third consecutive identical action is blocked, as is a
  repeating three-action cycle. Excess context stops with a structured error.
- **Tools:** `read_file`, `write_file`, `execute_python` and the aliases `run_code` and `exec_python`.
  File tools reject absolute paths, traversal, hidden paths and symlinks. UTF-8
  files are capped at 100 KB each, 64 files and a 1 MB execution snapshot.
- **Sandbox:** Docker is mandatory for model-generated code. Each execution gets a
  fresh source snapshot via stdin, no host bind mounts, no network, a read-only
  root filesystem, an unprivileged user, no capabilities, limited memory/CPU/PIDs,
  temporary storage and capped output. A host subprocess enforces a configurable
  timeout (10 seconds by default). Timeout/overflow triggers container removal.
  There is no `eval`, shell command execution, or automatic unsafe fallback.
- **Output integrity:** final code and filenames come from actual file operations.
  Execution results come from the runner. Writing a file invalidates earlier test
  evidence; a model cannot mark completion after a failed or missing execution.
- **Observability:** logs include model/tool calls, token usage and termination
  metadata, without raw prompts, responses, source or credentials. `total_tokens`
  uses provider-reported usage (0 if omitted). Dollar pricing is not guessed.

Full details: [architecture](docs/architecture.md), [requirements map](docs/requirements.md).

## Structured output

```json
{
  "task_complete": true,
  "code": "# File: add.py\nprint(2 + 3)",
  "explanation": "Implemented and checked addition.",
  "plan": ["Write the addition script", "Run the script"],
  "result": {"status": "passed", "stdout": "5\n", "stderr": "", "exit_code": 0},
  "files_written": ["add.py"],
  "iterations_used": 3,
  "total_tokens": 123,
  "error": null,
  "warnings": []
}
```

This is an illustrative shape, not a recorded live-model result. Result statuses:
`not_run`, `passed`, `failed`, `timeout`, `unavailable`, `output_limit`.

## Tests

```bash
python -m pytest -q
# Opt in individually (PowerShell: set $env:RUN_DOCKER_TESTS="1", then run pytest):
RUN_DOCKER_TESTS=1 python -m pytest tests/test_integration.py -q
RUN_SEMANTIC_TESTS=1 python -m pytest tests/test_integration.py -q
RUN_LIVE_LLM=1 python -m pytest tests/test_integration.py -q
```

The default suite uses the real LangGraph and Chroma with deterministic test vectors,
a scripted model and explicitly trusted fixture code in a local subprocess. This
makes tests free and offline after dependency installation. It does **not** establish
live LLM quality or Docker isolation. The integration switches test those separately.
`trusted-local` is available to test code only through the Python API; it is not a
security sandbox and is never selected by the CLI or `build_agent`.
Live tests need environment variables exported in the shell (pytest does not load `.env`).

## Docker Compose

After preparing `.env` and pulling `python:3.12-slim`:

```bash
docker compose run --build --rm coder
# Or provide another task:
docker compose run --rm coder "Write and test an iterative factorial function."
```

Compose runs the trusted orchestrator with access to the host Docker socket, so it
can launch separate code sandboxes. **That socket grants host-level Docker control**;
only use this configuration with trusted orchestration source on a development machine.
Generated code never receives the socket or API credentials. For stronger separation,
run the CLI locally against a dedicated Docker daemon/VM. Compose's named volume
preserves workspace and memory; its embedding cache is temporary and may redownload.
Docker sandbox execution and timeout checks passed locally; the Compose build remains untested.

## Limits

Python standard-library, self-contained scripts are the intended Module 1 workload.
Execution uses Python isolated mode (`-I`), so sibling-module imports and third-party
packages are not supported by the default runner. Runtime writes occur only in the
disposable container and are not copied back; persistent source must use `write_file`.
Container isolation is not a formal guarantee against kernel vulnerabilities.
Path checks assume no hostile concurrent host process replacing workspace entries.
Memory and generated code can contain user-provided sensitive text: use non-sensitive
tasks, keep runtime directories private, and never commit them. No project/course PDFs
are bundled in this public-ready source distribution.
