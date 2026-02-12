"""Launch Vanna web UI with read-only MySQL + Anthropic.

Starts a FastAPI (or Flask fallback) server with a chat interface at
http://localhost:8000. All SQL queries are protected by 4 defense layers
to ensure the database is never modified.

Usage:
    python run_web_ui.py
"""

import os
import sys


def load_env():
    """Load environment variables from .env and validate required keys exist."""
    from dotenv import load_dotenv

    # override=False means existing env vars take priority over .env values
    load_dotenv(override=False)

    missing = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.getenv("MYSQL_HOST"):
        missing.append("MYSQL_HOST")
    if missing:
        print(f"[error] Missing env vars: {', '.join(missing)}")
        print("       Add them to your .env file.")
        sys.exit(1)


# ── Layer 4: System prompt ───────────────────────────────────────────────
# This is injected as the LLM's system message and is the first thing
# Claude reads. It sets the behavioral boundary for the entire conversation,
# instructing Claude to never generate write queries. Even if a user asks
# Claude to "delete all records", Claude should refuse at this layer.
READ_ONLY_SYSTEM_PROMPT = (
    "You are Vanna, an AI data analyst assistant. "
    "You have READ-ONLY access to a MySQL database.\n\n"
    "CRITICAL RULES:\n"
    "- You may ONLY generate SELECT, SHOW, DESCRIBE, and EXPLAIN queries.\n"
    "- You must NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, "
    "TRUNCATE, or any other query that modifies data or schema.\n"
    "- If the user asks you to modify, insert, update, or delete data, "
    "politely refuse and explain that you only have read-only access.\n"
    "- Never use multi-statement queries (no semicolons separating statements).\n"
)


def create_agent():
    """Create and configure the Vanna Agent with all 4 read-only defense layers."""
    from vanna import Agent, AgentConfig
    from vanna.core.registry import ToolRegistry
    from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder
    from vanna.core.user import UserResolver, User, RequestContext
    from vanna.integrations.anthropic import AnthropicLlmService
    from vanna.integrations.local import LocalFileSystem
    from vanna.integrations.chromadb import ChromaAgentMemory
    from vanna.integrations.mysql import ReadOnlyMySQLRunner
    from vanna.tools import RunSqlTool, VisualizeDataTool
    from vanna.tools.agent_memory import (
        SaveQuestionToolArgsTool,
        SearchSavedCorrectToolUsesTool,
        SaveTextMemoryTool
    )
    from vanna.core.enhancer.memory_enhancer import MemoryBasedEnhancer
    from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook

    # Import domain-specific configuration
    import domain_config

    # ── Layers 1 & 2: ReadOnlyMySQLRunner ────────────────────────────────
    # Layer 1: SQL parsing — validates every query with sqlparse before
    #          execution (blocks writes, multi-statements, comment injection)
    # Layer 2: MySQL session — sets SET SESSION TRANSACTION READ ONLY so
    #          the database itself rejects writes as a last-resort safety net
    mysql = ReadOnlyMySQLRunner(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
    )

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
    print(f"Using model: {model}")
    llm = AnthropicLlmService(model=model)

    # Local filesystem for storing query result CSVs (used by VisualizeDataTool)
    file_system = LocalFileSystem("./vanna_data")

    tools = ToolRegistry()

    # ── Layer 3: Tool description ────────────────────────────────────────
    # The custom_tool_description is sent to the LLM as part of the tool
    # schema. Claude sees this BEFORE generating SQL, so it knows upfront
    # that only read-only queries will be accepted. This reduces the chance
    # of Claude generating a write query that would be rejected by Layer 1.
    tools.register_local_tool(
        RunSqlTool(
            sql_runner=mysql,
            file_system=file_system,
            custom_tool_description=(
                "Execute READ-ONLY SQL queries against the configured MySQL database. "
                "ONLY SELECT, SHOW, DESCRIBE, and EXPLAIN statements are allowed. "
                "INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, and all other write "
                "operations are strictly forbidden and will be rejected."
            ),
        ),
        access_groups=[],  # No group restrictions — all authenticated users can query
    )

    # Visualization tool — generates Plotly charts from query result CSV files.
    # This is read-only by nature (reads CSVs, outputs HTML charts).
    tools.register_local_tool(
        VisualizeDataTool(file_system=file_system), access_groups=[]
    )

    # Agent memory tools — enable continuous learning from successful queries.
    # Users can explicitly save good queries during chat sessions, and the agent
    # can search its memory for similar past queries to improve future responses.

    # SaveQuestionToolArgsTool — saves successful question-SQL patterns
    # Only admins can save to prevent memory pollution from incorrect queries
    tools.register_local_tool(
        SaveQuestionToolArgsTool(),
        access_groups=["admin"]
    )

    # SearchSavedCorrectToolUsesTool — searches memory for similar queries
    # All users can search memory to see what patterns have worked before
    tools.register_local_tool(
        SearchSavedCorrectToolUsesTool(),
        access_groups=[]  # Available to all users
    )

    # SaveTextMemoryTool — saves free-form insights and documentation
    # Only admins can save text memories (e.g., schema changes, new business rules)
    tools.register_local_tool(
        SaveTextMemoryTool(),
        access_groups=["admin"]
    )

    # Simple user resolver — extracts email from the vanna_email cookie set
    # by the web UI's demo login form. Falls back to "dev@local" if no
    # cookie is present (e.g., during development/testing).
    class SimpleUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            email = request_context.cookies.get("vanna_email", "dev@local")
            group = "admin" if email == "admin@example.com" else "user"
            return User(id=email, email=email, group_memberships=[group])

    # Persistent agent memory using ChromaDB — survives server restarts and
    # enables the agent to learn from successful queries over time. The embeddings
    # allow semantic search for similar past queries, improving accuracy.
    agent_memory = ChromaAgentMemory(
        persist_directory="./vanna_memory",
        collection_name="mysql_queries"
    )

    # Memory-based context enhancer — automatically injects relevant past queries
    # into the LLM's system prompt. When a user asks a question, this searches
    # agent memory for the top 5 most similar past questions and includes their
    # SQL as reference examples. This dramatically improves SQL accuracy by showing
    # the LLM proven patterns that work with your specific database schema.
    context_enhancer = MemoryBasedEnhancer(
        max_examples=5,           # Inject up to 5 similar past queries
        similarity_threshold=0.7,  # Only include queries with 70%+ similarity
        include_metadata=False     # Keep injected examples concise
    )

    # Domain-specific system prompt builder — combines read-only rules with
    # database-specific knowledge from domain_config.py. This tells Claude about
    # your business definitions, SQL patterns, performance considerations, and
    # data quality issues, resulting in much more accurate SQL generation.
    # Customize domain_config.py to match your specific database and domain.
    system_prompt_builder = DomainPromptBuilder(
        base_prompt=READ_ONLY_SYSTEM_PROMPT,
        database_type=domain_config.DATABASE_INFO.get("type"),
        database_purpose=domain_config.DATABASE_INFO.get("purpose"),
        business_definitions=domain_config.BUSINESS_DEFINITIONS,
        sql_patterns=domain_config.SQL_PATTERNS,
        performance_hints=domain_config.PERFORMANCE_HINTS,
        data_quality_notes=domain_config.DATA_QUALITY_NOTES,
        additional_context=domain_config.ADDITIONAL_CONTEXT
    )

    # Query logging hook — tracks all SQL queries for monitoring and analytics.
    # Logs are written to vanna_query_log.jsonl as JSON lines for easy parsing.
    # Use this to identify failing queries, track usage patterns, and export
    # successful queries for expanding your training data.
    query_logger = QueryLoggingHook(
        log_file="./vanna_query_log.jsonl",
        log_all_tools=False,  # Only log SQL queries, not other tool executions
        include_result_preview=False  # Set to True to include result snippets
    )

    return Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=SimpleUserResolver(),
        agent_memory=agent_memory,
        llm_context_enhancer=context_enhancer,
        system_prompt_builder=system_prompt_builder,
        lifecycle_hooks=[query_logger],
    )


def main():
    load_env()
    agent = create_agent()

    # Prefer FastAPI (async, better performance) but fall back to Flask
    # if fastapi/uvicorn aren't installed
    try:
        from vanna.servers.fastapi import VannaFastAPIServer

        print("Starting FastAPI server at http://localhost:8000")
        server = VannaFastAPIServer(agent)
        server.run(host="0.0.0.0", port=8000)
    except ImportError:
        from vanna.servers.flask import VannaFlaskServer

        print("Starting Flask server at http://localhost:5000")
        server = VannaFlaskServer(agent)
        server.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
