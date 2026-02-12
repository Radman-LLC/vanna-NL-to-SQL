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
