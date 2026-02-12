# ADR/Zangerine Database Schema Documentation

**Database Type:** MySQL 5.6.10+ (InnoDB)
**Database Name:** ADR Production
**Purpose:** Complete ERP system for order management, inventory control, purchasing, customer relationship management, and financial tracking

**Version:** MySQL 5.6.10+
**Character Set:** utf8mb4
**Timezone:** UTC (server time); local times in date fields

---

## Database Overview

The ADR/Zangerine system is a comprehensive ERP database managing:
- **Orders & Sales**: Customer orders, invoicing, payments, shipping
- **Inventory**: Product catalog, stock tracking across warehouses
- **Purchasing**: Purchase orders, vendor management, receiving
- **CRM**: Customer records, companies, contacts, sales reps
- **Fulfillment**: Pick, pack, ship workflows
- **Returns**: RMA processing and customer credits
- **Recurring Orders**: Subscription/auto-order management
- **Commission Tracking**: Sales rep commission calculations

**Total Tables:** 360+ tables per client (multi-tenant architecture)

---

## Core Tables (Top 15)

### Table: orders

**Purpose:** Central transactional table storing all customer sales orders. Every sale creates a row here.

**Row Count:** ~100,000+ (varies by client)

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique order identifier
- `customer_id` (BIGINT, NOT NULL, INDEXED) - FK to `customers`
- `status` (TINYINT, NOT NULL, DEFAULT 1, INDEXED) - FK to `order_status` (1=Abandoned, 2=Completed, 11=Cancelled, etc.)
- `total` (DECIMAL(15,5), NOT NULL) - Grand total (line items + shipping + tax - discounts)
- `tax_fee` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Tax amount
- `shipping_fee` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Shipping charge
- `discount_amount` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Total discounts applied
- `ship_id` (BIGINT, NOT NULL, DEFAULT 0, INDEXED) - FK to `addresses` (shipping address)
- `bill_id` (BIGINT, DEFAULT 0, INDEXED) - FK to `addresses` (billing address)
- `time` (DATETIME, NOT NULL, DEFAULT CURRENT_TIMESTAMP, INDEXED) - Order creation timestamp
- `invoice_date` (DATETIME) - **PRIMARY reporting date** (use this for sales reports, not `time`)
- `due_date` (DATE) - Payment due date
- `ship_date` (DATE) - Actual ship date
- `sales_rep` (INT, NOT NULL, DEFAULT 0) - FK to `synced_users`
- `store` (TINYINT, NOT NULL, DEFAULT 0) - FK to `stores`
- `picked` (ENUM('0','1','2'), NOT NULL, DEFAULT '0') - 0=Not Picked, 1=Picked, 2=Partially Picked
- `shipped` (ENUM('0','1','2'), NOT NULL, DEFAULT '0') - 0=Not Shipped, 1=Shipped, 2=Partially Shipped
- `order_type` (VARCHAR(255), NOT NULL, DEFAULT 'sales_order') - 'sales_order', 'transfer_order', etc.
- `reference_id` (VARCHAR(20), NOT NULL, INDEXED) - Unique reference identifier

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `time`, `status`, `customer_id`, `ship_id`, `bill_id`, `reference_id`
- COMPOSITE INDEX on (`status`, `customer_id`)

**Important Notes:**
- **Use `invoice_date` for reports, NOT `time`** (time is creation date, invoice_date is when invoiced)
- Order balance = `total - SUM(successful transaction amounts)`
- Status 1 (ABANDONED) and 11 (CANCELLED) are excluded from sales reports
- `picked` and `shipped` are ENUMs using string values ('0', '1', '2'), NOT booleans
- ship_id = 0 and bill_id = 0 mean no address set (not a valid FK)
- **Always JOIN `order_status` to get status titles** - do NOT hardcode status names in CASE statements

---

### Table: order_status

**Purpose:** Lookup table containing human-readable status titles for orders. Always JOIN this table to display proper status names.

**Row Count:** ~20 statuses

**Key Columns:**
- `id` (TINYINT, PRIMARY KEY) - Status ID (referenced by `orders.status`)
- `title` (VARCHAR(255), NOT NULL) - Human-readable status title

**Key Status Values:**

| ID | Title | Usage |
|----|-------|-------|
| 1 | Abandoned | Incomplete/abandoned carts - exclude from sales reports |
| 2 | Completed | Order completed |
| 3 | Shipped | Order has been shipped |
| 9 | Paid in Full | Order fully paid |
| 10 | Pro Forma | Pro forma invoice (quote) - exclude from sales reports |
| 11 | Cancelled | Order cancelled - exclude from sales reports |
| 12 | Refunded | Order refunded |
| 15 | Paid Partial | Partially paid order |
| 30 | Pending Fulfilment | Awaiting fulfillment |
| 31 | Picking | Currently being picked |
| 32 | Packed | Order has been packed |
| 33 | Picked | Order has been picked |
| 34 | Picked Partially | Partially picked order |
| 40 | Shipped Partially | Partially shipped order |
| 50 | Backordered | Items on backorder |

**Important Notes:**
- **ALWAYS use JOIN instead of hardcoded CASE statements**:
  ```sql
  INNER JOIN `order_status` os ON o.`status` = os.`id`
  SELECT os.`title` AS status_name
  ```
- **Never hardcode status titles** - they may change or vary by client
- Common filters: `status IN (2, 3, 9)` for completed orders
- Exclude from sales reports: `status NOT IN (1, 10, 11)` (Abandoned, Pro Forma, Cancelled)

---

### Table: orders_details

**Purpose:** Line items within orders. Each row is one product/SKU on an order with quantity, price, and cost.

**Row Count:** ~500,000+ (10-20x orders table)

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique line item ID
- `order_id` (BIGINT, NOT NULL) - FK to `orders`
- `real_product_id` (BIGINT) - FK to `products` (actual product reference - use this for JOINs!)
- `product_sku` (VARCHAR) - SKU snapshot at order time
- `product_name` (VARCHAR) - Product name snapshot at order time
- `qty` (DECIMAL) - Ordered quantity
- `price` (DECIMAL) - Unit selling price at order time
- `original_price` (DECIMAL) - Original price before discounts
- `costs` (DECIMAL) - Unit cost (COGS)
- `sort` (INT) - Display order

**Calculated Fields (not in DB, from EntityService):**
- `total_price` = `price * qty`
- `total_cost` = Complex cost calculation based on inventory_type_id
- `gross_margin` = `total_price - total_cost`

**Important Notes:**
- **Use `real_product_id` for JOINs, not product_id**
- `product_name` and `product_sku` are snapshots that don't update if product is renamed
- Sort by `sort` field for correct display order

---

### Table: customers

**Purpose:** Customer master records - every buyer in the system.

**Row Count:** ~50,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique customer ID
- `fname` (VARCHAR(100), NOT NULL) - First name (API: `first_name`)
- `lname` (VARCHAR(50), NOT NULL) - Last name (API: `last_name`)
- `company_id` (INT, NOT NULL) - FK to `customer_companies`
- `email` (VARCHAR(100), NOT NULL, INDEXED) - Email address
- `phone` (VARCHAR(30), INDEXED) - Phone number
- `creation_date` (DATETIME, NOT NULL, DEFAULT CURRENT_TIMESTAMP) - Creation timestamp (API: `created_at`)
- `sales_rep_id` (INT, NOT NULL, DEFAULT 0) - FK to `synced_users`
- `guest` (TINYINT UNSIGNED, DEFAULT 0) - Guest checkout flag (1 = guest)
- `currency_id` (INT, NOT NULL, DEFAULT 5) - FK to currencies (5 = USD default)

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `email`, `phone`, `fname`, `lname`, `company_id`

**Important Notes:**
- Emails starting with `$$` are system-generated placeholders (filter with `email NOT LIKE '$$%'`)
- `guest = 1` indicates guest checkout customers (not registered)
- Display label: if company exists → "Company (First Last)", else → "First Last"
- Customer groups are in `customer_group_relations` link table

---

### Table: products

**Purpose:** Product catalog - every SKU including variants, kits, and recurring products.

**Row Count:** ~25,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique product ID
- `sku` (VARCHAR) - Stock keeping unit (unique business identifier)
- `name` (VARCHAR) - Product name
- `price` (DECIMAL) - Standard selling price
- `cost` (DECIMAL) - Standard cost
- `manage_stock` (ENUM('1','0')) - Whether stock is managed
- `min_stock_level` (INT) - Minimum stock threshold
- `status` (ENUM('1','0')) - Published/active status (API: `is_published`)
- `deleted_by` (INT) - FK to `synced_users` (soft delete; NULL = active)
- `master_product_id` (INT) - FK to parent product (for variants)
- `is_child` (ENUM('1','0')) - Is a variant of parent product
- `inventory_type_id` (INT) - 1=FIFO, 2=Serial Number, 3=Standard Cost

**Important Notes:**
- **Soft delete:** `deleted_by IS NULL` = active, `deleted_by IS NOT NULL` = deleted
- Deleted products still referenced by historical order_details
- Many boolean-like fields use ENUM('1','0') instead of BOOLEAN
- Product categories in `product_category_relations` link table
- Stock levels in `products_stock` table

---

### Table: products_stock

**Purpose:** Stock levels by warehouse location. Multiple rows per product (one per warehouse location).

**Row Count:** ~100,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `product_id` (BIGINT) - FK to `products`
- `location_warehouse_id` (INT) - FK to `location_warehouses` (0 = no specific warehouse)
- `location_row`, `location_column`, `location_shelf`, `location_bin` (VARCHAR) - Warehouse location
- `qty` (INT) - Quantity at this location

**Important Notes:**
- **Always SUM(qty) and GROUP BY product_id** for total stock
- location_warehouse_id = 0 means no specific warehouse assigned
- Filter `deleted_by IS NULL` on products table when joining

---

### Table: addresses

**Purpose:** Shared address records used by customers, orders, quotes, POs, vendors.

**Row Count:** ~100,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `fname` (VARCHAR(100), NOT NULL) - First name (API: `first_name`)
- `lname` (VARCHAR(50), NOT NULL) - Last name (API: `last_name`)
- `address1`, `address2` (VARCHAR) - Street address
- `city`, `state`, `zip` (VARCHAR) - City, state, postal code (API: `postal_code`)
- `country` (VARCHAR) - Country code
- `phone` (VARCHAR)

**Important Notes:**
- Shared table: same address can be referenced by multiple entities
- Column mappings: `fname` → `first_name`, `lname` → `last_name`, `zip` → `postal_code`
- Orders reference via `ship_id` (shipping) and `bill_id` (billing)

---

### Table: transaction_log

**Purpose:** Payment transactions for orders. Multiple transactions per order (payments, refunds, voids).

**Row Count:** ~200,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `type` (VARCHAR) - Segment: 'order' for order transactions
- `type_id` (BIGINT) - FK to `orders` (when type = 'order')
- `amount` (DECIMAL) - Transaction amount
- `time` (DATETIME) - Transaction timestamp (API: `created_at`)
- `status` (TINYINT) - 1=Pending, 2=Succeeded, 3=Declined, 4=Refunded, 5=Voided
- `customer_credit_id` (INT) - FK to `customers_credit` (if paying with store credit)

**Important Notes:**
- **Always filter `type = 'order'`** for order transactions
- **Successful transactions:** status IN (1, 2, 4) count toward paid amount
- Order balance = `orders.total - SUM(transaction_log.amount WHERE type='order' AND (status=1 OR status=2 OR status=4))`
- Status 4 (Refunded) reduces balance

---

### Table: po_ (purchase_orders)

**Purpose:** Purchase orders placed with vendors for restocking or dropship fulfillment.

**Row Count:** ~10,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `vendor_id` (INT) - FK to `po_vendors`
- `is_dropship` (ENUM('1','0')) - Dropship order flag
- `status_id` (INT) - FK to `po_statuses` (1=Pending, 3=Approved, 4=Sent, 5=Accepted, 8=Received)
- `total` (DECIMAL) - PO total
- `value_received` (DECIMAL) - Value of goods received
- `outstanding_balance` (DECIMAL) - Outstanding balance
- `time` (DATETIME) - Creation timestamp (API: `created_at`)

**Important Notes:**
- **Table name is `po_`** (with trailing underscore) - intentional
- `is_dropship = '1'` means vendor ships directly to customer
- PO line items in `po_details` table

---

### Table: po_details

**Purpose:** Line items on purchase orders.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `po_id` (INT) - FK to `po_`
- `real_product_id` (INT) - FK to `products`
- `qty` (DECIMAL) - Ordered quantity
- `cost` (DECIMAL) - Unit cost
- `order_detail_id` (INT) - FK to `orders_details` (links PO line to sales order line for dropship)

---

### Table: quotes

**Purpose:** Customer quotes/estimates that can be converted to orders.

**Row Count:** ~20,000+

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `customer_id` (BIGINT) - FK to `customers`
- `status` (TINYINT) - 1=Created, 2=Sent, 4=Cancelled, 7=Accepted, etc.
- `total` (DECIMAL) - Quote total
- `generation_time` (DATETIME) - Creation timestamp (API: `created_at`)
- `order_id` (INT) - FK to `orders` (populated when converted to order)

**Important Notes:**
- When quote is converted to order, `order_id` is set to the new order's ID
- Quote line items in `quotes_details` table
- Status 4 (Cancelled) typically excluded from reports

---

### Table: rmas

**Purpose:** Return merchandise authorizations (customer returns).

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `customer_id` (BIGINT) - FK to `customers`
- `status` (TINYINT) - 0=Created, 1=Pending, 2=Received, 3=Accepted, 4=Rejected
- `created_at` (DATETIME)

**Important Notes:**
- RMA line items in `rma_details` table
- RMA details link to `orders_details` to get original prices

---

### Table: customer_companies

**Purpose:** Company records that customers belong to.

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `name` (VARCHAR) - Company name
- `email`, `phone`, `website` (VARCHAR)

---

### Table: synced_users

**Purpose:** System users (employees, sales reps, admins).

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `fname`, `lname` (VARCHAR) - First and last name
- `email` (VARCHAR)
- `role_id` (INT) - FK to roles table

**Important Notes:**
- Used for `orders.sales_rep`, `customers.sales_rep_id`, etc.
- sales_rep = 0 means no sales rep assigned

---

### Table: commissions

**Purpose:** Commission calculations for sales reps.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `commission_period_id` (INT) - FK to `commission_periods`
- `order_id` (BIGINT) - FK to `orders`
- `amount` (DECIMAL) - Commission amount

**Important Notes:**
- Commission data links through `commission_periods` → `sales_rep_user`
- Not directly linked to `orders.sales_rep`

---

## Table Relationships

### Key Foreign Key Patterns

1. **orders → customers**
   - `orders.customer_id` → `customers.id`
   - Many orders per customer

2. **orders → addresses**
   - `orders.ship_id` → `addresses.id` (shipping)
   - `orders.bill_id` → `addresses.id` (billing)
   - ship_id/bill_id = 0 means no address set

3. **orders_details → orders**
   - `orders_details.order_id` → `orders.id`
   - Many line items per order

4. **orders_details → products**
   - `orders_details.real_product_id` → `products.id`
   - Use real_product_id, not product_id

5. **transaction_log → orders**
   - `transaction_log.type_id` → `orders.id` (when type = 'order')
   - Segmented pattern: always filter type = 'order'

6. **products_stock → products**
   - `products_stock.product_id` → `products.id`
   - Multiple stock rows per product

7. **customers → customer_companies**
   - `customers.company_id` → `customer_companies.id`
   - company_id = 0 means no company

---

## Common Query Patterns

**Sales by Date Range:**
```sql
WHERE `invoice_date` >= '2024-01-01'
  AND `invoice_date` < '2024-02-01'
  AND `status` NOT IN (1, 11)
```

**Order Balance Calculation:**
```sql
LEFT JOIN (
    SELECT `type_id` AS order_id, SUM(`amount`) AS amount_paid
    FROM `transaction_log`
    WHERE `type` = 'order'
      AND (`status` = 1 OR `status` = 2 OR `status` = 4)
    GROUP BY `type_id`
) t ON o.`id` = t.order_id
```

**Customer Name Display:**
```sql
TRIM(CONCAT(c.`fname`, ' ', c.`lname`)) AS customer_name
```

**Product Stock Total:**
```sql
SELECT p.`id`, IFNULL(SUM(ps.`qty`), 0) AS total_stock
FROM `products` p
LEFT JOIN `products_stock` ps ON ps.`product_id` = p.`id`
WHERE p.`deleted_by` IS NULL
GROUP BY p.`id`
```

---

## Data Quality Notes

- Customer emails starting with `$$` are system placeholders
- `guest = 1` customers have incomplete data
- `order.time` is creation; `invoice_date` may be NULL for drafts
- Soft-deleted products: `deleted_by IS NOT NULL`
- ENUMs use string values ('0', '1') not integers
- ship_id/bill_id = 0 means no address (not valid FK)
- sales_rep = 0 means no rep assigned
- `po_` table name has trailing underscore (intentional)

---

## Performance Tips

- `orders`: indexed on id, time, status, customer_id, ship_id, bill_id
- `invoice_date` is NOT indexed - use date ranges to limit scans
- `time` IS indexed - prefer for creation date filtering
- Transaction log: always filter `type = 'order'`
- products_stock: always SUM(qty) with GROUP BY product_id
- Use LIMIT for large result sets (default 1000)

---

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- REPORT-SPECIFIC ADDITIONS                                        -->
<!-- From: nl-to-sql-training-data-response-reports.md                -->
<!-- Added: 2025-02-11                                                -->
<!-- ═══════════════════════════════════════════════════════════════ -->

## Reports Overview

The system includes 22 report modules for sales, commission tracking, and reward/rebate management:

### Revenue & Sales Reports

1. **Revenue Performance Report** (`/reports/sales/revenue-performance`)
   - Permission: `report/sales`
   - Purpose: Monthly order count and revenue by status

2. **JBD Commission Report** (`/reports/jbd-commission`)
   - Permission: `x_rewards/commission_report/all`
   - Purpose: Profit-sharing commission calculations

### Plugin Rewards Reports (20 reports under `/plugin-rewards/reports/`)

| Report Name | Purpose |
|-------------|---------|
| Commission Report | Sales rep commission tracking |
| Sales by Reps Commission | Multi-rep contribution analysis |
| Adjustment Detail | Manual reward adjustments |
| Adjustment Totals | Aggregated adjustment summary |
| Net Profit | Profit analysis with reward deductions |
| Label Sales | Serial number label tracking |
| Reward Report | Detailed reward transaction log |
| Liability Summary | Outstanding reward obligations summary |
| Liability Detail | Detailed liability breakdown by customer |
| YTD Sales Comparison | Year-to-date sales trend analysis |
| Paid Pay Sheets | Payment history by recipient |
| P&L by Customer Association | Profit/loss grouped by association |
| P&L by Customer | Profit/loss by individual customer |
| Customer Product Inventory | Stock levels for customer-specific products |
| 1099 Tax Report | Annual tax reporting for recipients |
| Customer Purchase Obligations | Contractual purchase requirements |
| Connecticut Sales | State-specific sales reporting |
| Total Sold | Aggregate sales totals |
| Retail Profit Management (RPM) | Gross/net revenue with labor metrics |
| RPM CSV Download | Export RPM data for analysis |

---

## Report-Specific Tables

### Table: commissions

**Purpose:** Individual commission records per sales rep per order/RMA line item.

**Row Count:** ~50,000+

**Key Columns:**
- `id` (BIGINT UNSIGNED, PRIMARY KEY) - Commission record ID
- `commission_period_id` (BIGINT UNSIGNED, INDEXED) - FK to `commission_periods`
- `commission_date` (DATE, NOT NULL) - Effective commission date
- `order_id` (BIGINT UNSIGNED, INDEXED) - FK to `orders`
- `order_detail_id` (BIGINT UNSIGNED) - FK to `orders_details`
- `rma_detail_id` (BIGINT UNSIGNED) - FK to `rma_details` (for returns)
- `quantity` (INT) - Quantity sold/returned
- `commission_price` (DECIMAL(12,4)) - Unit price for commission calc (after rewards)
- `commission_percent` (DECIMAL(7,4)) - Commission percentage
- `unit_commission` (DECIMAL(12,4)) - Commission per unit
- `amount` (DECIMAL(12,4), NOT NULL) - Total commission amount
- `category_id` (INT UNSIGNED, NOT NULL) - FK to `commission_categories` (1=SALE, 2=QUOTA)

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `commission_period_id`, `order_id`

**Important Notes:**
- `commission_price` is the net price after reward deductions
- Links to either `order_detail_id` (for sales) or `rma_detail_id` (for returns)
- SALE category (1) for standard commissions, QUOTA (2) for quota-based bonuses

---

### Table: commission_periods

**Purpose:** Payment cycles grouping commissions by sales rep and cutoff date.

**Row Count:** ~5,000+

**Key Columns:**
- `id` (BIGINT UNSIGNED, PRIMARY KEY) - Period ID
- `sales_rep_user_id` (INT UNSIGNED, NOT NULL) - FK to `synced_users`
- `cutoff_date` (DATE, NOT NULL) - Period cutoff date
- `status_id` (INT UNSIGNED, NOT NULL) - FK to `commission_period_statuses` (1=Unpaid, 2=Paid, 3=On Hold)

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on (`sales_rep_user_id`, `cutoff_date`)
- INDEX on `status_id`

**Computed Fields:**
- `balance` = `total_commissions - total_payments`

---

### Table: x_rewards_rewards

**Purpose:** Individual reward/rebate entries generated when orders are fulfilled.

**Row Count:** ~200,000+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Reward ID
- `order_fulfillment_detail_id` (INT UNSIGNED, INDEXED) - FK to `orders_details_picked`
- `serial_number` (VARCHAR(255), UNIQUE) - Reward serial number
- `profile_id` (INT UNSIGNED, INDEXED) - FK to `x_rewards_profiles`
- `amount` (DECIMAL(12,4), NOT NULL, INDEXED) - Reward dollar amount
- `redeemed_at` (DATETIME, INDEXED) - When reward was redeemed
- `redemption_period_id` (INT UNSIGNED, INDEXED) - FK to `x_rewards_redemption_periods` (NULL = unredeemed)
- `is_void` (TINYINT, NOT NULL, INDEXED) - 0=active, 1=voided
- `is_imported_label` (TINYINT) - 1=imported from external system

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `serial_number`
- INDEX on `order_fulfillment_detail_id`, `profile_id`, `redemption_period_id`, `is_void`, `redeemed_at`, `amount`
- COMPOSITE INDEX on (`redeemed_at`, `is_void`)

**Important Notes:**
- **ALWAYS filter `is_void = 0`** to exclude voided rewards
- `redemption_period_id IS NULL` = unredeemed (liability)
- `redemption_period_id IS NOT NULL` = redeemed (paid out)

---

### Table: x_rewards_profiles

**Purpose:** Customer reward program configurations defining redemption method and payout rules.

**Row Count:** ~500+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Profile ID
- `customer_id` (INT UNSIGNED, INDEXED) - FK to `customers`
- `title` (VARCHAR(255), INDEXED) - Profile name/title
- `redemption_method` (VARCHAR(255), INDEXED) - How rewards are redeemed
- `status` (TINYINT UNSIGNED) - 0=inactive, 1=active
- `hide_on_rpm` (TINYINT UNSIGNED) - Hide from RPM reports
- `hide_on_executive_portal` (TINYINT UNSIGNED) - Hide from executive portal

**Redemption Methods:**
- `serial_number` - Physical serial number labels
- `manual` - Manual redemption trigger
- `on_payment` - Auto-redeem when order is paid
- `on_redemption` - Explicit redemption request
- `on_first_of_month` - Auto-redeem on 1st
- `on_15_of_month` - Auto-redeem on 15th

---

### Table: x_rewards_recipients

**Purpose:** Individuals who receive reward payments (for pay sheets and 1099s).

**Row Count:** ~200+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Recipient ID
- `first_name` (VARCHAR(255), NOT NULL)
- `last_name` (VARCHAR(255), NOT NULL)
- `email` (VARCHAR(255), NOT NULL)
- `ssn_encrypted` (VARCHAR(255)) - Encrypted SSN for 1099 reporting
- `w9_received` (TINYINT) - W-9 tax form received flag
- `preferred_payment_type` (VARCHAR(255)) - 'check', 'ach'
- `status` (TINYINT UNSIGNED) - 0=inactive, 1=active

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on (`first_name`, `middle_name`, `last_name`)

---

### Table: x_rewards_redemption_periods

**Purpose:** Payment cycles grouping rewards by recipient, customer, and cutoff date (pay sheets).

**Row Count:** ~10,000+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Redemption period ID
- `recipient_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_recipients`
- `customer_id` (INT UNSIGNED, NOT NULL) - FK to `customers`
- `cutoff_date` (DATE, NOT NULL) - Period cutoff date
- `balance` (DECIMAL(12,4), NOT NULL) - Remaining balance

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on (`recipient_id`, `customer_id`, `cutoff_date`)

**Computed Fields:**
- `total` = `rewards_total + approved_adjustments_total`
- `balance` = `total - payments_total`

---

### Table: x_rewards_adjustments

**Purpose:** Manual adjustments to reward balances (additions or deductions).

**Row Count:** ~2,000+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Adjustment ID
- `redemption_period_id` (INT UNSIGNED, INDEXED) - FK to `x_rewards_redemption_periods`
- `amount` (DECIMAL(12,4), NOT NULL) - Adjustment amount (positive or negative)
- `note` (VARCHAR(255), NOT NULL) - Reason for adjustment
- `is_approved` (TINYINT, NOT NULL) - 0=pending, 1=approved

**Important Notes:**
- **ALWAYS filter `is_approved = 1`** when summing adjustments

---

### Table: x_rewards_payments

**Purpose:** Actual payments made against redemption periods (checks, ACH, etc.).

**Row Count:** ~8,000+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Payment ID
- `redemption_period_id` (INT UNSIGNED, INDEXED) - FK to `x_rewards_redemption_periods`
- `amount` (DECIMAL(12,4), NOT NULL) - Payment amount
- `payment_type` (VARCHAR(255), NOT NULL) - 'check', 'ach'
- `check_number` (INT UNSIGNED) - Check number if type is check
- `void` (TINYINT UNSIGNED, DEFAULT 0) - 0=valid, 1=voided

**Important Notes:**
- **ALWAYS filter `void = 0`** when summing payments

---

### Table: x_rewards_customer_products

**Purpose:** Customer-specific product configurations with custom pricing, reward amounts, and commission percentages.

**Row Count:** ~20,000+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - Customer product ID
- `customer_id` (INT UNSIGNED, INDEXED) - FK to `customers`
- `product_id` (INT UNSIGNED, INDEXED) - FK to `products`
- `price` (DECIMAL(12,4), NOT NULL) - Customer-specific unit price
- `deleted_by_user_id` (INT) - Soft delete FK to `synced_users`
- `deactivated` (TINYINT UNSIGNED) - Deactivation flag
- `hide_from_rpm` (TINYINT UNSIGNED) - Hide from RPM reports

**Dynamic Fields (EAV Pattern):**
- `reward_amount` per profile - stored in `x_rewards_customer_product_reward_amounts`
- `commission_percent` per sales rep - stored in `x_rewards_customer_product_commission_percents`

**Important Notes:**
- **Filter `deleted_by_user_id IS NULL`** for active records (soft delete)
- **Filter `deactivated = 0`** for active products

---

### Table: x_rewards_rpm_data

**Purpose:** Retail Profit Management (RPM) data snapshots capturing revenue and labor metrics.

**Row Count:** ~100,000+

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY) - RPM data ID
- `order_fulfillment_detail_id` (INT UNSIGNED, INDEXED) - FK to `orders_details_picked`
- `reward_id` (INT UNSIGNED, INDEXED) - FK to `x_rewards_rewards`
- `product_id` (INT UNSIGNED, NOT NULL) - FK to `products`
- `parts_sold` (DECIMAL(12,4)) - Parts quantity sold
- `gross_parts_revenue` (DECIMAL(12,4)) - Gross revenue from parts
- `net_parts_revenue` (DECIMAL(12,4)) - Net revenue (after rewards)
- `labor_hours` (DECIMAL(10,2)) - Associated labor hours
- `gross_labor_revenue` (DECIMAL(12,4)) - Gross labor revenue
- `net_labor_revenue` (DECIMAL(12,4)) - Net labor revenue

**Important Notes:**
- Net revenue = Gross revenue - reward amounts
- Always filter via `x_rewards_rewards.is_void = 0`

---

## Additional Table Relationships

**Report-Specific Relationships:**

8. **commissions → commission_periods**
   - `commissions.commission_period_id` → `commission_periods.id`
   - Many commissions per period

9. **commission_periods → synced_users**
   - `commission_periods.sales_rep_user_id` → `synced_users.id`
   - One sales rep per period

10. **x_rewards_rewards → orders_details_picked**
    - `x_rewards_rewards.order_fulfillment_detail_id` → `orders_details_picked.id`
    - Rewards link to fulfillment details, not order details directly

11. **x_rewards_rewards → x_rewards_profiles**
    - `x_rewards_rewards.profile_id` → `x_rewards_profiles.id`
    - Each reward belongs to one profile

12. **x_rewards_profiles → customers**
    - `x_rewards_profiles.customer_id` → `customers.id`
    - One profile per customer (multiple profiles possible)

13. **x_rewards_redemption_periods → x_rewards_recipients**
    - `x_rewards_redemption_periods.recipient_id` → `x_rewards_recipients.id`
    - Each period belongs to one recipient

14. **x_rewards_customer_products → customers/products**
    - `x_rewards_customer_products.customer_id` → `customers.id`
    - `x_rewards_customer_products.product_id` → `products.id`
    - Links customer-specific product configurations

---

## Business Logic Definitions

### Revenue Performance Report Terms

| Term | Definition |
|------|------------|
| **Revenue Performance** | Monthly trend of order counts and revenue totals, segmented by order status |
| **Search by Creation Date** | Toggle to filter orders by `time` (creation) instead of `invoice_date` |
| **Time Bucketing** | Orders grouped by Year-Month (format: 'Y-M' e.g. '2025-02') |

### JBD Commission Terms

| Term | Definition |
|------|------------|
| **JBD Commission** | Profit-sharing commission: `(company_rate / 100) × net_profit_per_unit × quantity` |
| **Net Price** | Customer product price minus sum of all active profile reward amounts |
| **Net Profit** | Net price minus product cost: `net_price - cost` |
| **Commission Rate** | Company-specific rate stored as custom field `custom_jbd_commission_rate` |
| **Paid Order** | Order where balance = 0 (total - sum of successful transactions = 0) |

### Plugin Rewards - Commission System Terms

| Term | Definition |
|------|------------|
| **Commission** | Earnings for a sales rep on a specific order or RMA line item |
| **Commission Period** | Payment cycle grouping commissions by sales rep and cutoff date |
| **Commission Price** | Unit price after reward deductions (base for commission calculation) |
| **Commission Percent** | Percentage of net sales earned as commission |
| **Unit Commission** | Commission per unit: `commission_price × (commission_percent / 100)` |
| **Total Sales** | Gross sales: `quantity × price` |
| **Net Sales** | After-reward sales: `quantity × commission_price` |
| **Total Rewards** | `total_sales - net_sales` |
| **Paid Indicator** | "P" if order balance is exactly $0.0000 (4 decimals), "U" otherwise |
| **SALE Category** | Commission category ID 1 - standard sale commission |
| **QUOTA Category** | Commission category ID 2 - quota-based commission |
| **Contribution Percent** | In Sales by Reps: `this_rep_percent / SUM(all_reps_percent)` |

### Plugin Rewards - Reward/Liability System Terms

| Term | Definition |
|------|------------|
| **Reward** | Rebate/reward earned on a fulfilled order item |
| **Profile** | Customer reward program configuration defining redemption method |
| **Recipient** | Individual who receives reward payments |
| **Redemption Period** | Payment cycle grouping rewards by recipient, customer, cutoff date |
| **Redemption Method** | How rewards trigger: serial_number, manual, on_payment, on_redemption, etc. |
| **Unredeemed Reward** | Reward where `redemption_period_id IS NULL` - outstanding liability |
| **Redeemed Reward** | Reward where `redemption_period_id IS NOT NULL` - included in pay sheet |
| **Voided Reward** | Reward where `is_void = 1` - excluded from all calculations |
| **Liability** | Total unredeemed, non-void reward amounts - company's financial obligation |
| **Adjustment** | Manual addition/deduction; only `is_approved = 1` adjustments count |
| **Pay Sheet** | Redemption period with associated payments - payout document |
| **RPM** | Retail Profit Management - gross/net revenue, labor hours, penetration rates |
| **Customer Product** | Customer-specific product config with custom pricing, rewards, commissions |

---

## SQL Conventions (Report-Specific)

**Critical filtering rules for report queries:**

1. **Reward void filtering**: Always include `is_void = 0` when querying `x_rewards_rewards`
2. **Unredeemed filter**: `redemption_period_id IS NULL` for liability/unredeemed rewards
3. **Redeemed filter**: `redemption_period_id IS NOT NULL` for paid/redeemed rewards
4. **Adjustment approval**: Always include `is_approved = 1` when summing adjustments
5. **Payment void filtering**: Always include `void = 0` when querying `x_rewards_payments`
6. **Soft delete on customer products**: Filter `deleted_by_user_id IS NULL` for active records
7. **Transaction log segmentation**: Always include `type = 'order'` when querying order transactions
8. **Decimal precision**: Commission amounts use DECIMAL(12,4); display rounded to 2 decimals
9. **Commission percent precision**: DECIMAL(7,4) - supports up to 999.9999%
10. **Paid status check**: Order is paid when `ABS(balance)` rounds to 0 at 4 decimal places
11. **Date range inclusivity**: All date filters use `>=` and `<=` (inclusive on both ends)

---

## Report Calculation Formulas

### JBD Commission Calculation

```
For each order line item:
  1. customer_product = lookup x_rewards_customer_products
     WHERE customer_id AND product_id AND deleted_by_user_id IS NULL
  2. net_price = customer_product.price
     - SUM(x_rewards_customer_product_reward_amounts.reward_amount)
  3. cost = customer_product.product_kit_components_total_cost ?? order_detail.costs
  4. net_profit = net_price - cost
  5. rate = custom_fields.value
     WHERE type='customer_company' AND name='custom_jbd_commission_rate'
  6. jbd_commission = (rate / 100) × net_profit
  7. total_net_sales = net_price × quantity
  8. total_net_profit = net_profit × quantity
  9. total_jbd_commission = jbd_commission × quantity
```

### Commission Report Calculation

```
For each commission record:
  1. total_sales = quantity × price
  2. net_sales = quantity × commission_price
  3. total_rewards = total_sales - net_sales
  4. reward_amount_per_unit = total_rewards / quantity (0 if quantity = 0)
  5. commission = ROUND(net_sales × (commission_percent / 100), 2)
  6. paid = ABS(order_balance) formatted to 4 decimals === '0.0000'
```

### Sales by Reps Contribution Calculation

```
For each commission record:
  1. all_reps_sum_percent = SUM(commission_percent)
     across ALL reps for same order_detail_id
  2. contribution_percent = this_rep_commission_percent / all_reps_sum_percent
  3. rep_gross_sales_contribution = total_sales × contribution_percent
  4. rep_net_sales_contribution = net_sales × contribution_percent
```

### Liability Balance Calculation

```
For a redemption period:
  1. rewards_total = SUM(x_rewards_rewards.amount
     WHERE redemption_period_id AND is_void = 0)
  2. approved_adjustments_total = SUM(x_rewards_adjustments.amount
     WHERE redemption_period_id AND is_approved = 1)
  3. payments_total = SUM(x_rewards_payments.amount
     WHERE redemption_period_id AND void = 0)
  4. total_owed = rewards_total + approved_adjustments_total
  5. balance = total_owed - payments_total
```

---

## Report Access Patterns

### Revenue Performance Report Filters

- Date Range: `invoice_date >= ? AND invoice_date <= ?`
- Order Status: Multiple OR equality checks (`status IN (2,3,4)`)
- Aggregation: COUNT and SUM grouped by Year-Month and status

### JBD Commission Report Filters

- Payment Date Range: `transaction_log.time >= ? AND <= ?`
- Paid Orders Only: `order.balance = 0`
- Exclude Abandoned/Cancelled: `status != 1 AND != 10`
- Active Customer Products: `deleted_by_user_id IS NULL`
- Active Profiles: `x_rewards_profiles.status = 1`

### Commission Report Filters

- Date Range: `commissions.commission_date >= ? AND <= ?`
- Sales Rep (optional): `commission_periods.sales_rep_user_id = ?`
- Aggregation: SUM of total_sales, total_rewards, net_sales, commission

### Liability Report Filters

- Date Range: `x_rewards_rewards.created_at >= ? AND <= ?`
- Non-voided: `x_rewards_rewards.is_void = 0`
- Unredeemed: `x_rewards_rewards.redemption_period_id IS NULL`
- Aggregation: SUM of amount, COUNT of id grouped by customer

### Pay Sheet / 1099 Report Filters

- Date Range: `x_rewards_redemption_periods.cutoff_date >= ? AND <= ?`
- Non-voided Payments: `x_rewards_payments.void = 0`
- Aggregation: SUM of payment amounts grouped by recipient

### RPM Report Filters

- Date Range: `x_rewards_rewards.created_at >= ? AND <= ?`
- Non-voided: `x_rewards_rewards.is_void = 0`
- Hide from RPM: `x_rewards_profiles.hide_on_rpm = 0`
- Aggregation: SUM of parts_sold, gross/net revenue, labor_hours

---

## Report Permissions

| Permission Key | Scope | Used By |
|----------------|-------|---------|
| `report/sales` | View revenue performance report | Revenue Performance |
| `x_rewards/commission_report` | View own commission data | Commission Report, JBD Commission |
| `x_rewards/commission_report/all` | View all reps' commission data | Commission Report, JBD Commission |
| `x_rewards/sales_by_reps_commission_report` | View own sales by reps data | Sales by Reps Commission |
| `x_rewards/sales_by_reps_commission_report/all` | View any rep's sales by reps data | Sales by Reps Commission |
