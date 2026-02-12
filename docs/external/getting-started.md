# Getting Started with Vanna

Vanna is a framework that converts natural language questions into SQL queries. This guide will help you get started with Vanna and customize it for your database.

## What Is Vanna?

Vanna uses AI to translate questions like "What was our revenue last month?" into accurate SQL queries. It learns from your database structure, business rules, and past successful queries to generate SQL that matches your needs.

## Quick Start

### Installation

Install Vanna with all dependencies:

```bash
pip install vanna[all]
```

For specific database support:

```bash
# MySQL
pip install vanna[mysql]

# PostgreSQL
pip install vanna[postgres]

# Snowflake
pip install vanna[snowflake]
```

### Basic Setup

Create a simple agent to start querying:

```python
from vanna import Agent, AgentConfig
from vanna.integrations.anthropic import ClaudeLlmService
from vanna.integrations.mysql import MySQLRunner

# Configure your database connection
sql_runner = MySQLRunner(
    host="localhost",
    database="mydb",
    user="user",
    password="password"
)

# Configure the AI model
llm_service = ClaudeLlmService(
    api_key="your-api-key",
    model="claude-sonnet-4-5"
)

# Create the agent
agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    llm_service=llm_service,
    sql_runner=sql_runner
)

# Ask a question
response = await agent.send_message("How many customers do we have?")
```

## Customizing Vanna

### Step 1: Configure Your Database

Create a `domain_config.py` file to teach Vanna about your database:

```python
# domain_config.py

DATABASE_INFO = {
    "type": "MySQL 8.0",
    "purpose": "E-commerce transaction database"
}

BUSINESS_DEFINITIONS = {
    "active_customer": "Customer with order in last 30 days",
    "churn": "Customer with no orders in last 90 days",
}

SQL_PATTERNS = [
    "Use UPPERCASE for SQL keywords",
    "Always filter test data: WHERE is_test = FALSE",
]

PERFORMANCE_HINTS = [
    "orders table is indexed on customer_id and date",
]

DATA_QUALITY_NOTES = [
    "Soft deletes: deleted_at IS NOT NULL means deleted",
]
```

**Learn more:** [Configuring Vanna for Your Database](domain-configuration.md)

### Step 2: Add Training Examples

Help Vanna learn by adding example queries:

```python
from vanna.integrations.chromadb import ChromaAgentMemory

# Create memory storage
agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory"
)

# Add training examples
await agent_memory.save_tool_usage(
    question="What was our revenue last month?",
    tool_name="run_sql",
    args={
        "sql": "SELECT SUM(amount) FROM transactions WHERE date >= '2024-01-01'"
    },
    success=True
)
```

**Learn more:** [Improving Query Accuracy](improving-query-accuracy.md)

### Step 3: Enable Query Logging

Track query patterns and identify areas for improvement:

```python
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook

# Create logger
query_logger = QueryLoggingHook(
    log_file="./vanna_query_log.jsonl"
)

# Add to agent
agent = Agent(
    config=AgentConfig(...),
    lifecycle_hooks=[query_logger],
    ...
)
```

**Learn more:** [Query Logging and Analytics](query-logging.md)

## Understanding Vanna Architecture

Vanna uses a modular architecture:

### Core Components

**Agent**
- Main orchestrator
- Manages conversation flow
- Coordinates tool execution

**LLM Service**
- AI model integration (Claude, OpenAI, etc.)
- Generates SQL from natural language
- Supports streaming responses

**SQL Runner**
- Database execution interface
- Runs generated SQL
- Returns results

**Agent Memory**
- Stores successful query patterns
- Enables learning from past queries
- Uses vector search for similarity matching

**Tool Registry**
- Manages available tools
- Validates permissions
- Executes tools safely

### Request Flow

```
User Question
    → Agent receives question
    → Agent searches memory for similar questions
    → Agent enhances prompt with examples
    → LLM Service generates SQL
    → Tool Registry validates permissions
    → SQL Runner executes query
    → Results returned to user
```

## Common Use Cases

### Business Analytics

Ask business questions in natural language:

- "What was our revenue last quarter?"
- "Show top 10 customers by order count"
- "What is our average order value?"

### Data Exploration

Explore data without writing SQL:

- "How many products do we have?"
- "List all active customers"
- "Show me recent orders"

### Report Generation

Generate reports automatically:

- "Create a monthly sales report"
- "Show inventory levels by warehouse"
- "List overdue invoices"

## Best Practices

### Start Small

Begin with:
- Basic database configuration
- 5 to 10 training examples
- Simple queries

Then expand as you identify needs.

### Iterate and Improve

1. **Monitor**: Use query logging to track patterns
2. **Analyze**: Identify common failures
3. **Improve**: Add training data and configuration
4. **Measure**: Track success rate improvements

### Keep Configuration Current

Update your domain configuration when:
- Database schema changes
- New tables or columns are added
- Business definitions evolve
- Performance characteristics change

### Use Clear Questions

Better questions lead to better SQL:

**Good:**
- "Show revenue by month for 2024"
- "List customers with more than 10 orders"
- "What is the average order value?"

**Less Clear:**
- "Show me stuff"
- "Get the numbers"
- "Check the data"

## Security Considerations

### Read-Only Access

For most use cases, use read-only database access:

```python
from vanna.integrations.mysql import ReadOnlyMySQLRunner

# Read-only runner prevents data modification
sql_runner = ReadOnlyMySQLRunner(
    host="localhost",
    database="mydb",
    user="readonly_user",
    password="password"
)
```

### User Permissions

Implement user-based access control:

```python
from vanna.core.user import User

# Define user with specific groups
user = User(
    user_id="user123",
    user_email="user@example.com",
    user_groups=["sales", "analytics"]
)

# Tools can be restricted to specific groups
```

### Validate Generated SQL

Always review generated SQL before execution in production:
- Check for unintended data access
- Verify query performance
- Confirm business logic correctness

## Troubleshooting

### Incorrect SQL Generated

**Possible causes:**
- Insufficient training data
- Missing domain configuration
- Ambiguous question

**Solutions:**
- Add more training examples
- Configure business definitions
- Ask more specific questions

### Slow Query Performance

**Possible causes:**
- Missing indexes
- Large date ranges without filters
- Complex JOINs

**Solutions:**
- Add performance hints to domain configuration
- Optimize database indexes
- Ask more specific questions with filters

### Connection Errors

**Possible causes:**
- Incorrect database credentials
- Network issues
- Database not running

**Solutions:**
- Verify connection parameters
- Check network connectivity
- Confirm database is accessible

## Next Steps

### Learn More

- **[Domain Configuration](domain-configuration.md)**: Customize Vanna for your database
- **[Improving Query Accuracy](improving-query-accuracy.md)**: Use memory enhancement
- **[Query Logging](query-logging.md)**: Track and analyze query patterns

### Explore Advanced Features

- **Lifecycle Hooks**: Customize behavior at each stage
- **Custom Tools**: Add new capabilities beyond SQL
- **Multi-Database Support**: Query multiple databases
- **Streaming Responses**: Real-time query results

### Get Support

- **Documentation**: Comprehensive guides and API reference
- **Community**: Join discussions and share experiences
- **Issues**: Report bugs and request features

## Example: Complete Setup

```python
from vanna import Agent, AgentConfig
from vanna.integrations.anthropic import ClaudeLlmService
from vanna.integrations.mysql import ReadOnlyMySQLRunner
from vanna.integrations.chromadb import ChromaAgentMemory
from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder
from vanna.core.system_prompt import READ_ONLY_SYSTEM_PROMPT
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook
from vanna.core.enhancer import DefaultLlmContextEnhancer
import domain_config

# Database connection
sql_runner = ReadOnlyMySQLRunner(
    host="localhost",
    database="mydb",
    user="readonly_user",
    password="password"
)

# AI model
llm_service = ClaudeLlmService(
    api_key="your-api-key",
    model="claude-sonnet-4-5"
)

# Memory storage
agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory"
)

# Domain configuration
prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,
    database_type=domain_config.DATABASE_INFO["type"],
    database_purpose=domain_config.DATABASE_INFO["purpose"],
    business_definitions=domain_config.BUSINESS_DEFINITIONS,
    sql_patterns=domain_config.SQL_PATTERNS,
    performance_hints=domain_config.PERFORMANCE_HINTS,
    data_quality_notes=domain_config.DATA_QUALITY_NOTES,
)

# Memory enhancement
memory_enhancer = DefaultLlmContextEnhancer(agent_memory)

# Query logging
query_logger = QueryLoggingHook(
    log_file="./vanna_query_log.jsonl"
)

# Create agent
agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    llm_service=llm_service,
    sql_runner=sql_runner,
    agent_memory=agent_memory,
    system_prompt_builder=prompt_builder,
    llm_context_enhancer=memory_enhancer,
    lifecycle_hooks=[query_logger]
)

# Ready to use!
response = await agent.send_message("What was our revenue last month?")
```

This setup includes:
- Read-only database access
- Domain configuration for your database
- Memory-based learning
- Query logging for analytics
- Full customization capabilities
