from langgraph.graph import START, StateGraph
from agent_state import State
from planner import planner_node
from executor import executor_node
from text2sql_agent import text2sql_node
from charting_agent import chart_generator_node
from chart_summary_agent import chart_summary_node
from synthesizer_agent import synthesizer_node  
from dotenv import load_dotenv
import os
import streamlit as st

_ = load_dotenv(override=True)
openai_api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = openai_api_key

workflow = StateGraph(State)
workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("text2sql_agent", text2sql_node)
workflow.add_node("chart_generator", chart_generator_node)
workflow.add_node("chart_summarizer", chart_summary_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.add_edge(START, "planner")

graph = workflow.compile()

png_bytes = graph.get_graph().draw_png()

with open("agent_graph.png", "wb") as f:
    f.write(png_bytes)


from langchain_core.messages import HumanMessage
import os

def _extract_chart_meta(messages):
    chart_path = None
    chart_notes = None
    for msg in reversed(messages or []):
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            continue
        if "CHART_PATH:" in content:
            for line in content.splitlines():
                if line.startswith("CHART_PATH:"):
                    chart_path = line.split(":", 1)[1].strip()
                elif line.startswith("CHART_NOTES:"):
                    chart_notes = line.split(":", 1)[1].strip()
            break
    return chart_path, chart_notes

def _pick_final_answer(result):
    if result.get("final_answer"):
        return result["final_answer"]
    messages = result.get("messages", []) or []
    for msg in reversed(messages):
        if getattr(msg, "name", "") in ("chart_summarizer", "synthesizer"):
            return getattr(msg, "content", "")
    return getattr(messages[-1], "content", "No response available.") if messages else "No response available."

def main():
    st.title("Email Insights Assistant")
    query = st.text_input("Enter your query")
    if st.button("Submit"):
        state = {
            "messages": [HumanMessage(content=query)],
            "user_query": query,
            "enabled_agents": ["text2sql_agent", "chart_generator", "chart_summarizer", "synthesizer"],
        }
        result = graph.invoke(state)
        messages = result.get("messages", []) or []

        final_answer = _pick_final_answer(result)
        chart_path, chart_notes = _extract_chart_meta(messages)

        st.subheader("Answer")
        st.write(final_answer)

        if chart_path:
            if os.path.exists(chart_path):
                st.image(chart_path, caption=chart_notes or "Chart", use_column_width=True)
            else:
                st.info(f"Chart path reported but file not found: {chart_path}")

if __name__ == "__main__":
    main()
# def main():
#     st.title("Email Insights Assistant")
#     query = st.text_input("Enter your query")
#     if st.button("Submit"):
#         state = {
#             "messages": [HumanMessage(content=query)],
#             "user_query": query,
#             "enabled_agents": ["text2sql_agent", "chart_generator", 
#                                "chart_summarizer", "synthesizer"],
#         }
#         result = graph.invoke(state)
#         print(result)
#         # for message in result["messages"]:
#         #     st.write(message.pretty_print())

# if __name__ == "__main__":
#     main()