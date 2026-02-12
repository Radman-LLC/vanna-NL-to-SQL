"""Default system prompt builder implementation with memory workflow support.

This module provides a default implementation of the SystemPromptBuilder interface
that automatically includes memory workflow instructions when memory tools are available.

Memory instruction generation is delegated to the shared memory_instructions module
so that other builders (e.g., DomainPromptBuilder) can reuse the same logic.
"""

from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from .base import SystemPromptBuilder
from .memory_instructions import build_memory_workflow_instructions

if TYPE_CHECKING:
    from ..tool.models import ToolSchema
    from ..user.models import User


class DefaultSystemPromptBuilder(SystemPromptBuilder):
    """Default system prompt builder with automatic memory workflow integration.

    Dynamically generates system prompts that include memory workflow
    instructions when memory tools (search_saved_correct_tool_uses and
    save_question_tool_args) are available.
    """

    def __init__(self, base_prompt: Optional[str] = None):
        """Initialize with an optional base prompt.

        Args:
            base_prompt: Optional base system prompt. If not provided, uses a default.
        """
        self.base_prompt = base_prompt

    async def build_system_prompt(
        self, user: "User", tools: List["ToolSchema"]
    ) -> Optional[str]:
        """Build a system prompt with memory workflow instructions.

        Args:
            user: The user making the request
            tools: List of tools available to the user

        Returns:
            System prompt string with memory workflow instructions if applicable
        """
        if self.base_prompt is not None:
            return self.base_prompt

        tool_names = [tool.name for tool in tools]

        # Get today's date for the LLM to reference in date-relative queries
        today_date = datetime.now().strftime("%Y-%m-%d")

        # Base system prompt with role, date context, and response guidelines
        prompt_parts = [
            f"You are Vanna, an AI data analyst assistant created to help users "
            f"with data analysis tasks. Today's date is {today_date}.",
            "",
            "Response Guidelines:",
            "- Any summary of what you did or observations should be the final step.",
            "- Use the available tools to help the user accomplish their goals.",
            "- When you execute a query, that raw result is shown to the user outside "
            "of your response so YOU DO NOT need to include it in your response. "
            "Focus on summarizing and interpreting the results.",
        ]

        if tools:
            prompt_parts.append(
                f"\nYou have access to the following tools: {', '.join(tool_names)}"
            )

        # Append memory workflow instructions (empty string if no memory tools)
        memory_instructions = build_memory_workflow_instructions(tools)
        if memory_instructions:
            prompt_parts.append("\n" + memory_instructions)

        return "\n".join(prompt_parts)
