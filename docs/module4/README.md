# Module 4: operational hardening

This branch extends the existing LangGraph PM/Coder/QA workflow. The course's
simplified A2A protocol, QA feedback loop and self-reflection remain in use.
Phoenix receives OpenTelemetry spans; it requires no new cloud account or key.

[Observed validation and submission evidence](validation.md)

## Rubric evidence map

| Criterion | Implementation and evidence |
|---|---|
| C4.1 Complete trace | `orchestration/observability.py`: one root per `Runtime.run()`, agent invocation spans and nested LLM/tool spans. Each agent records agent_name, token_count, tool_calls and duration_ms. Phoenix dashboard plus exported JSON and JSONL share trace_id/run_id. |
| C4.2 Call retries | `CallPolicy` wraps `ChatModel.complete` provider attempts and file/execution/memory tool calls through the active runtime. Maximum three retries beyond the initial attempt; exponential delay plus jitter. Tests inject transient/persistent failures without replaying agent workflows. |
| C4.3 Circuit breaker | Three consecutive transient failures open a per-boundary breaker. Cool-down enables a probe; success closes, failure reopens. Transitions are WARNING events. Valid unexpired cache hits remain usable; other open calls raise a typed error converted to a structured pipeline failure. |
| C4.4 Costs | Every provider attempt has a usage record. Successful replies use provider prompt/completion tokens; errors with unavailable usage are explicitly flagged. Every run automatically writes per-agent totals, configured rates and reconciled estimated USD under `docs/cost_reports/`. |
| C4.5 Cache/allocation | Hash-keyed per-role/model/prompt cache with configurable TTL. Repeated eligible JSON responses hit the cache; expiry removes entries. Defaults: GPT-4o PM, GPT-4o-mini Coder and QA. |
| C4.6 Validation/execution | Strict Pydantic RunInput, specifications, decisions, critiques, revisions, QA suites, handoffs and protocol messages gate actions. Tools validate arguments and paths. Code runs in bounded Docker subprocesses. `.env` is excluded from source and build context. |
| C4.7 Automated verification | Existing per-agent and pairwise tests plus `tests/test_operations.py` and opt-in `tests/test_production_e2e.py`. The latter builds and runs a new Compose project, checks real generated BST execution, independent acceptance requests, trace relationships and costs. |
| C4.8 Clean deployment | Python 3.11 Dockerfile, requirements install, ENTRYPOINT, agent/Chroma/Phoenix services, health-gated startup and env_file secrets. The embedding model is baked at build time, not borrowed from a host cache. |
| C4.9 Operations guide | Root README and this document cover configuration, interfaces, usage, tests, reports, trace inspection and unresolved exits. |

## Published task and local fixture

> Build a Python module that implements a binary search tree with insert, search,
> and in-order traversal methods, with full test coverage.

No instructor fixture was present in the supplied materials. The independent
local fixture in `tests/fixtures/test_bst_acceptance.py` documents these choices:
`bst.py`, `BinarySearchTree()`, integer insertion, duplicate values ignored,
boolean `search(value)`, and sorted-list `inorder()`. Its four tests cover empty
and missing values; insertion/search/traversal; zero/negatives/duplicates; and
ordered insertions with independent instances. The QA agent additionally generates
its own tests. Local success is not a claim of passing an unavailable hidden fixture.

## Callable interfaces

- `RunInput(requirement, session_id)`: validates a nonempty bounded requirement and
  a safe session identifier.
- `run_pipeline(request, runtime, model=None, workspace=None, image=None)`:
  runs all agents, validates the final BST source against the local fixture,
  returns a structured result and writes run artifacts even on failure.
- `Runtime(output, endpoint, cache_ttl, retries, base_delay, cooldown, rates, models)`:
  provides trace context, call policies, usage tracking and automatic reports.
- `RoleModels.complete(messages)`: selects the configured model using the current
  traced agent role. Calls outside an agent role are rejected.
- `CallPolicy.call(operation)`: retries only transient failures at a single call
  boundary. Validation errors and ordinary assertion failures are not transient.
- `CircuitBreaker.before/success/failure`: implements closed/open/half-open states.
- `PromptCache.get/put`: stores only eligible JSON replies in memory for this run.

## Recovery semantics

`CALL_MAX_RETRIES=3` permits at most four attempts including the original. The
breaker can stop earlier: three consecutive transient failures open it, so an
uninterrupted failing sequence makes three provider/tool attempts. A recovered
call resets consecutive failures. `CIRCUIT_COOLDOWN_SECONDS` defaults to 30.
`RETRY_BASE_DELAY_SECONDS` defaults to 0.25; delay before retry n is
`base * 2**(n-1) + uniform(0, base)`. Neither the PM/Coder graph nor the QA loop is
replayed by retry logic. Coder decision limits and QA round limits remain separate.

Only transport errors, timeouts, I/O/service failures and retryable HTTP statuses
are retried. Bad credentials, invalid output/input schemas, failed code assertions,
resource limits and normal QA failures are handled by their structured paths.
A code execution timeout is an observed failed execution, not a reason to repeat
an infinite loop. The breaker and prompt cache are process-local, not a shared
multi-worker distributed state service.

QA validates generated test JSON and exact coverage labels before writing or running
tests. It permits one schema-correction response with field-level feedback. If the
second response is invalid, the workflow stops with a structured QA setup failure;
it does not ask the Coder to alter working application code. Once tests execute,
the suite remains fixed across Coder revisions. This bounded validation correction
is separate from transport retries and the QA revision-round budget.

## Cost interpretation

The report records configured USD rates per million prompt/completion tokens.
Defaults are estimates based on [GPT-4o pricing](https://developers.openai.com/api/docs/models/gpt-4o)
and [GPT-4o-mini pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini).
Change rates when selecting another model/provider. These are estimates, not
billing receipts: provider-side cache discounts, taxes and unknown failed-request
usage are not inferred. `unknown_usage_calls` makes missing usage explicit. An
application cache hit makes no provider call and adds zero billable tokens/cost.
No fixed percentage savings is claimed.

## Security and deployment boundary

Only the trusted orchestrator receives the Docker socket and `.env` secrets.
That socket grants Docker host control; use this development deployment only with
trusted repository code. Generated-code subprocesses receive source snapshots,
no socket, no credentials, no host mounts and no network, with an unprivileged
user, read-only root, time/resource/output limits. Phoenix binds to localhost;
its dashboard/exported traces contain metadata, not prompts, source or API keys.
Saved result artifacts contain generated source and should use public course tasks.

The agent and Chroma share a built image to avoid redundant runtime downloads.
Chroma runs a different entrypoint, has its own data volume and receives no env_file.
Phoenix retains its own data volume. No automatic deletion of existing user data
is part of setup or testing. Review Docker disk availability before the first build.

## Test coverage pointers

- PM schema, handoff, ordered progress and task consolidation:
  `tests/test_project.py`. Invalid PM responses cannot call the Coder.
- Coder validation, actual subprocess execution, semantic retrieval, action-loop
  detection and the ten-call limit: `tests/test_agent.py` and `tests/test_integration.py`.
- QA schema, behavioral test execution, reflection, A2A fixes, success and
  maximum-iteration exits: `tests/test_qa_team.py`.
- Individual LLM/tool retries, jitter, breaker probes, WARNING events, cache TTL,
  allocation, usage reconciliation and trace metadata: `tests/test_operations.py`.
- Clean Python 3.11 deployment, live full-team BST generation, independent
  execution fixture, automatic reports and actual Phoenix ingestion:
  `tests/test_production_e2e.py` (explicit opt-in).
