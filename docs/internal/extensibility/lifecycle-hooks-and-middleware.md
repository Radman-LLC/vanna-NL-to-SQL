# Lifecycle Hooks and Middleware -- Extensibility Reference

Internal developer documentation for the 7 extensibility points in the Vanna 2.0 agent architecture. Each extensibility point is an abstract base class that you subclass and inject into the `Agent` constructor. The agent calls these hooks at well-defined points during message processing.

**Source**: `src/vanna/core/agent/agent.py` -- see the `Agent.__init__` constructor parameters and `_send_message` method for the integration points.

---

## Table of Contents

1. [Lifecycle Hooks](#1-lifecycle-hooks)
2. [LLM Middleware](#2-llm-middleware)
3. [LLM Context Enhancer](#3-llm-context-enhancer)
4. [Tool Context Enricher](#4-tool-context-enricher)
5. [Conversation Filter](#5-conversation-filter)
6. [Error Recovery Strategy](#6-error-recovery-strategy)
7. [Observability Provider](#7-observability-provider)
8. [Execution Order Summary](#execution-order-summary)
9. [Agent Constructor Reference](#agent-constructor-reference)

---

## 1. Lifecycle Hooks

**Source**: `src/vanna/core/lifecycle/base.py`

Lifecycle hooks intercept execution at four points in the agent's message processing pipeline. Multiple hooks can be registered; they execute in list order.

### ABC: `LifecycleHook`

```python
class LifecycleHook(ABC):
    async def before_message(self, user: User, message: str) -> Optional[str]:
        """Called before processing a user message.

        Return a modified message string to replace the original,
        or None to keep the original unchanged.
        Raise AgentError to halt message processing entirely
        (e.g., quota exceeded, banned user).
        """
        return None

    async def after_message(self, result: Any) -> None:
        """Called after message has been fully processed.

        The result argument is the final Conversation object.
        Cannot modify the result -- observation only.
        """
        pass

    async def before_tool(self, tool: Tool[Any], context: ToolContext) -> None:
        """Called before tool execution.

        Raise AgentError to prevent the tool from executing.
        Cannot modify tool arguments -- use for validation/gating only.
        """
        pass

    async def after_tool(self, result: ToolResult) -> Optional[ToolResult]:
        """Called after tool execution.

        Return a modified ToolResult to replace the original,
        or None to keep the original unchanged.
        """
        return None
```

### Hook Execution in the Agent

The agent iterates over `self.lifecycle_hooks` (a `List[LifecycleHook]`) at each hook point:

- **before_message**: Called once per `send_message` call, after user resolution but before the message is added to conversation history. Each hook can modify the message; the modified message is passed to the next hook in the chain.
- **after_message**: Called once per `send_message` call, after conversation is saved. Receives the `Conversation` object.
- **before_tool**: Called once per tool execution, after the tool is looked up from the registry but before `execute()`. All hooks run in order for each tool call.
- **after_tool**: Called once per tool execution, after `execute()` completes. If a hook returns a non-None `ToolResult`, that replaces the result for subsequent hooks and for the LLM feedback loop.

### Built-in: `QueryLoggingHook`

**Source**: `src/vanna/core/lifecycle/query_logging_hook.py`

Logs tool executions to a JSON Lines file (`./vanna_query_log.jsonl` by default). Uses the `after_tool` hook point only.

```python
from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook

hook = QueryLoggingHook(
    log_file="./vanna_query_log.jsonl",  # Path to log file
    log_all_tools=False,                  # False = only log run_sql; True = log all tools
    include_result_preview=False,         # True = include first 100 chars of result
)
```

Each log entry is a JSON object with: `timestamp`, `tool_name`, `success`, and optionally `user_id`, `question`, `arguments`, `error`, `result_preview`. File writes are offloaded to a thread pool via `asyncio.to_thread` to avoid blocking the event loop. Write failures are swallowed to prevent logging from crashing the tool pipeline.

The module also provides two utility functions for log analysis:

- `analyze_query_log(log_file)` -- prints summary statistics (success rates, top errors, user counts)
- `export_successful_queries(log_file, output_file)` -- exports question-SQL pairs for training data expansion

### Typical Use Cases

| Use Case | Hook Point | Pattern |
|---|---|---|
| Logging / telemetry | `after_message`, `after_tool` | Log metadata, don't modify results |
| Rate limiting / quotas | `before_message` | Raise `AgentError` if quota exceeded |
| Message sanitization | `before_message` | Return cleaned message string |
| Tool gating | `before_tool` | Raise `AgentError` for blocked tools |
| Result transformation | `after_tool` | Return modified `ToolResult` |
| Audit trail | `before_tool`, `after_tool` | Record who ran what and when |

### Example: Rate Limiting Hook

```python
from vanna.core.lifecycle.base import LifecycleHook

class RateLimitHook(LifecycleHook):
    def __init__(self, max_requests_per_minute: int = 10):
        self.max_rpm = max_requests_per_minute
        self.request_counts: dict[str, list[float]] = {}

    async def before_message(self, user, message):
        import time
        now = time.time()
        user_requests = self.request_counts.setdefault(user.id, [])

        # Evict requests older than 60 seconds
        user_requests[:] = [t for t in user_requests if now - t < 60]

        if len(user_requests) >= self.max_rpm:
            from vanna.core.errors import AgentError
            raise AgentError(
                "Rate limit exceeded. Please wait before sending more messages."
            )

        user_requests.append(now)
        return None  # Don't modify the message
```

---

## 2. LLM Middleware

**Source**: `src/vanna/core/middleware/base.py`

LLM middleware intercepts requests before they reach the LLM provider and responses before they are processed by the agent. Middleware is applied in list order for `before_llm_request` and in the same order for `after_llm_response`.

### ABC: `LlmMiddleware`

```python
class LlmMiddleware(ABC):
    async def before_llm_request(self, request: LlmRequest) -> LlmRequest:
        """Called before sending request to LLM.

        Return a modified request or the original.
        Can modify messages, tools, temperature, max_tokens, etc.
        """
        return request

    async def after_llm_response(
        self, request: LlmRequest, response: LlmResponse
    ) -> LlmResponse:
        """Called after receiving response from LLM.

        Receives both the original request and the response.
        Return a modified response or the original.
        """
        return response
```

### Middleware Execution in the Agent

Middleware runs in two locations within the agent:

1. **`_send_llm_request`** (non-streaming path): Iterates `before_llm_request` over all middleware, calls `llm_service.send_request()`, then iterates `after_llm_response` over all middleware.
2. **`_handle_streaming_response`** (streaming path): Same pattern but uses `llm_service.stream_request()` between the middleware passes. All streamed chunks are accumulated into a single `LlmResponse` before `after_llm_response` is called.

Both paths apply middleware in the same list order. The streaming path accumulates all chunks into a single `LlmResponse` before calling `after_llm_response`, so middleware sees the complete response in both cases.

### Typical Use Cases

| Use Case | Method | Pattern |
|---|---|---|
| Response caching | Both | Check cache in `before`, populate in `after` |
| Request/response logging | Both | Log without modifying |
| Content filtering | `after_llm_response` | Strip or mask sensitive content from response |
| Cost tracking | `after_llm_response` | Count tokens, record usage |
| Fallback strategies | `before_llm_request` | Route to different model based on request properties |
| Prompt injection defense | `before_llm_request` | Scan/sanitize user messages before sending to LLM |

### Example: Cost Tracking Middleware

```python
from vanna.core.middleware.base import LlmMiddleware

class CostTrackingMiddleware(LlmMiddleware):
    def __init__(self):
        self.total_requests = 0
        self.total_tokens_estimate = 0

    async def before_llm_request(self, request):
        self.total_requests += 1
        return request

    async def after_llm_response(self, request, response):
        # Rough token estimate from content length
        if response.content:
            self.total_tokens_estimate += len(response.content) // 4
        return response
```

---

## 3. LLM Context Enhancer

**Source**: `src/vanna/core/enhancer/base.py`

The LLM context enhancer injects additional context into system prompts and user messages before LLM calls. Unlike middleware (which operates on the full `LlmRequest`/`LlmResponse`), the enhancer specifically targets prompt content -- adding RAG results, memory, documentation, or other contextual data.

### ABC: `LlmContextEnhancer`

```python
class LlmContextEnhancer(ABC):
    async def enhance_system_prompt(
        self, system_prompt: str, user_message: str, user: User
    ) -> str:
        """Enhance the system prompt with additional context.

        Called once per conversation turn, before any tool calls.
        Receives the initial user message for relevance-based retrieval.
        """
        return system_prompt

    async def enhance_user_messages(
        self, messages: list[LlmMessage], user: User
    ) -> list[LlmMessage]:
        """Enhance user messages with additional context.

        Called before each LLM request, including after tool calls.
        Be careful not to add context repeatedly on each iteration
        of the tool loop.
        """
        return messages
```

### Enhancer Execution in the Agent

- **`enhance_system_prompt`**: Called once in `_send_message` after `system_prompt_builder.build_system_prompt()` returns, before the first LLM request. The enhanced system prompt is reused for all subsequent LLM calls within the same conversation turn (including tool loop iterations).
- **`enhance_user_messages`**: Called inside `_build_llm_request()`, which runs before every LLM call (including after tool results are appended to the conversation). The enhancer sees the full message list including tool responses.

### Built-in: `DefaultLlmContextEnhancer`

**Source**: `src/vanna/core/enhancer/default.py`

The default enhancer searches `AgentMemory` for relevant text memories based on the user's message and appends them to the system prompt under a "Relevant Context from Memory" heading. It does not modify user messages.

```python
from vanna.core.enhancer.default import DefaultLlmContextEnhancer

# Created automatically by Agent if llm_context_enhancer is not provided
enhancer = DefaultLlmContextEnhancer(agent_memory=agent_memory)
```

Behavior details:
- Creates a temporary `ToolContext` for memory search (conversation_id="temp").
- Calls `agent_memory.search_text_memories(query=user_message, limit=5)`.
- Appends matching memories as bullet points under `## Relevant Context from Memory`.
- If `agent_memory` is `None` or search fails, returns the original prompt unchanged (non-fatal).
- `enhance_user_messages` returns messages unchanged (no-op in default implementation).

### Typical Use Cases

| Use Case | Method | Pattern |
|---|---|---|
| RAG / memory injection | `enhance_system_prompt` | Search vector store, append results |
| Documentation injection | `enhance_system_prompt` | Add relevant schema docs based on query |
| Temporal context | `enhance_system_prompt` | Add current date/time, business calendar |
| Few-shot examples | `enhance_user_messages` | Prepend example Q&A pairs |
| User history context | `enhance_system_prompt` | Add user's recent query history |

### Example: Schema Documentation Enhancer

```python
from vanna.core.enhancer.base import LlmContextEnhancer

class SchemaDocEnhancer(LlmContextEnhancer):
    def __init__(self, schema_docs: dict[str, str]):
        # Map of table_name -> documentation string
        self.schema_docs = schema_docs

    async def enhance_system_prompt(self, system_prompt, user_message, user):
        # Find tables mentioned in the user's question
        relevant_docs = []
        for table_name, doc in self.schema_docs.items():
            if table_name.lower() in user_message.lower():
                relevant_docs.append(doc)

        if relevant_docs:
            system_prompt += "\n\n## Relevant Schema Documentation\n\n"
            system_prompt += "\n\n".join(relevant_docs)

        return system_prompt
```

---

## 4. Tool Context Enricher

**Source**: `src/vanna/core/enricher/base.py`

Tool context enrichers add data to the `ToolContext.metadata` dictionary before tools are executed. Unlike lifecycle hooks (which can block or transform), enrichers purely add contextual data that tools can read during execution.

### ABC: `ToolContextEnricher`

```python
class ToolContextEnricher(ABC):
    async def enrich_context(self, context: ToolContext) -> ToolContext:
        """Enrich the tool execution context with additional data.

        Typically modifies context.metadata dict in place and returns context.
        """
        return context
```

### Enricher Execution in the Agent

Enrichers run once per `send_message` call, after conversation loading and before tool schema fetching. All enrichers in `self.context_enrichers` execute in list order. The enriched context is then passed to every tool execution within that message turn.

The agent creates the initial `ToolContext` with:
- `user` -- the resolved user
- `conversation_id` -- current conversation ID
- `request_id` -- unique per-message UUID
- `agent_memory` -- the agent's memory instance
- `observability_provider` -- for tool-level tracing
- `metadata["ui_features_available"]` -- list of UI features the user can access

Enrichers add arbitrary keys to `context.metadata`.

### Typical Use Cases

| Use Case | Metadata Key (convention) | Pattern |
|---|---|---|
| User preferences | `preferences` | Fetch from database, add timezone/locale |
| Session state | `session` | Add session tokens, active filters |
| Environment config | `environment` | Add deployment stage, feature flags |
| Database schema cache | `schema_cache` | Pre-load table schemas for SQL tools |
| Business calendar | `business_calendar` | Add fiscal year info, holidays |

### Example: Timezone Enricher

```python
from vanna.core.enricher.base import ToolContextEnricher

class TimezoneEnricher(ToolContextEnricher):
    def __init__(self, user_prefs_db):
        self.db = user_prefs_db

    async def enrich_context(self, context):
        prefs = await self.db.get_user_preferences(context.user.id)
        context.metadata["timezone"] = prefs.get("timezone", "UTC")
        context.metadata["date_format"] = prefs.get("date_format", "YYYY-MM-DD")
        return context
```

Tools can then read `context.metadata["timezone"]` to format dates appropriately.

---

## 5. Conversation Filter

**Source**: `src/vanna/core/filter/base.py`

Conversation filters transform the conversation message history before it is converted into LLM messages. Filters run in list order; output of one filter feeds into the next.

### ABC: `ConversationFilter`

```python
class ConversationFilter(ABC):
    async def filter_messages(
        self, messages: List[Message]
    ) -> List[Message]:
        """Filter and transform conversation messages.

        Receives the full message list from the Conversation object.
        Returns a filtered/transformed list.
        May remove, modify, or reorder messages.
        """
        return messages
```

### Filter Execution in the Agent

Filters run inside `_build_llm_request()`, which is called before every LLM request (including after tool results are appended to the conversation). The filter chain operates on `conversation.messages` and produces the list that gets converted to `LlmMessage` objects for the LLM.

This means filters run **multiple times per conversation turn** if tool calls occur -- once before the initial LLM call, and once before each subsequent call after tool results are added to the conversation.

### Typical Use Cases

| Use Case | Pattern |
|---|---|
| Context window management | Keep only the N most recent messages, or truncate to a token budget |
| Sensitive data removal | Redact PII, credentials, or internal metadata from message content |
| Conversation summarization | Replace old messages with a summary message |
| Deduplication | Remove duplicate or near-duplicate messages |
| Role-based filtering | Remove admin-only messages from non-admin contexts |

### Example: Context Window Filter

```python
from vanna.core.filter.base import ConversationFilter

class ContextWindowFilter(ConversationFilter):
    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    async def filter_messages(self, messages):
        total_tokens = 0
        filtered = []

        # Keep recent messages that fit within the token budget.
        # Iterate in reverse to prioritize the most recent messages.
        for msg in reversed(messages):
            msg_tokens = len(msg.content or "") // 4  # Rough estimate
            if total_tokens + msg_tokens > self.max_tokens:
                break
            filtered.insert(0, msg)
            total_tokens += msg_tokens

        return filtered
```

---

## 6. Error Recovery Strategy

**Source**: `src/vanna/core/recovery/base.py`
**Models**: `src/vanna/core/recovery/models.py`

Error recovery strategies control how the agent responds to failures during tool execution and LLM communication. The default behavior is to fail immediately.

### ABC: `ErrorRecoveryStrategy`

```python
class ErrorRecoveryStrategy(ABC):
    async def handle_tool_error(
        self, error: Exception, context: ToolContext, attempt: int = 1
    ) -> RecoveryAction:
        """Handle errors during tool execution.

        attempt is 1-indexed (first attempt = 1).
        Default: fail immediately.
        """
        return RecoveryAction(
            action=RecoveryActionType.FAIL,
            message=f"Tool error: {str(error)}"
        )

    async def handle_llm_error(
        self, error: Exception, request: LlmRequest, attempt: int = 1
    ) -> RecoveryAction:
        """Handle errors during LLM communication.

        attempt is 1-indexed (first attempt = 1).
        Default: fail immediately.
        """
        return RecoveryAction(
            action=RecoveryActionType.FAIL,
            message=f"LLM error: {str(error)}"
        )
```

### Recovery Models

```python
class RecoveryActionType(str, Enum):
    RETRY = "retry"       # Retry the same operation
    FAIL = "fail"         # Fail and propagate the error
    FALLBACK = "fallback" # Use a fallback value
    SKIP = "skip"         # Skip the failed operation and continue

class RecoveryAction(BaseModel):
    action: RecoveryActionType          # What to do
    retry_delay_ms: Optional[int]       # Delay before retry (RETRY only)
    fallback_value: Optional[Any]       # Value to use (FALLBACK only)
    message: Optional[str]              # Human-readable description of the action
```

### Typical Use Cases

| Use Case | Action Type | Pattern |
|---|---|---|
| Exponential backoff | `RETRY` | Increase `retry_delay_ms` with each attempt |
| Circuit breaker | `FAIL` | Fail fast after N consecutive errors |
| Fallback model | `FALLBACK` | Switch to cheaper/faster LLM on error |
| Skip non-critical tools | `SKIP` | Skip visualization failures, continue with data |
| Alert on failure | `FAIL` | Log to alerting system, then fail |

### Example: Exponential Backoff Strategy

```python
from vanna.core.recovery.base import ErrorRecoveryStrategy
from vanna.core.recovery.models import RecoveryAction, RecoveryActionType

class ExponentialBackoffStrategy(ErrorRecoveryStrategy):
    async def handle_tool_error(self, error, context, attempt=1):
        if attempt < 3:
            delay = (2 ** attempt) * 1000  # 2s, 4s
            return RecoveryAction(
                action=RecoveryActionType.RETRY,
                retry_delay_ms=delay,
                message=f"Retrying after {delay}ms (attempt {attempt})"
            )
        return RecoveryAction(
            action=RecoveryActionType.FAIL,
            message=f"Max retries exceeded: {error}"
        )

    async def handle_llm_error(self, error, request, attempt=1):
        if attempt < 2:
            return RecoveryAction(
                action=RecoveryActionType.RETRY,
                retry_delay_ms=5000,
                message="Retrying LLM request after 5s"
            )
        return RecoveryAction(
            action=RecoveryActionType.FAIL,
            message=f"LLM request failed after retries: {error}"
        )
```

---

## 7. Observability Provider

**Source**: `src/vanna/core/observability/base.py`
**Models**: `src/vanna/core/observability/models.py`

The observability provider collects telemetry data (metrics and distributed traces) from the agent's execution pipeline. A single provider instance is injected; the agent creates spans and records metrics at every major execution point.

### ABC: `ObservabilityProvider`

```python
class ObservabilityProvider(ABC):
    async def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric measurement (counter, gauge, histogram)."""
        pass

    async def create_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        """Create a new tracing span. Call end_span() when complete."""
        return Span(name=name, attributes=attributes or {})

    async def end_span(self, span: Span) -> None:
        """End a span and record/export it. Calls span.end() internally."""
        span.end()
```

### Span Model

```python
class Span(BaseModel):
    id: str                              # Auto-generated UUID
    name: str                            # Operation name
    start_time: float                    # time.time() at creation
    end_time: Optional[float]            # Set by end()
    attributes: Dict[str, Any]           # Key-value metadata
    parent_id: Optional[str]             # For nested/hierarchical spans

    def end(self) -> None: ...                    # Set end_time to now
    def duration_ms(self) -> Optional[float]: ... # (end - start) * 1000
    def set_attribute(self, key, value) -> None: ...
```

### Metric Model

```python
class Metric(BaseModel):
    name: str                 # e.g., "agent.request.duration"
    value: float              # Measurement value
    unit: str                 # e.g., "ms", "tokens", "count"
    tags: Dict[str, str]      # Dimensional labels
    timestamp: float          # time.time() at creation
```

### Spans Created by the Agent

The agent creates spans at these execution points (from `_send_message` and helper methods):

| Span Name | When | Key Attributes |
|---|---|---|
| `agent.user_resolution` | Resolving user from request context | `has_context`, `user_id` |
| `agent.workflow_handler.starter_ui` | Generating starter UI | `user_id`, `has_components`, `component_count` |
| `agent.workflow_handler.try_handle` | Checking workflow handler | `user_id`, `conversation_id`, `should_skip_llm` |
| `agent.send_message` | Entire message processing | `user_id`, `conversation_id`, `tool_iterations`, `hit_tool_limit` |
| `agent.hook.before_message` | Each before_message hook | `hook` (class name), `modified_message` |
| `agent.hook.after_message` | Each after_message hook | `hook` (class name) |
| `agent.hook.before_tool` | Each before_tool hook per tool | `hook`, `tool` |
| `agent.hook.after_tool` | Each after_tool hook per tool | `hook`, `tool`, `modified_result` |
| `agent.conversation.load` | Loading conversation from store | `conversation_id`, `user_id`, `is_new`, `message_count` |
| `agent.conversation.save` | Saving conversation to store | `conversation_id`, `message_count` |
| `agent.conversation.filter` | Each conversation filter | `filter` (class name), `message_count_before`, `message_count_after` |
| `agent.system_prompt.build` | Building system prompt | `tool_count`, `prompt_length` |
| `agent.llm_context.enhance_system_prompt` | Enhancing system prompt | `enhancer` (class name) |
| `agent.llm_context.enhance_user_messages` | Enhancing user messages | `enhancer`, `message_count`, `message_count_after` |
| `agent.tool_schemas.fetch` | Fetching tool schemas for user | `user_id`, `schema_count` |
| `agent.context.enrichment` | Each context enricher | `enricher` (class name) |
| `agent.tool.execute` | Each tool execution | `tool`, `arg_count`, `success`, `error` |
| `agent.middleware.before_llm` | Each middleware before LLM | `middleware` (class name), `stream` |
| `agent.middleware.after_llm` | Each middleware after LLM | `middleware` (class name), `stream` |
| `llm.request` | Non-streaming LLM call | `model`, `stream` |
| `llm.stream` | Streaming LLM call | `model`, `content_length`, `tool_call_count` |
| `agent.send_message.error` | Top-level error handler | `error_type`, `error_message`, `conversation_id` |

### Metrics Recorded by the Agent

| Metric Name | Unit | Tags | Description |
|---|---|---|---|
| `agent.user_resolution.duration` | ms | -- | Time to resolve user identity |
| `agent.workflow_handler.starter_ui.duration` | ms | -- | Time to generate starter UI |
| `agent.hook.duration` | ms | `hook`, `phase` | Time per lifecycle hook execution |
| `agent.conversation.load.duration` | ms | `is_new` | Time to load conversation |
| `agent.conversation.save.duration` | ms | -- | Time to save conversation |
| `agent.system_prompt.duration` | ms | -- | Time to build system prompt |
| `agent.llm_context.enhance_system_prompt.duration` | ms | `enhancer` | Time to enhance system prompt |
| `agent.llm_context.enhance_user_messages.duration` | ms | `enhancer` | Time to enhance user messages |
| `agent.tool_schemas.duration` | ms | `schema_count` | Time to fetch tool schemas |
| `agent.enrichment.duration` | ms | `enricher` | Time per context enricher |
| `agent.tool.duration` | ms | `tool`, `success` | Time per tool execution |
| `agent.filter.duration` | ms | `filter` | Time per conversation filter |
| `agent.middleware.duration` | ms | `middleware`, `phase`, `stream` | Time per middleware execution |
| `llm.request.duration` | ms | -- | Time for non-streaming LLM call |
| `llm.stream.duration` | ms | -- | Time for streaming LLM call |
| `agent.message.duration` | ms | `user_id`, `hit_tool_limit` | Total message processing time |
| `agent.error.count` | count | `error_type` | Error counter |

### Example: Logging Observability Provider

```python
import logging
from vanna.core.observability.base import ObservabilityProvider
from vanna.core.observability.models import Span

logger = logging.getLogger("vanna.observability")

class LoggingObservabilityProvider(ObservabilityProvider):
    async def record_metric(self, name, value, unit="", tags=None):
        logger.info(f"METRIC {name}={value}{unit} tags={tags or {}}")

    async def create_span(self, name, attributes=None):
        span = Span(name=name, attributes=attributes or {})
        logger.debug(f"SPAN START {name} id={span.id}")
        return span

    async def end_span(self, span):
        span.end()
        duration = span.duration_ms()
        logger.debug(
            f"SPAN END {span.name} id={span.id} duration={duration:.1f}ms"
        )
```

### Integration Targets

The observability ABC is designed to integrate with:

- **Prometheus**: Map `record_metric` to counters/histograms; ignore spans or export as exemplars
- **Datadog**: Map both metrics and spans to Datadog APM
- **OpenTelemetry**: Map `Span` to OTel spans, `Metric` to OTel metrics
- **Custom dashboards**: Collect into a time-series database for internal monitoring

---

## Execution Order Summary

The following shows the complete order of extensibility point invocations during a single `send_message` call:

```
1. User Resolution (UserResolver)
2. Starter UI check (WorkflowHandler.get_starter_ui) -- only if empty message
3. Lifecycle Hooks: before_message (all hooks, in order)
4. Conversation Load (ConversationStore)
5. Workflow Handler: try_handle -- may short-circuit and return here
6. Context Enrichers (all enrichers, in order)
7. Tool Schema Fetch (ToolRegistry)
8. System Prompt Build (SystemPromptBuilder)
9. LLM Context Enhancer: enhance_system_prompt (once per turn)

--- Tool Loop (repeats up to max_tool_iterations) ---

10. Conversation Filters (all filters, in order)
11. LLM Context Enhancer: enhance_user_messages (each iteration)
12. LLM Middleware: before_llm_request (all middleware, in order)
13. LLM Call (LlmService.send_request or stream_request)
14. LLM Middleware: after_llm_response (all middleware, in order)

    If response contains tool calls:
    15. Lifecycle Hooks: before_tool (all hooks, per tool call)
    16. Tool Execution (ToolRegistry.execute)
    17. Lifecycle Hooks: after_tool (all hooks, per tool call)
    18. Loop back to step 10

--- End Tool Loop ---

19. Conversation Save (ConversationStore)
20. Lifecycle Hooks: after_message (all hooks, in order)
```

---

## Agent Constructor Reference

All extensibility points are injected via the `Agent` constructor in `src/vanna/core/agent/agent.py`:

```python
from vanna.core.agent.agent import Agent

agent = Agent(
    # Required
    llm_service=my_llm_service,           # LlmService
    tool_registry=my_registry,            # ToolRegistry
    user_resolver=my_resolver,            # UserResolver
    agent_memory=my_memory,               # AgentMemory

    # Optional extensibility points
    lifecycle_hooks=[                     # List[LifecycleHook], default: []
        LoggingHook(),
        QuotaCheckHook(),
    ],
    llm_middlewares=[                     # List[LlmMiddleware], default: []
        CachingMiddleware(),
    ],
    workflow_handler=CommandWorkflow(),    # Optional[WorkflowHandler]
                                          # default: DefaultWorkflowHandler()
    error_recovery_strategy=strategy,     # Optional[ErrorRecoveryStrategy]
                                          # default: None (fail immediately)
    context_enrichers=[                   # List[ToolContextEnricher], default: []
        TimezoneEnricher(db),
    ],
    llm_context_enhancer=enhancer,        # Optional[LlmContextEnhancer]
                                          # default: DefaultLlmContextEnhancer(agent_memory)
    conversation_filters=[                # List[ConversationFilter], default: []
        ContextWindowFilter(),
    ],
    observability_provider=provider,      # Optional[ObservabilityProvider]
                                          # default: None (no telemetry)
)
```

**Defaults when not provided**:
- `workflow_handler`: `DefaultWorkflowHandler()` -- handles `/help`, `/status`, `/memories`, `/delete` commands and provides starter UI
- `llm_context_enhancer`: `DefaultLlmContextEnhancer(agent_memory)` -- searches text memories and injects into system prompt
- All list parameters: empty list (no-op)
- All other `Optional` parameters: `None` (disabled)
