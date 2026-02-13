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

    # Pattern 0: Order Status JOIN (Best Practice)
    {
        "question": "Show me all orders with their status names from last month",
        "sql": """
            SELECT
                o.`id` AS order_id,
                o.`time` AS created_at,
                o.`invoice_date`,
                o.`total`,
                os.`title` AS status_name,
                TRIM(CONCAT(c.`fname`, ' ', c.`lname`)) AS customer_name
            FROM `orders` o
            INNER JOIN `order_status` os ON o.`status` = os.`id`
            INNER JOIN `customers` c ON o.`customer_id` = c.`id`
            WHERE o.`invoice_date` >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
              AND o.`invoice_date` < DATE_FORMAT(CURDATE(), '%Y-%m-01')
            ORDER BY o.`invoice_date` DESC
        """,
        "category": "aggregation",
        "notes": "ALWAYS JOIN order_status to get status titles (os.title). NEVER use CASE statements with hardcoded status names - they vary by client."
    },

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

    # ═══════════════════════════════════════════════════════════════
    # REPORT-SPECIFIC QUERIES
    # From nl-to-sql-training-data-response-reports.md Section 4
    # Added: 2025-02-11
    # ═══════════════════════════════════════════════════════════════

    # Revenue Performance Report - Q1
    {
        "question": "Show me monthly order count and revenue by status for this year",
        "sql": """
            SELECT
                YEAR(`invoice_date`) AS `year`,
                MONTH(`invoice_date`) AS `month`,
                os.`title` AS `status_label`,
                COUNT(*) AS `order_count`,
                COALESCE(SUM(`total`), 0) AS `revenue`
            FROM `orders` o
            INNER JOIN `order_status` os ON o.`status` = os.`id`
            WHERE `invoice_date` >= DATE_FORMAT(CURDATE(), '%Y-01-01')
              AND `invoice_date` <= DATE_FORMAT(CURDATE(), '%Y-12-31 23:59:59')
              AND (`status` = 2 OR `status` = 3 OR `status` = 4)
            GROUP BY `year`, `month`, `status_label`
            ORDER BY `year`, `month`
        """,
        "category": "revenue_performance",
        "notes": "Use invoice_date for revenue reports. Filter by Completed(2), Invoiced(3), Shipped(4). Group by Year-Month."
    },

    # Revenue Performance Report - Q2
    {
        "question": "Show revenue performance by creation date for Q1 2025",
        "sql": """
            SELECT
                YEAR(`time`) AS `year`,
                MONTH(`time`) AS `month`,
                COUNT(*) AS `order_count`,
                COALESCE(SUM(`total`), 0) AS `revenue`
            FROM `orders`
            WHERE `time` >= '2025-01-01 00:00:00'
              AND `time` <= '2025-03-31 23:59:59'
              AND (`status` = 2 OR `status` = 3)
            GROUP BY `year`, `month`
            ORDER BY `year`, `month`
        """,
        "category": "revenue_performance",
        "notes": "Alternative to invoice_date filtering - uses time (creation date) instead. Useful when invoice_date is NULL."
    },

    # JBD Commission Report - Q3
    {
        "question": "Find all paid orders from Q1 2025 for JBD commission calculation",
        "sql": """
            SELECT
                tl.`type_id` AS `order_id`,
                o.`customer_id`,
                cc.`name` AS `company_name`,
                o.`invoice_date`
            FROM `transaction_log` tl
            INNER JOIN `orders` o ON tl.`type_id` = o.`id`
            INNER JOIN `customers` c ON o.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE tl.`type` = 'order'
              AND tl.`time` >= '2025-01-01 00:00:00'
              AND tl.`time` <= '2025-03-31 23:59:59'
              AND o.`status` != 1
              AND o.`status` != 10
            GROUP BY tl.`type_id`
            HAVING (o.`total` - COALESCE(SUM(
                CASE WHEN tl.`status` = 2 THEN tl.`amount` ELSE 0 END
            ), 0)) = 0
            ORDER BY cc.`name`
        """,
        "category": "jbd_commission",
        "notes": "Paid order = balance is exactly 0. Transaction status 2 = Succeeded. Exclude ABANDONED(1) and QUOTE(10)."
    },

    # JBD Commission Report - Q4
    {
        "question": "Get order line items with customer product pricing for commission calculation",
        "sql": """
            SELECT
                od.`id` AS `order_detail_id`,
                od.`qty` AS `quantity`,
                od.`price`,
                od.`costs` AS `cost`,
                p.`sku`,
                od.`product_name`,
                xrcp.`price` AS `customer_product_price`,
                xrcp.`id` AS `customer_product_id`
            FROM `orders_details` od
            INNER JOIN `products` p ON od.`real_product_id` = p.`id`
            LEFT JOIN `x_rewards_customer_products` xrcp
                ON xrcp.`customer_id` = 12345
                AND xrcp.`product_id` = p.`id`
                AND xrcp.`deleted_by_user_id` IS NULL
            WHERE od.`order_id` = 67890
        """,
        "category": "jbd_commission",
        "notes": "Filter deleted_by_user_id IS NULL for active customer products. Uses x_rewards_customer_products for customer-specific pricing."
    },

    # JBD Commission Report - Q5
    {
        "question": "Get reward amounts per profile for a customer product",
        "sql": """
            SELECT
                `profile_id`,
                `reward_amount`
            FROM `x_rewards_customer_product_reward_amounts`
            WHERE `customer_product_id` = 12345
        """,
        "category": "jbd_commission",
        "notes": "Each customer product can have different reward amounts per profile. Used to calculate net price for commission."
    },

    # JBD Commission Report - Q6
    {
        "question": "Get the custom JBD commission rate for a company",
        "sql": """
            SELECT `value`
            FROM `custom_fields`
            WHERE `type` = 'customer_company'
              AND `type_id` = 12345
              AND `name` = 'custom_jbd_commission_rate'
        """,
        "category": "jbd_commission",
        "notes": "JBD commission rates are stored as custom fields on customer_companies. EAV pattern for flexible field storage."
    },

    # Commission Report - Q7
    {
        "question": "Show me commission details for all sales reps between January and March 2025",
        "sql": """
            SELECT
                c.`id`,
                c.`commission_date`,
                c.`quantity`,
                c.`commission_price`,
                c.`commission_percent`,
                c.`unit_commission`,
                c.`amount`,
                c.`order_id`,
                c.`order_detail_id`,
                c.`rma_detail_id`,
                c.`category_id`,
                cp.`sales_rep_user_id`,
                cc.`label` AS `category_label`
            FROM `commissions` c
            INNER JOIN `commission_periods` cp ON c.`commission_period_id` = cp.`id`
            INNER JOIN `commission_categories` cc ON c.`category_id` = cc.`id`
            WHERE c.`commission_date` >= '2025-01-01'
              AND c.`commission_date` <= '2025-03-31'
            ORDER BY c.`order_id`
        """,
        "category": "commission_report",
        "notes": "Commissions link to commission_periods for sales rep. commission_categories has SALE(1) and QUOTA(2)."
    },

    # Commission Report - Q8
    {
        "question": "Sum commission percentages per order detail for contribution calculation",
        "sql": """
            SELECT
                `order_detail_id`,
                SUM(`commission_percent`) AS `total_percent`
            FROM `commissions`
            WHERE `order_detail_id` IN (123, 456, 789)
            GROUP BY `order_detail_id`
        """,
        "category": "commission_report",
        "notes": "Used in Sales by Reps report to calculate each rep's contribution percentage when multiple reps share an order."
    },

    # Reward Liability Report - Q9
    {
        "question": "Calculate unredeemed reward liability opening balance before March 2025",
        "sql": """
            SELECT
                COALESCE(SUM(`amount`), 0) AS `opening_liability`
            FROM `x_rewards_rewards`
            WHERE `created_at` < '2025-03-01 00:00:00'
              AND `is_void` = 0
              AND `redemption_period_id` IS NULL
        """,
        "category": "reward_liability",
        "notes": "is_void=0 excludes voided rewards. redemption_period_id IS NULL means unredeemed. This is the liability balance."
    },

    # Reward Liability Report - Q10
    {
        "question": "Show reward liability by customer for Q1 2025",
        "sql": """
            SELECT
                xrp.`customer_id`,
                c.`fname` AS `first_name`,
                c.`lname` AS `last_name`,
                cc.`name` AS `company_name`,
                COALESCE(SUM(xrr.`amount`), 0) AS `liability_amount`,
                COUNT(xrr.`id`) AS `reward_count`
            FROM `x_rewards_rewards` xrr
            INNER JOIN `x_rewards_profiles` xrp ON xrr.`profile_id` = xrp.`id`
            INNER JOIN `customers` c ON xrp.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE xrr.`created_at` >= '2025-01-01 00:00:00'
              AND xrr.`created_at` <= '2025-03-31 23:59:59'
              AND xrr.`is_void` = 0
              AND xrr.`redemption_period_id` IS NULL
            GROUP BY xrp.`customer_id`
            ORDER BY cc.`name`
        """,
        "category": "reward_liability",
        "notes": "Groups unredeemed rewards by customer. Always filter is_void=0 and redemption_period_id IS NULL for liability."
    },

    # Adjustment Report - Q11
    {
        "question": "Get adjustment details by customer for Q1 2025",
        "sql": """
            SELECT
                xa.`id`,
                xa.`created_at`,
                xa.`amount`,
                xa.`note`,
                xa.`is_approved`,
                xrp.`cutoff_date`,
                xrr.`first_name` AS `recipient_first_name`,
                xrr.`last_name` AS `recipient_last_name`,
                c.`fname` AS `customer_first_name`,
                c.`lname` AS `customer_last_name`,
                cc.`name` AS `company_name`
            FROM `x_rewards_adjustments` xa
            INNER JOIN `x_rewards_redemption_periods` xrp ON xa.`redemption_period_id` = xrp.`id`
            INNER JOIN `x_rewards_recipients` xrr ON xrp.`recipient_id` = xrr.`id`
            INNER JOIN `customers` c ON xrp.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE xa.`created_at` >= '2025-01-01 00:00:00'
              AND xa.`created_at` <= '2025-03-31 23:59:59'
              AND xa.`is_approved` = 1
            ORDER BY cc.`name`
        """,
        "category": "adjustment_report",
        "notes": "Always filter is_approved=1 for adjustments that count toward balance. Adjustments can be positive or negative."
    },

    # Pay Sheet Report - Q12
    {
        "question": "Show paid pay sheets with recipient and payment details for Q1 2025",
        "sql": """
            SELECT
                xrp.`id` AS `redemption_period_id`,
                xrp.`cutoff_date`,
                xrp.`balance`,
                xrr.`first_name`,
                xrr.`middle_name`,
                xrr.`last_name`,
                xrr.`email`,
                xrr.`ssn_encrypted`,
                c.`fname` AS `customer_first_name`,
                c.`lname` AS `customer_last_name`,
                cc.`name` AS `company_name`,
                COALESCE(SUM(xrpay.`amount`), 0) AS `total_paid`
            FROM `x_rewards_redemption_periods` xrp
            INNER JOIN `x_rewards_recipients` xrr ON xrp.`recipient_id` = xrr.`id`
            INNER JOIN `customers` c ON xrp.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            LEFT JOIN `x_rewards_payments` xrpay ON xrpay.`redemption_period_id` = xrp.`id` AND xrpay.`void` = 0
            WHERE xrp.`cutoff_date` >= '2025-01-01'
              AND xrp.`cutoff_date` <= '2025-03-31'
            GROUP BY xrp.`id`
            ORDER BY cc.`name`, xrr.`last_name`
        """,
        "category": "pay_sheet",
        "notes": "Filter void=0 for payments. SSN is encrypted. Redemption periods group rewards by recipient, customer, and cutoff_date."
    },

    # 1099 Report - Q13
    {
        "question": "Calculate 1099 totals by recipient for tax year 2025",
        "sql": """
            SELECT
                xrr.`id` AS `recipient_id`,
                xrr.`first_name`,
                xrr.`middle_name`,
                xrr.`last_name`,
                xrr.`ssn_encrypted`,
                xrr.`address1`,
                xrr.`city`,
                xrr.`state`,
                xrr.`zip`,
                xrr.`w9_received`,
                COALESCE(SUM(xrpay.`amount`), 0) AS `total_payments`
            FROM `x_rewards_payments` xrpay
            INNER JOIN `x_rewards_redemption_periods` xrp ON xrpay.`redemption_period_id` = xrp.`id`
            INNER JOIN `x_rewards_recipients` xrr ON xrp.`recipient_id` = xrr.`id`
            WHERE xrp.`cutoff_date` >= '2025-01-01'
              AND xrp.`cutoff_date` <= '2025-12-31'
              AND xrpay.`void` = 0
            GROUP BY xrr.`id`
            HAVING `total_payments` > 0
            ORDER BY xrr.`last_name`, xrr.`first_name`
        """,
        "category": "pay_sheet",
        "notes": "1099 reporting uses cutoff_date year for tax purposes. w9_received indicates if W-9 form is on file. Filter void=0."
    },

    # RPM Report - Q14
    {
        "question": "Show RPM data aggregated by product for Q1 2025",
        "sql": """
            SELECT
                rpm.`product_id`,
                rpm.`product_sku`,
                rpm.`product_name`,
                SUM(rpm.`parts_sold`) AS `total_parts_sold`,
                SUM(rpm.`gross_parts_revenue`) AS `total_gross_parts_revenue`,
                SUM(rpm.`net_parts_revenue`) AS `total_net_parts_revenue`,
                SUM(rpm.`labor_hours`) AS `total_labor_hours`,
                SUM(rpm.`gross_labor_revenue`) AS `total_gross_labor_revenue`,
                SUM(rpm.`net_labor_revenue`) AS `total_net_labor_revenue`,
                SUM(rpm.`customer_retail_price`) AS `total_customer_retail_price`
            FROM `x_rewards_rpm_data` rpm
            INNER JOIN `x_rewards_rewards` xrr ON rpm.`reward_id` = xrr.`id`
            WHERE xrr.`created_at` >= '2025-01-01 00:00:00'
              AND xrr.`created_at` <= '2025-03-31 23:59:59'
              AND xrr.`is_void` = 0
            GROUP BY rpm.`product_id`
            ORDER BY rpm.`product_sku`
        """,
        "category": "rpm_report",
        "notes": "RPM = Retail Profit Management. Net revenue = gross revenue - rewards. Always filter is_void=0 on rewards."
    },

    # Customer Product Inventory - Q15
    {
        "question": "Show customer product inventory with stock levels",
        "sql": """
            SELECT
                xrcp.`id`,
                xrcp.`customer_id`,
                xrcp.`product_id`,
                p.`sku`,
                p.`name` AS `product_name`,
                xrcp.`price`,
                xrcp.`low_inventory_quantity`,
                xrcp.`preferred_inventory_quantity`,
                xrcp.`inventory_quantity_override`,
                xrcp.`reorder`,
                c.`fname` AS `customer_first_name`,
                c.`lname` AS `customer_last_name`,
                cc.`name` AS `company_name`
            FROM `x_rewards_customer_products` xrcp
            INNER JOIN `products` p ON xrcp.`product_id` = p.`id`
            INNER JOIN `customers` c ON xrcp.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE xrcp.`deleted_by_user_id` IS NULL
              AND xrcp.`deactivated` = 0
            ORDER BY cc.`name`, p.`sku`
        """,
        "category": "customer_product",
        "notes": "Filter deleted_by_user_id IS NULL for soft-delete. deactivated=0 for active products. Customer products have custom pricing."
    },

    # Purchase Obligations - Q16
    {
        "question": "List active purchase obligations by customer",
        "sql": """
            SELECT
                xrpo.`id`,
                xrpo.`label`,
                xrpo.`quantity_required`,
                xrpo.`rental_price`,
                xrpo.`agreement_date`,
                c.`fname` AS `customer_first_name`,
                c.`lname` AS `customer_last_name`,
                cc.`name` AS `company_name`
            FROM `x_rewards_purchase_obligations` xrpo
            INNER JOIN `customers` c ON xrpo.`customer_id` = c.`id`
            LEFT JOIN `customer_companies` cc ON c.`company_id` = cc.`id`
            WHERE xrpo.`deleted_by_user_id` IS NULL
            ORDER BY cc.`name`, xrpo.`label`
        """,
        "category": "customer_product",
        "notes": "Purchase obligations track customer contractual purchase requirements. Filter deleted_by_user_id IS NULL for active."
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
