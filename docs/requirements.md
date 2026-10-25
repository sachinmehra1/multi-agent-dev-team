# Module 1 requirements mapping

Source: uploaded *Build Autonomous Multi-Agent Systems — Course Project Guide*,
pages 3–5; *Module 1 Section 4: Planning Algorithms & Single-Agent Architecture*;
*Student Development Environment and GitHub Setup Guide*. The image-only project
guide was inspected visually. Source PDFs are intentionally not redistributed.

| Requirement | Implementation / evidence |
|---|---|
| Required top-level structure from first commit | Initial scaffold commit; agents, tools, orchestration, tests, docs and root configuration files |
| Single Coder v1.0; choose framework | LangGraph StateGraph in orchestration/graph.py; composition in agents/coder_agent.py |
| Natural-language coding task | main.py task argument; CoderGraph.run(task) |
| Last N turns | ConversationMemory deque of complete exchanges; test_memory.py |
| Chroma semantic memory | PersistentClient, production MiniLM embeddings, session-filtered top-3 query |
| Recall before every LLM call | think node before complete(), including JSON repair; test_agent.py |
| Custom file tools | tools/files.py; traversal/symlink/size tests |
| run_code / exec_python | tools/execution.py; alias and typed registry |
| Subprocess sandbox, default 10-second timeout, no eval | Per-execution Docker container started via subprocess; timeout/output limits |
| ReACT with maximum 10 iterations | Typed thought/action/observation loop; max-ten and tenth-call finish tests |
| Additional loop detection | Third identical action and repeating three-action cycle tests |
| Structured code/explanation/plan/result | Strict AgentOutput Pydantic model; smoke serialization validation |
| Token usage, structured logging | Host usage accounting and metadata-only JSON events |
| Smoke test | Real graph + Chroma + trusted fixture subprocess; scripted model clearly identified |
| README, environment template, Docker files, requirements | Included at repository root |
| Public repository, URL plus commit SHA | Not published from this environment; docs/submission.md explains remaining steps |

The generic setup guide describes a private instructor-provided repository; the
project-specific guide explicitly requires a public repository. This implementation
follows the project-specific requirement and the user's explicit instruction.
The initial README described the future team; PM and QA remain labeled placeholders,
as the progressive-build guide schedules them for later modules.
