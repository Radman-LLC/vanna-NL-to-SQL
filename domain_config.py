"""Domain-Specific Configuration

Customize this file to match your specific database and business domain.
This configuration is used to enhance the system prompt with domain knowledge,
improving SQL generation accuracy for your specific use case.

Instructions:
1. Fill in the DATABASE_INFO section with your database details
2. Add your business term definitions to BUSINESS_DEFINITIONS
3. List SQL patterns and best practices in SQL_PATTERNS
4. Add performance tips to PERFORMANCE_HINTS
5. Note any data quality issues in DATA_QUALITY_NOTES

The more specific and detailed you are, the better the SQL generation will be.
"""

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE INFORMATION
# ═══════════════════════════════════════════════════════════════════════════

DATABASE_INFO = {
    # Database type and version
    "type": "MySQL 5.6.10+ (InnoDB)",

    # Brief description of what this database is used for
    "purpose": "ADR/Zangerine ERP system - order management, inventory, purchasing, customer relationship management",
}

# ═══════════════════════════════════════════════════════════════════════════
# BUSINESS DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

# Define business terms and metrics specific to ADR database.
# The LLM will use these definitions when users ask about these concepts.

BUSINESS_DEFINITIONS = {
    "order_balance": "Order total minus the sum of all successful transaction amounts (status IN 1,2,4). Formula: orders.total - SUM(transaction_log.amount WHERE type='order' AND (status=1 OR status=2 OR status=4))",

    "gross_margin": "Revenue minus cost of goods sold. For order details: (price * qty) - total_cost. Can be expressed as dollar amount or percentage.",

    "margin_percentage": "Gross margin divided by revenue times 100. Formula: ((order_detail_subtotal - cost_total) / order_detail_subtotal) * 100",

    "aging": "Number of days between the order due_date and the current date (or a cutoff date). Positive values mean overdue. Buckets: Current, 1-30, 31-60, 61-90, 90+ days.",

    "successful_transaction": "A transaction_log entry with status = 1 (Pending), 2 (Succeeded), or 4 (Refunded). These are counted toward the paid amount on an order.",

    "invoice_date": "The primary date used for sales reporting. Set when the order is invoiced. This is the canonical 'order date' for reports, NOT the creation timestamp (time).",

    "fulfillment": "The process of picking, packing, and shipping order items. An order_fulfillment record is created per warehouse per order. Status tracks progress through picking → packing → shipping.",

    "dropship": "A purchase order where the vendor ships directly to the customer (is_dropship='1'). The PO line items link to order line items via order_detail_id.",

    "customer_label": "Display name for a customer. If company exists: 'Company Name (First Last)'. If no company: 'First Last'. If no name: just company name.",

    "product_label": "Display name for a product: 'Product Name (SKU)'. If unnamed: 'Untitled Product'.",

    "soft_delete": "Products use soft delete via deleted_by column. deleted_by IS NULL = active. deleted_by IS NOT NULL = deleted. Historical references (order details) still point to deleted products.",

    "physical_stock": "Stock in regular warehouses, excluding customer-specific and sales rep warehouses. Filter: warehouse_customer IS NULL AND warehouse_sales_rep_user IS NULL.",

    "recurring_profile": "A subscription/auto-order setup. Has recurrence pattern (daily/weekly/monthly/yearly), auto_charge and auto_fulfill flags. Generates orders automatically per schedule.",

    "customer_credit": "Store credit issued to a customer, often from an RMA return. Has balance = amount - sum(applied payments). Can be applied as payment on future orders.",

    "quote_conversion": "When a quote is accepted and converted to an order, the quotes.order_id field is populated with the new order's ID.",
}

# ═══════════════════════════════════════════════════════════════════════════
# SQL BEST PRACTICES
# ═══════════════════════════════════════════════════════════════════════════

# SQL patterns and conventions that should always be followed when
# generating queries for ADR database.

SQL_PATTERNS = [
    # Keywords & Formatting
    "Use UPPERCASE for all SQL keywords: SELECT, FROM, WHERE, AND, OR, JOIN, LEFT JOIN, ON, GROUP BY, ORDER BY, HAVING, LIMIT, SUM, COUNT, AVG, ROUND, IFNULL, CONCAT, TRIM, CASE, WHEN, THEN, ELSE, END, AS, IN, NOT, NULL, IS, LIKE, BETWEEN, DISTINCT, EXISTS",
    "Use backticks around all table names and column names: `orders`, `customer_id`, `status`",
    "Use table aliases for readability: o=orders, c=customers, p=products, od=orders_details, po=po_, v=po_vendors, a=addresses, u=synced_users",

    # Date Filtering
    "Use invoice_date (not time/created_at) for sales reports and date-based queries",
    "For date ranges use: WHERE `invoice_date` >= '2024-01-01' AND `invoice_date` < '2024-02-01' (inclusive start, exclusive end)",
    "Use DATE_FORMAT(CURDATE(), '%Y-%m-01') to get first of current month",
    "Use DATE_SUB(CURDATE(), INTERVAL N MONTH) for relative date ranges",
    "DATEDIFF(CURDATE(), `due_date`) for aging calculations",

    # Status Filtering
    "Always exclude ABANDONED (status=1) and CANCELLED (status=11) from sales reports",
    "For accounts receivable, also exclude REFUNDED (status=12)",
    "Transaction log: status 1=Pending, 2=Succeeded, 4=Refunded are 'successful' for balance calculations",
    "When filtering transaction_log for orders, always include: type = 'order'",

    # JOIN Patterns
    "Use INNER JOIN when relationship is required (order_details to orders)",
    "Use LEFT JOIN for optional relationships (orders to coupons, customers to companies)",
    "Always LEFT JOIN addresses since ship_id/bill_id can be 0",
    "For transaction totals, use subquery with GROUP BY: SELECT type_id, SUM(amount) FROM transaction_log WHERE type='order' AND (status=1 OR status=2 OR status=4) GROUP BY type_id",

    # NULL Handling
    "Use IFNULL(value, 0) for numeric aggregations that may be NULL",
    "Use NULLIF(denominator, 0) to prevent division by zero in percentage calculations",
    "Use TRIM(CONCAT(fname, ' ', lname)) for name display to handle empty values",
    "IFNULL(company_label, '') to handle optional company names",

    # Performance
    "Use LIMIT for large result sets (default LIMIT 1000 for exploratory queries)",
    "Filter by indexed columns: id, customer_id, status, time, email, ship_id, bill_id",
    "Use COUNT(DISTINCT id) when JOINs may produce duplicates",
    "Prefer subqueries in FROM clause over correlated subqueries",

    # Data Integrity
    "Products with deleted_by IS NOT NULL are soft-deleted - exclude from active product queries",
    "Emails starting with '$$' are system-generated placeholders - exclude from customer email queries",
    "guest = 1 customers are guest checkouts - may want to exclude from customer reports",
    "ENUM fields use string values ('0', '1', '2') not integers - use string comparison: picked = '1' not picked = 1",
    "The po_ table name has a trailing underscore - this is correct and intentional",
    "Order type 'sales_order' is the default; filter out 'transfer_order' for sales reports if needed",

    # Column Name Mappings (DB column vs API/display name)
    "fname → first_name, lname → last_name (customers, addresses, users)",
    "creation_date → created_at (customers), time → created_at (orders, transactions, POs)",
    "zip → postal_code (addresses)",
    "qty → quantity (order_details, PO details, stock)",
    "costs → cost (order_details unit cost)",
    "real_product_id → product (order_details, PO details, quote details)",
    "ship_id → shipping_address, bill_id → billing_address",
    "sales_rep → sales_rep_user (orders)",
    "pass → password_hash (customers)",
]

# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE HINTS
# ═══════════════════════════════════════════════════════════════════════════

# Performance characteristics and optimization tips for ADR database.

PERFORMANCE_HINTS = [
    "orders table: Indexed on id, time, status, customer_id, ship_id, bill_id, reference_id, (status,customer_id) composite",
    "customers table: Indexed on id, email, phone, fname, lname, company_id",
    "Queries filtering by invoice_date are common but invoice_date is NOT indexed - use date ranges to limit scan",
    "The time column on orders IS indexed - prefer it for date filtering when exact creation date is acceptable",
    "Transaction log queries should always filter by type='order' to use segmented data efficiently",
    "For large date ranges (>12 months), consider aggregating by month first then summing",
    "GROUP BY on primary key (o.id) is efficient since it maps to clustered index",
    "HAVING clause filters after aggregation - only use for computed columns, not for WHERE-eligible filters",
    "LEFT JOIN to subqueries (e.g., transaction totals) is more efficient than correlated subqueries",
    "products_stock may have many rows per product (one per warehouse location) - always SUM(qty) with GROUP BY",
    "colored_tags_relations is segmented by type column - always filter on type in WHERE clause",
    "For customer lookups, email index is available but may have duplicates across guest accounts",
]

# ═══════════════════════════════════════════════════════════════════════════
# DATA QUALITY NOTES
# ═══════════════════════════════════════════════════════════════════════════

# Known data quality issues, edge cases, and gotchas specific to ADR database.

DATA_QUALITY_NOTES = [
    "Customer emails starting with '$$' are system-generated placeholders for customers without real emails",
    "guest = 1 customers may have incomplete data (no real email, limited address info)",
    "order.time is creation timestamp; invoice_date may be NULL for draft/abandoned orders",
    "Products with deleted_by IS NOT NULL are soft-deleted but still referenced by historical order_details",
    "product_name and product_sku in orders_details are snapshots that may differ from current product values",
    "ship_id = 0 and bill_id = 0 mean no address set (not a valid FK) - handle in JOINs",
    "coupon_id = 0 means no coupon (not NULL) - the entity uses use_zero_for_null pattern",
    "sales_rep = 0 means no sales rep assigned (not NULL)",
    "Some older orders (before 2019-11-01) use standard cost calculation regardless of inventory_type_id",
    "The extras column in orders is serialized PHP data - do not parse in SQL",
    "order_type defaults to 'sales_order' but transfer_order records exist for warehouse transfers",
    "Currency defaults to id=5 (USD) but multi-currency accounts may have different values",
    "custom_fields table stores dynamic key-value pairs segmented by type (customer, product, order, etc.)",
    "Commission data links through commission_period → sales_rep_user, not directly to orders.sales_rep",
]

# ═══════════════════════════════════════════════════════════════════════════
# ADDITIONAL CONTEXT (OPTIONAL)
# ═══════════════════════════════════════════════════════════════════════════

# Any additional free-form context you want to include in the system prompt.
# This can be schema information, special instructions, or anything else.

ADDITIONAL_CONTEXT = """
"""

# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE CONFIGURATIONS (For Reference)
# ═══════════════════════════════════════════════════════════════════════════

# Uncomment and customize one of these examples, or create your own above.

# ─────────────────────────────────────────────────────────────────────────────
# Example 1: E-Commerce Database (MySQL)
# ─────────────────────────────────────────────────────────────────────────────
"""
DATABASE_INFO = {
    "type": "MySQL 8.0",
    "purpose": "E-commerce transaction and customer database",
}

BUSINESS_DEFINITIONS = {
    "churn": "User with no transactions in the last 90 days",
    "active customer": "Customer with completed transaction in last 30 days",
    "MRR": "Monthly Recurring Revenue - sum of active subscription values",
    "ARPU": "Average Revenue Per User - total revenue / unique customers",
    "conversion rate": "Percentage of users who made at least one purchase",
}

SQL_PATTERNS = [
    "Always filter out test transactions: WHERE is_test = FALSE",
    "Only count completed transactions: AND status = 'completed'",
    "Use table aliases in JOINs: users u, transactions t",
    "Date filtering: Use >= and < (not YEAR/MONTH functions)",
    "Use DISTINCT for unique user counts: COUNT(DISTINCT user_id)",
]

PERFORMANCE_HINTS = [
    "transactions table is partitioned by month",
    "Always include date filters for better performance",
    "user_id and transaction_date are indexed",
]

DATA_QUALITY_NOTES = [
    "Some users have duplicate emails - GROUP BY email when needed",
    "Refunds are new rows with negative amounts",
    "NULL in region means international user",
]
"""

# ─────────────────────────────────────────────────────────────────────────────
# Example 2: SaaS Analytics Database (PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────
"""
DATABASE_INFO = {
    "type": "PostgreSQL 14",
    "purpose": "SaaS application usage and billing analytics",
}

BUSINESS_DEFINITIONS = {
    "active account": "Account with API calls in last 7 days",
    "churned account": "Canceled subscription, no activity in 30+ days",
    "trial conversion": "Trial account that upgraded to paid within 14 days",
    "MAU": "Monthly Active Users - unique users with activity this month",
}

SQL_PATTERNS = [
    "Use EXTRACT for date parts: EXTRACT(MONTH FROM created_at)",
    "Always use lowercase table/column names (PostgreSQL convention)",
    "Use CTEs for complex queries instead of subqueries",
    "Add explicit column names in SELECT (no SELECT *)",
]

PERFORMANCE_HINTS = [
    "events table is partitioned by date - always filter by date",
    "Use EXPLAIN ANALYZE for complex queries",
    "Indexes exist on: user_id, account_id, created_at",
]

DATA_QUALITY_NOTES = [
    "Events before 2024-01-01 are sampled (not complete)",
    "Deleted accounts have soft delete: deleted_at IS NOT NULL",
    "User IDs can be NULL for anonymous events",
]
"""

# ─────────────────────────────────────────────────────────────────────────────
# Example 3: Data Warehouse (Snowflake)
# ─────────────────────────────────────────────────────────────────────────────
"""
DATABASE_INFO = {
    "type": "Snowflake Data Warehouse",
    "purpose": "Enterprise analytics with sales, marketing, product data",
}

BUSINESS_DEFINITIONS = {
    "qualified lead": "Lead with score >= 70 and engagement in last 14 days",
    "customer LTV": "Total revenue from customer across all time",
    "retention rate": "% of customers with repeat purchases",
}

SQL_PATTERNS = [
    "Use schema.table format: SALES.TRANSACTIONS",
    "Snowflake date functions: DATEADD, DATEDIFF, DATE_TRUNC",
    "Leverage CTEs (WITH) for readability",
    "Use QUALIFY for window function filtering",
]

PERFORMANCE_HINTS = [
    "Tables are clustered by date - include date filters",
    "Use SAMPLE for exploration: SELECT * FROM t SAMPLE (1000 ROWS)",
    "Avoid SELECT * - specify columns to reduce scanning",
]

DATA_QUALITY_NOTES = [
    "Data updated nightly via ETL (up to 24 hours old)",
    "Revenue in USD, converted from local currencies",
    "Customer IDs can be NULL for anonymous sessions",
]
"""
