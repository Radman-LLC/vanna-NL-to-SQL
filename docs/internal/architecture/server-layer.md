# Server and API Layer

## Overview

The server layer provides HTTP endpoints for the Vanna agent. It uses a framework-agnostic `ChatHandler` core with framework-specific adapters for FastAPI and Flask.

## Architecture

```
HTTP Request → FastAPI/Flask Route → ChatHandler → Agent.send_message() → UiComponents
                                                                            ↓
HTTP Response ← SSE Stream ← ChatStreamChunk.from_component() ←────────────┘
```

## ChatHandler

**Location:** `src/vanna/servers/base/chat_handler.py`

Framework-agnostic chat handling logic. Takes an `Agent` instance and provides two response modes:

### Streaming Mode
```python
async def handle_stream(self, request: ChatRequest) -> AsyncGenerator[ChatStreamChunk, None]:
```
Streams `ChatStreamChunk` objects as they are produced by `Agent.send_message()`.

### Polling Mode
```python
async def handle_poll(self, request: ChatRequest) -> ChatResponse:
```
Collects all stream chunks into a single `ChatResponse` via `ChatResponse.from_chunks(chunks)`.

### Conversation ID Generation
New conversations get IDs in the format `conv_{uuid_hex[:8]}` (e.g., `conv_a1b2c3d4`).

## Request/Response Models

**Location:** `src/vanna/servers/base/models.py`

### ChatRequest
```python
class ChatRequest:
    message: str                          # User's message
    conversation_id: Optional[str]        # For multi-turn conversations
    request_context: RequestContext        # Auth info (cookies, headers)
    request_id: Optional[str]             # Client-provided request tracking
```

### ChatStreamChunk
```python
class ChatStreamChunk:
    component: UiComponent     # Streamed UI component
    conversation_id: str       # Conversation identifier
    request_id: str            # Request tracking ID
```
Created via `ChatStreamChunk.from_component(component, conversation_id, request_id)`.

### ChatResponse
Aggregated response for polling mode, created via `ChatResponse.from_chunks(chunks)`.

## RichChatHandler

**Location:** `src/vanna/servers/base/rich_chat_handler.py`

Enhanced handler with rich component support and additional formatting.

## FastAPI Server

**Location:** `src/vanna/servers/fastapi/app.py`, `routes.py`

### VannaFastAPIServer
Factory class that creates a configured FastAPI application:

```python
server = VannaFastAPIServer(agent=agent, config={
    "cors": {"enabled": True, "origins": ["*"]},
    "dev_mode": False,
    "static_folder": "static"
})
app = server.create_app()
```

### Endpoints
- `GET /health` - Health check
- `POST /api/chat` - Chat endpoint (streaming or polling based on `stream` parameter)

### SSE Streaming
The FastAPI server streams responses as Server-Sent Events (SSE). Each event contains a JSON-serialized `ChatStreamChunk`.

## Flask Server

**Location:** `src/vanna/servers/flask/app.py`, `routes.py`

### VannaFlaskServer
Factory class with similar configuration options to the FastAPI variant:

```python
server = VannaFlaskServer(agent=agent, config={...})
app = server.create_app()
```

### Endpoints
- `POST /api/chat` - Chat endpoint

## CLI Server

**Location:** `src/vanna/servers/cli/server_runner.py`

Command-line server runner for development:
- Port configuration
- Agent setup from example configurations
- Entry point via `src/vanna/servers/__main__.py`

## Request Flow Detail

1. HTTP request arrives at FastAPI/Flask endpoint
2. `RequestContext` extracted from headers, cookies, query params
3. `ChatRequest` constructed with message, conversation_id, request_context
4. `ChatHandler.handle_stream(request)` called
5. Handler delegates to `Agent.send_message(request_context, message, conversation_id=...)`
6. Agent resolves user, processes message, yields `UiComponent` objects
7. Each `UiComponent` is wrapped as `ChatStreamChunk.from_component(...)`
8. Chunks serialized to JSON and streamed as SSE events
9. Frontend `<vanna-chat>` web component receives and renders components

## Related Files

- `src/vanna/servers/base/` - Framework-agnostic core
- `src/vanna/servers/fastapi/` - FastAPI implementation
- `src/vanna/servers/flask/` - Flask implementation
- `src/vanna/servers/cli/` - CLI runner
- `src/vanna/web_components/` - Frontend web component
