# Module 5 — end-to-end testing record

**Prepared:** 2 November 2026  
**Source:** Existing repository records, not a newly executed run.  
**Baseline:** `main` commit `e02873c83756758fbd60ac87ad9ea4c351e3d6e9`.

## Verified historical evidence (Module 1, not the Module 5 integrated team)

The existing `docs/verification.md` (dated 26 October 2026) reports a full suite of **37 passed, 0 skipped** with Docker, MiniLM and live GPT-4o enabled, plus a default offline suite of 34 passed and 3 skipped. `docs/rubric-verification.json` records two instrumented Coder tasks with four iterations each, real `write_file`, `read_file`, and `run_code` observations and passing results. `docs/live-addition-output.json` records a passed addition script (3 iterations, 3,754 reported tokens). Those are historical repository records, not re-executed or independently attested here.

## Required diverse *Module 5* integrated E2E scenarios

| ID | Task and acceptance criteria | Observed run | Fixes | Final status |
| --- | --- | --- | --- | --- |
| E2E-01 | Build a CSV transaction summarizer; verify empty file, invalid rows, duplicates and numerical totals; PM defines acceptance criteria, Coder implements, QA tests. | Not run against integrated PM–Coder–QA pipeline | Not available | **BLOCKED** |
| E2E-02 | Implement a typed password-policy validator with tests for length, Unicode, forbidden substrings and boundary values; QA verifies outputs. | Not run against integrated pipeline | Not available | **BLOCKED** |
| E2E-03 | Implement a deterministic log parser with counts by severity, malformed lines and zero events; QA challenges edge cases and requests fixes. | Not run against integrated pipeline | Not available | **BLOCKED** |

**Why blocked:** `agents/pm_agent.py` and `agents/qa_agent.py` are only module docstrings; `orchestration/graph.py` currently orchestrates a Coder alone. A passing Coder smoke test cannot count as a completed three-agent E2E run.

## Reproduction commands when implementation is ready

```bash
python -m pytest -q
RUN_DOCKER_TESTS=1 RUN_SEMANTIC_TESTS=1 python -m pytest -q
RUN_LIVE_LLM=1 python -m pytest tests/test_integration.py -q
docker compose up --build
```

These commands are **proposed checks, not execution claims**. The current Compose service is a single `coder` command; it is not yet a Module 5 integrated team demo. For every new E2E case capture the exact commit SHA, date, environment, prompt, PM spec, Coder artifacts, QA verdict, iterations, model tokens, fix diff, and test output. Redact provider credentials.

## Failure/rework evidence already present

The October 26 verification note documents a real issue where generated code executed but final `Decision` JSON validation failed. Commit [e80af509](https://github.com/sachinmehra1/multi-agent-dev-team/commit/e80af509fa119d330768ff67855146acc34cc32d) adds a concrete `finish` schema example and field-level repair feedback; a regression test verifies the repair details. This is genuine repository evidence of debugging, not proof of AI authorship unless a prompt log corroborates it.
