# Quick Start Guide - Project 2: Coding Agent

This guide will get you up and running with the Coding Agent in under 5 minutes.

## Overview

The Coding Agent is an AI-powered assistant that can:
- Execute shell commands to create code files and projects
- Search the web for technical information and best practices
- Install dependencies automatically
- Generate complete applications based on your prompts

**Example**: Ask it to "create a Next.js dashboard with shadcn/ui" and it will:
1. Search for the latest setup instructions
2. Run commands to create the project
3. Install dependencies
4. Set up the project structure

## Prerequisites

### Required

- **Python 3.8+** installed
- **OpenAI API Key** (get one at [platform.openai.com](https://platform.openai.com))
- **pip** package manager

### Optional but Recommended

- **Node.js** (if you want to generate Node.js projects)
- **Git** (for version control in generated projects)

### Verify Prerequisites

```bash
# Check Python version
python --version  # Should be 3.8 or higher

# Check pip
pip --version

# Check Node.js (optional)
node --version
```

## Installation

### Step 1: Install Dependencies

The project uses the `agents` library. Install it:

```bash
pip install agents
```

**Note**: If you encounter issues, you may need to install from a specific source. Check the `agents` library documentation for the latest installation instructions.

### Step 2: Set Up Environment Variables

Set your OpenAI API key:

```bash
# On macOS/Linux
export OPENAI_API_KEY="sk-your-api-key-here"

# On Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-api-key-here"

# On Windows (CMD)
set OPENAI_API_KEY=sk-your-api-key-here
```

**For permanent setup**, add to your shell profile:
- **macOS/Linux**: Add to `~/.bashrc` or `~/.zshrc`
- **Windows**: Add to System Environment Variables

### Step 3: Verify Setup

Run the prerequisites check:

```bash
python prequisites.py
```

You should see:
```
Workspace directory: /path/to/project-2-coding-agent/coding-agent-workspace
```

If you see an error about `OPENAI_API_KEY`, make sure you've set it correctly.

## Usage

### Basic Usage

Run the main script:

```bash
python main.py
```

You'll be prompted to enter a task. For example:

```
Enter a prompt: Create a Next.js dashboard with shadcn/ui components
```

The agent will:
1. **Search the web** for setup instructions
2. **Run shell commands** to create the project
3. **Install dependencies** automatically
4. **Show progress** with streaming logs

### Understanding the Output

The agent provides real-time feedback:

- `[tool] web search called` - Agent is searching for information
- `[tool] shell - running commands: [...]` - Agent is executing shell commands
- `[tool] output: ...` - Command output preview
- `[assistant]` - Agent's explanation of what it's doing
- `Final Answer:` - Summary of completed work

### Shell Command Approval

**By default**, the agent asks for approval before running shell commands:

```
Shell commands approval required:
  - npm create next-app@latest my-app
Proceed? [y/N]
```

Type `y` or `yes` to proceed, or `N` to cancel.

### Auto-Approval Mode

To skip approval prompts (useful for testing or CI):

```bash
export SHELL_AUTO_APPROVE=1
python main.py
```

**Warning**: Only use this if you trust the agent's commands!

## Example Prompts

### Create a Next.js App

```
Enter a prompt: Create a Next.js 16 app with TypeScript and Tailwind CSS
```

### Create a React Dashboard

```
Enter a prompt: Create a React dashboard with charts and data tables using shadcn/ui
```

### Create a Python API

```
Enter a prompt: Create a FastAPI application with authentication endpoints
```

### Create a Full-Stack App

```
Enter a prompt: Create a full-stack app with Next.js frontend and Python FastAPI backend
```

## Project Structure

```
project-2-coding-agent/
├── agent.py              # Agent definition with tools and instructions
├── main.py               # Main entry point with streaming logs
├── shellexecutor.py      # Custom shell executor with approval
├── prequisites.py        # Setup and workspace initialization
├── coding-agent-workspace/  # Directory where projects are created
│   └── shadcn-dashboard/    # Example generated project
└── QUICKSTART.md         # This file
```

## How It Works

### Agent Configuration

The agent is defined in `agent.py`:

- **Model**: Uses `gpt-5.1` (or your configured model)
- **Tools**: 
  - `ShellTool` - Execute shell commands in the workspace
  - `WebSearchTool` - Search the web for technical information
- **Instructions**: Agent knows to search, create files, and install dependencies

### Shell Executor

The `ShellExecutor` in `shellexecutor.py`:

- Runs commands in the `coding-agent-workspace/` directory
- Requires approval before execution (unless `SHELL_AUTO_APPROVE=1`)
- Captures stdout and stderr
- Supports timeouts
- Returns structured results

### Workspace

All generated projects are created in `coding-agent-workspace/`:

- Each project gets its own subdirectory
- The workspace is created automatically if it doesn't exist
- You can manually clean it up if needed

## Troubleshooting

### "OPENAI_API_KEY is not set"

**Solution:**
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Verify with:
```bash
echo $OPENAI_API_KEY
```

### "ModuleNotFoundError: No module named 'agents'"

**Solution:**
```bash
pip install agents
```

If that doesn't work, check the `agents` library documentation for installation instructions.

### Agent keeps asking for approval

**Solution:**
Set auto-approval mode:
```bash
export SHELL_AUTO_APPROVE=1
```

### Commands fail or timeout

**Possible causes:**
- Network issues
- Missing dependencies (Node.js, npm, etc.)
- Invalid commands generated by agent

**Solution:**
- Check the command output in the logs
- Verify required tools are installed
- Try a simpler prompt first

### Workspace directory issues

**Solution:**
The workspace is created automatically. If you have permission issues:

```bash
# Check permissions
ls -la coding-agent-workspace/

# Create manually if needed
mkdir -p coding-agent-workspace
```

## Advanced Usage

### Custom Workspace Directory

Edit `prequisites.py` to change the workspace location:

```python
workspace_dir = Path("/path/to/your/workspace").resolve()
```

### Modify Agent Instructions

Edit `agent.py` to change the agent's behavior:

```python
INSTRUCTIONS = '''
Your custom instructions here...
'''
```

### Add More Tools

You can add additional tools to the agent in `agent.py`:

```python
coding_agent = Agent(
    name = "Coding Agent",
    model = "gpt-5.1",
    instructions = INSTRUCTIONS,
    tools = [shell_tool, WebSearchTool(), YourCustomTool()],
)
```

## Best Practices

1. **Start Simple**: Begin with basic prompts to test the agent
2. **Review Commands**: Always review shell commands before approving
3. **Use Workspace**: Keep generated projects in the workspace directory
4. **Clean Up**: Periodically clean the workspace to save disk space
5. **Version Control**: Consider adding the workspace to `.gitignore`

## Next Steps

1. ✅ Run your first agent task
2. ✅ Explore the generated projects in `coding-agent-workspace/`
3. ✅ Try different types of projects
4. ✅ Customize the agent instructions for your needs
5. ✅ Integrate into your workflow

## Example Workflow

```bash
# 1. Set up environment
export OPENAI_API_KEY="sk-your-key"

# 2. Run the agent
python main.py

# 3. Enter a prompt
Enter a prompt: Create a React todo app with TypeScript

# 4. Review and approve commands
Shell commands approval required:
  - npm create vite@latest todo-app -- --template react-ts
Proceed? [y/N] y

# 5. Wait for completion
[assistant] Creating React app...
[tool] shell - running commands: ['npm create vite@latest...']
...

# 6. Check the result
cd coding-agent-workspace/todo-app
npm install
npm run dev
```

## Security Notes

⚠️ **Important Security Considerations:**

- The agent can execute **any shell command** - use with caution
- Always review commands before approving
- Don't run in production environments without proper sandboxing
- Keep your `OPENAI_API_KEY` secure and never commit it
- Consider using `SHELL_AUTO_APPROVE=1` only in trusted environments

## Getting Help

- Check the agent's output logs for error messages
- Review the generated code in `coding-agent-workspace/`
- Verify all prerequisites are installed
- Check the `agents` library documentation

---

**Happy Coding! 🚀**

The agent is ready to help you build projects. Start with a simple prompt and watch it work!


