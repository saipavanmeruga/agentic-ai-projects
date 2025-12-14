import asyncio
from agents import ItemHelpers, Runner
from agent import coding_agent
from updatedagent import updated_coding_agent

async def run_coding_agent_with_logs(prompt: str):
    """
    Run the coding agent and stream the logs to the console.
    """
    print(f"Running coding agent with prompt: {prompt}")

    result = Runner.run_streamed(coding_agent, input = prompt)

    async for event in result.stream_events():
        if event.type == "run_item_stream_event":
            item = event.item

            if item.type == "tool_call_item":
                raw = item.raw_item
                raw_type_name = type(raw).__name__


                if raw_type_name == "ResponseFunctionWebSearch":
                    print("[tool] web search called - agent is calling the web search tool")

                elif raw_type_name == "LocalShellCall":
                    commands = getattr(getattr(raw, "action", None), "commands", None)
                    if commands:
                        print(f"[tool] shell - running commands: {commands}")
                    else:
                        print("[tool] shell - running command")
                else:
                    print(f"[tool] {raw_type_name} called")
            elif item.type == "tool_call_output_item":
                output_preview = str(item.output)

                if len(output_preview) > 400:
                    output_preview = output_preview[:400] + "..."
                print(f"[tool] output: {output_preview}")

            elif item.type == "message_output_item":
                text = ItemHelpers.text_message_output(item)
                print(f"[assistant]\n{text}\n")
            else:   
                pass

    print("===== Run complete ===== \n")
        
    print("Final Answer:")

    print(result.final_output)


async def run_updated_coding_agent_with_logs(prompt: str):
    """
    Run the updated coding agent and stream the logs to the console.
    """
    print(f"Running updated coding agent with prompt: {prompt}")

    apply_patch_seen = False

    result = Runner.run_streamed(updated_coding_agent, input = prompt)

    async for event in result.stream_events():
        if event.type != "run_item_stream_event":
            continue

        item = event.item

        if item.type == "tool_call_item":
            raw = item.raw_item
            raw_type_name = type(raw).__name__

            if raw_type_name == "ResponseFunctionWebSearch":
                print("[tool] web_search - agent is calling the web search tool")
            elif raw_type_name == "ResponseFunctionShellToolCall":
                action = getattr(raw, "action", None)
                commands = getattr(action, "commands", None) if action else None
                if commands:
                    print(f"[tool] shell - running commands: {commands}")
                else:
                    print(f"[tool] shell - running command")
            elif "MCP" in raw_type_name or "Mcp" in raw_type_name:
                tool_name = getattr(raw, "tool_name", None)
                if tool_name is None:
                    action = getattr(raw, "action", None)
                    tool_name = getattr(action, "tool_name", None) if action else None
                server_label = getattr(raw, "server_label", None)
                label_str = f" (server= {server_label})" if server_label else ""
                if tool_name:
                    print(f"[tool] mcp{label_str} - calling {tool_name!r} tool")
                else:
                    print(f"[tool] mcp{label_str} - MCP tool call")
            else:
                print(f"[tool] {raw_type_name} - agent is calling an unknown tool")
        
        elif item.type == "tool_call_output_item":
            raw = item.raw_item
            output_preview = str(item.output)

            is_apply_patch = False
            if isinstance(raw, dict) and raw.get("type") == "apply_patch_call_output":
                is_apply_patch = True
            elif any(
                output_preview.startswith(prefix)
                for prefix in ("Created", "Updated", "Deleted")
            ):
                is_apply_patch = True
            if is_apply_patch:
                apply_patch_seen = True
                if len(output_preview) > 400:
                    output_preview = output_preview[:400] + "..."
                print(f"apply_patch - {output_preview}\n")
            else:
                if len(output_preview) > 400:
                    output_preview = output_preview[:400] + "..."
                print(f"[tool output] {output_preview}\n")
        
        elif item.type == "message_output_item":
            text = ItemHelpers.text_message_output(item)
            print(f"[assistant]\n{text}\n")
        else:
            pass

    print("===== Run complete ===== \n")

    print("Final Answer:")

    print(result.final_output)
    if apply_patch_seen:
        _ = print("\n[apply_patch] One or more apply_patch calls were executed.")
    else:
        print("\n[apply_patch] No apply_patch calls detected in this run.")


if __name__ == "__main__":
    prompt = input("Enter a prompt: ")
    asyncio.run(run_updated_coding_agent_with_logs(prompt))