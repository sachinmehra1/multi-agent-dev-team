# Supplementary Module 1 course labs

Submit this hub URL: https://github.com/sachinmehra1/multi-agent-dev-team

The consolidated rubric explicitly makes recommended labs and multiple frameworks optional.
The graded artifact is the main Coder Agent; see [rubric evidence](rubric-evidence.md).
The four completed lab forks are linked below as supplementary work. The original standalone Coder Agent
remains available in this repository, with its separate verification evidence.

| Lab | Completed fork | Verification |
|---|---|---|
| 1.1 Memory | [Memory](https://github.com/sachinmehra1/Multi-agents-lab-1-1-memory) | 5 offline tests; supplied live recall test passed |
| 1.2 Tools | [Tools](https://github.com/sachinmehra1/Multi-agents-lab-1-2-tools) | 24 supplied tests; live write/execute/DONE demo passed |
| 1.3 ReACT | [ReACT Coder](https://github.com/sachinmehra1/Multi-agents-lab-1-3-react-coder) | 24 supplied tests including live test; 3 regression tests; default task completed in 6 iterations |
| 1.4 Framework comparison | [LangGraph, AutoGen, CrewAI](https://github.com/sachinmehra1/Multi-agents-lab-1-4-langgraph-autogen-crewai) | 29 supplied live tests + 9 generated-artifact tests passed; all three comparison runs successful |

## Reproduction

Each fork has requirements-tested.txt, a blank .env.example, and run_openai.py.
Use Python 3.12 and follow that fork's README. The owner authorized the existing
OpenAI account for live verification. No user keys are stored in the repositories.
The live runs used direct OpenAI, gpt-4.1-mini, rather than the course Helicone route.
Course-provided client and tool files marked read-only were preserved.
The lab tools use subprocess execution; the separate standalone agent uses Docker.

## Evidence and limitations

The framework comparison contains actual usage counts and generated files, plus
six written tradeoff sections. It is one observed comparison, not a statistically
representative benchmark. Repeated live tests may have different token counts.
The supplied Chroma integration emits deprecation warnings but passes its tests.

The public upstream starters contained credential-like values. Those values were
removed from the current fork files and setup scripts, and environment files are
ignored. Historical upstream commits still contain them; their owner must rotate
any real credentials. They were not used for verification.

LMS submission has not been performed. The URL above is the single submission
hub requested by the student; grading remains subject to the course rubric.
