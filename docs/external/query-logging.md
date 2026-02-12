# Query Logging and Analytics

Vanna can track all SQL queries, user interactions, and tool executions for monitoring, analytics, and continuous improvement. This guide shows you how to set up query logging and analyze usage patterns.

## What Is Query Logging?

Query logging captures information about every SQL query executed through Vanna, including:

- User questions
- Generated SQL
- Success or failure status
- Error messages (if any)
- Execution timestamps

Logs are written in JSON Lines format for easy parsing and analysis.

## Setting Up Query Logging

### Basic Setup

Add the query logging hook to your agent:

```python
from vanna import Agent, AgentConfig
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook

# Create the logging hook
query_logger = QueryLoggingHook(
    log_file="./vanna_query_log.jsonl",
    log_all_tools=False,
    include_result_preview=False
)

# Add to agent
agent = Agent(
    config=AgentConfig(...),
    lifecycle_hooks=[query_logger],
    ...
)
```

### Configuration Options

**log_file** (required)
- Path to the log file
- Use `.jsonl` extension for JSON Lines format
- Directory will be created if it does not exist

**log_all_tools** (default: False)
- If True, logs ALL tool executions (SQL, visualizations, file operations)
- If False, only logs SQL queries
- Recommended: False for most use cases

**include_result_preview** (default: False)
- If True, includes first 100 characters of query result
- Useful for debugging but increases log size
- Not recommended for sensitive data

## Understanding Log Entries

### Successful Query Example

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

### Failed Query Example

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

## Analyzing Query Logs

### View Statistics

Use the built-in analysis tool to view summary statistics:

```bash
python -c "from vanna.core.lifecycle.query_logging_hook import analyze_query_log; analyze_query_log()"
```

Or from Python:

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
Successful: 1108 (88.9 percent)
Failed: 139 (11.1 percent)

Tool usage:
  run_sql: 1247

Top errors:
  Table 'orders_summary' doesn't exist : 45
  Column 'total_revenue' doesn't exist : 28
  Syntax error near 'WHERE' : 19

======================================================================
```

### Extract Successful Queries

Export all successful queries for training data:

```bash
python -c "from vanna.core.lifecycle.query_logging_hook import export_successful_queries; export_successful_queries()"
```

Or from Python:

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
    "timestamp": "2024-02-12T14:23:45.123456"
  },
  {
    "question": "How many active customers?",
    "sql": "SELECT COUNT(DISTINCT customer_id) FROM ...",
    "timestamp": "2024-02-12T15:10:22.789012"
  }
]
```

## Common Use Cases

### Monitor Query Patterns

Find the most frequently asked questions:

```bash
# Extract and count unique SQL queries
cat vanna_query_log.jsonl | jq -r '.arguments.sql' | sort | uniq -c | sort -rn | head -20
```

### Identify Failing Queries

Find queries that consistently fail:

```bash
# Extract failed queries with errors
cat vanna_query_log.jsonl | jq 'select(.success == false) | {error: .error, sql: .arguments.sql}' | head -10
```

### Track Success Rate Over Time

Monitor improvement as training data grows:

```bash
# Count success and failure by date
cat vanna_query_log.jsonl | jq -r '"\(.timestamp[:10]) \(.success)"' | sort | uniq -c
```

### Build Training Data

Export successful queries and add them to memory:

```python
from vanna.core.lifecycle.query_logging_hook import export_successful_queries

# Export successful queries
export_successful_queries(
    log_file="./vanna_query_log.jsonl",
    output_file="./training_data.json"
)

# Import into agent memory (custom workflow)
# Review and selectively add high-quality examples
```

## Best Practices

### Implement Log Rotation

JSON Lines files can grow large over time. Rotate logs daily:

```python
import os
from datetime import datetime

# Create dated log file
log_file = f"./logs/vanna_query_{datetime.now().strftime('%Y%m%d')}.jsonl"

query_logger = QueryLoggingHook(log_file=log_file)
```

Or use external log rotation tools:
- `logrotate` on Linux
- Windows Task Scheduler on Windows

### Privacy Considerations

Be mindful of sensitive data in logs:

- **SQL queries**: May contain sensitive search terms or WHERE clause values
- **Results**: Do not enable `include_result_preview` for sensitive data
- **User info**: Consider anonymizing if tracking user data

### Performance Impact

- **File I/O is asynchronous**: No blocking on write operations
- **Disk space**: 100K queries require approximately 50MB (varies by query complexity)
- **Parsing**: Use `jq` for efficient JSON Lines parsing instead of loading entire file

### Set Up Alerts

Monitor for:

- **High failure rate**: Success rate drops below 80 percent
- **Specific errors**: Connection timeouts, permission denied
- **Unusual activity**: Sudden spike in queries

## Troubleshooting

### Log File Not Created

**Possible causes:**
- Directory does not exist
- Insufficient permissions
- Invalid file path

**Solutions:**
- Verify directory exists or create it manually
- Check file permissions
- Use absolute path instead of relative path

### Missing Log Entries

**Possible causes:**
- Hook not added to lifecycle_hooks list
- Tool execution bypassing registry
- Log file path incorrect

**Solutions:**
- Verify hook is in lifecycle_hooks list
- Check that queries are executing through the agent
- Confirm log file path is correct

### Large Log Files

**Possible causes:**
- No log rotation
- include_result_preview enabled
- High query volume

**Solutions:**
- Implement daily log rotation
- Disable result preview
- Archive old logs periodically

## Integration with Analytics Tools

Export logs to monitoring platforms for advanced analytics:

### ELK Stack (Elasticsearch, Logstash, Kibana)

Configure Logstash to read JSON Lines:

```conf
input {
  file {
    path => "/path/to/vanna_query_log.jsonl"
    codec => json_lines
  }
}
```

### Splunk

Import JSON Lines directly:

```bash
splunk add oneshot /path/to/vanna_query_log.jsonl -sourcetype json_lines
```

### Custom Dashboards

Parse logs with Python and create visualizations:

```python
import json
import pandas as pd

# Load logs
with open("vanna_query_log.jsonl") as f:
    logs = [json.loads(line) for line in f]

# Convert to DataFrame
df = pd.DataFrame(logs)

# Analyze
success_rate = df['success'].mean() * 100
print(f"Success rate: {success_rate:.1f}%")

# Group by date
df['date'] = pd.to_datetime(df['timestamp']).dt.date
daily_stats = df.groupby('date')['success'].agg(['count', 'sum'])
print(daily_stats)
```

## Example: Complete Logging Setup

```python
from vanna import Agent, AgentConfig
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook
from datetime import datetime
import os

# Create logs directory
os.makedirs("./logs", exist_ok=True)

# Create dated log file
log_file = f"./logs/vanna_query_{datetime.now().strftime('%Y%m%d')}.jsonl"

# Create logger
query_logger = QueryLoggingHook(
    log_file=log_file,
    log_all_tools=False,              # Only log SQL queries
    include_result_preview=False      # Do not include results
)

# Create agent with logger
agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    lifecycle_hooks=[query_logger],
    tool_registry=tool_registry,
    llm_service=llm_service,
    sql_runner=sql_runner
)

# Agent now logs all SQL queries automatically
```

## Analyzing Logs for Improvements

### Identify Knowledge Gaps

Look for:
- Frequently failing query patterns
- Common error types
- Questions that need more training data

### Measure Impact

Track before and after metrics:

**Before improvements:**
- Success rate: 75 percent
- Average errors per day: 50

**After adding training data:**
- Success rate: 90 percent
- Average errors per day: 20

### Continuous Improvement Cycle

1. **Log queries**: Capture all query activity
2. **Analyze patterns**: Identify common failures
3. **Add training data**: Address knowledge gaps
4. **Monitor improvement**: Track success rate increase
5. **Repeat**: Continuously refine

## Related Topics

- Improving Query Accuracy: Use memory enhancement to reduce errors
- Training Vanna: Add examples to improve SQL generation
- Domain Configuration: Teach Vanna about your database
