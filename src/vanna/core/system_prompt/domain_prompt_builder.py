"""Domain-specific system prompt builder.

Extends the base read-only system prompt with customizable domain knowledge,
business rules, and SQL best practices specific to your database.

This allows you to inject expertise about:
- Database schema and structure
- Business logic definitions (churn, active customer, MRR, etc.)
- SQL patterns and conventions for your database
- Performance optimization hints
- Data quality rules and edge cases
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from vanna.core.system_prompt.base import SystemPromptBuilder

if TYPE_CHECKING:
    from ..tool.models import ToolSchema
    from ..user.models import User


class DomainPromptBuilder(SystemPromptBuilder):
    """System prompt builder with domain-specific customization.

    This builder takes a base prompt (e.g., read-only rules) and allows you to
    add domain-specific knowledge sections like database type, business definitions,
    SQL patterns, and performance hints.

    Example:
        ```python
        prompt_builder = DomainPromptBuilder(
            base_prompt=READ_ONLY_SYSTEM_PROMPT,
            database_type="MySQL 8.0",
            database_purpose="E-commerce transaction database",
            business_definitions={
                "churn": "User with no transactions in 90+ days",
                "active_customer": "Transaction in last 30 days"
            },
            sql_patterns=[
                "Always filter test data: WHERE is_test = FALSE",
                "Use table aliases in all JOINs for clarity",
                "Date filtering: Use indexed columns with >= and <"
            ],
            performance_hints=[
                "transactions table is partitioned by month",
                "Always include date range for queries >6 months"
            ]
        )
        ```

    Args:
        base_prompt: Base system prompt (usually read-only rules or base instructions)
        database_type: Type and version of database (e.g., "MySQL 8.0", "PostgreSQL 14")
        database_purpose: Brief description of what this database is for
        business_definitions: Dict of business term definitions
        sql_patterns: List of SQL best practices specific to this database
        performance_hints: List of performance tips and gotchas
        data_quality_notes: List of data quality issues or edge cases to be aware of
        additional_context: Any additional free-form context to include
    """

    def __init__(
        self,
        base_prompt: str,
        database_type: Optional[str] = None,
        database_purpose: Optional[str] = None,
        business_definitions: Optional[Dict[str, str]] = None,
        sql_patterns: Optional[list] = None,
        performance_hints: Optional[list] = None,
        data_quality_notes: Optional[list] = None,
        additional_context: Optional[str] = None
    ):
        self.base_prompt = base_prompt
        self.database_type = database_type
        self.database_purpose = database_purpose
        self.business_definitions = business_definitions or {}
        self.sql_patterns = sql_patterns or []
        self.performance_hints = performance_hints or []
        self.data_quality_notes = data_quality_notes or []
        self.additional_context = additional_context

    async def build_system_prompt(self, user: "User", tools: list["ToolSchema"]) -> Optional[str]:
        """Build the complete system prompt with domain knowledge.

        Args:
            user: The user making the request
            tools: List of tools available to the user

        Returns:
            Complete system prompt string
        """
        # Start with base prompt
        sections = [self.base_prompt]

        # Add database information section
        if self.database_type or self.database_purpose:
            sections.append(self._build_database_info_section())

        # Add business definitions section
        if self.business_definitions:
            sections.append(self._build_business_definitions_section())

        # Add SQL patterns section
        if self.sql_patterns:
            sections.append(self._build_sql_patterns_section())

        # Add performance hints section
        if self.performance_hints:
            sections.append(self._build_performance_section())

        # Add data quality notes section
        if self.data_quality_notes:
            sections.append(self._build_data_quality_section())

        # Add any additional context
        if self.additional_context:
            sections.append(self.additional_context)

        # Join all sections with double newlines
        return "\n\n".join(sections)

    def _build_database_info_section(self) -> str:
        """Build the database information section."""
        section = "DATABASE INFORMATION:"

        if self.database_type:
            section += f"\n- Database Type: {self.database_type}"

        if self.database_purpose:
            section += f"\n- Purpose: {self.database_purpose}"

        return section

    def _build_business_definitions_section(self) -> str:
        """Build the business definitions section."""
        section = "BUSINESS DEFINITIONS:"
        section += "\nWhen users ask about these business concepts, use these definitions:\n"

        for term, definition in self.business_definitions.items():
            section += f"\n- **{term}**: {definition}"

        return section

    def _build_sql_patterns_section(self) -> str:
        """Build the SQL patterns and best practices section."""
        section = "SQL BEST PRACTICES FOR THIS DATABASE:"
        section += "\nAlways follow these patterns when generating SQL:\n"

        for i, pattern in enumerate(self.sql_patterns, 1):
            section += f"\n{i}. {pattern}"

        return section

    def _build_performance_section(self) -> str:
        """Build the performance hints section."""
        section = "PERFORMANCE CONSIDERATIONS:"
        section += "\nBe aware of these performance characteristics:\n"

        for i, hint in enumerate(self.performance_hints, 1):
            section += f"\n{i}. {hint}"

        return section

    def _build_data_quality_section(self) -> str:
        """Build the data quality notes section."""
        section = "DATA QUALITY NOTES:"
        section += "\nBe aware of these data quality issues:\n"

        for i, note in enumerate(self.data_quality_notes, 1):
            section += f"\n{i}. {note}"

        return section


# ═══════════════════════════════════════════════════════════════════════════
# Example Usage and Template
# ═══════════════════════════════════════════════════════════════════════════

def create_example_mysql_prompt(base_prompt: str) -> DomainPromptBuilder:
    """Example: Create a domain prompt for a MySQL e-commerce database.

    This serves as a template showing how to customize the system prompt
    for a specific database and business domain.

    Args:
        base_prompt: Base prompt with read-only rules or core instructions

    Returns:
        Configured DomainPromptBuilder
    """
    return DomainPromptBuilder(
        base_prompt=base_prompt,

        # Database metadata
        database_type="MySQL 8.0",
        database_purpose="E-commerce transaction and customer database",

        # Business term definitions
        business_definitions={
            "churn": "A user is churned if they have no transactions in the last 90 days",
            "active customer": "A customer with at least one completed transaction in the last 30 days",
            "MRR": "Monthly Recurring Revenue - sum of active subscription values",
            "ARPU": "Average Revenue Per User - total revenue divided by unique customers",
            "conversion rate": "Percentage of users who made at least one purchase",
        },

        # SQL best practices
        sql_patterns=[
            "Always filter out test transactions: WHERE is_test = FALSE",
            "Only count completed transactions: AND status = 'completed'",
            "Use table aliases in all JOINs for clarity (users u, transactions t)",
            "For date filtering, use >= and < with indexed columns (not YEAR/MONTH functions)",
            "Use DISTINCT when counting unique users: COUNT(DISTINCT user_id)",
            "Add LIMIT clauses for exploratory queries to avoid large result sets",
        ],

        # Performance tips
        performance_hints=[
            "The transactions table is partitioned by month - include date filters for better performance",
            "Queries spanning more than 6 months may be slow - consider date range limits",
            "user_id and transaction_date are indexed - use them in WHERE clauses",
            "For large aggregations, consider using WITH (CTE) for better readability",
        ],

        # Data quality issues
        data_quality_notes=[
            "Some users have duplicate emails (legacy data) - GROUP BY email when needed",
            "Transaction amounts before 2023-01-01 may have rounding errors",
            "Product names may contain typos - use LIKE with wildcards for searching",
            "NULL in users.region means international user (outside known regions)",
            "Refunds are represented as new rows with negative amounts, not UPDATEs",
        ]
    )


def create_example_snowflake_prompt(base_prompt: str) -> DomainPromptBuilder:
    """Example: Create a domain prompt for a Snowflake data warehouse.

    Args:
        base_prompt: Base prompt with read-only rules or core instructions

    Returns:
        Configured DomainPromptBuilder
    """
    return DomainPromptBuilder(
        base_prompt=base_prompt,

        database_type="Snowflake Data Warehouse",
        database_purpose="Analytics data warehouse with sales, marketing, and product data",

        business_definitions={
            "qualified lead": "Lead with score >= 70 and engagement in last 14 days",
            "customer lifetime value": "Total revenue from a customer across all time",
            "retention rate": "Percentage of customers who made repeat purchases",
        },

        sql_patterns=[
            "Use Snowflake date functions: DATEADD, DATEDIFF, DATE_TRUNC",
            "Leverage CTEs (WITH clauses) for complex queries instead of subqueries",
            "Use QUALIFY for window function filtering instead of nested queries",
            "Schema qualification: Always use schema.table format (SALES.TRANSACTIONS)",
            "Case insensitive: Column names and table names are case-insensitive",
        ],

        performance_hints=[
            "Tables are clustered by date - always include date filters",
            "Use SAMPLE for exploratory queries: SELECT * FROM table SAMPLE (1000 ROWS)",
            "Avoid SELECT * - specify columns to reduce data scanning",
            "LIMIT doesn't improve performance - Snowflake scans full table anyway",
        ],

        data_quality_notes=[
            "Data is updated nightly via ETL - may be up to 24 hours old",
            "Customer IDs can be NULL for anonymous sessions",
            "Revenue figures are in USD, converted from local currencies at transaction time",
        ]
    )
