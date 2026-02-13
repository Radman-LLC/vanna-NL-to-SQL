# Audit Logging System

## Overview

The audit logging system tracks user actions, tool invocations, and access control decisions for security, compliance, and debugging. It uses an abstract `AuditLogger` interface that can be implemented for various backends.

**Location:** `src/vanna/core/audit/base.py` and `src/vanna/core/audit/models.py`

## AuditLogger Interface

```python
class AuditLogger(ABC):
    @abstractmethod
    async def log_event(self, event: AuditEvent) -> None: ...
```

### Convenience Methods

The base class provides convenience methods that construct typed events and call `log_event()`:

| Method | Event Type | What It Records |
|--------|-----------|-----------------|
| `log_tool_access_check()` | `ToolAccessCheckEvent` | Permission check: user, tool, granted/denied, required groups |
| `log_tool_invocation()` | `ToolInvocationEvent` | Tool call: user, tool, parameters (sanitized), UI features |
| `log_tool_result()` | `ToolResultEvent` | Result: success/failure, error, execution time, result size |
| `log_ui_feature_access()` | `UiFeatureAccessCheckEvent` | UI feature check: feature name, granted/denied |
| `log_ai_response()` | `AiResponseEvent` | LLM response: length, hash, model, tool calls count |
| `query_events()` | N/A | Query stored events (optional, raises NotImplementedError by default) |

### Parameter Sanitization

`_sanitize_parameters()` automatically redacts sensitive fields before logging:

Redacted patterns: `password`, `secret`, `token`, `api_key`, `apikey`, `credential`, `auth`, `private_key`, `access_key`

```python
# Input:  {"sql": "SELECT ...", "api_key": "sk-abc123"}
# Output: {"sql": "SELECT ...", "api_key": "[REDACTED]"}, was_sanitized=True
```

## Audit Event Types

**Location:** `src/vanna/core/audit/models.py`

### Base Event
All events share common fields:
- `event_type: str` - Event type identifier
- `timestamp: datetime` - When the event occurred (UTC)
- `user_id: str`, `username`, `user_email`, `user_groups` - User context
- `conversation_id: str`, `request_id: str` - Request context

### ToolAccessCheckEvent
```python
tool_name: str
access_granted: bool
required_groups: List[str]
reason: Optional[str]       # Denial reason
```

### ToolInvocationEvent
```python
tool_call_id: str
tool_name: str
parameters: Dict[str, Any]         # Tool arguments (possibly sanitized)
parameters_sanitized: bool          # Whether sanitization was applied
ui_features_available: List[str]    # UI features the user has access to
```

### ToolResultEvent
```python
tool_call_id: str
tool_name: str
success: bool
error: Optional[str]
execution_time_ms: float
result_size_bytes: int
ui_component_type: Optional[str]    # Type of UI component returned
```

### UiFeatureAccessCheckEvent
```python
feature_name: str
access_granted: bool
required_groups: List[str]
```

### AiResponseEvent
```python
response_length_chars: int
response_text: Optional[str]        # Only if include_full_text=True
response_hash: str                  # SHA-256 hash for deduplication
model_name: Optional[str]
temperature: Optional[float]
tool_calls_count: int
tool_names: List[str]
```

## Integration with Agent

The Agent wires the audit logger into the ToolRegistry during initialization:

```python
# In Agent.__init__()
if self.audit_logger and self.config.audit_config.enabled:
    self.tool_registry.audit_logger = self.audit_logger
    self.tool_registry.audit_config = self.config.audit_config
```

### What Gets Audited

| Event | Triggered By | AuditConfig Flag |
|-------|-------------|-----------------|
| Tool access check | `ToolRegistry.execute()` | `log_tool_access_checks` |
| Tool invocation | `ToolRegistry.execute()` | `log_tool_invocations` |
| Tool result | `ToolRegistry.execute()` | `log_tool_results` |
| UI feature check | `Agent._send_message()` | `log_ui_feature_checks` |
| AI response | Agent (if implemented) | `log_ai_responses` |

## Built-in Implementation

### LoggingAuditLogger
**Location:** `src/vanna/integrations/local/`

Uses Python's `logging` module to write audit events. Suitable for development and simple deployments.

## Custom Implementation Example

```python
class PostgresAuditLogger(AuditLogger):
    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def log_event(self, event: AuditEvent) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO audit_log (event_type, timestamp, user_id, data) VALUES ($1, $2, $3, $4)",
                event.event_type, event.timestamp, event.user_id, event.model_dump_json()
            )

    async def query_events(self, filters=None, start_time=None, end_time=None, limit=100):
        # Implement query logic for this backend
        ...
```

## Related Files

- `src/vanna/core/audit/__init__.py` - Module exports
- `src/vanna/core/agent/config.py` - `AuditConfig` model
- `docs/internal/security/user-auth-system.md` - Permission model documentation
- `docs/internal/architecture/tool-system.md` - Tool execution pipeline with audit points
