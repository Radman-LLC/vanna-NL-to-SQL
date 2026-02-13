# User and Authentication System

## Overview

Vanna uses a group-based access control model. Users are resolved from HTTP request context, and permissions are checked via set intersection between user group memberships and resource access groups.

## User Model

**Location:** `src/vanna/core/user/models.py`

```python
class User(BaseModel):
    id: str                                    # Unique identifier
    username: Optional[str] = None             # Display name
    email: Optional[str] = None                # Email address
    metadata: Dict[str, Any] = {}              # Custom fields (extensible)
    group_memberships: List[str] = []          # Groups for permission checking

    model_config = ConfigDict(extra="allow")   # Allows additional fields
```

The `extra="allow"` config means you can add custom fields beyond the defined ones, which is useful for integration-specific user data.

## UserResolver

**Location:** `src/vanna/core/user/resolver.py`

Abstract base class that resolves HTTP requests to authenticated `User` objects:

```python
class UserResolver(ABC):
    @abstractmethod
    async def resolve_user(self, request_context: RequestContext) -> User:
        """Extract user identity from request context (cookies, headers, tokens)."""
```

### Implementation Patterns

**JWT Token Resolver:**
```python
class JwtUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        token = request_context.get_header('Authorization')
        payload = jwt.decode(token, SECRET_KEY)
        return User(id=payload['sub'], username=payload['name'],
                    group_memberships=payload['groups'])
```

**Email-based Resolver:**
```python
class EmailUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        email = request_context.get_cookie('user_email')
        user_data = await db.get_user_by_email(email)
        return User(id=user_data['id'], email=email,
                    group_memberships=user_data['groups'])
```

## RequestContext

**Location:** `src/vanna/core/user/request_context.py`

Structured request context passed to UserResolver:
- `cookies: Dict[str, str]` - HTTP cookies
- `headers: Dict[str, str]` - HTTP headers
- `query_params: Dict[str, str]` - URL query parameters
- `metadata: Dict[str, Any]` - Additional context (e.g., `starter_ui_request` flag)

The server layer (FastAPI/Flask) extracts these from the incoming HTTP request and passes them to the Agent.

## Permission Model

### Tool Access Control

Defined in `ToolRegistry._validate_tool_permissions()` (`src/vanna/core/registry.py`):

```python
# Permission check: set intersection
user_groups = set(user.group_memberships)   # e.g., {"sales", "user"}
tool_groups = set(tool.access_groups)        # e.g., {"admin", "analyst", "sales"}
access_granted = bool(user_groups & tool_groups)  # True if any overlap
```

**Rules:**
- Empty `access_groups` on a tool = accessible to all users (no restriction)
- User must have at least one group in common with the tool's access groups
- Groups are simple strings (no hierarchy)

### UI Feature Access Control

Same intersection logic, defined in `UiFeatures.can_user_access_feature()` (`src/vanna/core/agent/config.py`):

```python
# Same logic as tool access
allowed_groups = self.feature_group_access[feature_name]
if not allowed_groups:
    return True  # Empty = all users
return bool(set(user.group_memberships) & set(allowed_groups))
```

### Default UI Feature Groups

| Feature | Default Groups | What It Controls |
|---------|---------------|-----------------|
| `tool_names` | `[admin, user]` | Show tool names in task tracker |
| `tool_arguments` | `[admin]` | Show tool arguments and status cards |
| `tool_error` | `[admin]` | Show detailed error messages |
| `tool_invocation_message_in_chat` | `[admin]` | Show LLM's tool invocation text |
| `memory_detailed_results` | `[admin]` | Show detailed memory search results |

### Where Permissions Are Checked

1. **ToolRegistry.get_schemas(user)** - Filters tool list sent to LLM
2. **ToolRegistry.execute()** - Validates before execution
3. **Agent._send_message()** - Checks UI feature access before yielding components
4. **AuditLogger** - Records all access check decisions

## Typical User Groups

| Group | Description | Typical Access |
|-------|-------------|----------------|
| `admin` | System administrators | All tools, all UI features |
| `analyst` | Data analysts | SQL queries, visualizations, memory tools |
| `sales` | Sales representatives | Read-only queries, filtered by sales_rep |
| `user` | General users | Basic queries, tool names visible |
| `readonly` | Read-only users | SQL queries only (no write tools) |

## Related Files

- `src/vanna/core/user/__init__.py` - Module exports
- `src/vanna/core/user/base.py` - UserService ABC (optional extended interface)
- `docs/internal/security/audit-logging.md` - Audit logging documentation
- `docs/internal/architecture/agent-architecture.md` - Agent's permission integration
