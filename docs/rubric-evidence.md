# Module 1 rubric evidence: C1.1–C1.6

This assesses the main LangGraph Coder Agent in this repository. The course-wide
rubric dated 20 October 2026, pages 1, 3 and 4, makes the six criteria mandatory;
recommended labs and multiple frameworks are optional supporting work.
The assessor determines the final grade. This is an evidence map, not an awarded mark.

| Criterion | Implementation and probes | Observed evidence |
|---|---|---|
| C1.1 Reproducible project | Required agents/, tools/, orchestration/, tests/, docs/; .env.example, Dockerfile, docker-compose.yml, requirements.txt and README.md. Python 3.12, pinned dependencies, LangGraph and GPT-4o. | README setup, GitHub Actions setup and real Docker/live runs reach the Coder. PM/QA placeholders are intentional. |
| C1.2 Two memory layers | orchestration/memory.py; CoderGraph.think retrieves before every call; test_last_n_complete_exchanges and test_retrieves_before_every_call_including_repair. Default MEMORY_LAST_N=5, live evidence uses N=2. | rubric-live-evidence.json contains the actual retrieved context and recent buffer at every call. A fresh graph with empty short-term memory recalls the prior task's tag from persistent Chroma and uses it in a related follow-up. |
| C1.3 Actual tools and timeout | tools/files.py, tools/registry.py and tools/execution.py. exec_python is an execution alias. CodeRunner default timeout is 10 seconds and is configurable. No direct eval/exec execution. | Live record shows write_file, read_file and execution observations. test_real_container_isolation runs real Docker and stops an infinite loop with a 1-second probe timeout. |
| C1.4 Bounded ReACT | orchestration/graph.py think/act transitions consume tool observations. AgentState limits max_iterations to 10; every model request counts, including repair. | Live record includes multi-step actions, observations and concise plans. test_max_ten_calls forces distinct actions until exactly 10 calls; cycle and repeated-action probes also pass. |
| C1.5 Validated results | Decision and AgentOutput are strict Pydantic models; finalize constructs AgentOutput and run validates it again. Code is read back from files and results come from the actual runner. | Live verifier validates JSON round-trip and exact equality between output.code and written artifacts. Edits invalidate execution evidence; tests reject fabricated success after failure or edits. |
| C1.6 Working smoke test | tests/test_agent.py::test_smoke_real_graph_chroma_and_subprocess invokes the graph with a coding task and checks all four required fields; tests/test_integration.py::test_live_end_to_end also checks them against a real model run. | Real GPT-4o generates code, Docker executes it, and assertions pass without manual writing or repair of generated code. The live evidence script performs two further end-to-end tasks. |

## Verified result (26 October 2026)

The full main-project suite passed **37 tests, zero skips**, with Docker, MiniLM
and real-model checks enabled. The instrumented two-task verifier passed: each
task completed in four iterations with write_file, read_file and execution.
See [machine-readable verification](rubric-verification.json),
[live call evidence](rubric-live-evidence.json), and the
[actual generated source](rubric-artifacts).

## Reproduce the assessment

Follow README setup and configure your private .env. Pull python:3.12-slim and
start Docker. From the repository root:

```sh
python -m pytest -q
RUN_DOCKER_TESTS=1 RUN_SEMANTIC_TESTS=1 python -m pytest -q
python -m scripts.verify_rubric
```

The live verifier loads .env and makes paid model calls. It uses real local
MiniLM embeddings, persistent Chroma, GPT-4o, and the Docker subprocess runner.
It records only task data, retrieved context, short action summaries and tool
observations—no credentials or hidden model reasoning. It sets N=2 to make
buffer bounds visible. Its second run rebuilds the graph, leaving the short-term
buffer empty while reopening the same Chroma store and session.

For the opt-in live pytest test, export the LLM settings from your private
configuration into the process environment and set RUN_LIVE_LLM=1. The local
verification run loaded .env in Python before invoking pytest; keys were not
printed or committed.

The timeout and iteration-limit probes are deterministic assessor-style probes.
They do not require the model to decide to create an infinite loop. Docker
startup is included in the configurable wall-clock timeout.

## Submission identity

Submit the repository URL and the full commit SHA supplied with the delivery.
Use `git rev-parse HEAD` to verify the checkout; view this evidence at that commit.
The live record is from the code and prompt included in the submission.
