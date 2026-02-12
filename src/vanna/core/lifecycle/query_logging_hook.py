"""Query logging lifecycle hook.

Tracks all SQL queries, user interactions, and tool executions for monitoring,
analytics, and continuous improvement.

Use cases:
- Monitor query patterns and user behavior
- Identify failing queries and error patterns
- Track most common questions and queries
- Build analytics dashboards for usage insights
- Export successful queries for training data expansion
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Any, Dict

from vanna.core.lifecycle.base import LifecycleHook

if TYPE_CHECKING:
    from vanna.core.tool.base import ToolContext, ToolCall, ToolResult
    from vanna.core.llm.models import LlmRequest, LlmResponse

logger = logging.getLogger(__name__)


class QueryLoggingHook(LifecycleHook):
    """Logs all SQL queries and tool executions to a file for analysis.

    This hook captures:
    - User information (ID, email, groups)
    - Question asked
    - SQL generated
    - Success/failure status
    - Error messages
    - Execution timestamps
    - Tool call metadata

    Logs are written as JSON lines (one JSON object per line) for easy
    parsing and analysis with tools like jq, pandas, or log aggregators.

    Args:
        log_file: Path to log file (default: ./vanna_query_log.jsonl)
        log_all_tools: If True, log all tool executions. If False, only
                      log SQL query tool executions. (default: False)
        include_result_preview: If True, include first 100 chars of result
                               in log. (default: False)
    """

    def __init__(
        self,
        log_file: str = "./vanna_query_log.jsonl",
        log_all_tools: bool = False,
        include_result_preview: bool = False
    ):
        self.log_file = Path(log_file)
        self.log_all_tools = log_all_tools
        self.include_result_preview = include_result_preview

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create log file if it doesn't exist
        if not self.log_file.exists():
            self.log_file.touch()
            logger.info(f"Created query log file: {self.log_file}")

    async def post_tool_execution(
        self,
        tool_call: "ToolCall",
        result: "ToolResult",
        context: "ToolContext"
    ) -> None:
        """Log tool execution after it completes.

        Args:
            tool_call: The tool that was executed
            result: The result from the tool
            context: Execution context with user info
        """
        # Filter by tool name if not logging all tools
        if not self.log_all_tools and tool_call.name != "run_sql":
            return

        # Build log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_call.name,
            "user_id": context.user.id if context.user else None,
            "user_email": context.user.email if context.user else None,
            "user_groups": context.user.group_memberships if context.user else [],
            "conversation_id": context.conversation_id,
            "request_id": context.request_id,
            "success": result.success,
        }

        # Add tool arguments (e.g., the SQL query)
        if tool_call.arguments:
            log_entry["arguments"] = tool_call.arguments

        # Add error information if failed
        if not result.success and result.error:
            log_entry["error"] = result.error

        # Optionally include result preview
        if self.include_result_preview and result.result_for_llm:
            preview = str(result.result_for_llm)[:100]
            log_entry["result_preview"] = preview

        # Add any metadata from context
        if context.metadata:
            # Extract question if available
            question = context.metadata.get("question")
            if question:
                log_entry["question"] = question

            # Add any other relevant metadata
            for key in ["conversation_turn", "retry_count"]:
                if key in context.metadata:
                    log_entry[key] = context.metadata[key]

        # Write log entry as JSON line
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write query log: {e}")


class DatabaseQueryLogger(QueryLoggingHook):
    """Extended logger that writes to a database instead of a file.

    This is a template for database-backed logging. Implement the
    _write_to_database method to connect to your database.

    Example databases:
    - SQLite for local development
    - PostgreSQL for production
    - MongoDB for document storage
    - ClickHouse for analytics
    """

    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        table_name: str = "vanna_query_logs",
        **kwargs
    ):
        # Don't create a log file
        super().__init__(log_file="/dev/null", **kwargs)
        self.db_connection_string = db_connection_string
        self.table_name = table_name

    async def post_tool_execution(
        self,
        tool_call: "ToolCall",
        result: "ToolResult",
        context: "ToolContext"
    ) -> None:
        """Log tool execution to database."""
        # Filter by tool name if not logging all tools
        if not self.log_all_tools and tool_call.name != "run_sql":
            return

        # Build log entry (same as parent class)
        log_entry = {
            "timestamp": datetime.utcnow(),
            "tool_name": tool_call.name,
            "user_id": context.user.id if context.user else None,
            "user_email": context.user.email if context.user else None,
            "user_groups": json.dumps(context.user.group_memberships) if context.user else "[]",
            "conversation_id": context.conversation_id,
            "request_id": context.request_id,
            "success": result.success,
            "arguments": json.dumps(tool_call.arguments) if tool_call.arguments else None,
            "error": result.error if not result.success else None,
        }

        # Extract question and SQL for easier querying
        if tool_call.name == "run_sql" and tool_call.arguments:
            log_entry["sql"] = tool_call.arguments.get("sql")

        if context.metadata:
            log_entry["question"] = context.metadata.get("question")

        # Write to database
        try:
            await self._write_to_database(log_entry)
        except Exception as e:
            logger.error(f"Failed to write to database: {e}")

    async def _write_to_database(self, log_entry: Dict[str, Any]) -> None:
        """Write log entry to database.

        Override this method to implement database-specific logic.

        Example for SQLite:
        ```python
        async def _write_to_database(self, log_entry):
            async with aiosqlite.connect(self.db_connection_string) as db:
                await db.execute(
                    f"INSERT INTO {self.table_name} (timestamp, tool_name, user_id, ...) "
                    f"VALUES (?, ?, ?, ...)",
                    tuple(log_entry.values())
                )
                await db.commit()
        ```

        Args:
            log_entry: Dictionary with log data
        """
        raise NotImplementedError(
            "Subclass must implement _write_to_database method"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Utility Functions for Log Analysis
# ═══════════════════════════════════════════════════════════════════════════

def analyze_query_log(log_file: str = "./vanna_query_log.jsonl"):
    """Analyze query log and print summary statistics.

    This is a utility function for quick log analysis. Run it periodically
    to understand usage patterns.

    Usage:
        python -c "from vanna.core.lifecycle.query_logging_hook import analyze_query_log; analyze_query_log()"
    """
    from collections import defaultdict, Counter

    if not Path(log_file).exists():
        print(f"Log file not found: {log_file}")
        return

    total_queries = 0
    successful_queries = 0
    failed_queries = 0
    users = set()
    questions = []
    errors = Counter()
    tools = Counter()

    # Read and parse log file
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                total_queries += 1

                if entry.get("success"):
                    successful_queries += 1
                else:
                    failed_queries += 1
                    error = entry.get("error", "Unknown error")
                    errors[error] += 1

                user_id = entry.get("user_id")
                if user_id:
                    users.add(user_id)

                question = entry.get("question")
                if question:
                    questions.append(question)

                tool = entry.get("tool_name")
                if tool:
                    tools[tool] += 1

            except json.JSONDecodeError:
                continue

    # Print summary
    print("=" * 70)
    print("Vanna Query Log Analysis")
    print("=" * 70)
    print(f"\nTotal queries: {total_queries}")
    print(f"Successful: {successful_queries} ({successful_queries/total_queries*100:.1f}%)")
    print(f"Failed: {failed_queries} ({failed_queries/total_queries*100:.1f}%)")
    print(f"\nUnique users: {len(users)}")

    print(f"\nTool usage:")
    for tool, count in tools.most_common():
        print(f"  {tool}: {count}")

    if errors:
        print(f"\nTop errors:")
        for error, count in errors.most_common(5):
            print(f"  {error[:60]}... : {count}")

    if questions:
        print(f"\nSample questions:")
        for q in questions[:5]:
            print(f"  - {q[:60]}...")

    print("\n" + "=" * 70)


def export_successful_queries(
    log_file: str = "./vanna_query_log.jsonl",
    output_file: str = "./successful_queries.json"
):
    """Export all successful SQL queries to a file for training data.

    This extracts question-SQL pairs from successful queries and saves
    them in a format that can be added to your training library.

    Usage:
        python -c "from vanna.core.lifecycle.query_logging_hook import export_successful_queries; export_successful_queries()"

    Args:
        log_file: Path to query log file
        output_file: Where to write successful queries
    """
    successful_pairs = []

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())

                # Only export successful SQL queries with questions
                if (
                    entry.get("success")
                    and entry.get("tool_name") == "run_sql"
                    and entry.get("question")
                    and entry.get("arguments", {}).get("sql")
                ):
                    successful_pairs.append({
                        "question": entry["question"],
                        "sql": entry["arguments"]["sql"],
                        "timestamp": entry["timestamp"],
                        "user_id": entry.get("user_id")
                    })
            except json.JSONDecodeError:
                continue

    # Write to output file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(successful_pairs, f, indent=2)

    print(f"Exported {len(successful_pairs)} successful queries to {output_file}")
