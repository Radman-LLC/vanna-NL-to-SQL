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

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from vanna.core.lifecycle.base import LifecycleHook

if TYPE_CHECKING:
    from vanna.core.tool.base import ToolResult

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

    For user_id and question to appear in logs, the caller (agent or registry)
    must populate them in the ToolResult metadata dict under the keys
    "user_id" and "question" before the after_tool hook fires.

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
        include_result_preview: bool = False,
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

    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        """Log tool execution after it completes.

        Args:
            result: The result from the tool execution

        Returns:
            None to keep the original result unchanged
        """
        # Tool name and arguments are added to metadata by the registry
        tool_name = result.metadata.get("tool_name")
        if not tool_name:
            # If metadata doesn't have tool_name, skip logging
            return None

        # By default only log run_sql executions to keep log volume manageable.
        # SQL queries are the primary artifact worth tracking for training data
        # and usage analytics. Set log_all_tools=True to capture everything.
        if not self.log_all_tools and tool_name != "run_sql":
            return None

        # Build log entry with all available metadata fields
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "success": result.success,
        }

        # Include user_id and question if the agent/registry populated them
        # in the result metadata. These are needed by analyze_query_log()
        # and export_successful_queries() for user tracking and training export.
        user_id = result.metadata.get("user_id")
        if user_id:
            log_entry["user_id"] = user_id

        question = result.metadata.get("question")
        if question:
            log_entry["question"] = question

        # Add tool arguments from metadata if available
        arguments = result.metadata.get("arguments")
        if arguments:
            log_entry["arguments"] = arguments

        # Add error information if failed
        if not result.success and result.error:
            log_entry["error"] = result.error

        # Optionally include a truncated result preview for debugging.
        # Capped at 100 chars to prevent log bloat from large DataFrames
        # or verbose result strings.
        if self.include_result_preview and result.result_for_llm:
            preview = str(result.result_for_llm)[:100]
            log_entry["result_preview"] = preview

        # Write log entry as JSON line using async I/O to avoid blocking
        # the event loop. File writes are offloaded to a thread pool since
        # aiofiles is not a project dependency and adding one for a single
        # write would be over-engineering.
        try:
            log_line = json.dumps(log_entry) + "\n"
            await asyncio.to_thread(self._write_log_line, log_line)
        except Exception:
            # Swallow write errors to prevent logging failures from crashing
            # the tool execution pipeline. Logging is best-effort — a flaky
            # filesystem or full disk should not break user-facing queries.
            logger.error(f"Failed to write query log to {self.log_file}", exc_info=True)

        # Return None to keep original result unchanged
        return None

    def _write_log_line(self, line: str) -> None:
        """Write a single log line to the log file (synchronous, runs in thread pool).

        Args:
            line: JSON line string to append
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line)


# ═══════════════════════════════════════════════════════════════════════════
# Utility Functions for Log Analysis
# ═══════════════════════════════════════════════════════════════════════════


def analyze_query_log(log_file: str = "./vanna_query_log.jsonl"):
    """Analyze query log and print summary statistics.

    This is a utility function for quick log analysis. Run it periodically
    to understand usage patterns.

    Note: user_id and question fields are only present if the agent/registry
    populates them in ToolResult metadata. If missing, those sections will
    show zero counts.

    Usage:
        python -c "from vanna.core.lifecycle.query_logging_hook import analyze_query_log; analyze_query_log()"
    """
    from collections import Counter

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

    # Avoid division by zero if log is empty
    if total_queries > 0:
        print(
            f"Successful: {successful_queries} ({successful_queries / total_queries * 100:.1f}%)"
        )
        print(f"Failed: {failed_queries} ({failed_queries / total_queries * 100:.1f}%)")
    else:
        print("No queries found in log file")

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
    output_file: str = "./successful_queries.json",
):
    """Export all successful SQL queries to a file for training data.

    This extracts question-SQL pairs from successful queries and saves
    them in a format that can be added to your training library.

    Note: Only entries where both 'question' and 'arguments.sql' are present
    will be exported. If the agent/registry does not populate the 'question'
    field in ToolResult metadata, this function will export zero entries.

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

                # Only export successful SQL queries that have both
                # a user question and the generated SQL — these form
                # the training pairs needed for query library expansion
                if (
                    entry.get("success")
                    and entry.get("tool_name") == "run_sql"
                    and entry.get("question")
                    and entry.get("arguments", {}).get("sql")
                ):
                    successful_pairs.append(
                        {
                            "question": entry["question"],
                            "sql": entry["arguments"]["sql"],
                            "timestamp": entry["timestamp"],
                            "user_id": entry.get("user_id"),
                        }
                    )
            except json.JSONDecodeError:
                continue

    # Write to output file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(successful_pairs, f, indent=2)

    print(f"Exported {len(successful_pairs)} successful queries to {output_file}")
