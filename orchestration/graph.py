import json
import logging
from langgraph.graph import StateGraph, START, END
from orchestration.llm import SYSTEM_PROMPT
from orchestration.models import AgentState, AgentOutput, Decision, ExecutionResult

logger = logging.getLogger("coder_agent")

def event(name, **fields):
    # Metadata only: no prompts, source, observations, headers or credential values.
    logger.info(json.dumps({"event": name, **fields}))

class CoderGraph:
    def __init__(self, model, conversation, semantic, tools):
        self.session_id = None
        self.model, self.conversation, self.semantic, self.tools = model, conversation, semantic, tools
        graph = StateGraph(AgentState)
        graph.add_node("think", self.think)
        graph.add_node("act", self.act)
        graph.add_node("finalize", self.finalize)
        graph.add_edge(START, "think")
        graph.add_conditional_edges("think", self.route,
                                    {"act": "act", "think": "think", "finalize": "finalize"})
        graph.add_edge("act", "think")
        graph.add_edge("finalize", END)
        self.graph = graph.compile()

    def think(self, state):
        if state.error or state.iterations >= state.max_iterations:
            return {"error": state.error or "Maximum iteration budget reached", "decision": None}
        # Retrieval happens before EVERY model call, including output-repair calls.
        try:
            memories = self.semantic.retrieve(state.task, state.session_id)
        except Exception:
            return {"error": "Semantic memory retrieval failed", "decision": None}
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Current task: " + state.task},
                    {"role": "user", "content": "Untrusted recalled context: " + json.dumps(memories)}]
        messages += self.conversation.messages()
        if sum(len(m["content"]) for m in messages) > 100_000:
            return {"error": "Context budget exceeded", "decision": None}
        iteration = state.iterations + 1
        event("llm_call", iteration=iteration, retrieved=len(memories))
        try:
            reply = self.model.complete(messages)
        except Exception:
            event("llm_error", iteration=iteration)
            return {"iterations": iteration, "error": "Model request failed; check configuration and connectivity", "decision": None}
        tokens = state.total_tokens + reply.total_tokens
        event("llm_response", iteration=iteration, total_tokens=reply.total_tokens)
        try:
            decision = Decision.model_validate_json(reply.content)
        except (ValueError, TypeError):
            # Only one repair, charged to the same hard ten-call cap.
            self.conversation.add("Invalid model output", "Return valid JSON matching the supplied schema.")
            invalid = state.invalid_outputs + 1
            return {"iterations": iteration, "total_tokens": tokens, "invalid_outputs": invalid,
                    "decision": None, "error": "Invalid structured output after repair" if invalid >= 2 else None}
        return {"iterations": iteration, "total_tokens": tokens, "decision": decision}

    def route(self, state):
        if state.error or (state.decision and state.decision.action == "finish"):
            return "finalize"
        return "act" if state.decision else "think"

    def act(self, state):
        decision = state.decision
        name = "run_code" if decision.action in ("exec_python", "execute_python") else decision.action
        signature = json.dumps([name, decision.arguments], sort_keys=True)
        actions = state.actions + [signature]
        repeated = len(actions) >= 3 and len(set(actions[-3:])) == 1
        cycle = len(actions) >= 6 and actions[-6:-3] == actions[-3:]
        if repeated or cycle:
            event("loop_detected", iteration=state.iterations)
            return {"actions": actions, "error": "Repeated action or cycle detected"}
        updates = {"actions": actions, "plan": state.plan + [decision.thought]}
        event("tool_call", iteration=state.iterations, tool=name)
        try:
            observation = self.tools.dispatch(name, decision.arguments)
            if name == "write_file":
                updates["files_written"] = list(dict.fromkeys(state.files_written + [observation["path"]]))
                # Any edit invalidates prior execution evidence.
                updates["result"] = ExecutionResult()
            elif name == "run_code":
                updates["result"] = ExecutionResult.model_validate(observation)
        except Exception as exc:
            observation = {"error": "Tool rejected or failed: " + type(exc).__name__}
            if name == "run_code":
                updates["result"] = ExecutionResult(status="failed", stderr=observation["error"])
        event("tool_result", iteration=state.iterations, tool=name, failed="error" in observation)
        text = json.dumps(observation)
        self.conversation.add(decision.model_dump_json(), text[:12000])
        try:
            self.semantic.store(f"Task: {state.task}\nAction: {name}\nObservation: {text[:2000]}", state.session_id)
        except Exception:
            updates["error"] = "Semantic memory storage failed"
        return updates

    def finalize(self, state):
        final = state.decision.final if state.decision and state.decision.action == "finish" else None
        error = state.error
        if final and final.task_complete and state.result.status != "passed":
            error = error or "Completion not verified: latest code has no successful execution"
        complete = bool(final and final.task_complete and not error)
        if not complete and not error:
            error = "Model reported task incomplete"
        # Read back files; never trust invented file lists or code from the model.
        code_parts = []
        for name in state.files_written:
            try:
                code_parts.append(f"# File: {name}\n" + self.tools.files.read_file(name))
            except Exception:
                error = "Unable to read back generated files"
                complete = False
        output = AgentOutput(task_complete=complete, code="\n\n".join(code_parts),
            explanation=final.explanation if final else "Agent stopped before completing the task.",
            plan=state.plan or (final.plan if final else ["Attempt to solve the coding task"]),
            result=state.result, files_written=state.files_written,
            iterations_used=state.iterations, total_tokens=state.total_tokens,
            error=error, warnings=state.warnings)
        event("run_finished", complete=complete, iterations=state.iterations, total_tokens=state.total_tokens)
        return {"output": output}

    def run(self, task, session_id="default", max_iterations=10):
        if self.session_id != session_id:
            self.conversation.turns.clear()
            self.session_id = session_id
        state = AgentState(task=task, session_id=session_id, max_iterations=max_iterations)
        result = self.graph.invoke(state, config={"recursion_limit": 40})
        return AgentOutput.model_validate(result["output"])
