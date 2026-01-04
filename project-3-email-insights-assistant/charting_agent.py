# Chart generator agent and node
# NOTE: THIS PERFORMS ARBITRARY CODE EXECUTION, 
# WHICH CAN BE UNSAFE WHEN NOT SANDBOXED
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from helper import python_repl_tool
from prompts import agent_system_prompt
from agent_state import State
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from typing import Literal

llm = ChatOpenAI(model = "gpt-5.1", temperature = 0)

chart_agent = create_agent(
    llm,
    tools = [python_repl_tool],
    system_prompt=agent_system_prompt(
        """
        You can only generate charts. You are working with a researcher 
        colleague.
        1) Print the chart first.
        2) Save the chart to a file in the current working directory.
        3) At the very end of your message, output EXACTLY two lines 
        so the summarizer can find them:
           CHART_PATH: <relative_path_to_chart_file>
           CHART_NOTES: <one concise sentence summarizing the main insight in the chart>
        Do not include any other trailing text after these two lines.
        """
    ),
)



def chart_generator_node(state: State) -> Command[Literal["chart_summarizer"]]:
    result = chart_agent.invoke(state)
    result["messages"][-1] = HumanMessage(content = result["messages"][-1].content, name="chart_generator")
    goto = "chart_summarizer"
    return Command(
        update = {
            "messages": result["messages"],
        },
        goto = goto
    )

