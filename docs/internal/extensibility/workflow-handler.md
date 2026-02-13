# Workflow Handler -- Extensibility Reference

Internal developer documentation for the `WorkflowHandler` extensibility point in the Vanna 2.0 agent architecture. The workflow handler is the first extensibility point in the message processing pipeline, enabling deterministic responses that bypass the LLM entirely.

---

## Table of Contents

1. [Overview](#overview)
2. [WorkflowHandler ABC](#workflowhandler-abc)
3. [WorkflowResult Dataclass](#workflowresult-dataclass)
4. [Agent Integration](#agent-integration)
5. [DefaultWorkflowHandler](#defaultworkflowhandler)
6. [Use Cases and Examples](#use-cases-and-examples)

---

## Overview

**Source**: `src/vanna/core/workflow/base.py`

The `WorkflowHandler` sits between user resolution and LLM processing. When a user sends a message, the agent calls `try_handle()` before adding the message to conversation history or calling the LLM. If the handler returns `should_skip_llm=True`, the agent streams the handler's components directly to the user and skips the entire LLM pipeline.

This is useful for operations where the response is fully deterministic and does not require LLM reasoning -- slash commands, report generation, quota enforcement, onboarding flows, and similar patterns.

### Position in the Pipeline

```
User Message
  -> User Resolution (UserResolver)
  -> Conversation Load
  -> WorkflowHandler.try_handle()    <-- HERE (before LLM)
     |
     +-- should_skip_llm=True  -> Stream components, apply mutation, return
     |
     +-- should_skip_llm=False -> Add message to conversation, continue to LLM
```

The workflow handler also provides the `get_starter_ui()` method, called when the user sends an empty message or the request context has `starter_ui_request=True`. This generates welcome messages, quick-action buttons, and setup guidance.

---

## WorkflowHandler ABC

**Source**: `src/vanna/core/workflow/base.py`

```python
class WorkflowHandler(ABC):
    @abstractmethod
    async def try_handle(
        self,
        agent: Agent,
        user: User,
        conversation: Conversation,
        message: str,
    ) -> WorkflowResult:
        """Attempt to handle a workflow for the given message.

        Called for every user message before it reaches the LLM.
        Inspect message content, user context, and conversation state
        to decide whether to execute a deterministic workflow.

        Args:
            agent: The agent instance. Provides access to:
                   - agent.tool_registry (for tool execution)
                   - agent.config (for configuration)
                   - agent.observability_provider (for tracing)
                   - agent.agent_memory (for memory access)
            user: The resolved user, including:
                  - user.id, user.username, user.email
                  - user.group_memberships (for permission checks)
                  - user.metadata (for custom user data)
            conversation: Current conversation context with message history.
                          Can be inspected for state-based workflows.
            message: The user's raw message content.

        Returns:
            WorkflowResult with should_skip_llm=True to handle the message,
            or should_skip_llm=False to pass through to LLM processing.

        Important:
            When should_skip_llm=True:
            - The message is NOT added to conversation history automatically.
            - The workflow is responsible for managing conversation state
              via the conversation_mutation callback if needed.

            When should_skip_llm=False:
            - The message is added to conversation history by the agent.
            - Normal LLM processing continues.
        """
        pass

    async def get_starter_ui(
        self,
        agent: Agent,
        user: User,
        conversation: Conversation,
    ) -> Optional[List[UiComponent]]:
        """Provide UI components when a conversation starts.

        Called when:
        - The user sends an empty message
        - The request context has starter_ui_request=True

        Args:
            agent: The agent instance
            user: The user starting the conversation
            conversation: The new conversation (typically empty)

        Returns:
            List of UiComponent instances to display, or None for no starter UI.
        """
        return None
```

### Key Design Decisions

- **`try_handle` is abstract**: Every workflow handler must implement it. There is no default behavior for message handling -- even the `DefaultWorkflowHandler` explicitly returns `should_skip_llm=False` for unrecognized messages.
- **`get_starter_ui` has a default no-op**: Returns `None` by default. Override only if you need starter UI.
- **Agent is passed by reference**: The handler has full access to the agent's tool registry, memory, config, and observability. This allows workflows to execute tools, search memory, and create spans.

---

## WorkflowResult Dataclass

**Source**: `src/vanna/core/workflow/base.py`

```python
@dataclass
class WorkflowResult:
    should_skip_llm: bool
    components: Optional[
        Union[List[UiComponent], AsyncGenerator[UiComponent, None]]
    ] = None
    conversation_mutation: Optional[
        Callable[[Conversation], Awaitable[None]]
    ] = None
```

### Fields

| Field | Type | Description |
|---|---|---|
| `should_skip_llm` | `bool` | **Required.** If `True`, the agent skips LLM processing and streams the provided components. If `False`, the agent continues normal processing. |
| `components` | `Optional[Union[List[UiComponent], AsyncGenerator[UiComponent, None]]]` | UI components to stream to the user. Can be a static list or an async generator for streaming. Only used when `should_skip_llm=True`. |
| `conversation_mutation` | `Optional[Callable[[Conversation], Awaitable[None]]]` | Async callback to modify conversation state (e.g., clear messages, add system events). Called after components are streamed but before conversation is saved. |

### Common Patterns

**Simple command response** (static components, no mutation):

```python
WorkflowResult(
    should_skip_llm=True,
    components=[
        UiComponent(
            rich_component=RichTextComponent(
                content="Help text here",
                markdown=True,
            ),
            simple_component=None,
        )
    ],
)
```

**Response with conversation mutation** (e.g., /reset command):

```python
async def clear_history(conversation: Conversation) -> None:
    conversation.messages.clear()

WorkflowResult(
    should_skip_llm=True,
    components=[
        UiComponent(
            rich_component=RichTextComponent(
                content="Conversation reset.",
                markdown=True,
            ),
            simple_component=None,
        )
    ],
    conversation_mutation=clear_history,
)
```

**Streaming response** (async generator for large outputs):

```python
async def generate_report_components():
    yield UiComponent(
        rich_component=RichTextComponent(
            content="Generating report...", markdown=True
        ),
        simple_component=None,
    )
    # ... expensive computation ...
    yield UiComponent(
        rich_component=DataFrameComponent(data=report_df),
        simple_component=None,
    )

WorkflowResult(
    should_skip_llm=True,
    components=generate_report_components(),
)
```

**Not handled -- pass through to LLM**:

```python
WorkflowResult(should_skip_llm=False)
```

---

## Agent Integration

**Source**: `src/vanna/core/agent/agent.py` -- `_send_message` method

### Starter UI Flow

The starter UI path is checked first, before `try_handle`. It activates when:
- The message is empty (whitespace only), OR
- `request_context.metadata["starter_ui_request"]` is `True`

```
Empty message or starter_ui_request=True
  -> Load/create conversation
  -> WorkflowHandler.get_starter_ui(agent, user, conversation)
  -> If components returned:
       Stream components to user
       Yield StatusBarUpdateComponent(status="idle", message="Ready")
       Yield ChatInputUpdateComponent(placeholder="Ask a question...")
       Save conversation if auto_save enabled
       Return (exit without LLM)
  -> If None or error:
       Fall through (exit without LLM for empty messages)
```

Observability: The agent creates an `agent.workflow_handler.starter_ui` span around `get_starter_ui()`, tracking `user_id`, `has_components`, and `component_count`.

### Message Handling Flow

For non-empty messages, `try_handle` runs after conversation loading but **before** the message is added to conversation history:

```
Non-empty message
  -> User resolution
  -> before_message hooks
  -> Load/create conversation
  -> WorkflowHandler.try_handle(agent, user, conversation, message)
     |
     +-- should_skip_llm=True:
     |     Apply conversation_mutation (if provided)
     |     Stream components (list or async generator)
     |     Yield StatusBarUpdateComponent(status="idle", message="Workflow complete")
     |     Yield ChatInputUpdateComponent(placeholder="Ask a question...")
     |     Save conversation if auto_save enabled
     |     Return (exit without LLM)
     |
     +-- should_skip_llm=False:
     |     Add message to conversation
     |     Continue to LLM processing pipeline
     |
     +-- Exception:
           Log error
           Fall through to LLM processing (graceful degradation)
```

Important behavioral details:
- When `should_skip_llm=True`, the **message is NOT added to conversation history**. The workflow owns conversation state management through `conversation_mutation`.
- When `should_skip_llm=False`, the agent adds the message to conversation and proceeds normally.
- If `try_handle` raises an exception, the agent logs the error and falls through to normal LLM processing. Workflow handler errors do not crash the agent.
- The agent automatically appends `StatusBarUpdateComponent` and `ChatInputUpdateComponent` after workflow components to reset the UI state.

Observability: The agent creates an `agent.workflow_handler.try_handle` span, tracking `user_id`, `conversation_id`, and `should_skip_llm`.

---

## DefaultWorkflowHandler

**Source**: `src/vanna/core/workflow/default.py`

The `DefaultWorkflowHandler` is used automatically when no workflow handler is provided to the `Agent` constructor. It handles several built-in slash commands and provides a setup-aware starter UI.

### Built-in Commands

| Command | Aliases | Access | Description |
|---|---|---|---|
| `/help` | `help`, `/h` | All users | Shows available commands and example queries |
| `/status` | `status` | Admin only (`"admin" in user.group_memberships`) | Shows detailed setup health check with tool availability |
| `/memories` | `memories`, `/recent_memories`, `recent_memories` | Admin only | Lists recent tool and text memories with delete buttons |
| `/delete [id]` | -- | Admin only | Deletes a specific memory by ID |

All other messages return `WorkflowResult(should_skip_llm=False)` to continue to LLM processing.

### Admin Access Control

Admin commands check `"admin" in user.group_memberships`. Non-admin users who attempt admin commands receive an "Access Denied" message with a suggestion to contact an administrator. The check is performed per-command, not at the handler level.

### Starter UI Generation

The `get_starter_ui` method generates role-aware welcome content:

**Admin users** receive a `CardComponent` that includes:
- Setup status indicators (SQL, Memory, Visualization)
- Memory management link (if memory tools are configured)
- `/help` button
- Overall system health status (success/warning/error)

**Regular users** receive a `RichTextComponent` with:
- Welcome message (or "Setup Required" if no SQL tool is detected)
- Suggestion to type `/help`

**Custom welcome**: Pass a `welcome_message` string to the constructor to override the auto-generated starter UI with a custom markdown message.

```python
handler = DefaultWorkflowHandler(
    welcome_message="# Welcome\n\nAsk me about sales data!"
)
```

### Setup Analysis

The `_analyze_setup` method inspects available tool names to determine system readiness:

| Check | Tool Names Searched | Status |
|---|---|---|
| SQL (critical) | `run_sql`, `sql_query`, `execute_sql`, `query_sql` | Required for functionality |
| Memory | `search_saved_correct_tool_uses` AND `save_question_tool_args` | Both needed for full memory |
| Visualization | `visualize_data`, `create_chart`, `plot_data`, `generate_chart` | Nice-to-have |
| Calculator | `calculator`, `calc`, `calculate` | Nice-to-have |

The analysis result is a dict with keys: `has_sql`, `has_memory`, `has_search`, `has_save`, `has_viz`, `has_calculator`, `is_complete`, `is_functional`, `tool_count`, `tool_names`.

### `/status` Command Output

The `/status` command generates a comprehensive status report including:
1. Overall status summary (complete, functional, or needs configuration)
2. Tool count and individual tool status indicators
3. `StatusCardComponent` cards for SQL, Memory, and Visualization status
4. Setup guidance with code examples for missing tools

### `/memories` Command Output

The `/memories` command displays recent memories from `AgentMemory`:
1. Calls `agent.agent_memory.get_recent_memories(context, limit=10)` for tool memories
2. Calls `agent.agent_memory.get_recent_text_memories(context, limit=10)` for text memories (gracefully handles `AttributeError`/`NotImplementedError` if not supported)
3. Renders each memory as a `CardComponent` with a delete button (`/delete [memory_id]`)

---

## Use Cases and Examples

### Slash Command Handler

The most common pattern -- intercept messages starting with `/` and return deterministic responses:

```python
from vanna.core.workflow.base import WorkflowHandler, WorkflowResult
from vanna.components import UiComponent, RichTextComponent

class SlashCommandWorkflow(WorkflowHandler):
    async def try_handle(self, agent, user, conversation, message):
        msg = message.strip().lower()

        if msg == "/help":
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    UiComponent(
                        rich_component=RichTextComponent(
                            content="## Commands\n- /help\n- /reset\n- /report",
                            markdown=True,
                        ),
                        simple_component=None,
                    )
                ],
            )

        if msg == "/reset":
            async def clear(conv):
                conv.messages.clear()

            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    UiComponent(
                        rich_component=RichTextComponent(
                            content="Conversation has been reset.",
                            markdown=True,
                        ),
                        simple_component=None,
                    )
                ],
                conversation_mutation=clear,
            )

        # Not a command -- continue to LLM
        return WorkflowResult(should_skip_llm=False)
```

### Pattern-Based Routing with Tool Execution

Execute tools directly from the workflow handler for known patterns, bypassing the LLM's tool selection:

```python
import re
from vanna.core.workflow.base import WorkflowHandler, WorkflowResult
from vanna.core.tool import ToolContext

class ReportWorkflow(WorkflowHandler):
    async def try_handle(self, agent, user, conversation, message):
        # Match "generate [type] report" pattern
        match = re.match(
            r"^(?:/report|generate)\s+(\w+)\s+report$",
            message.strip(),
            re.IGNORECASE,
        )

        if match:
            report_type = match.group(1).lower()
            tool = await agent.tool_registry.get_tool("generate_report")

            if tool:
                context = ToolContext(
                    user=user,
                    conversation_id=conversation.id,
                    request_id="workflow-report",
                    agent_memory=agent.agent_memory,
                )
                result = await tool.execute(
                    context, {"report_type": report_type}
                )

                components = []
                if result.ui_component:
                    components.append(result.ui_component)

                return WorkflowResult(
                    should_skip_llm=True,
                    components=components,
                )

        return WorkflowResult(should_skip_llm=False)
```

### State-Based Workflow (Onboarding)

Use conversation state or user metadata to drive multi-step workflows:

```python
from vanna.core.workflow.base import WorkflowHandler, WorkflowResult
from vanna.components import (
    UiComponent, RichTextComponent, ButtonComponent
)

class OnboardingWorkflow(WorkflowHandler):
    async def try_handle(self, agent, user, conversation, message):
        # Check if user needs onboarding
        if not user.metadata.get("onboarding_complete"):
            step = user.metadata.get("onboarding_step", 1)

            if step == 1:
                return WorkflowResult(
                    should_skip_llm=True,
                    components=[
                        UiComponent(
                            rich_component=RichTextComponent(
                                content=(
                                    "# Welcome to Vanna!\n\n"
                                    "Let me show you how to query your data.\n\n"
                                    "Try asking: **Show me the top 10 customers**"
                                ),
                                markdown=True,
                            ),
                            simple_component=None,
                        )
                    ],
                )

            # Other steps...

        # User is onboarded, pass to LLM
        return WorkflowResult(should_skip_llm=False)
```

### Quota Enforcement

Check usage limits before allowing LLM processing:

```python
from vanna.core.workflow.base import WorkflowHandler, WorkflowResult
from vanna.components import UiComponent, RichTextComponent

class QuotaWorkflow(WorkflowHandler):
    def __init__(self, quota_db):
        self.quota_db = quota_db

    async def try_handle(self, agent, user, conversation, message):
        usage = await self.quota_db.get_daily_usage(user.id)
        limit = await self.quota_db.get_daily_limit(user.id)

        if usage >= limit:
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    UiComponent(
                        rich_component=RichTextComponent(
                            content=(
                                f"## Daily Limit Reached\n\n"
                                f"You've used {usage}/{limit} queries today.\n"
                                f"Your quota resets at midnight UTC."
                            ),
                            markdown=True,
                        ),
                        simple_component=None,
                    )
                ],
            )

        # Under quota, continue to LLM
        return WorkflowResult(should_skip_llm=False)
```

### Starter UI with Role-Based Quick Actions

Generate different starter UI based on user permissions:

```python
from vanna.core.workflow.base import WorkflowHandler, WorkflowResult
from vanna.components import (
    UiComponent, RichTextComponent, CardComponent
)

class CustomStarterWorkflow(WorkflowHandler):
    async def try_handle(self, agent, user, conversation, message):
        return WorkflowResult(should_skip_llm=False)

    async def get_starter_ui(self, agent, user, conversation):
        # Get tools available to this user
        tools = await agent.tool_registry.get_schemas(user)
        tool_names = [t.name for t in tools]

        actions = []
        if "run_sql" in tool_names:
            actions.append({
                "label": "Example Query",
                "action": "Show me the top 10 customers by revenue",
                "variant": "primary",
            })
        if "generate_report" in tool_names:
            actions.append({
                "label": "Sales Report",
                "action": "/report sales",
                "variant": "secondary",
            })

        return [
            UiComponent(
                rich_component=CardComponent(
                    title=f"Welcome, {user.username}",
                    content=(
                        "Ask me anything about your data in plain English."
                    ),
                    icon="👋",
                    status="success",
                    actions=actions,
                    markdown=True,
                ),
                simple_component=None,
            )
        ]
```

---

## Composing Workflow Handlers

Since the `Agent` accepts a single `WorkflowHandler`, you can compose multiple handlers by creating a composite:

```python
from vanna.core.workflow.base import WorkflowHandler, WorkflowResult

class CompositeWorkflowHandler(WorkflowHandler):
    """Chains multiple workflow handlers. First handler to return
    should_skip_llm=True wins."""

    def __init__(self, handlers: list[WorkflowHandler]):
        self.handlers = handlers

    async def try_handle(self, agent, user, conversation, message):
        for handler in self.handlers:
            result = await handler.try_handle(
                agent, user, conversation, message
            )
            if result.should_skip_llm:
                return result
        return WorkflowResult(should_skip_llm=False)

    async def get_starter_ui(self, agent, user, conversation):
        # Use the first handler that returns starter UI
        for handler in self.handlers:
            ui = await handler.get_starter_ui(agent, user, conversation)
            if ui:
                return ui
        return None

# Usage:
agent = Agent(
    llm_service=...,
    tool_registry=...,
    user_resolver=...,
    agent_memory=...,
    workflow_handler=CompositeWorkflowHandler([
        QuotaWorkflow(quota_db),
        OnboardingWorkflow(),
        SlashCommandWorkflow(),
        DefaultWorkflowHandler(),
    ]),
)
```

This pattern allows layering concerns (quota check first, then onboarding, then commands, then default behavior) while maintaining the single-handler interface.
