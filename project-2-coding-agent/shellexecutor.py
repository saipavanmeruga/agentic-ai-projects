import os
import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from agents import (
    ShellTool,
    ShellCommandRequest,
    ShellCommandOutput,
    ShellCallOutcome,
    ShellResult
)


async def require_approval(commands: Sequence[str]) -> None:
    """
    Ask for confirmation before running shell commands.

    Set SHELL_AUTO_APPROVE=1 in your environment to skip this prompt
    (useful when you're iterating a lot or running in CI).
    """

    if os.environ.get("SHELL_AUTO_APPROVE") == "1":
        return
    
    print("Shell commands approval required:")
    for entry in commands:
        print(f"  - {entry}")
    response = input("Proceed? [y/N] ").strip().lower()
    if response not in {"y", "yes"}:
        raise RuntimeError("Shell command execution rejected by user")
    
class ShellExecutor:
    """
    Shell executor for notebook cookbook.
    Runs all commands inside a workspace directory.
    Captures stdout and stderr for each command.
    Enforces an optionals timeout from action.timeout_ms
    Returns a ShellResult with ShellCommandOutput  entries using Shellcalloutcome
    """

    def __init__(self, cwd: Path):
        self.cwd = cwd

    async def __call__(self, request: ShellCommandRequest) -> ShellResult:
        action = request.data.action
        await require_approval(action.commands)

        outputs: list[ShellCommandOutput] = []

        for command in action.commands:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd = self.cwd,
                env =os.environ.copy(),
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE,
            )

            timed_out = False
            try:
                timeout = (action.timeout_ms or 0) / 1000 or None
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout = timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()
                timed_out = True

            stdout  = stdout_bytes.decode("utf-8", errors="ignore")
            stderr = stderr_bytes.decode("utf-8", errors="ignore")

            outcome = ShellCallOutcome(
                type = "timeout" if timed_out else "exit",
                exit_code = getattr(proc, "returncode", None),
            )

            outputs.append(ShellCommandOutput(
                stdout = stdout,
                stderr = stderr,
                outcome = outcome,
            ))

            if timed_out:
                break

        return ShellResult(output = outputs, provider_data = {"working_dir": str(self.cwd)},
        )

