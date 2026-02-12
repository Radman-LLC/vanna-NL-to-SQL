"""Shared memory workflow instruction generation.

Extracts the memory workflow prompt sections into a reusable function so that
any SystemPromptBuilder subclass (DefaultSystemPromptBuilder, DomainPromptBuilder,
or custom builders) can include memory instructions when memory tools are available.

This avoids duplicating the memory workflow logic across multiple builders and
ensures the LLM always receives consistent instructions for using memory tools.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..tool.models import ToolSchema


def build_memory_workflow_instructions(tools: List["ToolSchema"]) -> str:
    """Generate memory workflow instructions based on which memory tools are available.

    Checks the tool list for memory-related tools and generates appropriate
    instructions telling the LLM how and when to use them. Returns an empty
    string if no memory tools are registered.

    Args:
        tools: List of tool schemas available to the current user

    Returns:
        Memory workflow instruction string, or empty string if no memory tools present
    """
    tool_names = [tool.name for tool in tools]
    has_search = "search_saved_correct_tool_uses" in tool_names
    has_save = "save_question_tool_args" in tool_names
    has_text_memory = "save_text_memory" in tool_names

    # No memory tools registered — nothing to add
    if not (has_search or has_save or has_text_memory):
        return ""

    parts: list[str] = []

    parts.append("=" * 60)
    parts.append("MEMORY SYSTEM:")
    parts.append("=" * 60)

    # Structured tool usage memory (search before execute, save after success)
    if has_search or has_save:
        parts.append("\n1. TOOL USAGE MEMORY (Structured Workflow):")
        parts.append("-" * 50)

    if has_search:
        parts.append(
            "\n• BEFORE executing any tool (run_sql, visualize_data, or calculator), "
            "you MUST first call search_saved_correct_tool_uses with the user's question "
            "to check if there are existing successful patterns for similar questions."
        )
        parts.append(
            "\n• Review the search results (if any) to inform your approach "
            "before proceeding with other tool calls."
        )

    if has_save:
        parts.append(
            "\n• AFTER successfully executing a tool that produces correct and useful "
            "results, you MUST call save_question_tool_args to save the successful "
            "pattern for future use."
        )

    if has_search or has_save:
        parts.append("\nExample workflow:")
        parts.append("  • User asks a question")
        if has_search:
            parts.append(
                '  • First: Call search_saved_correct_tool_uses(question="user\'s question")'
            )
        parts.append(
            "  • Then: Execute the appropriate tool(s) based on search results and the question"
        )
        if has_save:
            parts.append(
                "  • Finally: If successful, call save_question_tool_args("
                'question="user\'s question", tool_name="tool_used", args={the args you used})'
            )

        if has_search:
            parts.append(
                "\nDo NOT skip the search step, even if you think you know how to answer. "
                "Do NOT forget to save successful executions."
            )

        parts.append("\nThe only exceptions to searching first are:")
        parts.append(
            '  • When the user is explicitly asking about the tools themselves (like "list the tools")'
        )
        parts.append(
            "  • When the user is testing or asking you to demonstrate the save/search functionality itself"
        )

    # Free-form text memory (domain knowledge, schema info, etc.)
    if has_text_memory:
        parts.append("\n2. TEXT MEMORY (Domain Knowledge & Context):")
        parts.append("-" * 50)
        parts.append(
            "\n• save_text_memory: Save important context about the database, schema, or domain"
        )
        parts.append("\nUse text memory to save:")
        parts.append(
            "  • Database schema details (column meanings, data types, relationships)"
        )
        parts.append("  • Company-specific terminology and definitions")
        parts.append("  • Query patterns or best practices for this database")
        parts.append("  • Domain knowledge about the business or data")
        parts.append("  • User preferences for queries or visualizations")
        parts.append("\nDO NOT save:")
        parts.append("  • Information already captured in tool usage memory")
        parts.append("  • One-time query results or temporary observations")
        parts.append("\nExamples:")
        parts.append(
            '  • save_text_memory(content="The status column uses 1 for active, 0 for inactive")'
        )
        parts.append(
            '  • save_text_memory(content="MRR means Monthly Recurring Revenue in our schema")'
        )
        parts.append(
            "  • save_text_memory(content=\"Always exclude test accounts where email contains 'test'\")"
        )

    return "\n".join(parts)
