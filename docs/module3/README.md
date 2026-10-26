# Module 3 evidence: complete agent team

The graded milestone is implemented in the main project on `module-3`. The four
linked lab READMEs and course notes were consulted; separate Module 3 lab forks
are not claimed as completed. The guide/rubric permits one protocol route and
makes the debate lab optional. This project implements the course A2A route.

## Rubric map

| Criterion | Implementation | Inspectable evidence |
|---|---|---|
| C3.1 Meaningful QA | `agents/qa_agent.py` generates pytest source and criterion-to-test mappings; `tools/pytest_runner.py` writes it, runs it in a Docker subprocess and parses pytest reports. Each issue includes location, failing assertion, criterion and fix instruction. | `generated/test_generated.py`, `live-final-state.json` QA reports, command/timeout/stdout/exit status |
| C3.2 Feedback revision | `TeamWorkflow` routes a failing A2A QA response to `CoderReviser.fix`, then tests the new source against the unchanged suite. Source digests prevent stale feedback. | `live-seeded-repair.json` and `controlled-repair.json`: first failed assertion, same task/correlation pairing, revised source and passing retest |
| C3.3 Bounded termination | `QA_MAX_ITERATIONS` defaults to five total QA rounds. A failed last round yields a final unresolved issue list and `approved=false`. | `controlled-limit.json`: configured three rounds, two fixes, final unresolved `reverse` assertion; environment/default and boundary tests |
| C3.4 Self-reflection | `CoderReviser.reflect` calls a critique prompt, then a revision prompt. It writes the revised files through file tools and requires a substantive parsed-code change. Reflection occurs before the first review request. | Live `reflection` record with critique, explanation, before/after source; first QA request's source digest matches revised source |
| C3.5 Protocol use | Five-field JSON A2A envelope, role/intent validation, capability registry, queues and correlated replies. Coder receives the actual QA message before revision. | `a2a-messages.json`; invalid-intent, wrong-route, unknown-correlation and stale-digest rejection tests |
| C3.6 Complete team | Automated tests cover issue schema, successful repair and maximum iteration exit. Live linked-list demo uses PM, Coder and QA. Root README has the three-agent diagram and protocol rationale. | Live generated module/tests and state; controlled probes and `tests/test_qa_team.py` |

## Evidence types

- `live-final-state.json`, `live-state-trace.json`, `a2a-messages.json` and
  `generated/` are produced by an actual configured-model run from an empty
  temporary workspace. There are no manual repairs to that run's application.
- `controlled-repair.json` uses explicitly injected buggy source and scripted
  model responses, with actual Docker pytest execution. Reflection corrects a
  zero-value search defect; QA then detects the remaining broken reverse method;
  the Coder consumes the structured issue and applies a correction. The same tests
  pass on the new source.
- `live-seeded-repair.json` starts from a declared faulty fixture, reuses the live-generated QA suite, and uses the real configured model to repair the application from its A2A fix instructions. The unchanged tests pass after that repair.
- `controlled-limit.json` keeps the reverse defect unresolved while making
  ineffective revisions. It demonstrates an actual bounded, unsuccessful exit.
  These controlled records are not presented as live model capability evidence.

The source contract is documented in the root README and `team_main.py`. The
course specifies four methods but does not prescribe parameter/return semantics;
our local contract makes those choices reproducible. There is no supplied hidden
instructor fixture, and no grading result is claimed.

## Run and reproduce

Use Python 3.12 and the root `requirements.txt`, configure `.env`, then:

```bash
docker build -f Dockerfile.qa -t coder-python-qa:module3 .
python -m pytest -q
RUN_MODULE3_DOCKER_TESTS=1 python -m pytest tests/test_qa_team.py -q
python -m scripts.verify_module3 --controlled-only
python -m scripts.verify_module3
```

The last command makes paid model calls and replaces live evidence. The QA test
source is generated once per run and retained during fixes, preventing the Coder
from silently weakening tests. Generated tests run in a disposable source snapshot
with no network, no secrets, no host mount, an unprivileged user, read-only root,
resource/output limits and a default ten-second host-enforced timeout. The runner
removes the container on timeout. The trusted-local backend is used only by tests
with hand-written fixtures and is not available through the CLI.

QA checks explicit assertions, criterion mappings and observed passing tests;
these checks do not prove arbitrary tests are semantically complete or prevent a
malicious application from tampering inside its own test process. This is an
educational coding workflow, not an adversarial test-certification system.

The A2A implementation follows the course's simplified in-process envelope/broker
model. It does not advertise external A2A HTTP, Agent Cards, authentication or
MCP support. Protocol messages contain task code and QA evidence, so use public
course tasks and keep credentials exclusively in the ignored environment file.

## Recorded validation (26 October 2026)

- Full suite: **78 passed, zero skips**, with Docker, semantic memory, all milestone
  integration flags and the original live Coder smoke test enabled.
- Live three-agent demo: PM/Coder generation, substantive self-reflection, then one
  QA round; **five generated behavioral pytest tests passed**, covering all four
  methods. Source and test files match the saved state exactly.
- Controlled repair: two actual Docker QA rounds, with the same tests failing then
  passing after the scripted Coder consumes the failure.
- Controlled non-convergence: exactly three configured rounds, then a final report
  retaining the failing reverse assertion; no success claim.

The observed reflected implementation rejects inserting `None` with `ValueError`;
its generated QA suite exercises ordinary values and does not certify all possible
Python object types. An earlier development run generated a contradictory
first-match deletion test and was rejected. The QA prompt was corrected and the
published evidence was produced by a new run, without manual edits to its code or
tests. Generated tests remain reviewable evidence, not an infallible oracle.

The additional **live seeded-repair probe passed**: the intentionally broken reverse method failed QA, the actual model revised it from the returned fix instruction, and all five retained tests passed. Both messages share the task ID and each request/reply pair shares its correlation ID.
