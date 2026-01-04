#the planner takes the user query and generates a plan.
from prompts import plan_prompt
from langgraph.types import Command 
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from agent_state import State
from typing import Literal, Dict, Any
import json

reasoning_llm = ChatOpenAI(model = "gpt-5.1", model_kwargs = {"response_format": {"type": "json_object"}})

def planner_node(state: State) -> Command[Literal['executor']]:
    """Runs the planning LLM and stores the resulting plan in the state."""
    #1. Invoke LLM with the planner prompt
    llm_reply = reasoning_llm.invoke([plan_prompt(state)])

    try:
        content_str =llm_reply.content if isinstance(llm_reply.content, str) else str(llm_reply.content)
        parsed_plan = json.loads(content_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {llm_reply.content}") 

    replan = state.get("replan_flag", False)
    updated_plan: Dict[str, Any] = parsed_plan

    return Command(
        update = {
            "plan": updated_plan,
            "messages": [HumanMessage(
                content = llm_reply.content,
                name = "replan" if replan else "initial_plan"
            )],
            "user_query": state.get("user_query", state["messages"][0].content),
            "current_step": 1 if not replan else state["current_step"],
            "replan_flag": state.get("replan_flag", False),
            "last_reason": "",
            "enabled_agents": state.get("enabled_agents")
            },
            goto = "executor"
    )

