# Agent Architecture

## Overview

The `Agent` class (`src/vanna/core/agent/agent.py`) is the central orchestrator of the Vanna framework. It coordinates LLM services, tool execution, conversation management, and all extensibility points.

**Location:** `src/vanna/core/agent/agent.py`

## Constructor Parameters

The Agent accepts these pluggable dependencies via constructor injection:

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `llm_service` | `LlmService` | **Required** | Abstract LLM provider (Anthropic, OpenAI, etc.) |
| `tool_registry` | `ToolRegistry` | **Required** | Manages tool registration, permissions, execution |
| `user_resolver` | `UserResolver` | **Required** | Resolves users from HTTP request context |
| `agent_memory` | `AgentMemory` | **Required** | RAG-style memory for tool usage patterns |
| `conversation_store` | `ConversationStore` | `MemoryConversationStore()` | Persists conversation history |
| `config` | `AgentConfig` | `AgentConfig()` | Controls agent behavior |
| `system_prompt_builder` | `SystemPromptBuilder` | `DefaultSystemPromptBuilder()` | Builds LLM system prompts |
| `lifecycle_hooks` | `List[LifecycleHook]` | `[]` | Pre/post message and tool hooks |
| `llm_middlewares` | `List[LlmMiddleware]` | `[]` | Intercept/transform LLM requests/responses |
| `workflow_handler` | `WorkflowHandler` | `DefaultWorkflowHandler()` | Deterministic workflows before LLM |
| `error_recovery_strategy` | `ErrorRecoveryStrategy` | `None` | Custom error handling with retry logic |
| `context_enrichers` | `List[ToolContextEnricher]` | `[]` | Add data to tool execution context |
| `llm_context_enhancer` | `LlmContextEnhancer` | `DefaultLlmContextEnhancer(agent_memory)` | Inject RAG/memory into system prompts |
| `conversation_filters` | `List[ConversationFilter]` | `[]` | Filter conversation history before LLM calls |
| `observability_provider` | `ObservabilityProvider` | `None` | Telemetry and metrics collection |
| `audit_logger` | `AuditLogger` | `None` | Audit event recording |

## AgentConfig

**Location:** `src/vanna/core/agent/config.py`

```python
class AgentConfig(BaseModel):
    max_tool_iterations: int = 20       # Max tool call loops before stopping (gt=0)
    stream_responses: bool = True       # Enable streaming via AsyncGenerator
    auto_save_conversations: bool = True # Auto-persist conversations
    include_thinking_indicators: bool = True  # Show thinking indicators in UI
    temperature: float = 0.7            # LLM temperature (0.0-2.0)
    max_tokens: Optional[int] = None    # Token limit (gt=0)
    ui_features: UiFeatures = UiFeatures()  # Group-based UI feature access
    audit_config: AuditConfig = AuditConfig()  # Audit logging settings
```

### UiFeatures

Controls what users see in the UI based on group membership. Uses the same set-intersection permission model as tool access.

```python
# Default feature access
DEFAULT_UI_FEATURES = {
    "tool_names": ["admin", "user"],         # Show tool names in UI
    "tool_arguments": ["admin"],             # Show tool arguments
    "tool_error": ["admin"],                 # Show error details
    "tool_invocation_message_in_chat": ["admin"],  # Show LLM tool invocation text
    "memory_detailed_results": ["admin"],    # Show detailed memory search results
}
```

Custom features can be registered at runtime via `ui_features.register_feature(name, access_groups)`.

### AuditConfig

```python
class AuditConfig(BaseModel):
    enabled: bool = True
    log_tool_access_checks: bool = True      # Permission checks
    log_tool_invocations: bool = True        # Tool calls with parameters
    log_tool_results: bool = True            # Execution results
    log_ui_feature_checks: bool = False      # UI feature checks (noisy)
    log_ai_responses: bool = True            # LLM responses
    include_full_ai_responses: bool = False  # Full text (privacy concern)
    sanitize_tool_parameters: bool = True    # Redact passwords, tokens, etc.
```

## Request Flow

The `send_message()` method is the primary entry point. Here is the complete execution flow:

```
1. Resolve user from request_context via UserResolver
2. Check for starter UI request (empty message)
   └─ If starter: workflow_handler.get_starter_ui() → yield components, return
3. Run before_message lifecycle hooks (can modify message)
4. Generate conversation_id and request_id (UUIDs)
5. Load or create conversation from ConversationStore
6. Try workflow_handler.try_handle()
   └─ If should_skip_llm: stream components, apply mutation, return
7. Add user message to conversation
8. Create ToolContext (user, conversation_id, request_id, agent_memory)
9. Run context_enrichers on ToolContext
10. Get tool schemas filtered by user permissions
11. Build system prompt via system_prompt_builder
12. Enhance system prompt via llm_context_enhancer (RAG/memory injection)
13. Build LlmRequest:
    a. Apply conversation_filters to message history
    b. Convert Messages to LlmMessages
    c. Enhance user messages via llm_context_enhancer
14. Enter tool loop (max_tool_iterations):
    a. Send LLM request (streaming or non-streaming, with middleware)
    b. If response has tool_calls:
       - Add assistant message to conversation
       - For each tool_call:
         · Check UI feature access (show tool names/args/errors)
         · Run before_tool lifecycle hooks
         · Execute via ToolRegistry.execute()
         · Run after_tool lifecycle hooks
         · Yield status and result UI components
       - Add tool response messages to conversation
       - Rebuild LLM request with updated history
       - Continue loop
    c. If no tool_calls:
       - Yield final text response
       - Break loop
15. Handle tool iteration limit (warning if reached)
16. Save conversation if auto_save_conversations
17. Run after_message lifecycle hooks
18. Record observability metrics
```

## Streaming Architecture

The agent uses `AsyncGenerator[UiComponent, None]` for streaming:

```python
async def send_message(
    self, request_context: RequestContext, message: str,
    *, conversation_id: Optional[str] = None,
) -> AsyncGenerator[UiComponent, None]:
```

### Streaming vs Non-Streaming LLM Calls

- **Streaming** (`_handle_streaming_response`): Calls `LlmService.stream_request()`, accumulates content and tool_calls from chunks, applies middleware before/after
- **Non-streaming** (`_send_llm_request`): Calls `LlmService.send_request()`, applies middleware before/after

Both paths apply the same middleware chain.

### UI Component Yielding

The agent yields several types of UI components during execution:

| Component | When | Purpose |
|-----------|------|---------|
| `StatusBarUpdateComponent` | Throughout | Update status bar (working/idle/error/warning) |
| `TaskTrackerUpdateComponent` | Tool execution | Track tool execution progress |
| `ChatInputUpdateComponent` | End of flow | Re-enable chat input |
| `RichTextComponent` | LLM response | Display text responses |
| `StatusCardComponent` | Tool execution | Show tool status and results |

## Error Handling

The outer `send_message()` wraps `_send_message()` with error handling:

1. Catches all exceptions
2. Logs full stack trace
3. Records error span to observability provider
4. Yields error `StatusCardComponent` to UI
5. Updates status bar to error state
6. Re-enables chat input so user can retry

## Audit Logger Wiring

If an `AuditLogger` is provided and `audit_config.enabled` is True, the Agent wires it into the `ToolRegistry`:

```python
if self.audit_logger and self.config.audit_config.enabled:
    self.tool_registry.audit_logger = self.audit_logger
    self.tool_registry.audit_config = self.config.audit_config
```

The registry then calls audit methods at each step: access check, invocation, and result.

## Observability Integration

The agent creates observability spans throughout execution:

- `agent.user_resolution` - User resolver timing
- `agent.workflow_handler.starter_ui` - Starter UI generation
- `agent.workflow_handler.try_handle` - Workflow handler attempt
- `agent.conversation.load` - Conversation loading
- `agent.context.enrichment` - Context enricher timing
- `agent.tool_schemas.fetch` - Schema fetching
- `agent.system_prompt.build` - Prompt building
- `agent.llm_context.enhance_system_prompt` - Memory enhancement
- `agent.llm_context.enhance_user_messages` - Message enhancement
- `agent.tool.execute` - Tool execution
- `agent.hook.before_message/after_message` - Lifecycle hook timing
- `agent.hook.before_tool/after_tool` - Tool lifecycle hook timing
- `agent.middleware.before_llm/after_llm` - Middleware timing
- `agent.conversation.save` - Conversation save timing
- `agent.message.duration` - Total message processing time
- `llm.request` / `llm.stream` - LLM call timing

## Related Files

- `src/vanna/core/agent/config.py` - AgentConfig, UiFeatures, AuditConfig, UiFeature enum
- `src/vanna/core/agent/__init__.py` - Module exports
- `src/vanna/core/registry.py` - ToolRegistry (see tool-system.md)
- `src/vanna/core/llm/base.py` - LlmService interface
- `src/vanna/servers/base/chat_handler.py` - HTTP handler that wraps Agent (see server-layer.md)
