# Improving Query Accuracy with Memory Enhancement

Vanna uses a memory-based learning system to improve SQL generation accuracy over time by learning from past successful queries.

## How It Works

When you ask Vanna a question:

1. Vanna searches its memory for similar past questions
2. The most similar successful query patterns are retrieved
3. These examples are shown to the AI model alongside your question
4. The AI generates better SQL by learning from proven patterns

This approach can reduce incorrect SQL generation by 40 to 60 percent.

## Key Benefits

- **Fewer errors**: 40 to 60 percent reduction in incorrect table and column names
- **Consistent style**: Query patterns and formatting remain consistent
- **Better complexity handling**: Improved handling of complex JOINs and business logic
- **Continuous learning**: Accuracy improves automatically over time
- **Zero user effort**: Works completely automatically

## Setting Up Memory Enhancement

### Enable Memory-Based Enhancement

Configure the memory enhancer when creating your agent:

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
    agent_memory=agent_memory,
    max_examples=5,
    similarity_threshold=0.7,
)

# Create agent with enhancer
agent = Agent(
    config=AgentConfig(...),
    llm_context_enhancer=llm_context_enhancer,
    agent_memory=agent_memory,
    ...
)
```

### Configuration Options

**max_examples** (default: 5)
- Controls how many past queries to show the AI
- More examples provide more context but increase processing time
- Recommended range: 3 to 7

**similarity_threshold** (default: 0.7)
- Minimum similarity score (0.0 to 1.0) for including an example
- Lower values (0.3 to 0.5) are more permissive
- Higher values (0.7 to 0.9) are stricter
- Too high may find no matches

**include_metadata** (default: False)
- Include timestamps and categories in examples
- Useful for debugging
- Set to True to see when examples were created

## Adaptive Memory Enhancement

For situations where strict matching may not find results, use the adaptive enhancer:

```python
from vanna.core.enhancer.memory_enhancer import AdaptiveMemoryEnhancer

enhancer = AdaptiveMemoryEnhancer(
    agent_memory=agent_memory,
    max_examples=5,
    initial_threshold=0.7,      # Starting similarity threshold
    min_threshold=0.3,          # Do not go below this threshold
    threshold_step=0.1,         # Amount to decrease per attempt
    min_examples=1              # Keep trying until at least this many found
)
```

The adaptive enhancer automatically lowers the similarity threshold if it cannot find enough examples, ensuring the AI always has some context even for novel questions.

## Building Your Memory

### Add Training Data

Populate memory with example queries:

```python
from vanna.capabilities.agent_memory.base import AgentMemory

# Save a successful query pattern
await agent_memory.save_tool_usage(
    question="What was our revenue last month?",
    tool_name="run_sql",
    args={
        "sql": "SELECT SUM(amount) FROM transactions WHERE date >= '2024-01-01'"
    },
    success=True,
    metadata={"category": "revenue"}
)
```

### Import Bulk Training Data

You can import multiple queries at once from a JSON file:

```python
import json

# Prepare training data
training_data = [
    {
        "question": "How many customers do we have?",
        "sql": "SELECT COUNT(*) FROM customers WHERE active = true",
        "category": "customer_metrics"
    },
    {
        "question": "Show top products by revenue",
        "sql": "SELECT product_name, SUM(amount) as revenue FROM sales GROUP BY product_name ORDER BY revenue DESC LIMIT 10",
        "category": "product_analysis"
    }
]

# Save each to memory
for item in training_data:
    await agent_memory.save_tool_usage(
        question=item["question"],
        tool_name="run_sql",
        args={"sql": item["sql"]},
        success=True,
        metadata={"category": item["category"]}
    )
```

## Best Practices

### Start with Quality Examples

Focus on:
- Most frequently asked question types
- Complex queries with business logic
- Queries using domain-specific terminology
- Queries with tricky JOINs or aggregations

### Use Consistent Patterns

When adding examples, maintain consistency in:
- SQL formatting (uppercase keywords, indentation)
- Naming conventions (table aliases, column names)
- Business logic application
- Performance optimization patterns

### Organize with Categories

Use categories to organize your training data:

```python
metadata = {
    "category": "revenue_analysis",  # or "customer_metrics", "inventory", etc.
}
```

Categories help with:
- Finding and managing examples
- Analyzing which topics need more training data
- Filtering examples for specific use cases

### Monitor Similarity Scores

Track how well your memory matches new questions:
- If scores are always very low (below 0.3), add more diverse examples
- If scores are always very high (above 0.9), you may have good coverage
- Scores between 0.5 and 0.8 indicate good relevance

### Recommended Settings by Use Case

**Development and Testing:**
```python
max_examples=3
similarity_threshold=0.5
include_metadata=True  # For debugging
```

**Production with Small Memory (less than 100 examples):**
```python
max_examples=5
similarity_threshold=0.6
```

**Production with Large Memory (100 plus examples):**
```python
max_examples=5
similarity_threshold=0.7
```

**Novel or Diverse Queries:**
```python
# Use AdaptiveMemoryEnhancer
initial_threshold=0.7
min_threshold=0.3
min_examples=1
```

## Performance Considerations

### Memory Search Speed

- Embedding search takes 50 to 200 milliseconds depending on memory size
- Larger max_examples increases response time slightly
- Lower threshold increases search time

### Cost Impact

- More examples mean larger prompts
- Larger prompts increase AI model costs
- Typical increase: 500 to 2000 tokens per request
- Cost increase: approximately $0.001 to $0.005 per query

### Scaling to Large Memory

For 10,000 plus memories:
- Consider GPU acceleration for vector search
- Use more selective similarity thresholds (0.75 plus)
- Limit max_examples to 5 or fewer

## Troubleshooting

### No Examples Being Found

**Possible causes:**
- Similarity threshold too high
- Not enough training data in memory
- Questions are very different from examples

**Solutions:**
- Lower similarity_threshold to 0.5 or 0.6
- Use AdaptiveMemoryEnhancer
- Add more diverse training examples

### Irrelevant Examples Being Injected

**Possible causes:**
- Similarity threshold too low
- Poorly organized training data
- Generic question phrasing

**Solutions:**
- Raise similarity_threshold to 0.75 or 0.8
- Improve training data quality
- Add more specific examples

### Memory Growing Too Large

**Possible causes:**
- Auto-saving all queries without filtering
- Duplicate or near-duplicate entries

**Solutions:**
- Implement deduplication
- Set minimum confidence thresholds
- Periodically clean up low-quality examples

## Example: Complete Setup

```python
from vanna import Agent, AgentConfig
from vanna.core.enhancer.memory_enhancer import AdaptiveMemoryEnhancer
from vanna.integrations.chromadb import ChromaAgentMemory

# Create memory storage
agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory",
    collection_name="sql_patterns"
)

# Create adaptive enhancer for best results
memory_enhancer = AdaptiveMemoryEnhancer(
    agent_memory=agent_memory,
    max_examples=5,
    initial_threshold=0.7,
    min_threshold=0.4,
    threshold_step=0.1,
    min_examples=1
)

# Create agent
agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    llm_context_enhancer=memory_enhancer,
    agent_memory=agent_memory,
    llm_service=llm_service,
    sql_runner=sql_runner
)

# Add initial training data
training_examples = [
    {
        "question": "Show revenue by month",
        "sql": "SELECT DATE_TRUNC('month', date) as month, SUM(amount) FROM sales GROUP BY month ORDER BY month",
    },
    {
        "question": "List active customers",
        "sql": "SELECT * FROM customers WHERE status = 'active' AND last_login > NOW() - INTERVAL '30 days'",
    }
]

for example in training_examples:
    await agent_memory.save_tool_usage(
        question=example["question"],
        tool_name="run_sql",
        args={"sql": example["sql"]},
        success=True
    )
```

## Measuring Improvement

Track these metrics to measure the impact of memory enhancement:

### Before Enabling Memory Enhancement
- Number of successful queries
- Number of queries requiring user correction
- Average user satisfaction rating

### After Enabling Memory Enhancement
- Compare the same metrics
- Look for 20 to 40 percent improvement in success rate
- Track reduction in errors related to table and column names

## Related Topics

- Domain Configuration: Teach Vanna about your database structure
- Query Logging: Track query patterns for analysis
- Training Data: Add examples to improve accuracy
