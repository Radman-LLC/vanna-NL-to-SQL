"""Quick test: verify MySQL connection, read-only guardrails, then ask Vanna a question.

Runs three steps:
  1. Raw PyMySQL connection test (no Vanna) — confirms network connectivity
  2. Read-only guardrail validation — confirms dangerous queries are blocked
  3. Full Vanna Agent test — sends a natural language question through the agent
"""

import asyncio
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


async def test_raw_connection():
    """Step 1: Test raw PyMySQL connection — no Vanna involved.

    Verifies that we can reach the MySQL server, lists all databases,
    and shows tables in the configured database.
    """
    import pymysql

    print("=" * 60)
    print("STEP 1: Testing raw MySQL connection...")
    print("=" * 60)

    # Direct PyMySQL connection using env vars — this bypasses all Vanna
    # abstractions to isolate network/auth issues from framework issues.
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION() AS version")
        row = cursor.fetchone()
        print(f"  Connected! MySQL version: {row['version']}")

        cursor.execute("SHOW DATABASES")
        dbs = [r["Database"] for r in cursor.fetchall()]
        print(f"  Databases: {dbs}")

        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        if tables:
            # The column name varies by MySQL version (e.g., "Tables_in_mydb")
            col = list(tables[0].keys())[0]
            table_names = [r[col] for r in tables]
            print(f"  Tables in '{os.getenv('MYSQL_DATABASE')}': {table_names}")
        else:
            print(f"  No tables in '{os.getenv('MYSQL_DATABASE')}'")

        cursor.close()
    finally:
        conn.close()

    print("  Raw connection test PASSED\n")


async def test_read_only_guardrails():
    """Step 2: Verify that ReadOnlyMySQLRunner blocks all write operations.

    Tests both sides:
      - Dangerous queries (INSERT, UPDATE, DELETE, DROP, etc.) must be BLOCKED
      - Safe queries (SELECT, SHOW, DESCRIBE, EXPLAIN) must be ALLOWED

    This validates Layer 1 (SQL parsing) without touching the database.
    """
    from vanna.integrations.mysql import ReadOnlyMySQLRunner, ReadOnlyViolationError

    print("=" * 60)
    print("STEP 2: Testing read-only guardrails...")
    print("=" * 60)

    # Create a runner — we only call validate_sql() here (no DB connection needed)
    runner = ReadOnlyMySQLRunner(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
    )

    # Each tuple is (label for output, SQL that should be rejected).
    # Covers: direct DML, DDL, DCL, multi-statement injection, and
    # comment-based obfuscation attacks.
    dangerous_queries = [
        ("INSERT", "INSERT INTO users VALUES (1, 'hacked')"),
        ("UPDATE", "UPDATE users SET name='hacked' WHERE id=1"),
        ("DELETE", "DELETE FROM users WHERE id=1"),
        ("DROP TABLE", "DROP TABLE users"),
        ("DROP DATABASE", "DROP DATABASE production"),
        ("ALTER TABLE", "ALTER TABLE users ADD COLUMN hacked INT"),
        ("CREATE TABLE", "CREATE TABLE evil (id INT)"),
        ("TRUNCATE", "TRUNCATE TABLE users"),
        ("GRANT", "GRANT ALL ON *.* TO 'hacker'@'%'"),
        ("Multi-statement", "SELECT 1; DROP TABLE users"),        # Semicolon injection
        ("Comment injection", "/* safe */ DELETE FROM users"),     # Hidden behind comment
        ("SET", "SET GLOBAL max_connections = 1"),                 # Admin variable change
        ("LOAD DATA", "LOAD DATA INFILE '/etc/passwd' INTO TABLE users"),  # File import
        ("CALL", "CALL dangerous_procedure()"),                    # Stored proc execution
    ]

    all_blocked = True
    for label, sql in dangerous_queries:
        try:
            runner.validate_sql(sql)
            # If we get here, the query was NOT blocked — test failure
            print(f"  FAIL: {label} was NOT blocked: {sql}")
            all_blocked = False
        except ReadOnlyViolationError:
            # Expected — query was correctly rejected
            print(f"  BLOCKED: {label}")

    # These read-only queries must pass validation without errors.
    safe_queries = [
        ("SELECT", "SELECT * FROM user LIMIT 5"),
        ("SHOW TABLES", "SHOW TABLES"),
        ("SHOW DATABASES", "SHOW DATABASES"),
        ("DESCRIBE", "DESCRIBE user"),
        ("EXPLAIN", "EXPLAIN SELECT * FROM user"),
    ]

    print()
    all_allowed = True
    for label, sql in safe_queries:
        try:
            runner.validate_sql(sql)
            print(f"  ALLOWED: {label}")
        except ReadOnlyViolationError as e:
            # If we get here, a safe query was incorrectly blocked — test failure
            print(f"  FAIL: {label} was incorrectly blocked: {e}")
            all_allowed = False

    if all_blocked and all_allowed:
        print("\n  Read-only guardrails test PASSED\n")
    else:
        print("\n  Read-only guardrails test FAILED\n")
        sys.exit(1)


async def test_vanna_agent():
    """Step 3: End-to-end test — send a natural language question through the full agent.

    Wires up all 4 defense layers:
      Layer 1: ReadOnlyMySQLRunner SQL parsing (validate_sql)
      Layer 2: MySQL session-level READ ONLY
      Layer 3: Tool description tells LLM only read queries are accepted
      Layer 4: System prompt instructs LLM to never generate write queries
    """
    from vanna import Agent, AgentConfig
    from vanna.core.registry import ToolRegistry
    from vanna.core.system_prompt import DefaultSystemPromptBuilder
    from vanna.core.user import UserResolver, User, RequestContext
    from vanna.integrations.anthropic import AnthropicLlmService
    from vanna.integrations.local.agent_memory import DemoAgentMemory
    from vanna.integrations.mysql import ReadOnlyMySQLRunner
    from vanna.tools import RunSqlTool

    print("=" * 60)
    print("STEP 3: Testing Vanna Agent (Anthropic + MySQL)...")
    print("=" * 60)

    # Layer 1 & 2: ReadOnlyMySQLRunner validates SQL + sets session READ ONLY
    mysql = ReadOnlyMySQLRunner(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
    )

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
    print(f"  Using model: {model}")
    llm = AnthropicLlmService(model=model)

    tools = ToolRegistry()

    # Layer 3: The custom tool description is sent to the LLM as part of
    # the tool schema. This tells Claude what queries are allowed BEFORE
    # it generates any SQL, reducing the chance of blocked queries.
    tools.register_local_tool(
        RunSqlTool(
            sql_runner=mysql,
            custom_tool_description=(
                "Execute READ-ONLY SQL queries against the configured MySQL database. "
                "ONLY SELECT, SHOW, DESCRIBE, and EXPLAIN statements are allowed. "
                "INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, and all other write "
                "operations are strictly forbidden and will be rejected."
            ),
        ),
        access_groups=[],  # No group restrictions — all users can use this tool
    )

    # Layer 4: System prompt — the strongest LLM-level guardrail.
    # This is the first thing Claude reads and sets the behavioral boundary
    # for the entire conversation.
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

    # Minimal user resolver for testing — always returns the same dev user.
    # In production, this would resolve from cookies/JWT/session.
    class SimpleUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            return User(
                id="dev",
                email="dev@local",
                group_memberships=["admin"],
            )

    agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=SimpleUserResolver(),
        agent_memory=DemoAgentMemory(),  # In-memory demo store — no persistence
        config=AgentConfig(stream_responses=False),
        # Override the default system prompt with our read-only version
        system_prompt_builder=DefaultSystemPromptBuilder(
            base_prompt=READ_ONLY_SYSTEM_PROMPT
        ),
    )

    # Simulate a web request context (normally provided by Flask/FastAPI)
    request_context = RequestContext(
        cookies={},
        metadata={"demo": True},
        remote_addr="127.0.0.1",
    )

    question = "What tables are available in this database? List them."
    print(f"  Asking: '{question}'\n")

    # Stream components from the agent — each component is a UI element
    # (text, dataframe, notification, etc.) yielded as it's produced.
    async for component in agent.send_message(
        request_context=request_context,
        message=question,
        conversation_id="test-session",
    ):
        # UiComponent has a simple_component (plain text) and rich_component
        # (dataframes, charts, etc.). We print the simple text version here.
        if hasattr(component, "simple_component") and component.simple_component:
            if hasattr(component.simple_component, "text"):
                # Encode to ASCII to avoid Windows console crashes on emoji
                text = component.simple_component.text.encode("ascii", "replace").decode()
                print(f"  Agent: {text}")
        elif hasattr(component, "content") and component.content:
            text = component.content.encode("ascii", "replace").decode()
            print(f"  Agent: {text}")
        else:
            print(f"  [{type(component).__name__}]")

    print("\n  Vanna agent test PASSED")


async def main():
    load_env()

    await test_raw_connection()       # Step 1: network/auth check
    await test_read_only_guardrails() # Step 2: guardrail validation (no API key needed)
    await test_vanna_agent()          # Step 3: full agent end-to-end

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
