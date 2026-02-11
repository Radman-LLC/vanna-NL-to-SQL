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
    from vanna.core.system_prompt import DefaultSystemPromptBuilder
    from vanna.core.user import UserResolver, User, RequestContext
    from vanna.integrations.anthropic import AnthropicLlmService
    from vanna.integrations.local import LocalFileSystem
    from vanna.integrations.local.agent_memory import DemoAgentMemory
    from vanna.integrations.mysql import ReadOnlyMySQLRunner
    from vanna.tools import RunSqlTool, VisualizeDataTool

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

    # Simple user resolver — extracts email from the vanna_email cookie set
    # by the web UI's demo login form. Falls back to "dev@local" if no
    # cookie is present (e.g., during development/testing).
    class SimpleUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            email = request_context.cookies.get("vanna_email", "dev@local")
            group = "admin" if email == "admin@example.com" else "user"
            return User(id=email, email=email, group_memberships=[group])

    return Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=SimpleUserResolver(),
        agent_memory=DemoAgentMemory(),  # In-memory store — resets on restart
        # Layer 4: Override default system prompt with our read-only version
        system_prompt_builder=DefaultSystemPromptBuilder(
            base_prompt=READ_ONLY_SYSTEM_PROMPT
        ),
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
