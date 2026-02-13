# Training Data for Vanna Agent Memory

This directory contains training data and utilities for optimizing your Vanna agent's SQL generation accuracy.

## Files

- **`schema_documentation_template.md`** - Template for documenting your database schema, tables, relationships, and business logic
- **`sample_query_library.py`** - Collection of high-quality question-SQL training pairs
- **`seed_agent_memory.py`** - Script to populate ChromaDB agent memory with training data

## Quick Start

### 1. Customize Your Training Data

**Fill out the schema documentation:**
```bash
# Edit the template with your database details
notepad training/schema_documentation_template.md
```

Include:
- Table descriptions and relationships
- Key columns and indexes
- Business definitions (churn, active customer, etc.)
- SQL best practices for your database

**Add training pairs:**
```bash
# Edit the sample query library
notepad training/sample_query_library.py
```

Add 20-30 realistic question-SQL pairs covering:
- Simple lookups and filters
- Aggregations (COUNT, SUM, AVG)
- JOINs across multiple tables
- Time-based queries
- Business metrics calculations

### 2. Seed the Agent Memory

```bash
# First-time setup (clears existing data)
python -m training.seed_agent_memory --clear --verify

# Update with new training data (preserves existing)
python -m training.seed_agent_memory --verify
```

### 3. Verify the Data

The `--verify` flag will search the memory to confirm data was saved correctly:

```bash
python -m training.seed_agent_memory --verify
```

## Advanced Usage

### Custom Memory Directory

```bash
python -m training.seed_agent_memory --memory-dir ./custom_memory --collection my_queries
```

### Custom Schema Documentation

```bash
python -m training.seed_agent_memory --schema-doc ./my_custom_schema.md
```

### Custom Training Pairs

```bash
python -m training.seed_agent_memory --training-pairs ./my_custom_queries.py
```

## Training Pair Guidelines

Good training pairs should:

1. **Be realistic** - Use questions your actual users will ask
2. **Cover diverse patterns** - Simple queries, complex JOINs, aggregations, etc.
3. **Include edge cases** - Date boundaries, NULL handling, test data filtering
4. **Use your schema** - Reference actual table/column names from your database
5. **Be tested** - Verify each SQL query returns correct results

### Example Training Pair

```python
{
    "question": "What was our revenue last month?",
    "sql": """
        SELECT SUM(amount) as revenue
        FROM transactions
        WHERE transaction_date >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m-01')
          AND transaction_date < DATE_FORMAT(NOW(), '%Y-%m-01')
          AND is_test = FALSE
          AND status = 'completed'
    """,
    "category": "time_based",
    "notes": "Uses date functions to get exact month boundaries"
}
```

## Categories to Cover

Your training pairs should span these categories:

- **schema_exploration** - SHOW TABLES, DESCRIBE, metadata queries
- **simple_lookup** - Basic SELECT with WHERE and ORDER BY
- **simple_aggregation** - COUNT, SUM, AVG, MIN, MAX
- **group_by** - GROUP BY with aggregations and HAVING
- **time_based** - Date/time filtering and calculations
- **time_series** - Queries grouped by date/month/year
- **join_aggregation** - JOINs with GROUP BY
- **multi_join** - Queries spanning 3+ tables
- **business_metric** - Domain-specific calculations (churn, ARPU, etc.)
- **filtering** - Complex WHERE clauses with multiple conditions
- **complex** - Advanced queries with subqueries, CTEs, CASE statements

## Memory Types

AgentMemory supports two distinct memory types:

### ToolMemory (Structured)
Stores structured tool usage patterns with question, tool_name, arguments, success status, and timestamp. Created via `save_tool_usage()`. Used for tracking which tools were called and with what arguments for a given question.

### TextMemory (Free-form)
Stores free-form text content (schema documentation, business rules, SQL patterns). Created via `save_text_memory()`. This is what the seeding script uses to store schema documentation and training pair context.

**Key difference:** ToolMemory tracks structured tool executions. TextMemory stores knowledge that the `DefaultLlmContextEnhancer` searches for RAG-based context injection.

## How Memory Improves Accuracy

When you ask a question, the agent uses **two complementary mechanisms**:

### 1. System Prompt Enhancement (DefaultLlmContextEnhancer)
The `DefaultLlmContextEnhancer` (`src/vanna/core/enhancer/default.py`) runs before each LLM call:

1. **Searches TextMemory** for relevant content using semantic similarity (`search_text_memories()`)
2. **Retrieves top 5 matches** from ChromaDB
3. **Appends context** to the system prompt under "Relevant Context from Memory"
4. **LLM sees domain knowledge** alongside the user's question

This is automatic when the agent has an `llm_context_enhancer` configured (which it is by default via `DefaultLlmContextEnhancer(agent_memory)`).

### 2. Memory Tool Workflow (Agent Memory Tools)
When memory tools are registered, the LLM can also:

1. **Call `search_saved_correct_tool_uses`** to find similar past queries with their SQL
2. **Use those patterns** to inform its SQL generation
3. **Call `save_question_tool_args`** after successful execution to save the pattern for future use

This provides both automatic (enhancer) and explicit (tool-based) memory retrieval.

### Combined Effect
Together, these dramatically reduce:
- Hallucinated table/column names
- Incorrect JOIN patterns
- Missing business logic filters (is_test = FALSE, etc.)
- Date/time calculation errors

## Continuous Improvement

After initial seeding, continue growing your memory:

1. **Use the web UI** to ask questions and generate queries
2. **When a query is correct**, say "save this query" (if memory tools are enabled)
3. **Periodically export** successful queries and add to training library
4. **Re-run seed script** to update the memory with new patterns

## Monitoring Memory Growth

Check memory contents:

```python
# In Python REPL or script
from vanna.integrations.chromadb import ChromaAgentMemory
from vanna.core.tool import ToolContext
from vanna.core.user import User

memory = ChromaAgentMemory(persist_directory="./vanna_memory")
user = User(id="admin", group_memberships=["admin"])
context = ToolContext(user=user, conversation_id="check", request_id="1")

# Get recent memories
recent = await memory.get_recent_memories(context, limit=10)
print(f"Total memories: {len(recent)}")
```

## Troubleshooting

### "No module named 'chromadb'"
Install ChromaDB:
```bash
pip install chromadb
```

### "Schema documentation not found"
Make sure you're running from the project root:
```bash
python -m training.seed_agent_memory
```

### Memory not persisting
Check that the directory is writable:
```bash
ls -la vanna_memory/
```

### Poor search results
- Increase training pairs (aim for 30-50)
- Use more diverse question phrasings
- Lower similarity_threshold in searches

## AgentMemory ABC Reference

The `AgentMemory` abstract base class (`src/vanna/capabilities/agent_memory/base.py`) defines these core methods:

| Method | Purpose |
|--------|---------|
| `save_tool_usage()` | Save structured tool usage pattern (question + tool + args + success) |
| `save_text_memory()` | Save free-form text content (schema docs, business rules) |
| `search_similar_usage()` | Search for similar tool usage patterns by semantic similarity |
| `search_text_memories()` | Search for similar text memories by semantic similarity |
| `get_recent_memories()` | Get recent tool usage patterns |
| `get_recent_text_memories()` | Get recent text memories |
| `delete_by_id()` | Delete a specific tool memory |
| `delete_text_memory()` | Delete a specific text memory |
| `clear_memories()` | Bulk delete memories (optionally filtered by tool_name or date) |

**Implementations:** ChromaDB (`src/vanna/integrations/chromadb/`), Qdrant, FAISS, Pinecone, Weaviate, Milvus, Marqo, OpenSearch, Azure Search.

## Related Documentation

- `docs/internal/configuration/domain-config-guide.md` - Domain configuration for system prompts
- `docs/internal/configuration/domain-prompt-builder.md` - System prompt builder with domain knowledge
- `docs/internal/operations/query-logging-hook.md` - Query logging for monitoring and training data export
- `src/vanna/core/enhancer/default.py` - DefaultLlmContextEnhancer implementation

## Next Steps

After seeding your memory:

1. Start the web UI: `python run_web_ui.py`
2. Ask test questions and verify SQL quality
3. Add more training pairs for any gaps you find
4. Consider enabling GPU acceleration for faster embeddings (see `examples/chromadb_gpu_example.py`)
