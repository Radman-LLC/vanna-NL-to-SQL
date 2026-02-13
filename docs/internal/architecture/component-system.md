# UI Component System

## Overview

Vanna uses a dual-component system with both Rich and Simple component types. Components are streamed as `AsyncGenerator` from the Agent through the server layer to the frontend `<vanna-chat>` web component.

## UiComponent Wrapper

**Location:** `src/vanna/core/components.py`

`UiComponent` wraps both a rich component and a simple component, with a timestamp for ordering:

```python
UiComponent(
    rich_component=RichTextComponent(content="Hello", markdown=True),
    simple_component=SimpleTextComponent(text="Hello"),
)
```

- `rich_component` - Structured component for advanced rendering
- `simple_component` - Plain text/image/link fallback for simple renderers
- Both are optional but at least one should be provided

## Simple Components

**Location:** `src/vanna/components/simple/`

Minimal text/image/link rendering for basic clients.

| Component | Fields | Purpose |
|-----------|--------|---------|
| `SimpleTextComponent` | `text: str` | Plain text display |
| `SimpleImageComponent` | `url: str` | Image rendering |
| `SimpleLinkComponent` | `url: str, text: str` | Hyperlink |

## Rich Components

**Location:** `src/vanna/components/rich/`

Structured JSON components for advanced frontend rendering. All inherit from `RichComponent` ABC with a `type` field for deserialization.

### Text
- **RichTextComponent** - Rich formatted text with `content` and `markdown` flag

### Data
- **DataFrameComponent** - Structured table rendering from query results
- **ChartComponent** - Plotly chart rendering with chart configuration

### Containers
- **CardComponent** - Card with header, content, footer sections

### Feedback
- **BadgeComponent** - Status badge (success, warning, error, info)
- **NotificationComponent** - Alert/notification messages
- **ProgressBarComponent** - Simple progress display
- **ProgressDisplayComponent** - Detailed progress with steps
- **StatusCardComponent** - Status card with title, value, status, description, icon, metadata
- **IconTextComponent** - Icon + text pair
- **LogViewerComponent** - Log/code display

### Interactive
- **TaskListComponent** - Task list with statuses
- **ButtonComponent** - Clickable button for UI interaction
- **StatusIndicatorComponent** - Status indicator (online, offline, etc.)

### Specialized
- **ArtifactComponent** - Code artifact display with syntax highlighting

## Agent-Internal Components

These components control the chat UI state and are yielded by the Agent during message processing:

| Component | Purpose |
|-----------|---------|
| `StatusBarUpdateComponent` | Update status bar (status: working/idle/error/warning, message, detail) |
| `TaskTrackerUpdateComponent` | Manage task tracking: `add_task(task)`, `update_task(id, status, detail)` |
| `ChatInputUpdateComponent` | Control chat input (placeholder text, disabled flag) |

### Task Model
Used with `TaskTrackerUpdateComponent`:
```python
Task(title="Execute run_sql", description="Running tool with provided arguments", status="pending")
```
Status values: `pending`, `in_progress`, `completed`

## Component Flow

```
1. Tool.execute() returns ToolResult with optional UiComponent
2. Agent yields UiComponents via AsyncGenerator
3. ChatHandler wraps each as ChatStreamChunk (adds conversation_id, request_id)
4. Server serializes to JSON and streams as SSE events
5. Frontend <vanna-chat> web component receives and renders
```

## When to Use Each Component

| Scenario | Component |
|----------|-----------|
| SQL query results | `DataFrameComponent` |
| Chart/visualization | `ChartComponent` |
| Text response from LLM | `RichTextComponent` |
| Tool execution status | `StatusCardComponent` |
| Error display | `StatusCardComponent(status="error")` |
| Progress tracking | `TaskTrackerUpdateComponent` |
| Status bar updates | `StatusBarUpdateComponent` |
| Re-enabling chat input | `ChatInputUpdateComponent` |
| Buttons/quick actions | `ButtonComponent` |
| Code artifacts | `ArtifactComponent` |

## Related Files

- `src/vanna/components/__init__.py` - All component exports
- `src/vanna/components/simple/` - Simple component implementations
- `src/vanna/components/rich/` - Rich component implementations
- `src/vanna/web_components/` - Frontend `<vanna-chat>` Lit web component
