#define the agent

from agents import Agent, ShellTool, WebSearchTool
from shellexecutor import ShellExecutor
from prequisites import workspace_dir

shell_tool = ShellTool(executor = ShellExecutor(cwd = workspace_dir))

# Define the agent's instructions
INSTRUCTIONS = '''
You are a coding assistant. The user will explain what they want to build, and your goal is to run commands to generate a new app.
You can search the web to find which command you should use based on the technical stack, and use commands to create code files. 
You should also install necessary dependencies for the project to work. 
'''

coding_agent = Agent(
    name = "Coding Agent",
    model = "gpt-5.1",
    instructions = INSTRUCTIONS,
    tools = [shell_tool, WebSearchTool()],
)

