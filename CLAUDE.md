# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Keep this file updated.** When you make architectural changes, add new integrations, or change build/test workflows, update the relevant sections below so future sessions have accurate context.

## Project Overview

Vanna 2.0 is a production-ready framework for natural language to SQL. It uses an agent architecture with tool-based execution, user-aware permissions, streaming UI components, and support for 30+ LLM/database/vector store providers.

Source code lives in `src/vanna/`, tests in `tests/`. Build system is flit (`pyproject.toml`).

## Common Commands

```bash
# Install for development
pip install -e ".[all]"
pip install tox ruff mypy pytest pytest-asyncio

# Run unit tests (no external deps needed)
tox -e py311-unit
# Or directly:
pytest tests/test_tool_permissions.py tests/test_llm_context_enhancer.py tests/test_workflow.py tests/test_memory_tools.py -v

# Run a single test file
pytest tests/test_tool_permissions.py -v

# Run tests by marker (requires API keys / services)
pytest tests/ -v -m anthropic
pytest tests/ -v -m openai

# Formatting and linting (ruff)
ruff format --check src/vanna/ tests/    # check
ruff format src/vanna/ tests/            # fix
ruff check src/vanna/ tests/             # lint
ruff check --fix src/vanna/ tests/       # lint + autofix

# Type checking (strict mode on core dirs)
tox -e mypy

# All checks at once
tox -e ruff && tox -e mypy && tox -e py311-unit
```

## Architecture

### Request Flow

```
Frontend (<vanna-chat> web component)
  → FastAPI/Flask server (SSE streaming endpoint)
    → ChatHandler
      → Agent.send_message()
        → LLM Service (generates tool calls)
          → ToolRegistry (permission check) → Tool.execute()
            → SqlRunner / AgentMemory / FileSystem / etc.
        → Streams UI Components back to frontend
```

### Key Abstractions (all in `src/vanna/core/`)

| Abstraction | Location | Purpose |
|---|---|---|
| **Agent** | `core/agent/agent.py` | Main orchestrator: LLM calls, tool dispatch, conversation management |
| **Tool[T]** | `core/tool/base.py` | Base class for all tools. Generic over Pydantic args model. Declares `access_groups` for permissions |
| **ToolRegistry** | `core/registry.py` | Registers tools, validates user permissions, generates LLM schemas |
| **LlmService** | `core/llm/base.py` | Abstract LLM provider interface with streaming support |
| **SqlRunner** | `capabilities/sql_runner/base.py` | Abstract database execution interface |
| **AgentMemory** | `capabilities/agent_memory/base.py` | RAG-style memory for tool usage patterns |
| **Components** | `components/` | UI components (text, charts, dataframes, cards) streamed to frontend |
| **User / UserResolver** | `core/user/` | User identity + group-based access control |

### Agent Extensibility Points

The Agent accepts these pluggable strategies via constructor injection:
- `lifecycle_hooks` - pre/post message and tool execution hooks
- `llm_middlewares` - intercept/modify LLM requests and responses
- `error_recovery_strategy` - custom failure handling
- `context_enrichers` - add data to tool execution context
- `llm_context_enhancer` - inject RAG/memory into system prompts
- `conversation_filters` - filter conversation history
- `observability_provider` - tracing and metrics

### Integrations (`src/vanna/integrations/`)

Each integration lives in its own subdirectory implementing one of the core abstractions above. LLMs: anthropic, openai, google, ollama, azure, mistral, bedrock, etc. Databases: postgres, mysql, snowflake, bigquery, duckdb, sqlite, oracle, mssql, etc. Vector stores: chromadb, qdrant, faiss, pinecone, weaviate, etc.

### Legacy Layer (`src/vanna/legacy/`)

`LegacyVannaAdapter` bridges the old Vanna 0.x `VannaBase` API to the new 2.0 agent architecture. Legacy code should not be modified unless fixing compatibility issues.

## Code Conventions

- **Async-first**: All agent and tool methods are async. Use `AsyncGenerator` for streaming.
- **Pydantic models**: All tool args, requests, and responses use Pydantic v2 models.
- **Type hints**: Strict mypy. Use `TYPE_CHECKING` to avoid circular imports.
- **Formatting**: Ruff, line-length 88, double quotes.
- **Linting rules**: E, W, F, N, B, C4, SIM (many rules ignored for legacy compat — see `pyproject.toml [tool.ruff.lint]`).
- **Commit messages**: Conventional format — `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- **Test markers**: Use `@pytest.mark.<provider>` for tests requiring external services. `asyncio_mode = "auto"` is configured globally.

### Inline Comments (Required)

Always write inline comments to explain code. Every file you create or modify must include comments that make the code understandable to a new reader.

- **Why, not what**: Comments should explain *why* something is done, not restate what the code already says. `# Increment counter` on `i += 1` is noise; `# Retry up to 3 times because the API is flaky under load` is useful.
- **Non-obvious logic**: Any conditional, loop, regex, or algorithm that isn't immediately self-evident must have a comment explaining its purpose or the edge case it handles.
- **Constants and config values**: Explain what each constant controls and why it has its current value (e.g., `# 10 second timeout — balances responsiveness with slow network conditions`).
- **Module/class/function docstrings**: Every public module, class, and function must have a docstring describing its purpose, parameters, and return values.
- **Security-critical code**: Any code enforcing security boundaries (auth, validation, permissions, SQL filtering) must have detailed comments explaining the threat model and why each check exists.
- **Workarounds and quirks**: If code works around a library bug, API limitation, or non-obvious behavior, comment with the context so future readers know why it's written that way.

### DRY (Don't Repeat Yourself)

Eliminate duplication. If you find yourself writing the same logic in two places, extract it.

- **Extract shared logic**: Repeated code blocks (3+ lines appearing in 2+ places) must be extracted into a function, method, or shared module.
- **Single source of truth**: Configuration values, magic numbers, SQL fragments, error messages, and business rules must be defined once and referenced everywhere else. Use constants, enums, or config objects.
- **Reuse existing abstractions**: Before writing new code, check if the codebase already provides a utility, base class, or pattern that handles the same concern. Prefer composition over reimplementation.
- **Parameterize, don't copy-paste**: When two code paths differ only in a value or small behavior, make the differing part a parameter rather than duplicating the entire block.

### SOLID Principles

Follow SOLID principles to keep the codebase modular and maintainable.

- **Single Responsibility (S)**: Each class and module should have one reason to change. A tool should not also handle authentication. A runner should not also build UI components. If a class does two unrelated things, split it.
- **Open/Closed (O)**: Design for extension without modification. Use abstract base classes (`SqlRunner`, `LlmService`, `AgentMemory`) and constructor injection so new implementations can be added without changing existing code. The `ReadOnlyMySQLRunner` wrapping `MySQLRunner` is an example of this — it extends behavior without modifying the original class.
- **Liskov Substitution (L)**: Any subclass must be usable wherever its parent is expected. If `ReadOnlyMySQLRunner` implements `SqlRunner`, it must honor the `run_sql()` contract (accept `RunSqlToolArgs`, return `pd.DataFrame`). Don't add preconditions or change return types that would break callers.
- **Interface Segregation (I)**: Don't force classes to implement methods they don't need. The codebase already follows this — `SqlRunner`, `AgentMemory`, and `LlmService` are separate interfaces rather than one monolithic base class.
- **Dependency Inversion (D)**: Depend on abstractions, not concrete implementations. `RunSqlTool` takes a `SqlRunner` (abstract), not a `MySQLRunner` (concrete). Agent setup code wires the concrete implementations; the tools themselves only know about interfaces.

## Adding a New Tool

1. Create args model (Pydantic `BaseModel`) and tool class inheriting `Tool[ArgsModel]` in `src/vanna/tools/`.
2. Implement: `name`, `description`, `access_groups`, `get_args_schema()`, `execute(context, args) -> ToolResult`.
3. Register via `ToolRegistry` in agent setup.
4. Add tests.

## Adding a New Integration

1. Create directory under `src/vanna/integrations/<name>/`.
2. Implement the appropriate abstract base: `LlmService`, `SqlRunner`, or `AgentMemory`.
3. Add optional dependency group in `pyproject.toml`.
4. Add sanity test in `tests/test_database_sanity.py` or `tests/test_agent_memory.py`.
5. Add tox environment in `tox.ini`.
