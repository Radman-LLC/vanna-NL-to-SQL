# Configuring Vanna for Your Database

This guide shows you how to customize Vanna to understand your specific database environment through domain configuration.

## What Is Domain Configuration?

Domain configuration teaches Vanna about your database without requiring code changes. You define business terms, SQL conventions, performance characteristics, and data quality rules in a configuration file that Vanna uses to generate accurate SQL queries tailored to your environment.

## Why Configure Your Database?

Out-of-the-box SQL generation works for simple queries, but struggles with:

- **Business terminology**: Vanna does not know what "churn" or "MRR" means in your business
- **Database differences**: MySQL, PostgreSQL, and Snowflake use different syntax and features
- **Performance patterns**: Vanna does not know which columns are indexed or how tables are partitioned
- **Data quality**: Vanna is unaware of edge cases like soft deletes, test data, or NULL semantics
- **Conventions**: May generate valid but non-idiomatic SQL for your database

Domain configuration solves these issues by providing context specific to your database.

## Getting Started

### Create a Configuration File

Create a file named `domain_config.py` in your project root with the following structure:

```python
# Database metadata
DATABASE_INFO = {
    "type": "MySQL 8.0",
    "purpose": "E-commerce transaction database"
}

# Business term definitions
BUSINESS_DEFINITIONS = {
    "churn": "User with no transactions in last 90 days",
    "active_customer": "Customer with transaction in last 30 days",
}

# SQL patterns and best practices
SQL_PATTERNS = [
    "Use UPPERCASE for SQL keywords: SELECT, FROM, WHERE",
    "Always filter test data: WHERE is_test = FALSE",
]

# Performance optimization hints
PERFORMANCE_HINTS = [
    "transactions table is partitioned by month",
    "Always include date filters for better performance",
]

# Data quality issues and edge cases
DATA_QUALITY_NOTES = [
    "Some users have duplicate emails from legacy data",
    "Refunds are new rows with negative amounts, not UPDATEs",
]
```

### Connect to Your Agent

Pass the configuration to your agent using the `DomainPromptBuilder`:

```python
from vanna import Agent, AgentConfig
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
)

# Create agent with domain configuration
agent = Agent(
    config=AgentConfig(...),
    system_prompt_builder=prompt_builder,
    ...
)
```

## Configuration Sections

### Database Information

Basic metadata about your database.

**Fields:**
- `type`: Database type and version (for example, "MySQL 8.0", "PostgreSQL 14")
- `purpose`: Brief description of what the database is used for

**Example:**

```python
DATABASE_INFO = {
    "type": "PostgreSQL 14",
    "purpose": "SaaS application usage and billing analytics"
}
```

### Business Definitions

Domain-specific business terms and metrics that users will ask about.

**Format:** Dictionary with term → definition pairs

**Example:**

```python
BUSINESS_DEFINITIONS = {
    "active_account": "Account with API calls in last 7 days",
    "churned_account": "Canceled subscription, no activity in 30 plus days",
    "MAU": "Monthly Active Users - unique users with activity this month",
}
```

**Guidelines:**
- Be specific: Include formulas, table references, and column names
- Avoid ambiguity: Define terms precisely
- Include calculation logic: Show exactly how to compute metrics
- Use your schema: Reference actual table and column names

### SQL Patterns

SQL conventions, best practices, and patterns specific to your database.

**Format:** List of strings (each string is one rule or pattern)

**Example:**

```python
SQL_PATTERNS = [
    "Use UPPERCASE for SQL keywords: SELECT, FROM, WHERE",
    "Always filter test data: WHERE is_test = FALSE",
    "For date ranges: WHERE date >= '2024-01-01' AND date < '2024-02-01'",
    "Use table aliases for readability: users u, transactions t",
]
```

**Categories to Cover:**
- Keywords and formatting
- Date filtering patterns
- Status filtering rules
- JOIN patterns
- NULL handling
- Performance optimization
- Data integrity rules

### Performance Hints

Performance characteristics, optimization tips, and index information.

**Format:** List of strings (each string is one hint)

**Example:**

```python
PERFORMANCE_HINTS = [
    "orders table is indexed on customer_id, status, date",
    "transactions table is partitioned by month",
    "Always include date filters for queries spanning more than 6 months",
]
```

**What to Include:**
- Index information on key tables
- Table partitioning details
- Query patterns that are fast or slow
- Aggregation tips for large datasets
- JOIN optimization strategies

### Data Quality Notes

Known data quality issues, edge cases, and gotchas.

**Format:** List of strings (each string is one note)

**Example:**

```python
DATA_QUALITY_NOTES = [
    "Emails starting with '$$' are system-generated placeholders",
    "Products with deleted_by IS NOT NULL are soft-deleted",
    "Some older records use standard cost regardless of type",
]
```

**What to Include:**
- Sentinel values (special values like 0, '$$', NULL)
- Soft delete patterns
- Data migration artifacts
- Invalid foreign keys
- Test data markers
- Duplicate handling

## Best Practices

### Start Small, Iterate

Do not try to document everything upfront. Start with:

- 3 to 5 business definitions
- 5 to 10 SQL patterns
- Top 3 performance hints
- Top 3 data quality issues

Add more as you identify gaps in query accuracy.

### Use Concrete Examples

Instead of vague rules, show concrete patterns.

Bad:
```python
"Use proper date filtering"
```

Good:
```python
"For date ranges: WHERE invoice_date >= '2024-01-01' AND invoice_date < '2024-02-01'"
```

### Document Formulas

For business metrics, include the exact formula.

Bad:
```python
"order_balance": "The remaining balance on an order"
```

Good:
```python
"order_balance": "Order total minus sum of successful payments. Formula: orders.total - SUM(transaction_log.amount WHERE type='order' AND status IN (1,2,4))"
```

### Be Prescriptive

Use directive language ("Always", "Never", "Use X") instead of suggestions.

Bad:
```python
"Consider using table aliases for better readability"
```

Good:
```python
"Use table aliases for readability: o=orders, c=customers"
```

### Keep It Current

Update the configuration as your database evolves:

- New tables added: Update business definitions and patterns
- Schema changes: Update column references
- Performance changes: Update hints if indexes are added or removed
- Data quality fixes: Remove notes for resolved issues

## Example Configurations

### E-Commerce Database (MySQL)

```python
DATABASE_INFO = {
    "type": "MySQL 8.0",
    "purpose": "E-commerce order and inventory management"
}

BUSINESS_DEFINITIONS = {
    "gross_margin": "Revenue minus cost. Formula: (price * qty) - cost",
    "active_customer": "Customer with completed order in last 30 days",
}

SQL_PATTERNS = [
    "Use invoice_date for sales reports, not created_at",
    "Always exclude status IN (1, 11) from sales reports",
    "Use table aliases: o=orders, c=customers, od=order_details",
]

PERFORMANCE_HINTS = [
    "orders table indexed on customer_id, status, date",
    "Use invoice_date for reporting",
]

DATA_QUALITY_NOTES = [
    "Emails starting with '$$' are placeholders",
    "Products with deleted_by IS NOT NULL are soft-deleted",
]
```

### SaaS Analytics (PostgreSQL)

```python
DATABASE_INFO = {
    "type": "PostgreSQL 14",
    "purpose": "SaaS application usage and billing analytics"
}

BUSINESS_DEFINITIONS = {
    "active_account": "Account with API calls in last 7 days",
    "trial_conversion": "Trial account that upgraded to paid within 14 days",
    "MAU": "Monthly Active Users - unique users with activity this month",
}

SQL_PATTERNS = [
    "Use EXTRACT for date parts: EXTRACT(MONTH FROM created_at)",
    "Always use lowercase table and column names",
    "Use CTEs for complex queries instead of subqueries",
]

PERFORMANCE_HINTS = [
    "events table is partitioned by date - always filter by date",
    "Indexes exist on user_id, account_id, created_at",
]

DATA_QUALITY_NOTES = [
    "Events before 2024-01-01 are sampled, not complete",
    "Deleted accounts have soft delete: deleted_at IS NOT NULL",
]
```

## Troubleshooting

### Vanna Ignores Domain Rules

**Symptom:** Vanna generates SQL that violates documented patterns.

**Solutions:**
1. Make rules more explicit and emphatic ("ALWAYS", "NEVER", "CRITICAL")
2. Move most important rules to top of each section
3. Reduce prompt size - Vanna may lose focus with very long prompts

### Prompt Too Long

**Symptom:** Token limit exceeded or high costs.

**Solutions:**
1. Prioritize: Keep only the most impactful rules
2. Remove redundant or obvious patterns
3. Consolidate similar rules into single entries

### Business Definitions Not Applied

**Symptom:** Vanna asks for clarification on terms defined in prompt.

**Solutions:**
1. Make definitions more prominent
2. Add examples showing how to use the definition in SQL
3. Add the same terms to training data queries

## Related Topics

- Domain Prompt Builder: Learn how domain configuration is integrated into system prompts
- Training Vanna: Add query examples to improve accuracy
