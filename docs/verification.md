# Verification record — 26 October 2026

Environment: macOS ARM64, Python 3.12.4, isolated virtual environment.
Installed direct dependencies: LangGraph 1.2.17, Chroma 1.5.9, Pydantic 2.14.1,
HTTPX 0.28.1, python-dotenv 1.2.4, pytest 9.1.1.

## Completed checks

```text
python -m pytest -q
................sss.................                                         [100%]
33 passed, 3 skipped in 2.10s

python -m pip check
No broken requirements found.
```

- Smoke: real LangGraph and persistent Chroma, deterministic test embeddings,
  scripted model decisions, real local subprocess running trusted fixture code.
  The generated addition function passes positive/negative input assertions and
  prints `5`. Four iterations, 28 **synthetic** tokens from the scripted model.
- Execution tool names: `execute_python`, `exec_python` and `run_code` each pass the
  full smoke test; aliases share a canonical signature for loop detection.
- Guards: ten-call cap, finish on call ten, one bounded JSON repair, identical-action
  detection, three-action cycle detection and session-switch isolation.
- Integrity: failed execution cannot be reported complete; edits invalidate prior
  execution; model/provider and memory failures return structured errors.
- Tools: path traversal, hidden paths, symlink escape, file size limit, argument
  validation, timeout, output cap, credential-free child environment and alias.
- Docker command construction: required isolation flags, no host mount, cleanup
  on simulated timeout. This is a unit check, not a real container execution.
- Memory: last-N trimming, real Chroma persistence and session-filtered retrieval.
- CLI: help works; missing provider configuration returns failure JSON and exit 1.
- Docker Compose YAML parsed successfully; this does not validate a Docker build.
- Source whitespace check and credential-pattern scan completed before packaging.

`sample-smoke-output.json` records the scripted smoke run. `output.schema.json`
is generated from the actual Pydantic output model. Neither is a live-model demo.

## Incomplete or unavailable checks

1. **Real MiniLM semantic ranking:** an opt-in production-embedding test was started.
   Its model download progressed slowly and was intentionally stopped before
   completion. No semantic-quality pass is claimed. The default tests use test-only
   vectors; run `RUN_SEMANTIC_TESTS=1 python -m pytest tests/test_integration.py -q`
   after downloading the embedding model to verify production ranking.
2. **Docker build, Compose execution, real isolation and container timeout:** Docker
   was not installed in this environment. The opt-in Docker test and CI workflow
   are provided, but neither was run here. Run them on a Docker-equipped machine.
3. **Live LLM end-to-end:** no live provider request was made and no credentials were
   supplied or retrieved. Run the opt-in live test with your own configuration.
4. **GitHub/CI/LMS:** local commits only. No remote was configured, no push was made,
   no hosted CI ran, and no LMS submission was performed. Public URL and published
   SHA remain required before the assignment is submitted.

Offline tests establish implementation behavior under controlled responses; they
cannot establish model coding quality, real semantic ranking or container security.
