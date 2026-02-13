# Domain-Specific System Prompt Builder

## Overview

The `DomainPromptBuilder` is a system prompt builder that extends base prompts with customizable domain knowledge, business rules, and SQL best practices specific to your database. This allows you to inject expertise about your database schema, business logic, performance characteristics, and data quality into the LLM's context.

**Location:** `src/vanna/core/system_prompt/domain_prompt_builder.py`

**Purpose:** Teach the LLM about your specific database environment to generate more accurate, optimized, and business-aware SQL queries.

## Key Features

- **Database Information** - Type, version, and purpose of your database
- **Business Definitions** - Domain-specific terms and metrics (churn, MRR, conversion rate, etc.)
- **SQL Best Practices** - Database-specific patterns, conventions, and optimization rules
- **Performance Hints** - Partitioning strategy, indexes, and performance characteristics
- **Data Quality Notes** - Edge cases, gotchas, and known data quality issues
- **Modular Sections** - Only include sections you need, skip the rest

## Why Use Domain Prompts?

Generic SQL generation works for simple queries but struggles with:

- **Business terminology** - LLM doesn't know what "churn" or "MRR" means in your context
- **Database quirks** - MySQL vs PostgreSQL vs Snowflake have different syntax and features
- **Performance patterns** - Doesn't know which columns are indexed or how tables are partitioned
- **Data quality** - Unaware of edge cases like soft deletes, test data, or NULL semantics
- **Conventions** - May generate valid but non-idiomatic SQL for your database

Domain prompts solve this by teaching the LLM your specific database environment.

## Components

### DomainPromptBuilder Class

The main class that builds domain-enhanced system prompts.

**Configuration:**

```python
from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder

prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,  # Base prompt (read-only rules, etc.)
    database_type="MySQL 8.0",
    database_purpose="E-commerce transaction database",
    business_definitions={
        "churn": "User with no transactions in last 90 days",
        "active_customer": "Transaction in last 30 days",
        "ARPU": "Average Revenue Per User - total revenue / unique customers"
    },
    sql_patterns=[
        "Always filter out test transactions: WHERE is_test = FALSE",
        "Use table aliases in JOINs: users u, transactions t",
        "Date filtering: Use >= and < (not YEAR/MONTH functions)"
    ],
    performance_hints=[
        "transactions table is partitioned by month",
        "user_id and transaction_date are indexed"
    ],
    data_quality_notes=[
        "Some users have duplicate emails (legacy data)",
        "Refunds are new rows with negative amounts, not UPDATEs"
    ]
)
```

**Parameters Explained:**

- `base_prompt`: The base system prompt (usually read-only rules or core instructions)
- `database_type`: Type and version (e.g., "MySQL 8.0", "PostgreSQL 14", "Snowflake")
- `database_purpose`: Brief description of what the database is used for
- `business_definitions`: Dictionary of business term definitions (term → definition)
- `sql_patterns`: List of SQL best practices specific to this database
- `performance_hints`: List of performance tips and optimization guidance
- `data_quality_notes`: List of data quality issues, edge cases, gotchas
- `additional_context`: Any additional free-form context to include (optional)

### How It Works

The builder constructs the final system prompt by combining sections:

1. **Base Prompt** - Core instructions and read-only rules
2. **Database Information** - Type and purpose
3. **Business Definitions** - Domain-specific terms (rendered as bold key-value pairs)
4. **SQL Best Practices** - Patterns and conventions (numbered list)
5. **Performance Considerations** - Optimization hints (numbered list)
6. **Data Quality Notes** - Edge cases and gotchas (numbered list)
7. **Memory Workflow Instructions** - Auto-included when memory tools are registered
8. **Additional Context** - Free-form custom content

Sections are only included if they have content (empty sections are skipped).

### Memory Workflow Auto-Inclusion

When memory tools (`search_saved_correct_tool_uses`, `save_question_tool_args`, `save_text_memory`) are registered in the tool list, `DomainPromptBuilder` automatically appends memory workflow instructions to the system prompt. This is handled by the shared `build_memory_workflow_instructions()` function from `src/vanna/core/system_prompt/memory_instructions.py`.

Without these instructions, the LLM would not know to:
- Search memory for similar queries before generating SQL
- Save successful queries for future reference

### Internal Helper: `_build_list_section()`

The `_build_list_section()` method consolidates the repeated pattern used by business definitions, SQL patterns, performance hints, and data quality notes. It accepts:

- `header`: Section header (e.g., `"SQL BEST PRACTICES FOR THIS DATABASE:"`)
- `intro`: Introductory sentence below the header
- `items`: List of items to display
- `numbered`: If `True`, prefix items with `1. 2. 3.` etc. If `False`, items are included as-is

Business definitions use `numbered=False` since they are already formatted as bold key-value pairs. All other sections use `numbered=True`.

### Integration

Add the prompt builder to your agent:

```python
from vanna import Agent, AgentConfig
from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder
from vanna.core.system_prompt import READ_ONLY_SYSTEM_PROMPT

# Import your domain configuration
import domain_config

# Create domain-enhanced prompt builder
prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,
    database_type=domain_config.DATABASE_INFO["type"],
    database_purpose=domain_config.DATABASE_INFO["purpose"],
    business_definitions=domain_config.BUSINESS_DEFINITIONS,
    sql_patterns=domain_config.SQL_PATTERNS,
    performance_hints=domain_config.PERFORMANCE_HINTS,
    data_quality_notes=domain_config.DATA_QUALITY_NOTES,
    additional_context=domain_config.ADDITIONAL_CONTEXT
)

# Create agent with domain prompt builder
agent = Agent(
    config=AgentConfig(...),
    system_prompt_builder=prompt_builder,  # Add here
    ...
)
```

## Example: E-Commerce Database (MySQL)

See `domain_config.py` for a complete example. Here's a condensed version:

```python
from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder
from vanna.core.system_prompt import READ_ONLY_SYSTEM_PROMPT

prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,

    database_type="MySQL 8.0",
    database_purpose="E-commerce order and inventory management system",

    business_definitions={
        "order_balance": "Order total minus sum of successful payments. Formula: orders.total - SUM(transactions.amount WHERE status IN (1,2,4))",
        "gross_margin": "Revenue minus cost of goods. Formula: (price * qty) - total_cost",
        "active_customer": "Customer with at least one completed order in last 30 days"
    },

    sql_patterns=[
        "Use UPPERCASE for SQL keywords: SELECT, FROM, WHERE, JOIN",
        "Use backticks for identifiers: `orders`, `customer_id`",
        "Use table aliases: o=orders, c=customers, od=order_details",
        "For date ranges: WHERE `invoice_date` >= '2024-01-01' AND `invoice_date` < '2024-02-01'",
        "Always exclude ABANDONED (status=1) and CANCELLED (status=11) from sales reports"
    ],

    performance_hints=[
        "orders table: Indexed on id, time, status, customer_id",
        "Use invoice_date for sales reports (NOT time/created_at)",
        "Filter by indexed columns first: customer_id, status, ship_id"
    ],

    data_quality_notes=[
        "Emails starting with '$$' are system-generated placeholders",
        "guest = 1 customers may have incomplete data",
        "Products with deleted_by IS NOT NULL are soft-deleted",
        "ship_id = 0 means no address set (not a valid FK)"
    ]
)
```

## Example: SaaS Analytics (PostgreSQL)

```python
prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,

    database_type="PostgreSQL 14",
    database_purpose="SaaS application usage and billing analytics",

    business_definitions={
        "active_account": "Account with API calls in last 7 days",
        "churned_account": "Canceled subscription, no activity in 30+ days",
        "trial_conversion": "Trial account that upgraded to paid within 14 days",
        "MAU": "Monthly Active Users - unique users with activity this month"
    },

    sql_patterns=[
        "Use EXTRACT for date parts: EXTRACT(MONTH FROM created_at)",
        "Always use lowercase table/column names (PostgreSQL convention)",
        "Use CTEs for complex queries instead of subqueries",
        "Add explicit column names in SELECT (no SELECT *)"
    ],

    performance_hints=[
        "events table is partitioned by date - always filter by date",
        "Use EXPLAIN ANALYZE for complex queries",
        "Indexes exist on: user_id, account_id, created_at"
    ],

    data_quality_notes=[
        "Events before 2024-01-01 are sampled (not complete)",
        "Deleted accounts have soft delete: deleted_at IS NOT NULL",
        "User IDs can be NULL for anonymous events"
    ]
)
```

## Example: Data Warehouse (Snowflake)

```python
prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,

    database_type="Snowflake Data Warehouse",
    database_purpose="Enterprise analytics with sales, marketing, product data",

    business_definitions={
        "qualified_lead": "Lead with score >= 70 and engagement in last 14 days",
        "customer_LTV": "Total revenue from customer across all time",
        "retention_rate": "Percentage of customers with repeat purchases"
    },

    sql_patterns=[
        "Use schema.table format: SALES.TRANSACTIONS",
        "Snowflake date functions: DATEADD, DATEDIFF, DATE_TRUNC",
        "Leverage CTEs (WITH) for readability",
        "Use QUALIFY for window function filtering"
    ],

    performance_hints=[
        "Tables are clustered by date - include date filters",
        "Use SAMPLE for exploration: SELECT * FROM t SAMPLE (1000 ROWS)",
        "Avoid SELECT * - specify columns to reduce scanning"
    ],

    data_quality_notes=[
        "Data updated nightly via ETL (up to 24 hours old)",
        "Revenue in USD, converted from local currencies",
        "Customer IDs can be NULL for anonymous sessions"
    ]
)
```

## Configuration File Pattern

The recommended pattern is to create a `domain_config.py` file at the project root:

```python
# domain_config.py

DATABASE_INFO = {
    "type": "MySQL 8.0",
    "purpose": "Order management and inventory system"
}

BUSINESS_DEFINITIONS = {
    "churn": "User with no activity in 90+ days",
    "active_customer": "User with transaction in last 30 days"
}

SQL_PATTERNS = [
    "Always filter test data: WHERE is_test = FALSE",
    "Use table aliases for readability"
]

PERFORMANCE_HINTS = [
    "orders table is partitioned by month",
    "Always include date range for queries >6 months"
]

DATA_QUALITY_NOTES = [
    "Some products have NULL in category field",
    "Refunds are negative transaction amounts"
]

ADDITIONAL_CONTEXT = """
Custom context or notes here.
"""
```

Then import and use in your agent setup:

```python
import domain_config

prompt_builder = DomainPromptBuilder(
    base_prompt=READ_ONLY_SYSTEM_PROMPT,
    database_type=domain_config.DATABASE_INFO["type"],
    database_purpose=domain_config.DATABASE_INFO["purpose"],
    business_definitions=domain_config.BUSINESS_DEFINITIONS,
    sql_patterns=domain_config.SQL_PATTERNS,
    performance_hints=domain_config.PERFORMANCE_HINTS,
    data_quality_notes=domain_config.DATA_QUALITY_NOTES,
    additional_context=domain_config.ADDITIONAL_CONTEXT
)
```

**Benefits of Config File:**

- Easy to customize without code changes
- Version control friendly
- Can be environment-specific (dev, staging, prod)
- Easy to share across team members

## Generated Prompt Format

Here's what the final prompt looks like:

```
[Base prompt content here - read-only rules, etc.]

DATABASE INFORMATION:
- Database Type: MySQL 8.0
- Purpose: E-commerce transaction and customer database

BUSINESS DEFINITIONS:
When users ask about these business concepts, use these definitions:

- **churn**: User with no transactions in the last 90 days
- **active customer**: Customer with completed transaction in last 30 days
- **MRR**: Monthly Recurring Revenue - sum of active subscription values

SQL BEST PRACTICES FOR THIS DATABASE:
Always follow these patterns when generating SQL:

1. Always filter out test transactions: WHERE is_test = FALSE
2. Only count completed transactions: AND status = 'completed'
3. Use table aliases in JOINs: users u, transactions t

PERFORMANCE CONSIDERATIONS:
Be aware of these performance characteristics:

1. transactions table is partitioned by month
2. Always include date filters for better performance
3. user_id and transaction_date are indexed

DATA QUALITY NOTES:
Be aware of these data quality issues:

1. Some users have duplicate emails - GROUP BY email when needed
2. Refunds are new rows with negative amounts, not UPDATEs
3. NULL in region means international user
```

## Best Practices

### 1. Start Simple, Add Incrementally

Don't try to document everything upfront. Start with:

1. Database type and purpose
2. 3-5 most important business definitions
3. 5-10 critical SQL patterns
4. Top 3 performance hints
5. Top 3 data quality issues

Add more as you identify gaps in query accuracy.

### 2. Focus on What's Unique

Don't document general SQL knowledge (the LLM already knows `SELECT * FROM table`). Focus on:

- **Database-specific syntax** - MySQL `LIMIT` vs SQL Server `TOP`
- **Business terminology** - What does "churn" mean in YOUR business?
- **Schema conventions** - How you name tables, use soft deletes, handle test data
- **Performance gotchas** - Specific to your table sizes and partitioning

### 3. Use Concrete Examples

Instead of:
```
"Use date filtering best practices"
```

Write:
```
"Date filtering: Use >= and < with indexed columns (not YEAR/MONTH functions).
Example: WHERE transaction_date >= '2024-01-01' AND transaction_date < '2024-02-01'"
```

### 4. Keep It Current

Update domain config as your database evolves:

- New tables or columns added
- Business definitions change
- Performance characteristics shift
- New data quality issues discovered

### 5. Test with Real Queries

After adding domain knowledge, test with actual user questions:

```python
# Before domain prompt
"Show me churned users" → Generic SQL, may be wrong

# After domain prompt with churn definition
"Show me churned users" → Correct SQL using your churn definition
```

### 6. Don't Duplicate Training Data

Domain prompts should provide **context and rules**, not examples. Use training data (agent memory) for query examples. Domain prompts tell the LLM **how** to write queries, training data shows **what** queries to write.

## Performance Impact

- **Prompt size increase** - ~500-2000 tokens depending on customization
- **LLM cost increase** - Proportional to prompt size (~$0.001-$0.005 per query)
- **Accuracy improvement** - 20-40% fewer errors on domain-specific queries
- **User satisfaction** - Queries feel more "natural" and business-aware

The cost increase is usually worth it for improved accuracy.

## Troubleshooting

### Issue: LLM Ignores Domain Rules

**Symptom:** LLM generates SQL that violates documented patterns.

**Solutions:**

1. Make rules more explicit and emphatic ("ALWAYS", "NEVER", "CRITICAL")
2. Move most important rules to top of each section
3. Reduce prompt size - LLM may lose focus with very long prompts
4. Add examples to training data that demonstrate the rules

### Issue: Prompt Too Long

**Symptom:** Token limit exceeded or high costs.

**Solutions:**

1. Prioritize - keep only the most impactful rules
2. Remove redundant or obvious patterns
3. Consolidate similar rules into single entries
4. Use `additional_context` only when necessary

### Issue: Business Definitions Not Applied

**Symptom:** LLM asks for clarification on terms defined in prompt.

**Solutions:**

1. Make definitions more prominent - use bold or uppercase
2. Add examples: "churn: User with no activity in 90+ days. Example: SELECT * FROM users WHERE last_activity < NOW() - INTERVAL 90 DAY"
3. Add the same terms to training data queries

## Related Components

- `SystemPromptBuilder` (`src/vanna/core/system_prompt/base.py`) - Base interface
- `READ_ONLY_SYSTEM_PROMPT` (`src/vanna/core/system_prompt/`) - Base read-only rules
- `domain_config.py` - Configuration file for domain knowledge (project root)
- `Agent` (`src/vanna/core/agent/agent.py`) - Uses system_prompt_builder parameter

## Helper Functions

### create_example_mysql_prompt()

Creates a complete example configuration for a MySQL e-commerce database.

**Usage:**

```python
from vanna.core.system_prompt.domain_prompt_builder import create_example_mysql_prompt
from vanna.core.system_prompt import READ_ONLY_SYSTEM_PROMPT

prompt_builder = create_example_mysql_prompt(READ_ONLY_SYSTEM_PROMPT)
```

This is useful as a starting template - customize it for your specific database.

### create_example_snowflake_prompt()

Creates a complete example configuration for a Snowflake data warehouse.

**Usage:**

```python
from vanna.core.system_prompt.domain_prompt_builder import create_example_snowflake_prompt
from vanna.core.system_prompt import READ_ONLY_SYSTEM_PROMPT

prompt_builder = create_example_snowflake_prompt(READ_ONLY_SYSTEM_PROMPT)
```

## Related Architecture

- **`SystemPromptBuilder`** (`src/vanna/core/system_prompt/base.py`) - Abstract base class that `DomainPromptBuilder` implements
- **`DefaultSystemPromptBuilder`** (`src/vanna/core/system_prompt/default.py`) - Simpler alternative without domain knowledge
- **`memory_instructions`** (`src/vanna/core/system_prompt/memory_instructions.py`) - Shared module for memory workflow instructions, used by both `DomainPromptBuilder` and `DefaultSystemPromptBuilder`
- **`LlmContextEnhancer`** (`src/vanna/core/enhancer/`) - Complements the system prompt by injecting RAG-based context from AgentMemory at runtime
- **`domain_config.py`** (project root) - Configuration file containing domain knowledge

## Future Enhancements

Potential improvements:

1. **Auto-generation from schema** - Parse database schema and auto-generate patterns
2. **Multi-database support** - Different prompts for different databases in same agent
3. **User-specific customization** - Different rules for different user roles
4. **Dynamic updates** - Reload domain config without restarting agent
5. **Validation** - Lint domain config for common issues (duplicates, conflicts)
6. **Prompt compression** - Intelligent summarization to reduce token usage
