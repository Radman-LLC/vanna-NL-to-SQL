"""Read-only MySQL runner that blocks all write operations.

Wraps MySQLRunner with SQL validation to ensure only read-only queries
(SELECT, SHOW, DESCRIBE, EXPLAIN) are executed. Provides defense-in-depth
with both SQL parsing validation and MySQL session-level read-only mode.
"""

import re
from typing import List

import pandas as pd
import sqlparse

from vanna.capabilities.sql_runner import SqlRunner, RunSqlToolArgs
from vanna.core.tool import ToolContext
from .sql_runner import MySQLRunner


# Whitelist of top-level statement types we allow through.
# Any SQL whose first keyword is not in this set gets rejected.
_ALLOWED_STATEMENTS = frozenset({
    "SELECT",    # Standard data retrieval
    "SHOW",      # MySQL metadata (SHOW TABLES, SHOW DATABASES, etc.)
    "DESCRIBE",  # Table structure inspection
    "DESC",      # Shorthand alias for DESCRIBE
    "EXPLAIN",   # Query execution plan — read-only introspection
})

# Blocklist of keywords that indicate a write/admin operation.
# Checked via word-boundary regex scan of the ENTIRE query body,
# so they catch dangerous keywords even inside subqueries or CTEs
# (e.g., "WITH cte AS (...) DELETE FROM ...").
_BLOCKED_KEYWORDS = frozenset({
    # DML — data modification
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",     # MySQL-specific INSERT-or-UPDATE
    "MERGE",       # Standard SQL upsert
    "UPSERT",      # Non-standard but recognized by some parsers

    # DDL — schema modification
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "RENAME",

    # DCL — access control
    "GRANT",
    "REVOKE",

    # Administrative / dangerous operations
    "LOCK",        # Table locking
    "UNLOCK",      # Table unlocking
    "CALL",        # Stored procedures (could execute arbitrary writes)
    "LOAD",        # LOAD DATA INFILE — bulk file import
    "IMPORT",      # Alternative import syntax
    "SET",         # Session/global variable changes (e.g., SET GLOBAL)
    "KILL",        # Kill other connections
    "FLUSH",       # Flush logs/tables/privileges
    "RESET",       # Reset replication/master/slave state
    "PURGE",       # Purge binary logs
    "HANDLER",     # Low-level row access — bypasses normal SQL engine
    "DO",          # Execute expression (can call functions with side effects)

    # Prepared statements — could be used to construct and execute
    # arbitrary SQL that bypasses our static validation
    "PREPARE",
    "EXECUTE",
    "DEALLOCATE",
})


class ReadOnlyViolationError(Exception):
    """Raised when a query attempts to modify the database."""
    pass


class ReadOnlyMySQLRunner(SqlRunner):
    """MySQL runner that enforces read-only access via defense-in-depth.

    Protection layers:
      Layer 1 (SQL parsing):  Uses sqlparse to strip comments, detect the
              statement type, reject multi-statement queries, and scan for
              blocked keywords anywhere in the query body.
      Layer 2 (MySQL session): Runs SET SESSION TRANSACTION READ ONLY on
              every connection so that even if Layer 1 is somehow bypassed,
              MySQL itself will reject any write operation.
    """

    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        port: int = 3306,
        allowed_statements: List[str] | None = None,
        **kwargs,
    ):
        # Delegate actual connection details to the standard MySQLRunner.
        # We never call _inner.run_sql() directly — we reimplement run_sql()
        # so we can inject the READ ONLY session setting before each query.
        self._inner = MySQLRunner(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
            **kwargs,
        )

        # Allow callers to override the whitelist if needed,
        # otherwise use the module-level defaults.
        self._allowed = (
            frozenset(s.upper() for s in allowed_statements)
            if allowed_statements
            else _ALLOWED_STATEMENTS
        )

        # Expose pymysql so run_sql() can create connections directly
        self.pymysql = self._inner.pymysql

    def validate_sql(self, sql: str) -> None:
        """Validate that a SQL string is read-only.

        Raises ReadOnlyViolationError if the query is empty, contains multiple
        statements, starts with a disallowed keyword, or contains any blocked
        keyword anywhere in its body.
        """
        stripped = sql.strip()
        if not stripped:
            raise ReadOnlyViolationError("Empty SQL query")

        # ── Check 1: Statement-type validation via sqlparse ──────────────
        #
        # strip_comments=True removes /* ... */ and -- ... comments that
        # could be used to hide a malicious statement:
        #   e.g., "/* harmless */ DROP TABLE users"  →  "DROP TABLE users"
        cleaned = sqlparse.format(
            stripped,
            strip_comments=True,
            strip_whitespace=True,
        ).strip()

        if not cleaned:
            raise ReadOnlyViolationError("SQL query is empty after removing comments")

        # Split on semicolons to detect multi-statement injection:
        #   e.g., "SELECT 1; DROP TABLE users"
        statements = sqlparse.parse(cleaned)
        if not statements:
            raise ReadOnlyViolationError("Could not parse SQL query")

        # Reject multi-statement queries entirely — there is no legitimate
        # reason for the LLM to send two statements in one call.
        non_empty = [s for s in statements if s.value.strip()]
        if len(non_empty) > 1:
            raise ReadOnlyViolationError(
                "Multi-statement queries are not allowed. Send one query at a time."
            )

        # Determine the top-level statement type.
        stmt = non_empty[0]
        stmt_type = stmt.get_type()

        # sqlparse returns "UNKNOWN" (not None) for statements it doesn't
        # recognize as standard DML/DDL — including SHOW, DESCRIBE, and
        # EXPLAIN. In those cases, fall back to reading the first non-
        # whitespace, non-comment token as the keyword.
        if stmt_type is None or stmt_type == "UNKNOWN":
            first_token = stmt.token_first(skip_cm=True, skip_ws=True)
            if first_token:
                stmt_type = str(first_token).strip().upper()

        # Reject if the statement type isn't in our whitelist
        if not stmt_type or stmt_type.upper() not in self._allowed:
            raise ReadOnlyViolationError(
                f"Statement type '{stmt_type}' is not allowed. "
                f"Only {', '.join(sorted(self._allowed))} queries are permitted."
            )

        # ── Check 2: Full-body keyword scan ──────────────────────────────
        #
        # Even if the top-level statement is SELECT, the body might contain
        # dangerous operations (e.g., in a CTE or vendor-specific syntax).
        # Normalize to uppercase and collapse whitespace for matching.
        normalized = re.sub(r"\s+", " ", cleaned.upper())

        # Use \b (word boundary) to avoid false positives — e.g., a column
        # named "description" won't trigger the DELETE keyword check.
        for keyword in _BLOCKED_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, normalized):
                raise ReadOnlyViolationError(
                    f"Query contains blocked keyword '{keyword}'. "
                    f"Only read-only operations are permitted."
                )

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame:
        """Execute a SQL query after verifying it is read-only.

        Applies both Layer 1 (SQL parsing) and Layer 2 (MySQL session-level
        read-only mode) before executing the query.

        Raises:
            ReadOnlyViolationError: If the query fails Layer 1 validation
        """
        # Layer 1: Parse and validate the SQL string before it ever reaches
        # the database. This catches the vast majority of violations.
        self.validate_sql(args.sql)

        # Layer 2: Open a fresh connection and immediately set it to
        # read-only mode. Even if a query somehow slipped past Layer 1,
        # MySQL will reject any write attempt with:
        #   ERROR 1792: Cannot execute statement in a READ ONLY transaction.
        conn = self.pymysql.connect(
            host=self._inner.host,
            user=self._inner.user,
            password=self._inner.password,
            database=self._inner.database,
            port=self._inner.port,
            cursorclass=self.pymysql.cursors.DictCursor,
            **self._inner.kwargs,
        )

        try:
            conn.ping(reconnect=True)
            cursor = conn.cursor()

            # This MySQL command makes the entire session read-only.
            # Any INSERT/UPDATE/DELETE/DDL will fail at the database level.
            cursor.execute("SET SESSION TRANSACTION READ ONLY")

            # Safe to execute — both layers have approved
            cursor.execute(args.sql)
            results = cursor.fetchall()

            # Build DataFrame with column names from cursor metadata
            df = pd.DataFrame(
                results,
                columns=[desc[0] for desc in cursor.description]
                if cursor.description
                else [],
            )

            cursor.close()
            return df

        finally:
            # Always close the connection, even if the query fails.
            # Each call gets a fresh connection so there's no shared state.
            conn.close()
