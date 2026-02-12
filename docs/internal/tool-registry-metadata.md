# ToolRegistry Metadata Enhancement

## Overview

The `ToolRegistry` has been enhanced to add tool execution metadata to `ToolResult` objects. This enables lifecycle hooks to access tool name and arguments without requiring direct access to the original `ToolCall`.

**Location:** `src/vanna/core/registry.py` (lines 257-258)

**Purpose:** Provide lifecycle hooks with context about which tool was executed and with what arguments.

## What Changed

### Before (Original Code)

```python
# In ToolRegistry.execute_tool()
# ... tool execution logic ...

# Add execution time to metadata
result.metadata["execution_time_ms"] = execution_time_ms

# Audit tool result
if self.audit_logger:
    # ... audit logging ...
```

The `ToolResult` only contained execution time in metadata.

### After (Enhanced Code)

```python
# In ToolRegistry.execute_tool()
# ... tool execution logic ...

# Add execution time to metadata
result.metadata["execution_time_ms"] = execution_time_ms

# Add tool name and arguments to metadata for lifecycle hooks
result.metadata["tool_name"] = tool_call.name
result.metadata["arguments"] = tool_call.arguments

# Audit tool result
if self.audit_logger:
    # ... audit logging ...
```

Now `ToolResult.metadata` contains:

- `execution_time_ms` - How long the tool took to execute (milliseconds)
- `tool_name` - Name of the tool that was executed (e.g., "run_sql", "visualize_data")
- `arguments` - Full arguments dictionary passed to the tool

## Why This Change?

### Problem

Lifecycle hooks receive `ToolResult` objects via the `after_tool()` method:

```python
class MyLifecycleHook(LifecycleHook):
    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        # Need to know: Which tool was executed?
        # Need to know: What were the arguments?
        # But `result` doesn't contain this information!
        pass
```

Without this information, hooks couldn't:

- Filter by tool type (e.g., only log SQL queries)
- Extract specific arguments (e.g., SQL text from run_sql)
- Build meaningful log entries

### Solution

By adding `tool_name` and `arguments` to `result.metadata`, hooks can now:

```python
class QueryLoggingHook(LifecycleHook):
    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        # Extract tool info from metadata
        tool_name = result.metadata.get("tool_name")
        arguments = result.metadata.get("arguments")

        # Filter by tool name
        if tool_name == "run_sql":
            sql = arguments.get("sql")
            # Log the SQL query
            self.log_query(sql, result.success, result.error)

        return None  # Keep original result unchanged
```

## Impact on Existing Code

### No Breaking Changes

This is a **non-breaking change** because:

1. `metadata` is a dictionary - adding new keys doesn't affect existing code
2. Lifecycle hooks already had access to `result.metadata`
3. No existing code relied on these keys being absent

### Enables New Features

This change enables:

1. **QueryLoggingHook** (`src/vanna/core/lifecycle/query_logging_hook.py`) - Logs SQL queries with tool arguments
2. **AutoSaveMemoryHook** (planned) - Auto-saves successful queries to agent memory
3. **Custom audit hooks** - Build tool-specific auditing logic
4. **Analytics hooks** - Track tool usage patterns

## Usage in Lifecycle Hooks

### Example 1: Filtering by Tool Name

```python
from vanna.core.lifecycle.base import LifecycleHook

class SqlOnlyHook(LifecycleHook):
    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        # Only process SQL queries
        tool_name = result.metadata.get("tool_name")
        if tool_name != "run_sql":
            return None

        # Process SQL query result
        if result.success:
            print("SQL query succeeded!")
        else:
            print(f"SQL query failed: {result.error}")

        return None
```

### Example 2: Extracting Tool Arguments

```python
class ArgumentLogger(LifecycleHook):
    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        tool_name = result.metadata.get("tool_name")
        arguments = result.metadata.get("arguments", {})

        if tool_name == "run_sql":
            sql = arguments.get("sql", "")
            print(f"SQL: {sql[:100]}...")  # First 100 chars

        elif tool_name == "visualize_data":
            chart_type = arguments.get("chart_type")
            print(f"Chart: {chart_type}")

        return None
```

### Example 3: Complete Logging (QueryLoggingHook)

See `src/vanna/core/lifecycle/query_logging_hook.py` for a complete example:

```python
async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
    # Get tool name from metadata (added by registry at line 257)
    tool_name = result.metadata.get("tool_name")
    if not tool_name:
        return None

    # Filter by tool name if not logging all tools
    if not self.log_all_tools and tool_name != "run_sql":
        return None

    # Build log entry
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "success": result.success,
    }

    # Add tool arguments from metadata
    arguments = result.metadata.get("arguments")
    if arguments:
        log_entry["arguments"] = arguments

    # Add error if failed
    if not result.success and result.error:
        log_entry["error"] = result.error

    # Write to log file
    with open(self.log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return None
```

## Metadata Keys

### Standard Metadata Keys

After this change, `ToolResult.metadata` contains:

| Key | Type | Description | Added By |
|-----|------|-------------|----------|
| `execution_time_ms` | float | Execution time in milliseconds | ToolRegistry |
| `tool_name` | str | Name of executed tool | ToolRegistry |
| `arguments` | dict | Tool arguments (Pydantic model as dict) | ToolRegistry |

### Tool-Specific Metadata

Individual tools may add additional metadata keys. For example:

- `run_sql` might add: `rows_returned`, `query_hash`
- `visualize_data` might add: `chart_saved_to`
- Custom tools can add any metadata they need

## Performance Considerations

### Memory Impact

Adding `tool_name` and `arguments` to metadata has minimal memory impact:

- `tool_name`: ~10-30 bytes (short string)
- `arguments`: Varies by tool (typically 100-1000 bytes for SQL queries)

Total overhead: ~0.1-1KB per tool execution.

### CPU Impact

Negligible - just two dictionary assignments:

```python
result.metadata["tool_name"] = tool_call.name  # O(1)
result.metadata["arguments"] = tool_call.arguments  # O(1) - shallow copy
```

No performance impact on tool execution.

## Testing

To test that metadata is properly populated:

```python
from vanna.core.registry import ToolRegistry
from vanna.tools import RunSqlTool

# Create registry and register tool
registry = ToolRegistry()
registry.register_tool(RunSqlTool(sql_runner), access_groups=[])

# Execute tool
tool_call = ToolCall(
    name="run_sql",
    arguments={"sql": "SELECT 1"}
)
result = await registry.execute_tool(tool_call, context)

# Verify metadata
assert "tool_name" in result.metadata
assert result.metadata["tool_name"] == "run_sql"
assert "arguments" in result.metadata
assert result.metadata["arguments"]["sql"] == "SELECT 1"
```

## Related Components

- `ToolRegistry` (`src/vanna/core/registry.py`) - Adds metadata to results
- `LifecycleHook` (`src/vanna/core/lifecycle/base.py`) - Base interface for hooks
- `QueryLoggingHook` (`src/vanna/core/lifecycle/query_logging_hook.py`) - Uses metadata for logging
- `ToolResult` (`src/vanna/core/tool/base.py`) - Contains metadata dictionary

## Future Enhancements

Potential additions to metadata:

1. **User information** - `user_id`, `user_email`, `user_groups`
2. **Request context** - `conversation_id`, `request_id`, `question`
3. **Performance metrics** - `rows_returned`, `bytes_scanned`, `cache_hit`
4. **Execution context** - `retry_count`, `fallback_used`, `model_used`

These would enable even richer analytics and monitoring.
