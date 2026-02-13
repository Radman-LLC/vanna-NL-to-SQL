# Integration Development Guide

## Overview

Integrations are pluggable implementations of core abstractions. Each lives in its own directory under `src/vanna/integrations/<name>/` and implements one interface: `LlmService`, `SqlRunner`, or `AgentMemory`.

## Directory Structure

```
src/vanna/integrations/
├── anthropic/          # Claude LLM provider
├── openai/             # GPT LLM provider
├── google/             # Gemini LLM provider
├── azureopenai/        # Azure OpenAI
├── ollama/             # Local Ollama
├── postgres/           # PostgreSQL database
├── mysql/              # MySQL database
├── sqlite/             # SQLite database
├── snowflake/          # Snowflake database
├── bigquery/           # Google BigQuery
├── mssql/              # Microsoft SQL Server
├── oracle/             # Oracle database
├── chromadb/           # ChromaDB vector store
├── qdrant/             # Qdrant vector store
├── pinecone/           # Pinecone vector store
├── faiss/              # FAISS vector store
├── local/              # Built-in implementations
├── mock/               # Mock implementations for testing
└── ...                 # 30+ total providers
```

## Adding an LLM Provider

### Interface

**Location:** `src/vanna/core/llm/base.py`

```python
class LlmService(ABC):
    @abstractmethod
    async def send_request(self, request: LlmRequest) -> LlmResponse: ...

    @abstractmethod
    async def stream_request(self, request: LlmRequest) -> AsyncGenerator[LlmStreamChunk, None]: ...

    @abstractmethod
    async def validate_tools(self, tools: List[Any]) -> List[str]: ...
```

### Steps

1. Create `src/vanna/integrations/<provider>/`
2. Implement `LlmService`:
   - Convert `LlmRequest` messages to provider format
   - Convert `ToolSchema` list to provider's function calling format
   - Convert provider responses back to `LlmResponse` / `LlmStreamChunk`
   - Handle tool call format conversion (provider-specific → `ToolCall` model)
3. Add optional dependency in `pyproject.toml` under `[project.optional-dependencies]`
4. Add sanity test

### Key Considerations

- **Tool call format**: Each provider has different function calling formats. Map between `ToolCall(id, name, arguments)` and the provider's format.
- **Streaming**: Must yield `LlmStreamChunk` objects. Accumulate tool calls across chunks since some providers split them.
- **System prompt**: `LlmRequest.system_prompt` should be placed according to provider conventions.
- **Temperature/max_tokens**: Map from `LlmRequest` fields to provider parameters.

## Adding a Database Provider

### Interface

**Location:** `src/vanna/capabilities/sql_runner/base.py`

```python
class SqlRunner(ABC):
    @abstractmethod
    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame: ...
```

### Steps

1. Create `src/vanna/integrations/<database>/`
2. Implement `SqlRunner`:
   - Handle connection management (pool, per-request, etc.)
   - Execute SQL from `args.sql`
   - Return results as `pd.DataFrame`
   - Handle database-specific error types
3. Add dependency in `pyproject.toml`
4. Add sanity test in `tests/test_database_sanity.py`

### Key Considerations

- **Connection management**: Use connection pooling for production
- **Read-only access**: Consider wrapping with read-only enforcement (see `ReadOnlyMySQLRunner` pattern)
- **Error handling**: Convert database-specific exceptions to meaningful error messages
- **DataFrame conversion**: Ensure column types map correctly to pandas dtypes

## Adding a Vector Store Provider

### Interface

**Location:** `src/vanna/capabilities/agent_memory/base.py`

```python
class AgentMemory(ABC):
    @abstractmethod
    async def save_tool_usage(self, question, tool_name, args, context, success, metadata): ...

    @abstractmethod
    async def save_text_memory(self, content, context) -> TextMemory: ...

    @abstractmethod
    async def search_similar_usage(self, question, context, limit, similarity_threshold, tool_name_filter): ...

    @abstractmethod
    async def search_text_memories(self, query, context, limit, similarity_threshold): ...

    @abstractmethod
    async def get_recent_memories(self, context, limit) -> List[ToolMemory]: ...

    @abstractmethod
    async def get_recent_text_memories(self, context, limit) -> List[TextMemory]: ...

    @abstractmethod
    async def delete_by_id(self, context, memory_id) -> bool: ...

    @abstractmethod
    async def delete_text_memory(self, context, memory_id) -> bool: ...

    @abstractmethod
    async def clear_memories(self, context, tool_name, before_date): ...
```

### Steps

1. Create `src/vanna/integrations/<store>/`
2. Implement `AgentMemory`:
   - Handle vector embedding (use provider's built-in or a separate embedding model)
   - Store tool usage patterns and text memories
   - Implement similarity search with threshold filtering
   - Handle persistence (local directory, cloud service, etc.)
3. Add dependency in `pyproject.toml`
4. Add sanity test in `tests/test_agent_memory_sanity.py`

### Memory Models

- **ToolMemory**: Structured (question, tool_name, arguments, success, timestamp)
- **TextMemory**: Free-form (content, timestamp)
- **ToolMemorySearchResult**: Memory + similarity score
- **TextMemorySearchResult**: Memory + similarity score

## Built-in Implementations

**Location:** `src/vanna/integrations/local/`

| Implementation | Interface | Purpose |
|---------------|-----------|---------|
| `MemoryConversationStore` | `ConversationStore` | In-memory conversation storage |
| `FileSystemConversationStore` | `ConversationStore` | File-based storage |
| `LocalFileSystem` | `FileSystem` | Local filesystem operations |
| `LoggingAuditLogger` | `AuditLogger` | Python logging-based audit |
| `DemoAgentMemory` | `AgentMemory` | Simple in-memory memory for demos |

## Existing Provider Summary

### LLM Providers (Active)
Anthropic (Claude), OpenAI (GPT), Google (Gemini), Azure OpenAI, Ollama, AWS Bedrock

### LLM Providers (Legacy)
Mistral, Cohere, DeepSeek, Qianwen, Qianfan, ZhipuAI, vLLM, Xinference, Hugging Face

### Database Providers
PostgreSQL, MySQL, SQLite, Snowflake, BigQuery, MSSQL, Oracle, ClickHouse, DuckDB, Hive, Presto, Milvus

### Vector Store Providers
ChromaDB, Qdrant, Pinecone, Weaviate, Milvus, FAISS, Marqo, OpenSearch, Azure Search

## Legacy Adapter

**Location:** `src/vanna/legacy/`

The `LegacyVannaAdapter` bridges the Vanna 0.x `VannaBase` API to the 2.0 agent architecture. It contains 30+ legacy integration wrappers.

**Important:** The legacy layer should NOT be modified except for compatibility fixes. New code should use the 2.0 API directly.

## Related Files

- `pyproject.toml` - Optional dependency groups per integration
- `tox.ini` - Test environments per integration
- `tests/test_database_sanity.py` - Database sanity tests
- `tests/test_agent_memory_sanity.py` - Memory backend sanity tests
