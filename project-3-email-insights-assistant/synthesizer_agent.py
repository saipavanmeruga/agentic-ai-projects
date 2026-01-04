from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from prompts import agent_system_prompt
from agent_state import State
from langgraph.constants import END
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from typing import Literal

llm = ChatOpenAI(model = "gpt-5.1", temperature = 0)

def synthesizer_node(state: State) -> Command[Literal[END]]:
    messages = state.get("messages", [])
    # print(f"Messages: {messages}")
    relevant_msgs = [
        m.content for m in state.get("messages", [])
        # if getattr(m, "name", None) in ("text2sql_agent", "chart_generator", "chart_summarizer")

    ]
    # print(f"Relevant messages: {','.join(relevant_msgs)}")

    user_question = state.get("user_query", state.get("messages", [{}])[0].content if state.get("messages") else "")

    synthesis_instructions = (      """
        You are the Synthesizer. Use the context below to directly 
        answer the user's question. Perform any lightweight calculations, 
        comparisons, or inferences required. Do not invent facts not 
        supported by the context. If data is missing, say what's missing
        and, if helpful, offer a clearly labeled best-effort estimate 
        with assumptions.
        Produce a concise response that fully answers the question, with 
        the following guidance:
        - Start with the direct answer (one short paragraph or a tight bullet list).
                - Include key figures from any 'Results:' tables (e.g., totals, top items).
        - If any message contains citations, include them as a brief 'Citations: [...]' line.
        - Keep the output crisp; avoid meta commentary or tool instructions.
        """)

    summary_prompt = [
        HumanMessage(content = (f"User question: {user_question}"
                                f"Relevant context: {' '.join(relevant_msgs)}"
                                f"Synthesis instructions: {synthesis_instructions}"))
    ]

    llm_reply = llm.invoke(summary_prompt)
    answer = llm_reply.content.strip()
    print(f'Synthesizer answer: {answer}')


    goto = END
    return Command(update = {
        "messages": [HumanMessage(content = answer, name = "synthesizer")],
        "final_answer": answer,
    }, goto = goto)