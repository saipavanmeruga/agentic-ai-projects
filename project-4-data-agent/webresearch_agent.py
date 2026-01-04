from langchain.agents import create_agent
from typing import Literal
from langchain_tavily import TavilySearch
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from agent_state import State
from prompts import agent_system_prompt
tavily_tool = TavilySearch(max_results = 5)

llm = ChatOpenAI(model = "gpt-5.1", temperature = 0)


web_search_agent = create_agent(
    llm,
    tools = [tavily_tool],
    system_prompt = agent_system_prompt(f"""
        You are the Researcher. You can ONLY perform research 
        by using the provided search tool (tavily_tool). 
        When you have found the necessary information, end your output.  
        Do NOT attempt to take further actions.
    """),
)

def web_researcher_node(state: State) -> Command[Literal["executor"]]:
    agent_query = state.get("agent_query")
    result = web_search_agent.invoke({"messages": agent_query})
    goto = "executor"
    result["messages"][-1] = HumanMessage(content = result["messages"][-1].content, name="web_researcher")
    return Command(update={
        "messages": result["messages"],
    }, goto = goto)