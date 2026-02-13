# Domain Configuration Guide

## Overview

The `domain_config.py` file is the central configuration file for customizing Vanna's SQL generation to your specific database environment. It defines database characteristics, business logic, SQL conventions, performance hints, and data quality rules that are injected into the LLM's system prompt.

**Location:** `domain_config.py` (project root)

**Used By:** `DomainPromptBuilder` in `run_web_ui.py` and other agent setup code

**Purpose:** Teach the LLM about your database without modifying code - just update the config file.

## File Structure

The configuration file contains several dictionaries and lists:

```python
# Database metadata
DATABASE_INFO = {
    "type": "MySQL 8.0",
    "purpose": "Description of what the database is used for"
}

# Business term definitions (dict of term → definition)
BUSINESS_DEFINITIONS = {
    "term": "definition",
    ...
}

# SQL patterns and best practices (list of strings)
SQL_PATTERNS = [
    "Pattern or rule description",
    ...
]

# Performance optimization hints (list of strings)
PERFORMANCE_HINTS = [
    "Performance tip or characteristic",
    ...
]

# Data quality issues and edge cases (list of strings)
DATA_QUALITY_NOTES = [
    "Edge case or data quality issue",
    ...
]

# Optional additional context (string)
ADDITIONAL_CONTEXT = """
Free-form text for any additional context.
"""
```

## Sections Explained

### 1. DATABASE_INFO

Basic metadata about your database.

**Fields:**

- `type`: Database type and version (e.g., "MySQL 8.0", "PostgreSQL 14", "Snowflake")
- `purpose`: Brief description of what the database is used for (1-2 sentences)

**Example:**

```python
DATABASE_INFO = {
    "type": "MySQL 5.6.10+ (InnoDB)",
    "purpose": "ADR/Zangerine ERP system - order management, inventory, purchasing, customer relationship management"
}
```

**Why This Matters:**

The LLM uses database type to determine:

- SQL dialect and syntax (MySQL vs PostgreSQL vs Snowflake)
- Available functions (MySQL `DATE_ADD` vs PostgreSQL `INTERVAL`)
- Feature support (window functions, CTEs, JSON operators)

### 2. BUSINESS_DEFINITIONS

Domain-specific business terms and metrics that users will ask about.

**Format:** Dictionary with `term` → `definition` (both strings)

**Example:**

```python
BUSINESS_DEFINITIONS = {
    "order_balance": "Order total minus the sum of all successful transaction amounts (status IN 1,2,4). Formula: orders.total - SUM(transaction_log.amount WHERE type='order' AND (status=1 OR status=2 OR status=4))",

    "gross_margin": "Revenue minus cost of goods sold. For order details: (price * qty) - total_cost. Can be expressed as dollar amount or percentage.",

    "active_customer": "Customer with at least one completed order in last 30 days",

    "churn": "User with no activity in the last 90 days"
}
```

**Guidelines:**

- **Be specific** - Include formulas, table references, column names
- **Avoid ambiguity** - "Active customer" could mean many things, define it precisely
- **Include calculation logic** - Show exactly how to compute the metric
- **Use your schema** - Reference actual table and column names from your database

**What to Include:**

- Business metrics (revenue, profit, churn, conversion rate)
- Customer lifecycle states (active, churned, trial, paid)
- Order/transaction states (pending, completed, refunded)
- Domain-specific concepts (dropship, fulfillment, recurring profile)

### 3. SQL_PATTERNS

SQL conventions, best practices, and patterns specific to your database.

**Format:** List of strings (each string is one rule or pattern)

**Example:**

```python
SQL_PATTERNS = [
    # Formatting conventions
    "Use UPPERCASE for all SQL keywords: SELECT, FROM, WHERE, JOIN, GROUP BY, ORDER BY",
    "Use backticks around table and column names: `orders`, `customer_id`",
    "Use table aliases for readability: o=orders, c=customers, od=order_details",

    # Date handling
    "Use invoice_date (not time/created_at) for sales reports and date-based queries",
    "For date ranges: WHERE `invoice_date` >= '2024-01-01' AND `invoice_date` < '2024-02-01'",
    "Use DATE_SUB(CURDATE(), INTERVAL N MONTH) for relative date ranges",

    # Status filtering
    "Always exclude ABANDONED (status=1) and CANCELLED (status=11) from sales reports",
    "For accounts receivable, also exclude REFUNDED (status=12)",

    # JOIN patterns
    "Use INNER JOIN when relationship is required (order_details to orders)",
    "Use LEFT JOIN for optional relationships (orders to coupons)",

    # NULL handling
    "Use IFNULL(value, 0) for numeric aggregations that may be NULL",
    "Use TRIM(CONCAT(fname, ' ', lname)) for name display to handle empty values"
]
```

**Categories to Cover:**

- **Keywords & Formatting** - Uppercase SQL, backticks, aliases
- **Date Filtering** - Which date columns to use, date range syntax
- **Status Filtering** - How to handle order/transaction statuses
- **JOIN Patterns** - INNER vs LEFT JOIN conventions
- **NULL Handling** - How to handle NULLs in your specific schema
- **Performance** - Use LIMIT, filter by indexed columns
- **Data Integrity** - Soft deletes, test data filtering, guest accounts

**Best Practices:**

- **Be prescriptive** - "Use X" not "Consider using X"
- **Include examples** - Show the pattern in action
- **Explain WHY** - "Use >= and < (not YEAR/MONTH functions)" → better because indexed columns
- **Database-specific** - Focus on patterns unique to YOUR database, not general SQL

### 4. PERFORMANCE_HINTS

Performance characteristics, optimization tips, and index information.

**Format:** List of strings (each string is one hint)

**Example:**

```python
PERFORMANCE_HINTS = [
    "orders table: Indexed on id, time, status, customer_id, ship_id, bill_id",
    "customers table: Indexed on id, email, phone, fname, lname, company_id",

    "invoice_date is NOT indexed - use date ranges to limit scan",
    "The time column on orders IS indexed - prefer it when exact creation date is acceptable",

    "Transaction log queries should always filter by type='order' to use segmented data efficiently",
    "For large date ranges (>12 months), consider aggregating by month first then summing",

    "LEFT JOIN to subqueries (e.g., transaction totals) is more efficient than correlated subqueries",
    "products_stock may have many rows per product - always SUM(qty) with GROUP BY"
]
```

**What to Include:**

- **Index information** - Which columns are indexed on key tables
- **Partitioning** - How tables are partitioned (by date, by key)
- **Table sizes** - Large tables that need careful querying
- **Query patterns** - Which patterns are fast vs slow
- **Aggregation tips** - How to efficiently aggregate large datasets
- **JOIN optimization** - Which JOIN patterns are efficient

**Why This Matters:**

The LLM will use these hints to:

- Filter by indexed columns first
- Include date ranges on partitioned tables
- Avoid expensive operations on large tables
- Choose efficient JOIN strategies

### 5. DATA_QUALITY_NOTES

Known data quality issues, edge cases, and gotchas.

**Format:** List of strings (each string is one note)

**Example:**

```python
DATA_QUALITY_NOTES = [
    "Customer emails starting with '$$' are system-generated placeholders for customers without real emails",
    "guest = 1 customers may have incomplete data (no real email, limited address info)",

    "order.time is creation timestamp; invoice_date may be NULL for draft/abandoned orders",
    "Products with deleted_by IS NOT NULL are soft-deleted but still referenced by historical order_details",

    "ship_id = 0 and bill_id = 0 mean no address set (not a valid FK) - handle in JOINs",
    "coupon_id = 0 means no coupon (not NULL) - the system uses use_zero_for_null pattern",

    "Some older orders (before 2019-11-01) use standard cost calculation regardless of inventory_type_id",
    "The extras column in orders is serialized PHP data - do not parse in SQL"
]
```

**What to Include:**

- **Sentinel values** - Special values like 0, '$$', NULL that mean something specific
- **Soft deletes** - How deleted records are marked
- **Data migration artifacts** - Historical data quirks from migrations
- **Invalid foreign keys** - Places where FK = 0 means "none" instead of referencing ID 0
- **Serialized data** - Columns containing JSON, PHP serialize, etc. that shouldn't be parsed
- **Test data markers** - How to identify and filter test/demo data
- **Duplicate handling** - Known duplicate issues (emails, names, etc.)

**Why This Matters:**

The LLM will use these notes to:

- Filter out test/placeholder data
- Handle soft deletes correctly
- Account for edge cases in WHERE clauses
- Avoid parsing unparseable columns

### 6. ADDITIONAL_CONTEXT (Optional)

Free-form text for any additional context that doesn't fit in other sections.

**Format:** Multi-line string

**Example:**

```python
ADDITIONAL_CONTEXT = """
IMPORTANT: When calculating order balances, only count transactions with
status IN (1, 2, 4). Status meanings:
- 1 = Pending (counted toward balance)
- 2 = Succeeded (counted toward balance)
- 3 = Failed (NOT counted)
- 4 = Refunded (counted toward balance)

The commission system links through commission_period table, not directly
to orders.sales_rep. Use this JOIN pattern:
  FROM orders o
  JOIN commission_period cp ON o.sales_rep = cp.sales_rep_user
  WHERE cp.period_start <= o.invoice_date
    AND cp.period_end >= o.invoice_date
"""
```

**When to Use:**

- Complex logic that requires explanation
- Multi-step instructions
- Join patterns that are hard to express concisely
- Schema relationships that need clarification

## Examples from domain_config.py

The included `domain_config.py` contains a complete ADR/Zangerine ERP configuration plus three reference examples:

### Example 1: E-Commerce (MySQL)

Commented out at bottom of file - shows patterns for a typical e-commerce database:

- Filtering test transactions
- Handling completed vs pending orders
- User churn definitions
- Revenue calculations

### Example 2: SaaS Analytics (PostgreSQL)

Commented out at bottom of file - shows patterns for SaaS metrics:

- Monthly Active Users (MAU)
- Trial conversion tracking
- Account churn definitions
- PostgreSQL-specific patterns (EXTRACT, lowercase conventions)

### Example 3: Data Warehouse (Snowflake)

Commented out at bottom of file - shows patterns for enterprise analytics:

- Customer lifetime value
- Qualified lead definitions
- Snowflake-specific functions (DATEADD, DATE_TRUNC, QUALIFY)
- Clustered table optimization

You can uncomment and customize any of these as a starting point.

## Customization Workflow

### Step 1: Fill in Database Info

```python
DATABASE_INFO = {
    "type": "MySQL 8.0",  # Your database type and version
    "purpose": "What is this database used for?"  # 1-2 sentence description
}
```

### Step 2: Add Business Definitions

Start with your top 5-10 most common business terms:

```python
BUSINESS_DEFINITIONS = {
    "revenue": "Sum of completed transaction amounts. Formula: SUM(amount WHERE status='completed')",
    "active_customer": "Customer with transaction in last 30 days",
    # Add more...
}
```

### Step 3: Document SQL Patterns

Focus on patterns unique to your database:

```python
SQL_PATTERNS = [
    "Always filter test data: WHERE is_test = FALSE",
    "Use invoice_date for sales reports (not created_at)",
    "Status filtering: Exclude status IN (1, 11) from revenue",
    # Add more...
]
```

### Step 4: Add Performance Hints

Document your indexes and partitioning:

```python
PERFORMANCE_HINTS = [
    "orders table: Indexed on customer_id, status, invoice_date",
    "transactions table is partitioned by month",
    # Add more...
]
```

### Step 5: Note Data Quality Issues

Document edge cases and gotchas:

```python
DATA_QUALITY_NOTES = [
    "Some users have duplicate emails (legacy data)",
    "Deleted records have deleted_at IS NOT NULL (soft delete)",
    # Add more...
]
```

### Step 6: Test with Real Queries

Ask the agent questions and verify it uses your domain knowledge:

```python
# User asks: "Show me churned customers"
# Agent should use your churn definition from BUSINESS_DEFINITIONS
# Agent should filter test data per SQL_PATTERNS
# Agent should handle soft deletes per DATA_QUALITY_NOTES
```

## Best Practices

### 1. Start Small, Iterate

Don't try to document everything upfront. Start with:

- 3-5 business definitions
- 5-10 SQL patterns
- Top 3 performance hints
- Top 3 data quality issues

Add more as you identify gaps in query accuracy.

### 2. Use Concrete Examples

Instead of vague rules, show concrete patterns:

❌ Bad:
```python
"Use proper date filtering"
```

✅ Good:
```python
"For date ranges: WHERE `invoice_date` >= '2024-01-01' AND `invoice_date` < '2024-02-01' (inclusive start, exclusive end)"
```

### 3. Document Formulas

For business metrics, include the exact formula:

❌ Bad:
```python
"order_balance": "The remaining balance on an order"
```

✅ Good:
```python
"order_balance": "Order total minus sum of successful payments. Formula: orders.total - SUM(transaction_log.amount WHERE type='order' AND status IN (1,2,4))"
```

### 4. Be Prescriptive

Use directive language ("Always", "Never", "Use X") instead of suggestions ("Consider", "You might"):

❌ Weak:
```python
"Consider using table aliases for better readability"
```

✅ Strong:
```python
"Use table aliases for readability: o=orders, c=customers, od=order_details"
```

### 5. Keep It Current

Update the config as your database evolves:

- New tables added → Update business definitions and patterns
- Schema changes → Update column references
- Performance changes → Update hints if indexes added/removed
- Data quality fixes → Remove notes for resolved issues

## Integration with Agent

The domain config is used by `DomainPromptBuilder` in `run_web_ui.py`:

```python
# In run_web_ui.py
from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder
from vanna.core.system_prompt import READ_ONLY_SYSTEM_PROMPT
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

# Agent uses this prompt builder
agent = Agent(
    config=AgentConfig(...),
    system_prompt_builder=prompt_builder,
    ...
)
```

No code changes needed - just edit `domain_config.py` and restart the agent.

## Common Pitfalls

### Pitfall 1: Too Generic

❌ "Use indexes for better performance"

This is too generic - the LLM already knows this.

✅ "orders.customer_id is indexed - filter by customer_id early in WHERE clause"

This is specific and actionable.

### Pitfall 2: Contradictory Rules

❌
```python
SQL_PATTERNS = [
    "Use invoice_date for sales reports",
    "Use time column for date filtering"  # Contradicts above
]
```

Make sure your rules are consistent.

### Pitfall 3: Outdated Information

❌ "products_stock table is slow for aggregations"

If you added an index and it's now fast, remove this note.

### Pitfall 4: Duplicating Training Data

Domain config should provide **rules and context**, not examples.

❌ "Example query: SELECT SUM(total) FROM orders..."

Use training data (agent memory) for examples, not domain config.

## Version Control

Since `domain_config.py` is checked into git, you can:

- Track changes to domain knowledge over time
- Review changes in PRs
- Revert if a change causes issues
- Maintain different configs for different environments (dev, staging, prod)

## Environment-Specific Configs

For different environments, you can use environment variables:

```python
import os

ENV = os.getenv("ENVIRONMENT", "production")

if ENV == "production":
    DATABASE_INFO = {
        "type": "MySQL 8.0",
        "purpose": "Production ERP system"
    }
elif ENV == "staging":
    DATABASE_INFO = {
        "type": "MySQL 8.0",
        "purpose": "Staging ERP system (contains test data)"
    }
    SQL_PATTERNS = [
        "This is staging - test data is allowed",
        ...
    ]
```

## Related Documentation

- `docs/internal/configuration/domain-prompt-builder.md` - How `DomainPromptBuilder` uses this config
- `docs/internal/training/memory-training.md` - Training data and agent memory optimization
- `docs/OPTIMIZATION_ROADMAP.md` - Development roadmap (domain prompts are Priority 1, Task 4)
- `src/vanna/core/system_prompt/domain_prompt_builder.py` - Implementation source code
- `src/vanna/core/system_prompt/memory_instructions.py` - Memory workflow instructions auto-included by the builder
