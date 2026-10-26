# Module 4 validation — 26 October 2026

The final clean Compose run passed. No person wrote or repaired the generated BST
or QA tests during the run. Files in `generated/` are exact exports from its result.

- **99 regression tests passed**, with only the separately run Compose test skipped:
  [complete result](test-results.txt).
- **1 clean Compose end-to-end test passed** in 105.66 seconds:
  [result](deployment-test-results.txt). Total: **100 project tests passed** across the two invocations.
- Generated QA: **12 behavioral tests passed**, one QA round.
- Independent documented local fixture: **4 tests passed** (not an instructor-supplied fixture).
- Phoenix retained **59 spans**, including every PM/Coder/reflection/QA invocation under one root.
- **11 provider calls**, no missing usage records; estimated run cost **$0.0129832**.
  This is the final run's estimate, not the cost of all development tests or a billing receipt.

Run ID: `77ace252b1c943f59859bceb0d88ea22`  
Trace ID: `dbf3921857d50943d4d5dae40ed2781a`

## Evidence

- [Final state, code and execution results](../results/77ace252b1c943f59859bceb0d88ea22.json)
- [Automatic cost report](../cost_reports/77ace252b1c943f59859bceb0d88ea22.json)
- [Exported trace](../traces/77ace252b1c943f59859bceb0d88ea22.json)
- [Structured events](../run_logs/77ace252b1c943f59859bceb0d88ea22.jsonl)
- [Phoenix trace response](deployment/phoenix-trace.json) and [stored span metadata](deployment/phoenix-spans.json)
- [Clean-start log](deployment/startup.log) and [service/run log](deployment/compose.log)
- [Generated BST](generated/bst.py) and [generated QA tests](generated/test_generated.py)

The clean test created project `module4-fba07bcb` with new data volumes. Chroma and
Phoenix were healthy before the agent started. The image uses Python 3.11; dependency
imports passed after unpacking, and `/app/.env` was absent. Secrets were supplied
only through Compose's env_file. The live Phoenix dashboard remains available at
http://localhost:6006 under project `module4` on the development machine.

## Reproduction

Use the README setup first, with your own local API key and Docker.

```bash
RUN_DOCKER_TESTS=1 RUN_SEMANTIC_TESTS=1 RUN_LIVE_LLM=1 RUN_MODULE2_DOCKER_TESTS=1 RUN_MODULE3_DOCKER_TESTS=1 python -m pytest -q
# Stop any prior test stack using port 6006, then:
RUN_MODULE4_COMPOSE=1 python -m pytest tests/test_production_e2e.py -q
```

The earlier Docker test flags require the images described in the corresponding
Module 1–3 README sections. The Module 4 Compose test builds its own image.
Live tests incur provider usage; the default test invocation needs no API key.

## Resolved development failures

Low disk space interrupted Docker and damaged an unpacked dependency layer. The
replacement image was rebuilt from verified layers and its imports checked. A
clean-start probe then exposed a local `.env` workspace override; Compose now pins
its writable paths to `/data`. Its failed run `0307c0a803ed4fdf9f146c1f616b3adf` is
retained in the reports as an explicitly unsuccessful startup, with zero model
usage. The successful run linked above is the submission evidence.

Live smaller-model checks also prompted clearer current-run execution feedback
and one bounded QA schema correction before execution. Regression tests cover
both changes; invalid QA setup stops without unrelated Coder edits. The final run
required no QA correction and passed without a Coder repair loop.
