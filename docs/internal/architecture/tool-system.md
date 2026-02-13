# Tool System and Registry

## Overview

The tool system provides the framework for defining, registering, and executing tools that the LLM can call. It enforces group-based permissions, validates arguments via Pydantic, supports argument transformation, and integrates with audit logging.

## Tool Base Class

**Location:** `src/vanna/core/tool/base.py`

`Tool[T]` is an abstract generic class where `T` is the Pydantic args model type.

```python
class Tool(ABC, Generic[T]):
    @property
    @abstractmethod
    def name(self) -> str: ...           # Unique tool identifier

    @property
    @abstractmethod
    def description(self) -> str: ...    # Description for LLM consumption

    @property
    def access_groups(self) -> List[str]:  # Default: [] = all users
        return []

    @abstractmethod
    def get_args_schema(self) -> Type[T]: ...  # Return Pydantic model class

    @abstractmethod
    async def execute(self, context: ToolContext, args: T) -> ToolResult: ...

    def get_schema(self) -> ToolSchema:  # Auto-generates from Pydantic JSON schema
```

The `get_schema()` method auto-generates a `ToolSchema` from the Pydantic model's `model_json_schema()`, which the LLM uses for function calling.

## Tool Models

**Location:** `src/vanna/core/tool/models.py`

### ToolCall
Represents a tool call from the LLM response:
- `id: str` - Unique identifier for this call
- `name: str` - Tool name to execute
- `arguments: Dict[str, Any]` - Raw arguments from LLM

### ToolContext
Passed to every tool execution:
- `user: User` - Current user
- `conversation_id: str` - Conversation identifier
- `request_id: str` - Request tracking ID
- `agent_memory: AgentMemory` - Access to learning memory
- `metadata: Dict[str, Any]` - Extensible metadata (enrichers add data here)
- `observability_provider: Optional[ObservabilityProvider]` - Metrics/tracing

### ToolResult
Returned from tool execution:
- `success: bool` - Whether execution succeeded
- `result_for_llm: str` - String content sent back to the LLM for next turn
- `ui_component: Optional[UiComponent]` - UI component for frontend rendering
- `error: Optional[str]` - Error message if failed
- `metadata: Dict[str, Any]` - Additional metadata (execution_time_ms, tool_name, arguments added by registry)

### ToolSchema
LLM-compatible tool description:
- `name: str`, `description: str` - Tool identification
- `parameters: Dict[str, Any]` - JSON Schema of parameters
- `access_groups: List[str]` - Permission groups

### ToolRejection
Used by `transform_args` to reject execution:
- `reason: str` - Explanation of why the execution was rejected

## ToolRegistry

**Location:** `src/vanna/core/registry.py`

The registry manages tool registration, permission validation, and execution.

### Registration

```python
registry = ToolRegistry()
registry.register_local_tool(tool=my_tool, access_groups=["admin", "analyst"])
```

- If `access_groups` is provided, wraps tool with `_LocalToolWrapper` that overrides access groups
- Raises `ValueError` if tool name is already registered
- Empty `access_groups` = accessible to all users

### Permission Validation

`_validate_tool_permissions(tool, user) -> bool`:
- Checks set intersection: `user.group_memberships ∩ tool.access_groups ≠ ∅`
- Empty `access_groups` on tool = returns `True` for all users

### Schema Generation

`get_schemas(user) -> List[ToolSchema]`:
- Returns schemas for tools the user has permission to access
- Used by Agent to tell LLM which tools are available

### Argument Transformation

`transform_args(tool, args, user, context) -> Union[T, ToolRejection]`:
- Hook for per-user argument transformation
- Default is a no-op (returns args unchanged)
- **Subclass ToolRegistry** to implement custom transformation
- Use cases: Row-level security (RLS), SQL filtering, argument validation, field redaction
- Return `ToolRejection(reason="...")` to block execution with an explanation

### Execution Pipeline

`execute(tool_call, context) -> ToolResult`:

```
1. Find tool by name (→ ToolResult error if not found)
2. Validate permissions (→ ToolResult error + audit if denied)
3. Parse arguments via Pydantic model_validate (→ ToolResult error if invalid)
4. Transform arguments via transform_args (→ ToolResult error if rejected)
5. Audit: log access check (if enabled)
6. Audit: log invocation with parameters (sanitized if configured)
7. Execute tool: tool.execute(context, final_args)
8. Record execution_time_ms in result.metadata
9. Audit: log result (success/failure, timing, result size)
10. Populate metadata: tool_name, arguments (for lifecycle hooks like QueryLoggingHook)
11. Return ToolResult
```

## Built-in Tools

**Location:** `src/vanna/tools/`

### RunSqlTool (`tools/run_sql.py`)
- Executes SQL queries via injected `SqlRunner`
- Args: `RunSqlToolArgs(sql: str)`
- Returns: DataFrame + `DataFrameComponent` for UI rendering
- Supports custom tool name/description
- Optional `FileSystem` for saving results

### Python Execution Tool (`tools/python.py`)
- Executes Python code in a sandboxed environment
- Returns execution output + code display component

### Agent Memory Tools (`tools/agent_memory.py`)
- `SaveQuestionToolArgsTool` - Saves question/answer patterns to memory
- `SearchSavedCorrectToolUsesTool` - Searches memory for similar past queries

### File System Tool (`tools/file_system.py`)
- File operations via injected `FileSystem` abstraction
- Save, read, list files

### Visualize Data Tool (`tools/visualize_data.py`)
- Creates Plotly chart visualizations
- Accepts dataframe + visualization configuration
- Returns `ChartComponent` for UI rendering

## Creating a Custom Tool

### Step 1: Define Args Model

```python
from pydantic import BaseModel, Field

class MyToolArgs(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=10, description="Max results", gt=0, le=100)
```

### Step 2: Implement Tool

```python
from vanna.core.tool import Tool, ToolContext, ToolResult

class MySearchTool(Tool[MyToolArgs]):
    @property
    def name(self) -> str:
        return "search_documents"

    @property
    def description(self) -> str:
        return "Search internal documents by keyword"

    @property
    def access_groups(self) -> list[str]:
        return ["admin", "analyst"]  # Restrict access

    def get_args_schema(self):
        return MyToolArgs

    async def execute(self, context: ToolContext, args: MyToolArgs) -> ToolResult:
        results = await search(args.query, limit=args.limit)
        return ToolResult(
            success=True,
            result_for_llm=f"Found {len(results)} documents matching '{args.query}'",
            ui_component=None,  # Or a UiComponent for rendering
        )
```

### Step 3: Register

```python
registry = ToolRegistry()
registry.register_local_tool(
    tool=MySearchTool(),
    access_groups=["admin", "analyst"]
)
```

## Related Files

- `src/vanna/core/tool/__init__.py` - Module exports
- `src/vanna/capabilities/sql_runner/base.py` - SqlRunner interface
- `src/vanna/capabilities/agent_memory/base.py` - AgentMemory interface
- `src/vanna/capabilities/file_system/base.py` - FileSystem interface
