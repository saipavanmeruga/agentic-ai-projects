# MongoDB Memory & Checkpointing
from langgraph.checkpoint.mongodb import MongoDBSaver
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

class LLMSummarizingMongoDBSaver(MongoDBSaver):
    """MongoDB saver with LLM-powered intelligent summarization"""

    def __init__(self, client, llm):
        super().__init__(client)
        self.llm = llm

        # Cache for performance (optional)
        self._summary_cache = {}

    def summarize_step(self, checkpoint_data: Dict[str, Any]) -> str:
        """Generate contextual summary using LLM"""
        try:
            # Extract channel values and messages
            channel_values = checkpoint_data.get("channel_values", {})
            messages = channel_values.get("messages", [])

            if not messages:
                return "🔄 Initial state"

            # Get the most recent message
            last_message = messages[-1]

            if not last_message:
                return "📭 Empty step"

            # Extract message details
            message_type = (
                type(last_message).__name__
                if hasattr(last_message, "__class__")
                else "unknown"
            )
            content = getattr(last_message, "content", "") or ""
            tool_calls = getattr(last_message, "tool_calls", [])

            # Handle dict-like messages (fallback)
            if isinstance(last_message, dict):
                message_type = last_message.get("type", "unknown")
                content = last_message.get("content", "")
                tool_calls = last_message.get("tool_calls", [])

            # Create a simple cache key to avoid redundant LLM calls
            cache_key = f"{message_type}:{content[:50]}:{len(tool_calls)}"
            if cache_key in self._summary_cache:
                return self._summary_cache[cache_key]

            # Build context for LLM
            context_parts = []
            if content:
                context_parts.append(f"Content: {content[:200]}")
            if tool_calls:
                tool_info = []
                for tc in tool_calls[:2]:  # Limit to first 2 tool calls
                    tool_name = tc.get("name", "unknown")
                    tool_args = str(tc.get("args", {}))[:100]
                    tool_info.append(f"{tool_name}({tool_args})")
                context_parts.append(f"Tool calls: {', '.join(tool_info)}")

            context = "\n".join(context_parts) if context_parts else "No content"

            # LLM prompt for summarization
            prompt = f"""Summarize this conversation step in 2-5 words with a relevant emoji.

Message type: {message_type}
{context}

Guidelines:
- Use emojis: 👤 for user, 🤖 for AI, 🔧 for tools, 📊 for data, ✨ for results
- Be concise and descriptive
- Focus on the action/intent

Examples:
- "👤 Count movies query"
- "🔧 Schema lookup: movies"
- "📊 Aggregation pipeline"
- "✨ Formatted results"
- "❌ Query validation error"

Summary:"""

            # Get LLM response
            response = self.llm.invoke(prompt)
            summary = response.content.strip()[:60]  # Limit length

            # Cache the result
            self._summary_cache[cache_key] = summary

            # Keep cache size reasonable
            if len(self._summary_cache) > 100:
                # Remove oldest entries (simple FIFO)
                oldest_keys = list(self._summary_cache.keys())[:50]
                for key in oldest_keys:
                    del self._summary_cache[key]

            return summary

        except Exception as e:
            # Fallback for any errors
            error_msg = str(e)[:30]
            return f"❓ Step (error: {error_msg}...)"

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Dict[str, Any],
        metadata: Dict[str, Any],
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """Override put method to add LLM-generated step summary"""
        try:
            # Generate step summary using LLM
            step_summary = self.summarize_step(checkpoint)

            # Create enhanced metadata
            enhanced_metadata = metadata.copy() if metadata else {}
            enhanced_metadata["step_summary"] = step_summary
            enhanced_metadata["step_timestamp"] = checkpoint.get("ts", "unknown")

            # Add step number if available
            messages = checkpoint.get("channel_values", {}).get("messages", [])
            enhanced_metadata["step_number"] = len(messages)

            # Call parent's put method
            return super().put(config, checkpoint, enhanced_metadata, new_versions)

        except Exception as e:
            print(f"❌ Error adding LLM summary: {e}")
            # Fallback to basic metadata
            return super().put(config, checkpoint, metadata, new_versions)