# Advanced Domain Configuration

This guide provides advanced techniques for customizing Vanna's SQL generation through domain configuration. After reading [Configuring Vanna for Your Database](domain-configuration.md), use this guide to implement more sophisticated configurations.

## Overview

Domain configuration teaches Vanna about your specific database environment. While basic configuration covers standard patterns, advanced configuration addresses complex scenarios such as multi-database environments, conditional logic, calculated fields, and specialized query patterns.

## Advanced Configuration Patterns

### Complex Business Definitions

Define business metrics with detailed formulas and conditions.

#### Example: Multi-Step Calculations

```python
BUSINESS_DEFINITIONS = {
    "order_balance": """
        Order total minus the sum of all successful transaction amounts.
        Formula: orders.total - SUM(transaction_log.amount
        WHERE type='order' AND (status=1 OR status=2 OR status=4))

        Status meanings:
        - 1 = Pending (counted toward balance)
        - 2 = Succeeded (counted toward balance)
        - 4 = Refunded (counted toward balance)
    """,

    "gross_margin": """
        Revenue minus cost of goods sold. For order details:
        (price * qty) - total_cost

        Cost calculation varies by inventory_type_id:
        - 1 = FIFO (use fifo_cost_total)
        - 2 = Serial Number (use serial_number_cost_total)
        - 3 = Standard Cost (use cost * qty)
    """,

    "aging": """
        Number of days between the order due_date and the current date.
        Positive values mean overdue.

        Buckets:
        - Current: 0 days or less
        - 1-30 Days
        - 31-60 Days
        - 61-90 Days
        - 90+ Days
    """,
}
```

### Database-Specific SQL Patterns

Define patterns that vary by database type.

#### Example: Date Handling Across Databases

```python
SQL_PATTERNS = [
    # MySQL-specific patterns
    "MySQL date functions: DATE_FORMAT, DATE_SUB, DATE_ADD, INTERVAL",
    "For date ranges: WHERE date >= '2024-01-01' AND date < '2024-02-01'",
    "Get first of month: DATE_FORMAT(CURDATE(), '%Y-%m-01')",

    # PostgreSQL-specific patterns (if needed)
    # "PostgreSQL date functions: EXTRACT, DATE_TRUNC, INTERVAL",
    # "Use :: for type casting: column::DATE",

    # Snowflake-specific patterns (if needed)
    # "Snowflake date functions: DATEADD, DATEDIFF, DATE_TRUNC",
    # "Use QUALIFY for window function filtering",
]
```

### Conditional Logic Patterns

Document when to use specific approaches based on conditions.

```python
SQL_PATTERNS = [
    """
    When calculating cost_total:
    - For orders before 2019-11-01: Use standard cost (cost * qty)
    - For FIFO inventory (type 1): Use fifo_cost_total from stock_location_history
    - For Serial Number (type 2): Use serial_number_cost_total
    - For Standard Cost (type 3): Use cost * qty
    - Always add dropship_cost_total if applicable
    """,

    """
    When displaying customer names:
    - If company exists: 'Company Name (First Last)'
    - If no company: 'First Last'
    - If no name: Just company name
    - Use TRIM(CONCAT(...)) to handle empty values
    """,
]
```

### Performance Optimization by Query Type

Provide specific performance guidance for different query patterns.

```python
PERFORMANCE_HINTS = [
    # Aggregation queries
    "For aggregation queries >12 months: Aggregate by month first, then sum",
    "Use GROUP BY on primary key (orders.id) for efficient clustering",

    # JOIN patterns
    "LEFT JOIN to subqueries (transaction totals) is faster than correlated subqueries",
    "For multi-table JOINs: Filter by indexed columns early in WHERE clause",

    # Partitioned tables
    "orders table: Queries without date filters scan all partitions (slow)",
    "Optimal date range: 1-6 months (queries >12 months may timeout)",

    # Large result sets
    "Use LIMIT 1000 for exploratory queries to prevent timeout",
    "For pagination: Use indexed columns in ORDER BY clause",
]
```

### Detailed Data Quality Rules

Document complex edge cases and data quality issues.

```python
DATA_QUALITY_NOTES = [
    # Sentinel values
    "ship_id = 0 and bill_id = 0 mean no address set (not a valid foreign key)",
    "coupon_id = 0 means no coupon (not NULL) - system uses zero instead of NULL",
    "sales_rep = 0 means no sales rep assigned (not NULL)",

    # Soft deletes
    "Products with deleted_by IS NOT NULL are soft-deleted but still referenced by historical order_details",
    "Always filter deleted_by IS NULL for active product queries",

    # Snapshot fields
    "product_name and product_sku in orders_details are snapshots from order time",
    "These values may differ from current product values - use real_product_id for JOINs",

    # Time zones and timestamps
    "order.time is creation timestamp (UTC)",
    "invoice_date may be NULL for draft or abandoned orders",
    "Use invoice_date for sales reports, not time",

    # Special handling
    "Emails starting with '$$' are system-generated placeholders for customers without real emails",
    "guest = 1 customers may have incomplete data (no real email, limited address info)",
    "The extras column in orders is serialized PHP data - do not parse in SQL",
]
```

## Configuration File Organization

### Modular Configuration

For large configurations, organize into modules.

**Directory structure:**

```
project/
├── domain_config.py          # Main config file
├── domain_config/
│   ├── __init__.py
│   ├── database_info.py
│   ├── business_defs.py
│   ├── sql_patterns.py
│   ├── performance.py
│   └── data_quality.py
```

**Main configuration file:**

```python
# domain_config.py
from domain_config.database_info import DATABASE_INFO
from domain_config.business_defs import BUSINESS_DEFINITIONS
from domain_config.sql_patterns import SQL_PATTERNS
from domain_config.performance import PERFORMANCE_HINTS
from domain_config.data_quality import DATA_QUALITY_NOTES

ADDITIONAL_CONTEXT = """
Additional notes or context that doesn't fit in other categories.
"""
```

**Module example:**

```python
# domain_config/business_defs.py
BUSINESS_DEFINITIONS = {
    # Financial metrics
    "revenue": "Total sales amount from completed orders",
    "gross_margin": "Revenue minus cost of goods sold",

    # Customer metrics
    "active_customer": "Customer with order in last 30 days",
    "churned_customer": "Customer with no orders in last 90 days",

    # Inventory metrics
    "physical_stock": "Stock in regular warehouses, excluding customer-specific warehouses",
}
```

### Environment-Specific Configuration

Use different configurations for development, staging, and production.

```python
import os

ENV = os.getenv("ENVIRONMENT", "production")

if ENV == "production":
    DATABASE_INFO = {
        "type": "MySQL 8.0",
        "purpose": "Production ERP system"
    }
    SQL_PATTERNS = [
        "Always exclude test data: WHERE is_test = FALSE",
    ]
elif ENV == "staging":
    DATABASE_INFO = {
        "type": "MySQL 8.0",
        "purpose": "Staging ERP system (contains test data)"
    }
    SQL_PATTERNS = [
        "Staging allows test data - filter only when necessary",
    ]
```

## Advanced Use Cases

### Multi-Database Configuration

Support queries across multiple databases with environment detection.

```python
# Detect database type from environment
DB_TYPE = os.getenv("DB_TYPE", "mysql")

if DB_TYPE == "mysql":
    SQL_PATTERNS = [
        "Use LIMIT for result limiting",
        "Use backticks for identifiers: `table`, `column`",
        "Date functions: DATE_FORMAT, DATE_SUB, DATE_ADD",
    ]
elif DB_TYPE == "postgres":
    SQL_PATTERNS = [
        "Use LIMIT for result limiting",
        "Use double quotes for case-sensitive identifiers",
        "Date functions: EXTRACT, DATE_TRUNC, INTERVAL",
    ]
elif DB_TYPE == "snowflake":
    SQL_PATTERNS = [
        "Use TOP or LIMIT for result limiting",
        "Schema.table format required: SCHEMA.TABLE",
        "Date functions: DATEADD, DATEDIFF, DATE_TRUNC",
    ]
```

### Dynamic Configuration Loading

Load configuration from a database or external source.

```python
import json

def load_domain_config_from_db(connection):
    """Load domain configuration from database settings table."""
    cursor = connection.cursor()
    cursor.execute("SELECT config_key, config_value FROM system_config WHERE config_type = 'domain'")

    config = {}
    for row in cursor.fetchall():
        key, value = row
        config[key] = json.loads(value)

    return config

# Usage
# db_config = load_domain_config_from_db(db_connection)
# DATABASE_INFO = db_config.get("database_info", {})
# BUSINESS_DEFINITIONS = db_config.get("business_definitions", {})
```

### Version-Controlled Configuration

Track configuration changes in version control.

```python
# Add version and changelog
CONFIG_VERSION = "2.1.0"

CONFIG_CHANGELOG = """
Version 2.1.0 (2024-02-15):
- Added aging bucket definitions
- Updated cost calculation logic for new inventory types
- Added performance hints for partitioned tables

Version 2.0.0 (2024-01-10):
- Restructured business definitions with formulas
- Added environment-specific patterns
- Updated data quality notes for new schema

Version 1.0.0 (2023-12-01):
- Initial configuration
"""
```

## Testing Your Configuration

### Validate Configuration Structure

Ensure configuration follows expected format.

```python
def validate_domain_config():
    """Validate domain configuration structure and content."""
    errors = []

    # Check required fields
    if not isinstance(DATABASE_INFO, dict):
        errors.append("DATABASE_INFO must be a dictionary")

    if not isinstance(BUSINESS_DEFINITIONS, dict):
        errors.append("BUSINESS_DEFINITIONS must be a dictionary")

    if not isinstance(SQL_PATTERNS, list):
        errors.append("SQL_PATTERNS must be a list")

    # Check content
    for key, value in BUSINESS_DEFINITIONS.items():
        if not isinstance(value, str):
            errors.append(f"Business definition '{key}' must be a string")

    if errors:
        print("Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("Configuration validation passed")
    return True

# Run validation
# validate_domain_config()
```

### Test with Sample Questions

Verify that configuration improves SQL generation.

```python
# Test questions that should use your configuration
TEST_QUESTIONS = [
    "Show me churned customers",  # Should use churn definition
    "Calculate order balance",    # Should use balance formula
    "What is the gross margin?",  # Should use margin calculation
]

# Run through agent and verify SQL follows patterns
```

## Best Practices

### Incremental Updates

Update configuration gradually:

1. **Week 1**: Add database info and top 5 business definitions
2. **Week 2**: Add 10 SQL patterns based on query logs
3. **Week 3**: Add performance hints for slow queries
4. **Week 4**: Document data quality issues discovered

### Review and Refine

Regularly review configuration:

- **Monthly**: Check for outdated or incorrect information
- **After schema changes**: Update affected definitions
- **After query log analysis**: Add patterns for common failures

### Keep Documentation Synchronized

When updating domain configuration:

1. Update `domain_config.py`
2. Update related training examples
3. Update schema documentation (if maintained)
4. Test with representative questions

### Use Clear, Concise Language

Write configuration entries that are:

- **Specific**: Reference exact table and column names
- **Complete**: Include all necessary context
- **Unambiguous**: Avoid vague terms
- **Actionable**: Provide clear guidance for SQL generation

## Troubleshooting

### Configuration Not Applied

**Symptom:** SQL generation does not reflect domain configuration.

**Solutions:**
- Verify `DomainPromptBuilder` is passed to the agent
- Check that configuration file is imported correctly
- Confirm no syntax errors in configuration file
- Review agent logs for configuration loading errors

### Conflicting Rules

**Symptom:** Configuration contains contradictory guidance.

**Solutions:**
- Review all sections for consistency
- Prioritize rules (most important first)
- Remove outdated or obsolete entries
- Test with questions that trigger the conflict

### Configuration Too Large

**Symptom:** Token limits exceeded or high AI costs.

**Solutions:**
- Remove redundant or obvious patterns
- Consolidate similar rules
- Move detailed examples to training data instead
- Use modular configuration to load only relevant sections

## Related Topics

- [Configuring Vanna for Your Database](domain-configuration.md): Basic configuration guide.
- [Training Vanna with Query Examples](training-data.md): Add training examples to complement configuration.
- [Query Logging and Analytics](query-logging.md): Track query patterns to identify configuration gaps.
