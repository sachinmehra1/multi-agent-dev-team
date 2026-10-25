# Verification record — 26 October 2026

## Latest results

- Default offline suite: **34 passed, 3 skipped**.
- Suite with real Docker and MiniLM semantic retrieval enabled: **36 passed, 1 skipped** in 3.56 seconds.
- Live CLI run using GPT-4o, persistent Chroma with production MiniLM embeddings,
  and Docker: **passed**, 3 iterations, 3,754 provider-reported tokens.
- Generated addition code passed assertions for positive, negative, mixed-sign,
  and zero inputs. Execution exited 0 and printed `All test cases passed.`
- See `live-addition-output.json` for the actual successful live result.
- The optional pytest live-LLM test remains skipped; the equivalent live CLI task
  was exercised separately. Docker build/Compose and hosted CI remain untested.
- No GitHub push or LMS submission has occurred.

## Fix discovered during live testing

The first live attempts generated and executed correct code but failed final
Decision validation, including the single permitted repair. The system prompt now
contains a concrete valid finish example, and repair feedback retains the rejected
response and field-level validation errors. Validation logs report schema locations,
error types and messages without raw responses or credentials. A regression test
covers field-level repair feedback. Validation remains strict and the ten-call cap
is unchanged. The successful run's token count excludes earlier failed attempts.

## Coverage and limitations

Tests cover sliding-window trimming, persistent and session-filtered Chroma retrieval,
recall before each model call, ten-iteration and repeated-action guards, invalid JSON,
file traversal/symlink restrictions, execution timeout/output limits, credential
isolation, failed-execution integrity, and execution-tool aliases.

The real Docker test verified unprivileged execution, read-only root filesystem,
network isolation, no exposed API key or Docker socket, and timeout handling.
The MiniLM integration test verified retrieval of a coding preference over an
unrelated gardening memory. This small test is not a comprehensive semantic benchmark.

The scripted `sample-smoke-output.json` remains a deterministic fixture, distinct
from the live result. API keys, memory databases, virtual environments and runtime
workspaces are excluded from the source archive.
