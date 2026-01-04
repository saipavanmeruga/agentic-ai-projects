
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from prompts import agent_system_prompt
from agent_state import State 
from langgraph.constants import END
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from typing import Literal

llm = ChatOpenAI(model = "gpt-5.1", temperature = 0)

chart_summary_agent = create_agent(
    llm,
    tools=[],  # Add image processing tools if available/needed.
    system_prompt=agent_system_prompt(
        "You can only generate image captions. You are working with a researcher colleague and a chart generator colleague. "
        + "Your task is to generate a standalone, concise summary for the provided chart image saved at a local PATH, where the PATH should be and only be provided by your chart generator colleague. The summary should be no more than 3 sentences and should not mention the chart itself."
    ),
)

def chart_summary_node(state: State) -> Command[Literal[END]]:
    result = chart_summary_agent.invoke(state)
    print(f'Chart Summarizer answer: {result["messages"][-1].content}')

    goto = END
    return Command(update = {
        "messages": result["messages"],
        "final_answer": result["messages"][-1].content,
    }, goto = goto)
