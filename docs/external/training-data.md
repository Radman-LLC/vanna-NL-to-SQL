# Training Vanna with Query Examples

Vanna learns from example queries to generate more accurate SQL. This guide explains how to add training data, manage memory, and improve query accuracy over time.

## What Is Training Data?

Training data consists of question-and-SQL pairs that teach Vanna how your database works. When a user asks a question, Vanna searches its memory for similar questions and uses matching examples to guide SQL generation. The more relevant examples you provide, the more accurate the generated SQL becomes.

## How Training Data Works

Vanna stores training examples in a vector database (such as ChromaDB). When a new question arrives, the system performs a similarity search across stored examples, retrieves the most relevant matches, and injects them into the prompt context. This gives the AI model proven patterns to follow when generating new SQL.

The process follows these steps:

1. You add question-and-SQL pairs to memory.
2. A user asks a question.
3. Vanna searches memory for similar questions.
4. The closest matches are included in the AI prompt.
5. The AI generates SQL informed by past successful queries.

## Setting Up Memory Storage

### Configure ChromaDB Memory

ChromaDB is the recommended vector store for training data:

```python
from vanna.integrations.chromadb import ChromaAgentMemory

# Create persistent memory storage
agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory"
)
```

The `persist_directory` parameter specifies where training data is stored on disk. Data persists across server restarts automatically.

### Connect Memory to Your Agent

Add memory and the context enhancer to your agent setup:

```python
from vanna import Agent, AgentConfig
from vanna.core.enhancer import DefaultLlmContextEnhancer

# Create memory-based context enhancer
memory_enhancer = DefaultLlmContextEnhancer(agent_memory)

# Create agent with memory
agent = Agent(
    config=AgentConfig(...),
    agent_memory=agent_memory,
    llm_context_enhancer=memory_enhancer,
    ...
)
```

## Adding Training Data

### Training Pair Format

Each training example includes the following fields:

- **question**: Natural language question (what users would ask).
- **sql**: Correct SQL query (properly formatted).
- **category**: Query type (for example, aggregation, lookup, financial).
- **notes**: Key SQL patterns, filters, or important details to highlight.

### Using the Training Library

Create training pairs in a structured format:

```python
TRAINING_PAIRS = [
    {
        "question": "What was our revenue last month?",
        "sql": """
            SELECT SUM(total) AS total_revenue
            FROM orders
            WHERE invoice_date >= DATE_FORMAT(
                DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
              AND invoice_date < DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND status NOT IN (1, 11)
        """,
        "category": "aggregation",
        "notes": "Use invoice_date for reporting. Exclude abandoned and cancelled orders."
    },
    {
        "question": "Which customers have the highest order totals?",
        "sql": """
            SELECT
                c.id AS customer_id,
                TRIM(CONCAT(c.fname, ' ', c.lname)) AS customer_name,
                COUNT(o.id) AS order_count,
                SUM(o.total) AS total_sales
            FROM orders o
            INNER JOIN customers c ON o.customer_id = c.id
            WHERE o.status NOT IN (1, 11)
            GROUP BY c.id, customer_name
            ORDER BY total_sales DESC
            LIMIT 20
        """,
        "category": "join_aggregation",
        "notes": "JOIN customers for name. Use TRIM to handle empty values."
    }
]
```

### Seeding Memory

After creating training pairs, seed them into memory:

```bash
python -m training.seed_agent_memory --clear --verify
```

**Important:** Use the `--clear` flag when re-seeding. The vector database does not automatically update existing entries, so clearing ensures a clean state.

The `--verify` flag confirms that all training pairs were stored correctly.

### Saving Queries During Chat

Users with administrator access can save successful queries directly from the chat interface. When a query produces correct results, an administrator can say "save this query" and the system will store the question-SQL pair in memory for future use.

Non-administrator users can search existing memory but cannot add new entries.

## Best Practices for Training Data

### Cover Key Query Categories

Include examples for each type of question your users ask:

- **Aggregation**: Totals, counts, averages, sums.
- **Lookups**: Finding specific records by identifier or name.
- **Time-based**: Queries filtered by date ranges.
- **JOINs**: Queries spanning multiple tables.
- **Financial**: Revenue, margins, balances, aging reports.
- **Inventory**: Stock levels, low stock alerts, warehouse queries.

### Write Realistic Questions

Use questions that reflect how real users phrase requests. Include variations:

- "What was our revenue last month?"
- "Show me total sales for January"
- "How much did we sell last quarter?"

### Include Important Filters

Ensure training examples demonstrate critical filtering patterns:

- Excluding test data or placeholder records
- Filtering by order status (excluding cancelled or abandoned)
- Handling soft-deleted records
- Date range best practices

### Start Small and Expand

Begin with 10 to 20 high-quality examples covering your most common queries. Expand as you identify gaps through query logging.

### Maintain Accuracy

Review training data periodically to ensure:

- SQL queries still produce correct results
- Table and column names match current schema
- Business logic reflects current definitions

## Improving Accuracy Over Time

### Use Query Logs

Export successful queries from your logs and review them for addition to training data:

```python
from vanna.core.lifecycle.query_logging_hook import export_successful_queries

export_successful_queries(
    log_file="./vanna_query_log.jsonl",
    output_file="./successful_queries.json"
)
```

Review exported queries before adding them to training data. Not all successful queries are good training examples. Select queries that represent common patterns.

### Monitor and Iterate

Follow this continuous improvement cycle:

1. **Log queries**: Capture all query activity with query logging.
2. **Analyze patterns**: Identify common failures and knowledge gaps.
3. **Add training data**: Create examples that address identified gaps.
4. **Re-seed memory**: Run the seeding script with the `--clear` flag.
5. **Monitor improvement**: Track success rate changes.
6. **Repeat**: Continuously refine.

### Schema Documentation

In addition to query examples, document your database schema to give Vanna comprehensive knowledge:

- Table purposes and relationships
- Column descriptions and data types
- Business logic for calculated fields
- Status values and their meanings

Store schema documentation alongside training pairs to provide full context.

## Troubleshooting

### No Similar Queries Found

**Symptom:** Vanna does not use training data patterns in generated SQL.

**Solutions:**
- Add more training pairs for that question category.
- Verify memory is properly configured and seeded.
- Check that the context enhancer is connected to the agent.

### Memory Not Persisting

**Symptom:** Training data is lost after server restart.

**Solutions:**
- Verify the `persist_directory` points to a valid location.
- Confirm the vector database package is installed correctly.
- Check file permissions on the storage directory.

### Poor SQL Quality Despite Training

**Symptom:** Generated SQL does not match training patterns.

**Solutions:**
- Add domain configuration to complement training data.
- Include more variations of similar questions.
- Verify training pairs contain correct SQL.
- Check that questions in training data match how users phrase requests.

## Related Topics

- [Configuring Vanna for Your Database](domain-configuration.md): Define business rules and conventions.
- [Query Logging and Analytics](query-logging.md): Track query patterns and identify gaps.
- [Getting Started with Vanna](getting-started.md): Initial setup and configuration.
