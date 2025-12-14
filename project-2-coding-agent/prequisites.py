import os

assert "OPENAI_API_KEY" in os.environ, "OPENAI_API_KEY is not set"

from pathlib import Path


workspace_dir = Path("coding-agent-workspace").resolve()

workspace_dir.mkdir(exist_ok=True)

print(f"Workspace directory: {workspace_dir}")

