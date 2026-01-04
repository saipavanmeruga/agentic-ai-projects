import os
from typing import  Literal

from langchain_core.messages import AIMessage
from prompts import MONGODB_AGENT_SYSTEM_PROMPT

# MongoDB Agent Toolkit
from langchain_mongodb.agent_toolkit.database import MongoDBDatabase
from langchain_mongodb.agent_toolkit.toolkit import MongoDBDatabaseToolkit
from langchain.messages import ToolMessage
from langchain.agents.middleware.types import wrap_tool_call
# LangChain Core
from langchain_openai import ChatOpenAI

import uuid
from langchain.agents import create_agent
# LangGraph Core
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from pymongo import MongoClient
from agent_state import State
from langgraph.types import Command
from langchain_core.messages import HumanMessage

print("📦 All dependencies installed successfully!")


from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from text2sql_llmsummarizer import LLMSummarizingMongoDBSaver

db = MongoDBDatabase.from_connection_string(os.getenv("MONGODB_URI"), database="email_objects")

client = MongoClient(
    os.getenv("MONGODB_URI"), appname="devrel.showcase.notebook.agent.text_to_mql_agent"
)

# Preview database collections
print("\n📋 Available Collections:", list(db.get_usable_collection_names()))

text2sql_llm = ChatOpenAI(model="gpt-5.1", temperature=0)

toolkit = MongoDBDatabaseToolkit(db=db, llm=text2sql_llm)

tools = toolkit.get_tools()

tool = {t.name: t for t in tools}

@wrap_tool_call
def handle_tool_errors(request, handler):
    try:
        return handler(request)
    except Exception as e:
        return ToolMessage(content=f"Tool Execution Error: {e}" + "Please check the syntax of the query and try again.", name=request.tool_call["name"], tool_call_id=request.tool_call["id"], status="error")
def create_react_agent_with_enhanced_memory():
    """Create ReAct agent with LLM-powered summarizing checkpointer"""
    system_message = MONGODB_AGENT_SYSTEM_PROMPT
    # summarizing_checkpointer = LLMSummarizingMongoDBSaver(client, text2sql_llm)

    return create_agent(
        text2sql_llm,
        tools=tools,
        system_prompt=system_message,
        middleware=[handle_tool_errors],
        # checkpointer=summarizing_checkpointer,
    )

text2sql_agent_with_memory = create_react_agent_with_enhanced_memory()

def text2sql_node(state: State) -> Command[Literal['executor']]:
    """Text-to-SQL agent node"""
    agent_query = state.get("agent_query")
    config = {"configurable": {"thread_id": uuid.uuid4()}}
    # print(f"Agent query: {agent_query}")
    result = text2sql_agent_with_memory.invoke({"messages": [HumanMessage(content=agent_query)]}, config)
    # print(f"Text2SQL agent result: {result['messages'][-1].content}")
    return Command(update={
        "messages": result["messages"],
        "user_query": state.get("user_query", state["messages"][0].content),
    }, goto="executor")