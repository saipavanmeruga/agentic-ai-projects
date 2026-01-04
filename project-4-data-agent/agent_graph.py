from langgraph.graph import START, StateGraph
from agent_state import State
from planner import planner_node
from executor import executor_node
from webresearch_agent import web_researcher_node
from charting_agent import chart_generator_node
from chart_summary_agent import chart_summary_node
from synthesizer_agent import synthesizer_node
from dotenv import load_dotenv
import os

_ = load_dotenv(override=True)
openai_api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = openai_api_key
tavily_api_key = os.getenv("TAVILY_API_KEY")
os.environ["TAVILY_API_KEY"] = tavily_api_key

workflow = StateGraph(State)
workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("web_researcher", web_researcher_node)
workflow.add_node("chart_generator", chart_generator_node)
workflow.add_node("chart_summarizer", chart_summary_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.add_edge(START, "planner")

graph = workflow.compile()


png_bytes = graph.get_graph().draw_png()

with open("agent_graph.png", "wb") as f:
    f.write(png_bytes)

from langchain_core.messages import HumanMessage
import json

query = "Chart the current market capitalization of the top 5 banks in the US?"
print(f"Query: {query}")

state = {
            "messages": [HumanMessage(content=query)],
            "user_query": query,
            "enabled_agents": ["web_researcher", "chart_generator", 
                               "chart_summarizer", "synthesizer"],
        }
graph.invoke(state)

print("--------------------------------")