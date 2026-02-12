"""Sample Query Library Template

This file contains high-quality question-SQL training pairs for your database.
Customize these examples to match your actual schema and business questions.

Guidelines for creating training pairs:
1. Cover diverse query types (simple, complex, aggregations, joins)
2. Use realistic business questions your users will actually ask
3. Include edge cases and common gotchas
4. Ensure all SQL is tested and produces correct results
5. Add explanatory comments for complex queries

Categories to cover:
- Simple lookups and filters
- Aggregations (COUNT, SUM, AVG, etc.)
- JOINs across multiple tables
- Time-based queries and date ranges
- GROUP BY with HAVING
- Subqueries and CTEs
- Window functions
- Business metrics calculations
"""

# Each training pair is a dictionary with:
# - question: Natural language question a user might ask
# - sql: The correct SQL query that answers the question
# - category: Type of query for organization
# - notes: Optional explanation of query logic

TRAINING_PAIRS = [
    # ═══════════════════════════════════════════════════════════════
    # ADR DATABASE - REAL TRAINING DATA
    # Generated from ADR/Zangerine production database schema
    # ═══════════════════════════════════════════════════════════════

    # Pattern 1: Total Sales by Date Range
    {
        "question": "What were the total sales last month?",
        "sql": """
            SELECT
                COUNT(*) AS order_count,
                SUM(`total`) AS total_sales,
                SUM(`tax_fee`) AS total_tax,
                SUM(`shipping_fee`) AS total_shipping,
                SUM(`discount_amount`) AS total_discounts
            FROM `orders`
            WHERE `invoice_date` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
              AND `invoice_date` < DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND `status` NOT IN (1, 11)
        """,
        "category": "aggregation",
        "notes": "Use invoice_date for reporting (not time). Exclude ABANDONED(1) and CANCELLED(11)."
    },

    # Pattern 2: Sales by Customer
    {
        "question": "Which customers have the highest order totals this year?",
        "sql": """
            SELECT
                c.`id` AS customer_id,
                TRIM(CONCAT(c.`fname`, ' ', c.`lname`)) AS customer_name,
                cc.`name` AS company_name,
                COUNT(o.`id`) AS order_count,
                SUM(o.`total`) AS total_sales
            FROM `orders` o
            INNER JOIN `customers` c ON o.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE YEAR(o.`invoice_date`) = YEAR(CURDATE())
              AND o.`status` NOT IN (1, 11)
            GROUP BY c.`id`, customer_name, company_name
            ORDER BY total_sales DESC
            LIMIT 20
        """,
        "category": "join_aggregation",
        "notes": "JOIN customers for name. LEFT JOIN companies since not all customers have a company."
    },

    # Pattern 3: Order Details with Product Info
    {
        "question": "Show me the line items for order 12345",
        "sql": """
            SELECT
                od.`id` AS line_item_id,
                p.`sku`,
                od.`product_name`,
                od.`qty` AS quantity,
                od.`price` AS unit_price,
                od.`costs` AS unit_cost,
                (od.`price` * od.`qty`) AS line_total,
                od.`original_price`,
                od.`note`
            FROM `orders_details` od
            LEFT JOIN `products` p ON od.`real_product_id` = p.`id`
            WHERE od.`order_id` = 12345
            ORDER BY od.`sort`
        """,
        "category": "detail_lookup",
        "notes": "Use real_product_id for JOIN, not product_id. Sort by sort field for display order."
    },

    # Pattern 4: Accounts Receivable / Outstanding Balances
    {
        "question": "Which orders have unpaid balances?",
        "sql": """
            SELECT
                o.`id` AS order_id,
                o.`invoice_date`,
                o.`due_date`,
                o.`total`,
                IFNULL(t.amount_paid, 0) AS amount_paid,
                ROUND(o.`total` - IFNULL(t.amount_paid, 0), 2) AS balance,
                TRIM(CONCAT(c.`fname`, ' ', c.`lname`)) AS customer_name,
                cc.`name` AS company_name
            FROM `orders` o
            LEFT JOIN (
                SELECT `type_id` AS order_id, SUM(`amount`) AS amount_paid
                FROM `transaction_log`
                WHERE `type` = 'order'
                  AND (`status` = 1 OR `status` = 2 OR `status` = 4)
                GROUP BY `type_id`
            ) t ON o.`id` = t.order_id
            LEFT JOIN `customers` c ON o.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE o.`status` NOT IN (1, 11)
            HAVING balance > 0.01
            ORDER BY balance DESC
        """,
        "category": "financial",
        "notes": "Transaction statuses 1(Pending), 2(Succeeded), 4(Refunded) are 'successful'. Use HAVING for post-aggregation filter."
    },

    # Pattern 5: Inventory Levels by Product
    {
        "question": "What is the current stock level for all products?",
        "sql": """
            SELECT
                p.`id` AS product_id,
                p.`sku`,
                p.`name`,
                p.`price`,
                p.`cost`,
                IFNULL(SUM(ps.`qty`), 0) AS total_stock
            FROM `products` p
            LEFT JOIN `products_stock` ps ON ps.`product_id` = p.`id`
            WHERE p.`deleted_by` IS NULL
            GROUP BY p.`id`, p.`sku`, p.`name`, p.`price`, p.`cost`
            ORDER BY p.`name`
        """,
        "category": "inventory",
        "notes": "Filter deleted_by IS NULL to exclude soft-deleted products. SUM(qty) aggregates across all warehouse locations."
    },

    # Pattern 6: Inventory by Warehouse
    {
        "question": "Show inventory levels by warehouse for product SKU 'ABC-123'",
        "sql": """
            SELECT
                w.`name` AS warehouse_name,
                ps.`location_row`, ps.`location_column`, ps.`location_shelf`, ps.`location_bin`,
                ps.`qty` AS quantity
            FROM `products_stock` ps
            INNER JOIN `products` p ON ps.`product_id` = p.`id`
            LEFT JOIN `location_warehouses` w ON ps.`location_warehouse_id` = w.`id`
            WHERE p.`sku` = 'ABC-123'
              AND p.`deleted_by` IS NULL
            ORDER BY w.`name`, ps.`location_row`, ps.`location_column`
        """,
        "category": "inventory",
        "notes": "location_warehouse_id = 0 means no specific warehouse assigned."
    },

    # Pattern 7: Sales by Product
    {
        "question": "What are the top selling products this year?",
        "sql": """
            SELECT
                p.`id` AS product_id,
                p.`sku`,
                p.`name`,
                SUM(od.`qty`) AS total_quantity_sold,
                SUM(od.`price` * od.`qty`) AS total_revenue,
                SUM(od.`costs` * od.`qty`) AS total_cost,
                SUM(od.`price` * od.`qty`) - SUM(od.`costs` * od.`qty`) AS gross_profit
            FROM `orders_details` od
            INNER JOIN `orders` o ON od.`order_id` = o.`id`
            LEFT JOIN `products` p ON od.`real_product_id` = p.`id`
            WHERE YEAR(o.`invoice_date`) = YEAR(CURDATE())
              AND o.`status` NOT IN (1, 11)
            GROUP BY p.`id`, p.`sku`, p.`name`
            ORDER BY total_revenue DESC
            LIMIT 20
        """,
        "category": "join_aggregation",
        "notes": "Use invoice_date for date filtering. JOIN through orders to get status filter."
    },

    # Pattern 8: Sales by Sales Rep
    {
        "question": "Show sales totals by sales rep this month",
        "sql": """
            SELECT
                u.`id` AS user_id,
                TRIM(CONCAT(u.`fname`, ' ', u.`lname`)) AS sales_rep_name,
                COUNT(o.`id`) AS order_count,
                SUM(o.`total`) AS total_sales
            FROM `orders` o
            INNER JOIN `synced_users` u ON o.`sales_rep` = u.`id`
            WHERE o.`invoice_date` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND o.`invoice_date` < DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
              AND o.`status` NOT IN (1, 11)
            GROUP BY u.`id`, sales_rep_name
            ORDER BY total_sales DESC
        """,
        "category": "join_aggregation",
        "notes": "sales_rep = 0 means no sales rep assigned. Filter these out or handle with LEFT JOIN."
    },

    # Pattern 9: Order Aging Report
    {
        "question": "Show me the aging report for all open orders",
        "sql": """
            SELECT
                o.`id` AS order_id,
                o.`invoice_date`,
                o.`due_date`,
                o.`total`,
                IFNULL(t.amount_paid, 0) AS amount_paid,
                ROUND(o.`total` - IFNULL(t.amount_paid, 0), 2) AS balance,
                DATEDIFF(CURDATE(), o.`due_date`) AS days_overdue,
                CASE
                    WHEN DATEDIFF(CURDATE(), o.`due_date`) <= 0 THEN 'Current'
                    WHEN DATEDIFF(CURDATE(), o.`due_date`) BETWEEN 1 AND 30 THEN '1-30 Days'
                    WHEN DATEDIFF(CURDATE(), o.`due_date`) BETWEEN 31 AND 60 THEN '31-60 Days'
                    WHEN DATEDIFF(CURDATE(), o.`due_date`) BETWEEN 61 AND 90 THEN '61-90 Days'
                    ELSE '90+ Days'
                END AS aging_bucket
            FROM `orders` o
            LEFT JOIN (
                SELECT `type_id` AS order_id, SUM(`amount`) AS amount_paid
                FROM `transaction_log`
                WHERE `type` = 'order'
                  AND (`status` = 1 OR `status` = 2 OR `status` = 4)
                GROUP BY `type_id`
            ) t ON o.`id` = t.order_id
            WHERE o.`status` NOT IN (1, 11)
            HAVING balance > 0.01
            ORDER BY days_overdue DESC
        """,
        "category": "financial",
        "notes": "Aging is calculated from due_date. HAVING filters post-aggregation."
    },

    # Pattern 10: Purchase Orders by Vendor
    {
        "question": "Show all pending purchase orders by vendor",
        "sql": """
            SELECT
                po.`id` AS po_id,
                v.`name` AS vendor_name,
                po.`total`,
                po.`value_received`,
                po.`outstanding_balance`,
                po.`time` AS created_at,
                ps.`title` AS status
            FROM `po_` po
            INNER JOIN `po_vendors` v ON po.`vendor_id` = v.`id`
            LEFT JOIN `po_statuses` ps ON po.`status_id` = ps.`id`
            WHERE po.`status_id` IN (1, 3, 4, 5)
            ORDER BY po.`time` DESC
        """,
        "category": "lookup",
        "notes": "PO table name is po_ (with trailing underscore). Status 1=Pending, 3=Approved, 4=Sent, 5=Accepted."
    },

    # Pattern 11: Quote Conversion Rate
    {
        "question": "What is our quote-to-order conversion rate this quarter?",
        "sql": """
            SELECT
                COUNT(*) AS total_quotes,
                SUM(CASE WHEN `order_id` IS NOT NULL AND `order_id` > 0 THEN 1 ELSE 0 END) AS converted_quotes,
                ROUND(
                    SUM(CASE WHEN `order_id` IS NOT NULL AND `order_id` > 0 THEN 1 ELSE 0 END) / COUNT(*) * 100,
                    2
                ) AS conversion_rate_pct
            FROM `quotes`
            WHERE `generation_time` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND `generation_time` < DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
              AND `status` NOT IN (4)
        """,
        "category": "aggregation",
        "notes": "Converted quotes have order_id > 0. Exclude CANCELLED(4)."
    },

    # Pattern 12: RMA/Returns Summary
    {
        "question": "How many returns were processed this month and what was the total refund value?",
        "sql": """
            SELECT
                COUNT(DISTINCT r.`id`) AS rma_count,
                COUNT(rd.`id`) AS returned_items,
                SUM(rd.`quantity_returned`) AS total_units_returned,
                SUM(rd.`quantity_returned` * od.`price`) AS total_refund_value
            FROM `rmas` r
            INNER JOIN `rma_details` rd ON rd.`rma_id` = r.`id`
            INNER JOIN `orders_details` od ON rd.`order_detail_id` = od.`id`
            WHERE r.`created_at` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND r.`created_at` < DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
        """,
        "category": "join_aggregation",
        "notes": "RMA details link to order_details to get the price. Use DISTINCT for rma_count since JOINs duplicate rows."
    },

    # Pattern 13: Gross Margin Analysis
    {
        "question": "What is the gross margin by product category?",
        "sql": """
            SELECT
                pc.`title` AS category,
                SUM(od.`price` * od.`qty`) AS revenue,
                SUM(od.`costs` * od.`qty`) AS cost_of_goods,
                SUM(od.`price` * od.`qty`) - SUM(od.`costs` * od.`qty`) AS gross_profit,
                ROUND(
                    (SUM(od.`price` * od.`qty`) - SUM(od.`costs` * od.`qty`))
                    / NULLIF(SUM(od.`price` * od.`qty`), 0) * 100,
                    2
                ) AS margin_pct
            FROM `orders_details` od
            INNER JOIN `orders` o ON od.`order_id` = o.`id`
            LEFT JOIN `products` p ON od.`real_product_id` = p.`id`
            LEFT JOIN `product_category_relations` pcr ON pcr.`product_id` = p.`id`
            LEFT JOIN `product_categories` pc ON pcr.`category_id` = pc.`id`
            WHERE YEAR(o.`invoice_date`) = YEAR(CURDATE())
              AND o.`status` NOT IN (1, 11)
            GROUP BY pc.`id`, pc.`title`
            ORDER BY revenue DESC
        """,
        "category": "financial",
        "notes": "Products can have multiple categories. Use NULLIF to avoid division by zero."
    },

    # Pattern 14: Customer Group Analysis
    {
        "question": "Show total sales by customer group",
        "sql": """
            SELECT
                cg.`title` AS customer_group,
                COUNT(DISTINCT o.`id`) AS order_count,
                COUNT(DISTINCT o.`customer_id`) AS customer_count,
                SUM(o.`total`) AS total_sales,
                ROUND(SUM(o.`total`) / COUNT(DISTINCT o.`customer_id`), 2) AS avg_per_customer
            FROM `orders` o
            INNER JOIN `customers` c ON o.`customer_id` = c.`id`
            INNER JOIN `customer_group_relations` cgr ON cgr.`customer_id` = c.`id`
            INNER JOIN `customer_groups` cg ON cgr.`group_id` = cg.`id`
            WHERE o.`invoice_date` >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
              AND o.`status` NOT IN (1, 11)
            GROUP BY cg.`id`, cg.`title`
            ORDER BY total_sales DESC
        """,
        "category": "join_aggregation",
        "notes": "Customers can belong to multiple groups; orders will appear once per group. Use DISTINCT counts."
    },

    # Pattern 15: Shipping Analysis
    {
        "question": "What is the average shipping cost by state?",
        "sql": """
            SELECT
                a.`state`,
                COUNT(*) AS order_count,
                SUM(o.`shipping_fee`) AS total_shipping,
                ROUND(AVG(o.`shipping_fee`), 2) AS avg_shipping,
                SUM(o.`total`) AS total_sales
            FROM `orders` o
            LEFT JOIN `addresses` a ON o.`ship_id` = a.`id`
            WHERE o.`invoice_date` >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
              AND o.`status` NOT IN (1, 11)
              AND a.`state` IS NOT NULL
              AND a.`state` != ''
            GROUP BY a.`state`
            ORDER BY total_shipping DESC
        """,
        "category": "geographic",
        "notes": "JOIN addresses on ship_id (not bill_id) for shipping address. State values vary (abbreviations vs full names)."
    },

    # Pattern 16: Low Stock Alert
    {
        "question": "Which products are below minimum stock level?",
        "sql": """
            SELECT
                p.`id` AS product_id,
                p.`sku`,
                p.`name`,
                p.`min_stock_level`,
                IFNULL(SUM(ps.`qty`), 0) AS current_stock,
                p.`min_stock_level` - IFNULL(SUM(ps.`qty`), 0) AS deficit
            FROM `products` p
            LEFT JOIN `products_stock` ps ON ps.`product_id` = p.`id`
            WHERE p.`deleted_by` IS NULL
              AND p.`manage_stock` = '1'
              AND p.`min_stock_level` > 0
            GROUP BY p.`id`, p.`sku`, p.`name`, p.`min_stock_level`
            HAVING current_stock < p.`min_stock_level`
            ORDER BY deficit DESC
        """,
        "category": "inventory",
        "notes": "Only check products with manage_stock='1' and min_stock_level > 0. ENUM values use strings."
    },

    # Pattern 17: Sales by Store
    {
        "question": "Compare sales across stores this month",
        "sql": """
            SELECT
                s.`name` AS store_name,
                COUNT(o.`id`) AS order_count,
                SUM(o.`total`) AS total_sales,
                ROUND(AVG(o.`total`), 2) AS avg_order_value
            FROM `orders` o
            LEFT JOIN `stores` s ON o.`store` = s.`id`
            WHERE o.`invoice_date` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND o.`invoice_date` < DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
              AND o.`status` NOT IN (1, 11)
            GROUP BY s.`id`, s.`name`
            ORDER BY total_sales DESC
        """,
        "category": "aggregation",
        "notes": "store column in orders is a tinyint FK to stores.id."
    },

    # Pattern 18: Customer Credit Balance
    {
        "question": "Which customers have open store credits?",
        "sql": """
            SELECT
                c.`id` AS customer_id,
                TRIM(CONCAT(c.`fname`, ' ', c.`lname`)) AS customer_name,
                cc_comp.`name` AS company_name,
                cr.`id` AS credit_id,
                cr.`amount` AS credit_amount,
                IFNULL(SUM(tl.`amount`), 0) AS amount_used,
                cr.`amount` - IFNULL(SUM(tl.`amount`), 0) AS remaining_balance,
                cr.`time` AS created_at
            FROM `customers_credit` cr
            INNER JOIN `customers` c ON cr.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc_comp ON c.`company_id` = cc_comp.`id`
            LEFT JOIN `transaction_log` tl ON tl.`customer_credit_id` = cr.`id`
            WHERE cr.`status` IN (1, 3)
            GROUP BY cr.`id`, c.`id`, customer_name, company_name, cr.`amount`, cr.`time`
            HAVING remaining_balance > 0.01
            ORDER BY remaining_balance DESC
        """,
        "category": "financial",
        "notes": "Credit statuses: 1=Open, 3=Partially Used. Transaction_log links via customer_credit_id."
    },

    # Pattern 19: Order Fulfillment Status
    {
        "question": "Show all unfulfilled orders",
        "sql": """
            SELECT
                o.`id` AS order_id,
                os.`title` AS order_status,
                o.`time` AS created_at,
                TRIM(CONCAT(c.`fname`, ' ', c.`lname`)) AS customer_name,
                o.`total`,
                o.`picked`,
                o.`shipped`
            FROM `orders` o
            INNER JOIN `customers` c ON o.`customer_id` = c.`id`
            LEFT JOIN `order_status` os ON o.`status` = os.`id`
            WHERE o.`shipped` != '1'
              AND o.`status` NOT IN (1, 11, 12)
            ORDER BY o.`time` ASC
        """,
        "category": "fulfillment",
        "notes": "shipped='0' means not shipped, '2' means partially shipped. Exclude cancelled(11) and refunded(12)."
    },

    # Pattern 20: Commission Report
    {
        "question": "Show commission totals by sales rep for this period",
        "sql": """
            SELECT
                TRIM(CONCAT(u.`fname`, ' ', u.`lname`)) AS sales_rep_name,
                COUNT(DISTINCT cm.`order_id`) AS order_count,
                SUM(cm.`amount`) AS total_commission,
                SUM(cm.`commission_price` * cm.`quantity`) AS total_commission_basis
            FROM `commissions` cm
            INNER JOIN `commission_periods` cp ON cm.`commission_period_id` = cp.`id`
            INNER JOIN `synced_users` u ON cp.`sales_rep_user_id` = u.`id`
            WHERE cp.`cutoff_date` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND cp.`cutoff_date` < DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
            GROUP BY u.`id`, sales_rep_name
            ORDER BY total_commission DESC
        """,
        "category": "financial",
        "notes": "Commissions are grouped by commission_period which has a sales_rep_user and cutoff_date."
    },
]


def get_training_pairs():
    """Return all training pairs."""
    return TRAINING_PAIRS


def get_pairs_by_category(category):
    """Get training pairs filtered by category."""
    return [pair for pair in TRAINING_PAIRS if pair.get("category") == category]


def get_categories():
    """Get list of all unique categories."""
    return list(set(pair.get("category", "uncategorized") for pair in TRAINING_PAIRS))


if __name__ == "__main__":
    # Print summary when run directly
    print("=" * 70)
    print("Sample Query Library Summary")
    print("=" * 70)
    print(f"\nTotal training pairs: {len(TRAINING_PAIRS)}")
    print(f"\nCategories:")
    for cat in sorted(get_categories()):
        count = len(get_pairs_by_category(cat))
        print(f"  - {cat}: {count} queries")
    print("\n" + "=" * 70)
