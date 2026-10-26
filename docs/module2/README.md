# Module 2: two-agent coordination evidence

This milestone extends the existing LangGraph Coder with a Product Manager in the
same process and graph workflow. The framework did not change. The optional
AutoGen/CrewAI comparison lab is not included.

## Published task and local acceptance contract

> Build a REST API with two endpoints: GET /health (returns {status: ok}) and
> POST /echo (returns the JSON body it receives). Include basic input validation.

The instructor's request fixture was not available. With the owner's approval,
`tests/fixtures/api_requests.json` defines our own eight requests:

| Request | Expected |
|---|---|
| GET /health | 200, `{"status":"ok"}` |
| POST /echo with an object | 200, unchanged object |
| POST /echo with a nested object | 200, unchanged object |
| POST /echo with an empty object | 200, `{}` |
| Malformed JSON | 400 |
| JSON array | 400 |
| JSON null | 400 |
| Plain text | 415 |

Object-only validation and these error status codes are local assumptions, not
claimed instructor requirements. Replace/compare this fixture when the course
provides its own. Passing it does not establish a grading result.

## Criterion map

| Criterion | Implementation and evidence |
|---|---|
| C2.1 Specification | `agents/pm_agent.py` uses the model to produce `TechnicalSpec`, validated before use; `live-state-trace.json` includes state immediately after the PM. |
| C2.2 Shared state | `orchestration/project_state.py` defines strict Pydantic models. Original requirement, specification, tasks/statuses and accumulated source survive each transition. |
| C2.3 Handoff | `orchestration/project_graph.py` links PM, prepare and Coder nodes. `Handoff` carries ready, task ID, description, acceptance criteria and priority. The Coder validates and consumes all fields. `handoff_history` records the same IDs as the task artifacts. |
| C2.4 Progress and bounds | Ordered Coder calls update status after every task; failures stop later work. Nine-, seventeen- and sixty-four-task tests demonstrate consolidation to at most eight without dropping descriptions, criteria or source IDs. `consolidation-example.json` records the nine-task case. |
| C2.5 Working system | `tests/test_project.py::test_pm_handoff_integration_through_graph` executes the real PM node with a scripted model and checks the typed task list. `scripts/verify_module2.py` runs both actual agents with GPT-4o, Chroma and Docker, saves the generated API and runs the eight local requests. |
| C2.6 Explanation | Root README includes the implemented PM → shared state → Coder diagram, setup and run commands. LangGraph is retained from Module 1. |

## Reproduce

Follow the root README to install the pinned Python 3.12 dependencies and configure
an ignored `.env`. Build the execution image before live runs:

```bash
docker build -f Dockerfile.executor -t coder-python-api:module2 .
python -m pytest -q
RUN_DOCKER_TESTS=1 RUN_SEMANTIC_TESTS=1 RUN_MODULE2_DOCKER_TESTS=1 python -m pytest -q
python -m scripts.verify_module2
```

The final command incurs model usage and replaces the live evidence with a fresh
run. It starts with an empty temporary workspace and semantic store. Nobody writes
or repairs the generated application during that run. `generated/` is the source
snapshot produced by tool calls. The trusted acceptance driver is kept separately
in `orchestration/api_fixture.py` and runs the submitted source in a restricted
container. The fixture tests include rejection of incorrect input validation and
premature process exit, as well as a correct trusted reference implementation.

Tests with scripted models establish orchestration behavior, not live model
quality. The live state evidence establishes an observed run. Earlier development
runs caught premature completion based on previous tasks' observations. The Coder
now rejects this and requires successful execution in the current task, with
retries still bounded by the existing ten-call budget.

Module 1's submitted commit remains `e02873c83756758fbd60ac87ad9ea4c351e3d6e9`
on `main`; this milestone is on `module-2`. No secrets or course PDFs are included.

## Recorded automated validation

On 26 October 2026, the full suite passed **56 tests, zero skips** with
`RUN_DOCKER_TESTS`, `RUN_SEMANTIC_TESTS`, `RUN_MODULE2_DOCKER_TESTS` and
`RUN_LIVE_LLM` enabled. This includes the original live Coder smoke test. The
separate two-agent demonstration is recorded in the linked state evidence.

The final live two-agent run completed two PM-planned tasks in order, using six
Coder iterations per task. The generated Flask API passed all eight independent
local request checks, with exit code 0 and no stderr. Its saved source exactly
matches `code_output` in the validated final state; no manual fixes were applied.
