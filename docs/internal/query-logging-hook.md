# Query Logging Lifecycle Hook

## Overview

The `QueryLoggingHook` is a lifecycle hook that tracks all SQL queries, user interactions, and tool executions for monitoring, analytics, and continuous improvement. It writes structured logs to a file in JSON Lines format for easy parsing and analysis.

**Location:** `src/vanna/core/lifecycle/query_logging_hook.py`

**Purpose:** Monitor query patterns, identify failures, and build analytics dashboards for usage insights.

## Key Features

- **Comprehensive Logging** - Captures user info, questions, SQL, success/failure, errors, timestamps
- **JSON Lines Format** - One JSON object per line for easy parsing with jq, pandas, log aggregators
- **Selective Logging** - Can log all tools or just SQL queries
- **Minimal Overhead** - Asynchronous writes, no impact on query performance
- **Built-in Analytics** - Utility functions for log analysis and export

## What Gets Logged

Each log entry captures:

- **Timestamp** - ISO 8601 format (UTC)
- **Tool name** - Which tool was executed (`run_sql`, `visualize_data`, etc.)
- **Success status** - Boolean indicating if execution succeeded
- **Tool arguments** - Full arguments passed to the tool (includes SQL for `run_sql`)
- **Error messages** - Detailed error if execution failed
- **Result preview** - Optional first 100 characters of result (if enabled)

### Example Log Entry

```json
{
  "timestamp": "2024-02-12T14:23:45.123456",
  "tool_name": "run_sql",
  "success": true,
  "arguments": {
    "sql": "SELECT COUNT(*) as total FROM orders WHERE status = 'completed'"
  }
}
```

### Example Failed Query Log

```json
{
  "timestamp": "2024-02-12T14:25:30.789012",
  "tool_name": "run_sql",
  "success": false,
  "arguments": {
    "sql": "SELECT * FROM nonexistent_table"
  },
  "error": "Table 'nonexistent_table' doesn't exist"
}
```

## Components

### 1. QueryLoggingHook

The base logging hook that writes to a JSON Lines file.

**Configuration:**

```python
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook

query_logger = QueryLoggingHook(
    log_file="./vanna_query_log.jsonl",    # Path to log file (default)
    log_all_tools=False,                    # Log all tools or just run_sql (default: False)
    include_result_preview=False            # Include first 100 chars of result (default: False)
)
```

**Parameters Explained:**

- `log_file`: Path to the log file. Directory will be created if it doesn't exist. Use `.jsonl` extension for JSON Lines format.
- `log_all_tools`: If `True`, logs ALL tool executions (SQL, visualizations, file operations, etc.). If `False`, only logs `run_sql` tool.
- `include_result_preview`: If `True`, includes the first 100 characters of the result in the log entry. Useful for debugging but increases log size.

**Integration:**

Add the hook to your agent's lifecycle hooks:

```python
from vanna import Agent, AgentConfig
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook

# Create the hook
query_logger = QueryLoggingHook(
    log_file="./vanna_query_log.jsonl",
    log_all_tools=False
)

# Add to agent
agent = Agent(
    config=AgentConfig(...),
    lifecycle_hooks=[query_logger],  # Add here
    ...
)
```

### 2. DatabaseQueryLogger (Template)

An extended logger that writes to a database instead of a file. This is a template class - you must implement the `_write_to_database()` method for your specific database.

**Supported Databases:**

- SQLite (local development)
- PostgreSQL (production)
- MongoDB (document storage)
- ClickHouse (analytics)
- Any database with async Python driver

**Configuration:**

```python
from vanna.core.lifecycle.query_logging_hook import DatabaseQueryLogger

db_logger = DatabaseQueryLogger(
    db_connection_string="postgresql://user:pass@localhost/vanna_logs",
    table_name="vanna_query_logs",
    log_all_tools=False,
    include_result_preview=False
)
```

**Implementation Required:**

You must subclass and implement `_write_to_database()`:

```python
import aiosqlite
from vanna.core.lifecycle.query_logging_hook import DatabaseQueryLogger

class SQLiteQueryLogger(DatabaseQueryLogger):
    async def _write_to_database(self, log_entry: Dict[str, Any]) -> None:
        """Write log entry to SQLite database."""
        async with aiosqlite.connect(self.db_connection_string) as db:
            await db.execute(
                f"INSERT INTO {self.table_name} "
                "(timestamp, tool_name, user_id, sql, success, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    log_entry["timestamp"],
                    log_entry["tool_name"],
                    log_entry.get("user_id"),
                    log_entry.get("sql"),
                    log_entry["success"],
                    log_entry.get("error")
                )
            )
            await db.commit()
```

## How It Works

The hook uses the `after_tool()` lifecycle method to log after each tool execution:

1. **Tool executes** → RunSqlTool runs the SQL query
2. **Result returned** → ToolResult contains success/failure and data
3. **Hook triggered** → `after_tool()` is called with the result
4. **Metadata extracted** → Tool name and arguments are read from `result.metadata`
5. **Log entry built** → JSON object created with all relevant data
6. **Write to file** → Entry appended to log file as single line
7. **Return None** → Original result unchanged (hook is read-only)

### Why Metadata?

The hook extracts tool information from `result.metadata`, which is populated by the `ToolRegistry` during execution:

```python
# In src/vanna/core/registry.py (line 257-258)
result.metadata["tool_name"] = tool_call.name
result.metadata["arguments"] = tool_call.arguments
```

This allows the hook to log the original tool call without having direct access to it.

## Utility Functions

### 1. analyze_query_log()

Analyzes a log file and prints summary statistics.

**Usage:**

```bash
python -c "from vanna.core.lifecycle.query_logging_hook import analyze_query_log; analyze_query_log()"
```

**Or from Python:**

```python
from vanna.core.lifecycle.query_logging_hook import analyze_query_log

analyze_query_log(log_file="./vanna_query_log.jsonl")
```

**Sample Output:**

```
======================================================================
Vanna Query Log Analysis
======================================================================

Total queries: 1247
Successful: 1108 (88.9%)
Failed: 139 (11.1%)

Unique users: 23

Tool usage:
  run_sql: 1247

Top errors:
  Table 'orders_summary' doesn't exist : 45
  Column 'total_revenue' doesn't exist : 28
  Syntax error near 'WHERE' : 19
  Connection timeout : 12
  Permission denied for table 'salaries' : 8

Sample questions:
  - What was our revenue last month?...
  - Show me top 10 customers by order count...
  - How many active users do we have?...
  - What is the average order value?...
  - List all products with low stock...

======================================================================
```

**What It Analyzes:**

- Total queries executed
- Success rate (percentage)
- Number of unique users
- Tool usage breakdown
- Most common errors (top 5)
- Sample questions asked

### 2. export_successful_queries()

Extracts all successful SQL queries from the log and exports them as training data.

**Usage:**

```bash
python -c "from vanna.core.lifecycle.query_logging_hook import export_successful_queries; export_successful_queries()"
```

**Or from Python:**

```python
from vanna.core.lifecycle.query_logging_hook import export_successful_queries

export_successful_queries(
    log_file="./vanna_query_log.jsonl",
    output_file="./successful_queries.json"
)
```

**Output Format:**

```json
[
  {
    "question": "What was our revenue last month?",
    "sql": "SELECT SUM(amount) FROM transactions WHERE ...",
    "timestamp": "2024-02-12T14:23:45.123456",
    "user_id": "user123"
  },
  {
    "question": "How many active customers?",
    "sql": "SELECT COUNT(DISTINCT customer_id) FROM ...",
    "timestamp": "2024-02-12T15:10:22.789012",
    "user_id": "user456"
  }
]
```

**Use Cases:**

- **Expand training data** - Add successful real-world queries to agent memory
- **Build documentation** - Create examples for user guides
- **Identify patterns** - See what questions users ask most often
- **Backfill memory** - Bulk import historical successful queries

## Use Cases

### 1. Monitor Query Patterns

Analyze what questions users ask most frequently:

```bash
# Extract questions from log
cat vanna_query_log.jsonl | jq -r '.arguments.sql' | sort | uniq -c | sort -rn | head -20
```

### 2. Identify Failing Queries

Find queries that consistently fail:

```bash
# Extract failed queries
cat vanna_query_log.jsonl | jq 'select(.success == false) | {error: .error, sql: .arguments.sql}' | head -10
```

### 3. Track Success Rate Over Time

Monitor improvement as agent memory grows:

```bash
# Count success/failure by date
cat vanna_query_log.jsonl | jq -r '"\(.timestamp[:10]) \(.success)"' | sort | uniq -c
```

### 4. User Behavior Analytics

See which users are most active:

```bash
# Count queries by user
cat vanna_query_log.jsonl | jq -r '.user_id' | sort | uniq -c | sort -rn
```

### 5. Build Training Data

Export successful queries and add them to agent memory:

```python
from vanna.core.lifecycle.query_logging_hook import export_successful_queries
from training.seed_agent_memory import import_successful_queries

# Export successful queries
export_successful_queries(
    log_file="./vanna_query_log.jsonl",
    output_file="./new_training_data.json"
)

# Import into agent memory (custom function)
import_successful_queries("./new_training_data.json")
```

## Best Practices

### 1. Log Rotation

JSON Lines files can grow large over time. Implement log rotation:

```python
import os
from datetime import datetime

# Rotate log daily
log_file = f"./logs/vanna_query_{datetime.now().strftime('%Y%m%d')}.jsonl"

query_logger = QueryLoggingHook(log_file=log_file)
```

Or use external log rotation tools (logrotate on Linux, Windows Task Scheduler).

### 2. Privacy Considerations

Be mindful of sensitive data in logs:

- **User info** - Consider anonymizing user IDs
- **SQL queries** - May contain sensitive search terms or WHERE clause values
- **Results** - Don't enable `include_result_preview` for sensitive data

### 3. Performance

- **File I/O is async** - No blocking on write operations
- **Disk space** - 100K queries ≈ 50MB log file (varies by query complexity)
- **Parsing** - Use `jq` for efficient JSON Lines parsing instead of loading entire file

### 4. Monitoring

Set up alerts for:

- **High failure rate** - Success rate drops below 80%
- **Specific errors** - Connection timeouts, permission denied
- **Unusual activity** - Sudden spike in queries from a single user

### 5. Integration with Observability Tools

Export logs to monitoring platforms:

- **ELK Stack** (Elasticsearch, Logstash, Kibana) - Full-text search and dashboards
- **Splunk** - Log aggregation and analysis
- **Datadog** - APM and log monitoring
- **Grafana Loki** - Log aggregation and visualization

## Example: Complete Setup

```python
from vanna import Agent, AgentConfig
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook
from vanna.core.registry import ToolRegistry
from vanna.tools import RunSqlTool

# Create logger
query_logger = QueryLoggingHook(
    log_file="./logs/vanna_query.jsonl",
    log_all_tools=False,              # Only log SQL queries
    include_result_preview=False      # Don't include results
)

# Create agent with logger
agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    lifecycle_hooks=[query_logger],   # Add logger to lifecycle
    tool_registry=tool_registry,
    llm_service=llm_service,
    sql_runner=sql_runner,
    agent_memory=agent_memory
)

# Agent now logs all SQL queries automatically
```

## Related Components

- `LifecycleHook` (`src/vanna/core/lifecycle/base.py`) - Base interface for lifecycle hooks
- `ToolRegistry` (`src/vanna/core/registry.py`) - Adds metadata to tool results (line 257-258)
- `ToolResult` (`src/vanna/core/tool/base.py`) - Contains success, error, and metadata
- `export_successful_queries()` - Exports successful queries for training data expansion

## Future Enhancements

Potential improvements:

1. **Structured logging** - Use Python's logging framework with custom formatters
2. **Real-time streaming** - WebSocket endpoint for live query monitoring
3. **Automatic training** - Auto-save successful queries to memory (via AutoSaveMemoryHook)
4. **Query performance metrics** - Log execution time, rows returned, bytes scanned
5. **User feedback capture** - Log thumbs up/down on query results
6. **Anomaly detection** - Alert on unusual query patterns or performance degradation
