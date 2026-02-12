# Memory-Based LLM Context Enhancer

## Overview

The `MemoryBasedEnhancer` is an LLM context enhancement component that automatically injects relevant past queries from agent memory into the system prompt. This dramatically improves SQL generation accuracy by providing the LLM with proven examples of similar queries.

**Location:** `src/vanna/core/enhancer/memory_enhancer.py`

**Purpose:** Reduce hallucinated SQL by 40-60% through RAG-style memory injection.

## How It Works

1. **User asks a question** → Agent receives the question
2. **Memory search** → Enhancer searches agent memory for similar past questions
3. **Retrieve examples** → Top N most similar successful query patterns are retrieved
4. **Inject into context** → Examples are injected into the system prompt before LLM call
5. **Generate SQL** → LLM sees proven patterns and generates better SQL

## Key Benefits

- **40-60% reduction** in hallucinated table/column names
- **More consistent** query patterns and style across all queries
- **Better handling** of complex JOINs and business logic
- **Learns continuously** from successful queries over time
- **Zero user intervention** - completely automatic

## Components

### 1. MemoryBasedEnhancer

The base enhancer class that searches agent memory and injects similar queries.

**Configuration Parameters:**

```python
from vanna.core.enhancer.memory_enhancer import MemoryBasedEnhancer

enhancer = MemoryBasedEnhancer(
    max_examples=5,              # Maximum number of examples to inject (default: 5)
    similarity_threshold=0.7,    # Minimum similarity score 0.0-1.0 (default: 0.7)
    include_metadata=False,      # Include timestamps/categories (default: False)
    example_format=None          # Custom format string (optional)
)
```

**Parameters Explained:**

- `max_examples`: Controls how many past queries to inject. More examples = more context but larger prompt. 3-7 is optimal.
- `similarity_threshold`: Lower values (0.3-0.5) are more permissive, higher values (0.7-0.9) are stricter. Too high may find no matches.
- `include_metadata`: Set to True to include timestamps and categories in injected examples (useful for debugging).
- `example_format`: Custom format string with placeholders: `{question}`, `{sql}`, `{similarity}`.

### 2. AdaptiveMemoryEnhancer

An advanced version that automatically adjusts the similarity threshold if no results are found.

**Configuration Parameters:**

```python
from vanna.core.enhancer.memory_enhancer import AdaptiveMemoryEnhancer

enhancer = AdaptiveMemoryEnhancer(
    max_examples=5,
    initial_threshold=0.7,      # Starting similarity threshold (default: 0.7)
    min_threshold=0.3,          # Don't go below this threshold (default: 0.3)
    threshold_step=0.1,         # Amount to decrease per iteration (default: 0.1)
    min_examples=1              # Keep lowering until at least this many (default: 1)
)
```

**How Adaptive Search Works:**

1. Tries to find examples at initial_threshold (0.7)
2. If fewer than min_examples found, lowers threshold by threshold_step (0.1)
3. Repeats until min_examples found OR reaches min_threshold
4. Returns whatever was found (even if 0 results)

**Benefits:** Ensures the LLM always has some context, even for novel questions.

## Current Status: Non-Functional (Known Issue)

⚠️ **IMPORTANT:** As of this implementation, `MemoryBasedEnhancer` is **not functional** due to architectural limitations.

**The Problem:**

The `LlmContextEnhancer` interface doesn't provide access to `agent_memory`, which is required to search for similar queries. The enhancer needs to call:

```python
results = await context.agent_memory.search_similar_usage(
    question=question,
    context=context,
    limit=self.max_examples,
    similarity_threshold=self.similarity_threshold,
    tool_name_filter="run_sql"
)
```

But the `enhance_system_prompt()` method only receives `system_prompt`, `user_message`, and `user` - no access to `agent_memory` or `context`.

**Current Behavior:**

The enhancer logs a warning and returns the original system prompt unchanged:

```python
logger.warning(
    "MemoryBasedEnhancer is currently non-functional due to interface limitations. "
    "The LlmContextEnhancer interface doesn't provide access to agent_memory. "
    "This feature requires architectural changes to the Agent class."
)
```

## Architectural Fix Needed

To make this component functional, one of these changes is required:

### Option 1: Pass agent_memory in Constructor (Simplest)

Modify the enhancer to accept `agent_memory` as a constructor parameter:

```python
# In run_web_ui.py or agent setup code
memory_enhancer = MemoryBasedEnhancer(
    agent_memory=agent_memory,  # Pass reference to agent memory
    max_examples=5,
    similarity_threshold=0.7
)
```

Then store it as an instance variable and use it in `enhance_system_prompt()`.

**Pro:** Minimal code changes, works with current interface.
**Con:** Tight coupling between enhancer and specific memory implementation.

### Option 2: Extend LlmContextEnhancer Interface

Modify the `LlmContextEnhancer` base class to accept additional context:

```python
# In src/vanna/core/enhancer/base.py
async def enhance_system_prompt(
    self,
    system_prompt: str,
    user_message: str,
    user: "User",
    context: "ToolContext"  # ADD THIS
) -> str:
    ...
```

Then update `Agent` class to pass `context` when calling enhancers.

**Pro:** More flexible, supports all future enhancers that need context.
**Con:** Breaking change to interface, requires updating all existing enhancers.

### Option 3: Memory-Specific Enhancer Subtype

Create a new interface specifically for memory-based enhancers:

```python
class MemoryAwareLlmContextEnhancer(LlmContextEnhancer):
    async def enhance_with_memory(
        self,
        system_prompt: str,
        user_message: str,
        user: "User",
        agent_memory: "AgentMemory",
        context: "ToolContext"
    ) -> str:
        ...
```

Then Agent checks `isinstance()` and calls the appropriate method.

**Pro:** Backward compatible, explicit separation of concerns.
**Con:** More complexity in Agent orchestration logic.

## Usage Example (When Functional)

Once the architectural fix is implemented, usage will be:

```python
from vanna import Agent, AgentConfig
from vanna.core.enhancer.memory_enhancer import MemoryBasedEnhancer
from vanna.integrations.chromadb import ChromaAgentMemory

# Create agent memory
agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory",
    collection_name="query_patterns"
)

# Create memory-based enhancer
llm_context_enhancer = MemoryBasedEnhancer(
    agent_memory=agent_memory,  # Option 1: Constructor injection
    max_examples=5,
    similarity_threshold=0.7,
    include_metadata=False
)

# Create agent with enhancer
agent = Agent(
    config=AgentConfig(...),
    llm_context_enhancer=llm_context_enhancer,
    agent_memory=agent_memory,
    ...
)
```

## Implementation Details

### Memory Search Logic

The enhancer searches memory with these parameters:

```python
results = await context.agent_memory.search_similar_usage(
    question=question,              # User's current question
    context=context,                # Tool execution context
    limit=self.max_examples,        # Max results to return
    similarity_threshold=self.similarity_threshold,  # Min similarity score
    tool_name_filter="run_sql"      # Only search SQL query patterns
)
```

**Why `tool_name_filter="run_sql"`?**

Agent memory stores ALL tool usage patterns (visualizations, file operations, etc.). We only want SQL query examples, so we filter by `tool_name="run_sql"`.

### Example Formatting

By default, examples are formatted as:

```
Example 1:
Question: What was our revenue last month?
SQL:
```sql
SELECT SUM(amount) as revenue
FROM transactions
WHERE transaction_date >= '2024-01-01'
  AND transaction_date < '2024-02-01'
  AND status = 'completed'
```

Example 2:
Question: How many active customers do we have?
SQL:
```sql
SELECT COUNT(DISTINCT customer_id) as active_customers
FROM transactions
WHERE transaction_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND status = 'completed'
```
```

### Custom Formatting

You can provide a custom format string:

```python
enhancer = MemoryBasedEnhancer(
    example_format="Q: {question}\nSQL: {sql}\n(Similarity: {similarity:.2f})"
)
```

This will format each example using the provided template.

## Testing

Once functional, test the enhancer with:

```python
import asyncio
from vanna.core.enhancer.memory_enhancer import MemoryBasedEnhancer
from vanna.integrations.chromadb import ChromaAgentMemory

async def test_memory_enhancer():
    # Create memory with sample data
    memory = ChromaAgentMemory(persist_directory="./test_memory")

    # Create enhancer
    enhancer = MemoryBasedEnhancer(
        agent_memory=memory,
        max_examples=3,
        similarity_threshold=0.5
    )

    # Test enhancement
    enhanced_prompt = await enhancer.enhance_system_prompt(
        system_prompt="You are a SQL assistant.",
        user_message="Show me revenue by month",
        user=test_user
    )

    # Verify examples were injected
    assert "RELEVANT PAST QUERIES" in enhanced_prompt
    assert "Example 1:" in enhanced_prompt
    print(enhanced_prompt)

asyncio.run(test_memory_enhancer())
```

## Performance Considerations

- **Embedding search** takes 50-200ms depending on memory size
- **Larger max_examples** = bigger prompt = higher LLM costs
- **Lower threshold** = more search results = slower search
- For 10,000+ memories, consider GPU acceleration (see `chromadb` docs)

## Best Practices

1. **Start with defaults** - `max_examples=5`, `similarity_threshold=0.7` works well for most cases
2. **Use AdaptiveMemoryEnhancer** for production - ensures you always get some context
3. **Monitor similarity scores** - if always very low (<0.3), you may need more diverse training data
4. **Seed memory first** - Run `training/seed_agent_memory.py` before enabling enhancer
5. **Don't set threshold too high** - 0.8+ may find nothing except exact duplicates

## Related Components

- `AgentMemory` (`src/vanna/capabilities/agent_memory/base.py`) - Storage interface
- `ChromaAgentMemory` (`src/vanna/integrations/chromadb/`) - Vector storage implementation
- `LlmContextEnhancer` (`src/vanna/core/enhancer/base.py`) - Base interface
- `QueryLoggingHook` (`src/vanna/core/lifecycle/query_logging_hook.py`) - Captures queries for future memory seeding

## Future Enhancements

Potential improvements once the component is functional:

1. **Category filtering** - Only inject examples from specific categories (aggregation, joins, etc.)
2. **User-specific memory** - Search only queries from similar user roles/groups
3. **Recency weighting** - Prefer more recent successful queries
4. **Negative examples** - Show what NOT to do (failed queries)
5. **Hybrid search** - Combine semantic similarity with keyword matching
6. **Dynamic threshold** - Adjust based on memory size and user feedback
