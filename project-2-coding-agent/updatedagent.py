from agents import HostedMCPTool,Agent,WebSearchTool,ShellTool
from applypatchtool import WorkSpaceEditor, ApprovalTracker

from agents import ApplyPatchTool
from prequisites import workspace_dir
from shellexecutor import ShellExecutor

CONTEXT7_API_KEY = ""



context7_tool = HostedMCPTool(
    tool_config = {
        "type": "mcp",
        "server_label": "context7",
        "server_url": "https://mcp.context7.com/mcp",
        **(
            {
                "authorization": f"Bearer {CONTEXT7_API_KEY}" 
            } if CONTEXT7_API_KEY else {}
        ),
        "require_approval": "never",
    },
)


approvals = ApprovalTracker()

editor = WorkSpaceEditor(root = workspace_dir, approvals = approvals, auto_approve = True)

apply_patch_tool = ApplyPatchTool(editor = editor)


UPDATED_INSTRUCTIONS = """
You are a coding assistant helping a user with an existing project.
Use the apply_patch tool to edit files based on their feedback. 
When editing files:
- Never edit code via shell commands.
- Always read the file first using `cat` with the shell tool.
- Then generate a unified diff relative to EXACTLY that content.
- Use apply_patch only once per edit attempt.
- If apply_patch fails, stop and report the error; do NOT retry.
You can search the web to find which command you should use based on the technical stack, and use commands to install dependencies if needed.
When the user refers to an external API, use the Context7 MCP server to fetch docs for that API.
For example, if they want to use the OpenAI API, search docs for the openai-python or openai-node sdk depending on the project stack.
"""

shell_tool = ShellTool(executor = ShellExecutor(cwd = workspace_dir))

updated_coding_agent =  Agent(
    name = "Updated Coding Agent",
    model = "gpt-5.1",
    instructions = UPDATED_INSTRUCTIONS,
    tools = [apply_patch_tool, context7_tool, WebSearchTool(), shell_tool],
)