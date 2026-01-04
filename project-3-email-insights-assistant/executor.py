from time import strptime
from typing import Dict, Any, Literal
from prompts import executor_prompt
from langgraph.graph import END
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from agent_state import State
from planner import reasoning_llm
import json

MAX_REPLANS = 3

def executor_node(state: State) -> Command[Literal["text2sql_agent", "chart_generator", "synthesizer"]]:
    plan: Dict[str, Any] = state.get("plan", {})
    step: int = state.get("current_step", 0)
    # print(f"Plan: {plan}")

    if state.get("replan_flag"):
        planned_agent = plan.get(str(step), {}).get("agent")
        return Command(
            update = {
                "replan_flag": False,
                "current_step": step + 1 #advance because we executed the planned agent.

            }, 
            goto = planned_agent
        )
    
    #1) Build the prompt (using executor_prompt function call) and call the LLM
    llm_reply = reasoning_llm.invoke([executor_prompt(state)])

    try:
        content_str = llm_reply.content if isinstance(llm_reply.content, str) else str(llm_reply.content)
        parsed = json.loads(content_str)
        # print(f"Parsed: {parsed}")
        replan: bool = parsed["replan"]
        goto: str = parsed["goto"]
        reason: str = parsed["reason"]
        query: str = parsed["query"]
    except Exception as exc:
        raise ValueError(f"Invalid Executor JSON: \n {llm_reply.content}") from exc
    #Update the state
    updates: Dict[str, Any] = {
        "messages": [HumanMessage(content = llm_reply.content, name = "executor")],
        "last_reason": reason,
        "agent_query": query,
    }

    #Replan accounting
    replans: Dict[int, int] = state.get("replan_attempts", {}) or {}
    step_replans = replans.get(step, 0)

    #2) Replan Decision
    if replan:
        if step_replans < MAX_REPLANS:
            replans[step] = step_replans + 1
            updates.update({
                "replan_attempts": replans,
                "replan_flag": True,
                "current_step": step,
            })
            return Command(update = updates, goto="planner")
        else:
            next_agent = plan.get(str(step + 1), {}).get("agent", "synthesizer")
            updates["current_step"] = step + 1
            return Command(update = updates, goto=next_agent)

    #3) Execute the planned agent
    planned_agent = plan.get(str(step), {}).get("agent")

    updates["current_step"] = step + 1 if goto == planned_agent else step
    updates["replan_flag"] = False
    return Command(update = updates, goto = goto)
