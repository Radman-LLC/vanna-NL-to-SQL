# Memory Workflow Instructions Module

## Overview

The `memory_instructions` module provides a shared function for generating memory workflow instructions that are injected into LLM system prompts. This allows multiple `SystemPromptBuilder` implementations to reuse the same memory workflow logic without duplication.

**Location:** `src/vanna/core/system_prompt/memory_instructions.py`

**Purpose:** Eliminate code duplication and ensure consistent memory workflow instructions across all system prompt builders.

## Why This Module Exists

### The Problem (Before)

Originally, `DefaultSystemPromptBuilder` contained 80+ lines of inline code to generate memory workflow instructions. When `DomainPromptBuilder` was added, it needed the same logic. This created two bad options:

1. **Duplicate the logic** - Copy 80 lines into `DomainPromptBuilder` (violates DRY principle)
2. **Skip memory instructions** - Don't include them in domain prompts (breaks functionality)

### The Solution (After)

Extract the memory instruction generation into a shared function that both builders can import and call:

```python
# src/vanna/core/system_prompt/memory_instructions.py
def build_memory_workflow_instructions(tools: List["ToolSchema"]) -> str:
    """Generate memory workflow instructions based on available tools."""
    # 100+ lines of instruction generation logic
    return memory_instructions_string
```

Now both `DefaultSystemPromptBuilder` and `DomainPromptBuilder` can use the same function:

```python
from vanna.core.system_prompt.memory_instructions import build_memory_workflow_instructions

# In both builders:
memory_instructions = build_memory_workflow_instructions(tools)
if memory_instructions:
    prompt_parts.append(memory_instructions)
```

## Architecture

### Design Pattern: Shared Utility Function

This module follows the **shared utility function** pattern:

- **Single source of truth** - Memory workflow logic defined once
- **Stateless function** - No class, no state, just pure transformation
- **Reusable** - Any `SystemPromptBuilder` can call it
- **Testable** - Can be tested independently of builders

### When to Use This Pattern

Use a shared utility module when:
- Logic is complex (50+ lines)
- Multiple classes need the exact same logic
- Logic is pure/stateless (no side effects)
- Testing in isolation is valuable

**Don't use this pattern when:**
- Logic is trivial (< 10 lines) - inline it
- Different classes need slightly different behavior - use inheritance or composition
- State is required - use a class

## API Reference

### `build_memory_workflow_instructions()`

**Signature:**
```python
def build_memory_workflow_instructions(tools: List["ToolSchema"]) -> str
```

**Purpose:** Generate memory workflow instructions based on which memory tools are available.

**Parameters:**
- `tools` - List of `ToolSchema` objects representing tools available to the current user

**Returns:**
- `str` - Formatted memory workflow instructions, or empty string if no memory tools present

**Behavior:**

1. **Checks for memory tools** - Scans `tools` list for:
   - `search_saved_correct_tool_uses` - RAG search for similar successful queries
   - `save_question_tool_args` - Save successful tool executions for future RAG
   - `save_text_memory` - Save free-form domain knowledge

2. **Generates instructions** - If any memory tools exist, returns formatted instructions explaining:
   - When to call search (BEFORE executing other tools)
   - When to call save (AFTER successful executions)
   - What to save in text memory (domain knowledge, schema info)
   - Example workflow showing the search → execute → save pattern

3. **Returns empty string** - If no memory tools are registered, returns `""` so builders can skip this section

**Example Usage:**

```python
from vanna.core.system_prompt.memory_instructions import build_memory_workflow_instructions

# In a SystemPromptBuilder implementation
async def build_system_prompt(self, user: User, tools: List[ToolSchema]) -> str:
    parts = [
        "You are Vanna, an AI data analyst...",
        "Response Guidelines:",
        "- Use available tools",
        # ... other prompt sections ...
    ]

    # Add memory instructions if memory tools are registered
    memory_instructions = build_memory_workflow_instructions(tools)
    if memory_instructions:
        parts.append("\n" + memory_instructions)

    return "\n".join(parts)
```

## Generated Output Format

### With All Memory Tools Registered

```
============================================================
MEMORY SYSTEM:
============================================================

1. TOOL USAGE MEMORY (Structured Workflow):
--------------------------------------------------

• BEFORE executing any tool (run_sql, visualize_data, or calculator),
  you MUST first call search_saved_correct_tool_uses with the user's
  question to check if there are existing successful patterns for
  similar questions.

• Review the search results (if any) to inform your approach before
  proceeding with other tool calls.

• AFTER successfully executing a tool that produces correct and useful
  results, you MUST call save_question_tool_args to save the successful
  pattern for future use.

Example workflow:
  • User asks a question
  • First: Call search_saved_correct_tool_uses(question="user's question")
  • Then: Execute the appropriate tool(s) based on search results and the question
  • Finally: If successful, call save_question_tool_args(question="user's question", tool_name="tool_used", args={the args you used})

Do NOT skip the search step, even if you think you know how to answer.
Do NOT forget to save successful executions.

The only exceptions to searching first are:
  • When the user is explicitly asking about the tools themselves (like "list the tools")
  • When the user is testing or asking you to demonstrate the save/search functionality itself

2. TEXT MEMORY (Domain Knowledge & Context):
--------------------------------------------------

• save_text_memory: Save important context about the database, schema, or domain

Use text memory to save:
  • Database schema details (column meanings, data types, relationships)
  • Company-specific terminology and definitions
  • Query patterns or best practices for this database
  • Domain knowledge about the business or data
  • User preferences for queries or visualizations

DO NOT save:
  • Information already captured in tool usage memory
  • One-time query results or temporary observations

Examples:
  • save_text_memory(content="The status column uses 1 for active, 0 for inactive")
  • save_text_memory(content="MRR means Monthly Recurring Revenue in our schema")
  • save_text_memory(content="Always exclude test accounts where email contains 'test'")
```

### With No Memory Tools

```
(empty string - no memory section added)
```

## Integration Examples

### DefaultSystemPromptBuilder

**Location:** `src/vanna/core/system_prompt/default.py:75-76`

```python
# Append memory workflow instructions (empty string if no memory tools)
memory_instructions = build_memory_workflow_instructions(tools)
if memory_instructions:
    prompt_parts.append("\n" + memory_instructions)
```

### DomainPromptBuilder

**Location:** `src/vanna/core/system_prompt/domain_prompt_builder.py:162-167`

```python
# Add memory workflow instructions if memory tools are registered.
# Without these, the LLM won't know to call search_saved_correct_tool_uses
# before execution or save_question_tool_args after success.
memory_instructions = build_memory_workflow_instructions(tools)
if memory_instructions:
    sections.append(memory_instructions)
```

## Best Practices

### For SystemPromptBuilder Implementors

**DO:**
- Always call `build_memory_workflow_instructions(tools)` in your `build_system_prompt()` method
- Check if the result is non-empty before appending (handles case with no memory tools)
- Import from `vanna.core.system_prompt.memory_instructions`

**DON'T:**
- Copy-paste the memory instruction generation logic
- Skip memory instructions in custom builders
- Modify the returned string (use it as-is)
- Generate your own memory instructions (reuse this function)

### For Framework Maintainers

**Updating Memory Instructions:**

When you need to change memory workflow instructions (new examples, clarified wording, additional guidelines):

1. Update ONLY `src/vanna/core/system_prompt/memory_instructions.py`
2. All builders using this function will automatically get the updates
3. No need to touch `DefaultSystemPromptBuilder` or `DomainPromptBuilder`

**This is the single source of truth for memory workflow instructions.**

## Testing

### Unit Test Example

```python
from vanna.core.system_prompt.memory_instructions import build_memory_workflow_instructions
from vanna.core.tool.models import ToolSchema

def test_memory_instructions_with_all_tools():
    tools = [
        ToolSchema(name="search_saved_correct_tool_uses", ...),
        ToolSchema(name="save_question_tool_args", ...),
        ToolSchema(name="save_text_memory", ...),
    ]
    result = build_memory_workflow_instructions(tools)

    assert "MEMORY SYSTEM" in result
    assert "TOOL USAGE MEMORY" in result
    assert "TEXT MEMORY" in result
    assert "search_saved_correct_tool_uses" in result

def test_memory_instructions_with_no_tools():
    tools = [
        ToolSchema(name="run_sql", ...),
        ToolSchema(name="visualize_data", ...),
    ]
    result = build_memory_workflow_instructions(tools)

    assert result == ""  # No memory tools, no instructions
```

## Related Documentation

- [Domain Prompt Builder](./domain-prompt-builder.md) - Uses this module for memory instructions
- [Memory Training Guide](./memory-training.md) - How to train and use agent memory
- [System Prompt Architecture](../../src/vanna/core/system_prompt/base.py) - Base interface for prompt builders

## Change History

- **2024-02** - Initial creation to eliminate duplication between `DefaultSystemPromptBuilder` and `DomainPromptBuilder`
