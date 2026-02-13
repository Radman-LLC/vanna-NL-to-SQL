# ADR (Zangerine) Database Information Response

## SECTION 1: Database Metadata

```
Database Type: MySQL
Database Version: 5.6.10+ (InnoDB)
Database Name: admin276_addOn_XXXXXX (per-client isolation; global admin DB: admin276_admin)
Character Set: utf8mb3 (most tables), utf8mb4 (newer tables)
Timezone: UTC (server-side; application displays in user's local TZ)
Total Tables: ~360 (per-client database)
Total Entity Types: 286 (defined in TOML)
Approximate Database Size: Varies per client (largest clients ~50GB+)
```

---

## SECTION 2: Core Tables (Top 15 Most Important)

### Table: orders

**Purpose:** Stores all customer sales orders. This is the central transactional table in the system. Every sale, whether from the website, manually entered, or imported from an integration, creates a row here.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique order identifier
- `customer_id` (BIGINT, NOT NULL, INDEXED) - FK to `customers` table
- `status` (TINYINT, NOT NULL, DEFAULT 1, INDEXED) - FK to `order_status` table (see SECTION 9 for values)
- `total` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Grand total including line items, shipping, tax, discounts
- `tax_fee` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Tax amount
- `state_tax_fees` (DECIMAL(15,5), NOT NULL) - State-specific invoice tax
- `shipping_fee` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Shipping charge
- `discount_amount` (DECIMAL(15,5), NOT NULL, DEFAULT 0) - Total coupon/discount applied
- `shipping_method` (INT, DEFAULT 0, INDEXED) - FK to shipping_modules
- `shipping_notes` (VARCHAR(200)) - Internal shipping notes
- `ship_id` (BIGINT, NOT NULL, DEFAULT 0, INDEXED) - FK to `addresses` (shipping address)
- `bill_id` (BIGINT, DEFAULT 0, INDEXED) - FK to `addresses` (billing address)
- `coupon_id` (INT, NOT NULL, DEFAULT 0) - FK to `coupons`
- `payment_term_id` (INT, NOT NULL, DEFAULT 1) - FK to `payment_terms_statuses`
- `tracking_num` (TEXT) - Legacy tracking number field
- `po_num` (TEXT) - Customer PO number
- `time` (DATETIME, NOT NULL, DEFAULT CURRENT_TIMESTAMP, INDEXED) - Order creation timestamp
- `invoice_date` (DATETIME) - Invoice date used for reporting
- `due_date` (DATE) - Payment due date (affects customer statements)
- `ship_date` (DATE) - Actual ship date
- `invoice_number` (INT) - Invoice number
- `customer_notes` (TEXT) - Notes visible to customer on invoices
- `admin_notes` (TEXT) - Internal admin notes
- `sales_rep` (INT, NOT NULL, DEFAULT 0) - FK to `synced_users`
- `marketing_source` (TINYINT, DEFAULT 0) - FK to marketing_sources
- `store` (TINYINT, NOT NULL, DEFAULT 0) - FK to `stores`
- `picked` (ENUM('0','1','2'), NOT NULL, DEFAULT '0') - 0=Not Picked, 1=Picked, 2=Picked Partially
- `shipped` (ENUM('0','1','2'), NOT NULL, DEFAULT '0') - 0=Not Shipped, 1=Shipped, 2=Shipped Partially
- `modified_on` (TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP) - Last modification timestamp
- `order_type` (VARCHAR(255), NOT NULL, DEFAULT 'sales_order') - 'sales_order', 'rental_order', 'transfer_order'
- `integration_id` (INT UNSIGNED, NOT NULL, DEFAULT 0) - FK to `integrations`
- `integration_order_id` (VARCHAR(128)) - External order ID from integration
- `integration_order_number` (VARCHAR(128)) - External order number
- `recurring_profile_id` (BIGINT) - FK to `recurring_profiles`
- `payment_account_id` (INT) - FK to payment_accounts
- `shipping_service_id` (INT) - FK to shipping_services
- `currency_id` (INT) - FK to currencies
- `last_edited_by` (INT) - FK to `synced_users`
- `reference_id` (VARCHAR(20), NOT NULL, INDEXED) - Unique reference identifier

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `time`
- INDEX on `status`
- INDEX on `customer_id`
- COMPOSITE INDEX on (`status`, `customer_id`)
- INDEX on `shipping_method`
- INDEX on `ship_id`
- INDEX on `bill_id`
- INDEX on `reference_id`
- INDEX on `integration_fulfillment_order_id`

**Important Notes:**
- `invoice_date` is the primary date field used for reports, NOT `time` (creation date)
- `total` is the grand total and includes line items + shipping + tax - discounts
- Balance is calculated as: `total - SUM(successful transaction amounts)`
- Order status values are stored as tinyint IDs (see SECTION 9 for complete mapping)
- The `picked` and `shipped` fields are ENUMs, not booleans
- Status 1 (ABANDONED) and 11 (CANCELLED) are typically excluded from reports
- `order_type` defaults to 'sales_order'; also used for 'transfer_order' (warehouse transfers)

---

### Table: orders_details

**Purpose:** Line items within an order. Each row represents one product/SKU on an order with its quantity, price, and cost.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique line item identifier
- `order_id` (BIGINT, NOT NULL) - FK to `orders`
- `real_product_id` (BIGINT) - FK to `products` (actual product reference)
- `product_sku` (VARCHAR) - SKU snapshot at time of order
- `product_name` (VARCHAR) - Product name snapshot at time of order
- `product_type` (VARCHAR) - Product type snapshot
- `qty` (DECIMAL) - Ordered quantity
- `price` (DECIMAL) - Unit selling price at order time
- `original_price` (DECIMAL) - Original unit price before discounts
- `credit_card_price` (DECIMAL) - Credit card payment price variant
- `costs` (DECIMAL) - Unit cost (COGS)
- `warehouse_id` (INT) - FK to `location_warehouses`
- `quantity_backordered` (INT) - Backordered quantity
- `sample_product` (BOOLEAN) - If TRUE, cost = 0 for margin calculations
- `note` (TEXT) - Line item notes
- `sort` (INT) - Display order
- `x_rewards_customer_product_id` (INT) - FK for rewards system
- `product_cross_reference_id` (INT) - FK to product_cross_references

**Calculated Expressions (EntityService level):**
- `total_price` = `price * qty`
- `total_original_price` = `original_price * qty`
- `total_quantity_picked` = SUM of `qty_picked` from `orders_details_picked`
- `committed_quantity` = `qty - total_quantity_picked`
- `unfulfilled_quantity` = `qty - total_quantity_picked - total_dropship_quantity`
- `total_cost` = Complex formula: `IF(sample_product != '1', dropship_cost_total + IF(inventory_type_id = 3 OR order_created_at < '2019-11-01', cost * qty, IF(inventory_type_id = 1, fifo_cost_total, serial_number_cost_total)), 0)`
- `gross_margin` = `total_price - total_cost`

**Important Notes:**
- `product_name` and `product_sku` are snapshots: they capture the value at order time and don't change if the product is later renamed
- `real_product_id` is the actual FK to products; use this for JOINs, not the snapshot fields
- Cost calculation varies by `inventory_type_id`: 1=FIFO, 2=Serial Number, 3=Standard Cost
- For orders before 2019-11-01, standard cost (cost * qty) is always used regardless of inventory type

---

### Table: customers

**Purpose:** Customer master records. Every buyer in the system, whether they ordered online, were imported, or manually created.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique customer identifier
- `fname` (VARCHAR(100), NOT NULL) - First name (API field: `first_name`)
- `lname` (VARCHAR(50), NOT NULL) - Last name (API field: `last_name`)
- `title` (VARCHAR(50)) - Title/prefix
- `company_id` (INT, NOT NULL) - FK to `customer_companies`
- `email` (VARCHAR(100), NOT NULL, INDEXED) - Email address
- `phone` (VARCHAR(30), INDEXED) - Phone number
- `phone_ext` (VARCHAR(11)) - Phone extension
- `secondary_phone` (VARCHAR(30)) - Secondary phone
- `fax` (VARCHAR(30)) - Fax number
- `website` (VARCHAR(255)) - Website URL
- `birthdate` (VARCHAR(15)) - Date of birth
- `notes` (TEXT) - Customer notes
- `creation_date` (DATETIME, NOT NULL, DEFAULT CURRENT_TIMESTAMP) - Creation timestamp (API field: `created_at`)
- `modified_at` (DATETIME, NOT NULL) - Last modification timestamp
- `gender` (INT, NOT NULL) - 1=Male, 2=Female (API maps to 'M'/'F')
- `status` (INT, NOT NULL, DEFAULT 1) - Customer status (1=active)
- `automated_payment_reminders` (INT, NOT NULL, DEFAULT 1) - 1=enabled
- `sales_rep_id` (INT, NOT NULL, DEFAULT 0) - FK to `synced_users`
- `default_ship_id` (INT, NOT NULL, DEFAULT 0) - FK to `addresses`
- `default_bill_id` (INT, NOT NULL, DEFAULT 0) - FK to `addresses`
- `currency_id` (INT, NOT NULL, DEFAULT 5) - FK to currencies (5 = USD default)
- `integration_id` (INT UNSIGNED, NOT NULL, DEFAULT 0) - FK to integrations
- `integration_customer_id` (TEXT) - External customer ID
- `guest` (TINYINT UNSIGNED, DEFAULT 0) - Guest customer flag
- `valid_email` (TINYINT, NOT NULL, DEFAULT 0) - Email validated flag

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `email`
- INDEX on `phone`
- INDEX on `fname`
- INDEX on `lname`
- INDEX on `company_id`

**Important Notes:**
- The `label` is a computed expression: if company exists, shows "Company (First Last)"; if no company, shows "First Last"
- Emails starting with `$$` are system-generated placeholders (filter with `NOT email LIKE '$$%'`)
- `guest = 1` indicates a guest checkout customer (not registered)
- Customers with `company_id > 0` belong to a customer company; use `customer_companies` table for company info
- Sales rep is the primary assigned rep; additional reps are in `customer_additional_sales_rep_users` link table
- Customer groups are in `customer_group_relations` link table
- Sellers are in `sellers_customers_relation` link table

---

### Table: products

**Purpose:** Product catalog. Every SKU in the system including parent products, child variants, kit products, and recurring products.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique product identifier
- `sku` (VARCHAR) - Stock keeping unit (unique business identifier)
- `name` (VARCHAR) - Product name
- `model_number` (VARCHAR) - Manufacturer model number
- `mpn` (VARCHAR) - Manufacturer part number
- `asin` (VARCHAR) - Amazon ASIN
- `upc` (VARCHAR) - UPC barcode
- `manufacturer_id` (INT) - FK to `products_manufacturers`
- `short_description` (VARCHAR) - Short description
- `description` (TEXT) - Full product description
- `pack_type` (VARCHAR) - Packing type
- `pack_qty` (DECIMAL) - Units per pack
- `sales_pack_qty` (INT) - Sales quantity per pack
- `manage_stock` (ENUM('1','0')) - Whether stock is managed
- `min_stock_level` (INT) - Minimum stock level threshold
- `preferred_stock_level` (INT) - Preferred/target stock level
- `allow_backorder` (ENUM('1','0')) - Allow backorders flag
- `price` (DECIMAL) - Standard selling price
- `cost` (DECIMAL) - Standard cost
- `list_price` (DECIMAL) - MSRP/list price
- `status` (ENUM('1','0')) - Published/active status (API field: `is_published`)
- `visible` (ENUM('1','0')) - Visible on website
- `taxable` (ENUM('1','0')) - Subject to tax
- `drop_ship` (ENUM('1','0')) - Dropship enabled
- `not_for_sale` (ENUM('1','0')) - Not for sale flag
- `weight` (DECIMAL) - Product weight
- `weight_unit` (VARCHAR) - Weight unit (lb, kg, etc.)
- `dimension_length` (DECIMAL), `dimension_width` (DECIMAL), `dimension_height` (DECIMAL)
- `date_added` (DATETIME) - Creation date (API field: `created_at`)
- `date_modified` (DATETIME) - Last modification (API field: `modified_at`)
- `master_product_id` (INT) - FK to parent product (for variants)
- `is_child` (ENUM('1','0')) - Is a variant of a parent product
- `deleted_by` (INT) - FK to `synced_users` (soft delete; NULL = not deleted)
- `inventory_type_id` (INT) - FK to `inventory_types` (1=FIFO, 2=Serial Number, 3=Standard)
- `is_recurring` (INT) - Recurring product flag
- `sort` (INT) - Display order

**Important Notes:**
- Soft delete: products with `deleted_by IS NOT NULL` are "deleted" but still referenced by historical orders
- `is_child = '1'` means it's a variant; `master_product_id` points to the parent
- Many boolean-like fields use ENUM('1','0') instead of actual BOOLEAN
- `label` is computed as: `IF(name = '', 'Untitled Product', CONCAT(name, ' (', sku, ')'))`
- Product categories are in `product_category_relations` link table
- Product stock is in `products_stock` table
- Vendors are in `po_vendor_product_relations` link table

---

### Table: addresses

**Purpose:** Shared address records used by customers, orders, quotes, purchase orders, vendors, companies, and warehouses. A single address row can be referenced by multiple entities.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique address identifier
- `fname` (VARCHAR(100), NOT NULL) - First name (API field: `first_name`)
- `lname` (VARCHAR(50), NOT NULL) - Last name (API field: `last_name`)
- `company` (VARCHAR) - Company name
- `address1` (VARCHAR) - Street address line 1
- `address2` (VARCHAR) - Street address line 2
- `city` (VARCHAR) - City
- `state` (VARCHAR) - State/province
- `zip` (VARCHAR) - ZIP/postal code (API field: `postal_code`)
- `country` (VARCHAR) - Country code
- `phone` (VARCHAR) - Phone number
- `phone_ext` (INT) - Phone extension
- `secondary_phone` (VARCHAR) - Secondary phone
- `fax` (VARCHAR) - Fax number

**Important Notes:**
- Column name `fname` maps to API field `first_name`, `lname` to `last_name`, `zip` to `postal_code`
- This is a shared table: the same address may be referenced by orders (ship_id, bill_id), customers (default_ship_id, default_bill_id), etc.
- Customer-address relationships are also tracked in `customer_address_relation` link table

---

### Table: transaction_log

**Purpose:** Records all payment transactions for orders. Each order can have multiple transactions (payments, refunds, voids). Uses a segment pattern where `type = 'order'` identifies order transactions.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique transaction identifier
- `type` (VARCHAR) - Segment: 'order' for order transactions
- `type_id` (BIGINT) - FK to `orders` (when type = 'order')
- `amount` (DECIMAL) - Transaction amount
- `payment_method_id` (INT) - FK to payment_modules
- `payment_gateway_type_id` (INT) - FK to payment_gateway_types
- `transaction_id` (VARCHAR(200)) - External transaction number (API field: `transaction_number`)
- `reference_number` (VARCHAR(200)) - Reference number
- `parent_transaction_log_id` (INT) - FK for refund linking
- `customer_credit_id` (INT) - FK to `customers_credit` (if paying with store credit)
- `bill_addr` (INT) - FK to `addresses`
- `last_four_digits` (INT) - Last 4 of card number
- `log` (TEXT) - Transaction response log
- `time` (DATETIME) - Transaction timestamp (API field: `created_at`)
- `status` (TINYINT) - FK to `transaction_statuses` (1=Pending, 2=Succeeded, 3=Declined, 4=Refunded, 5=Voided)
- `status_message` (VARCHAR) - Status detail message
- `payment_account_id` (INT) - FK to payment_accounts

**Important Notes:**
- Order balance = `orders.total - SUM(transaction_log.amount WHERE type = 'order' AND type_id = order_id AND (status = 1 OR status = 2 OR status = 4))`
- Status 1 (Pending) and 2 (Succeeded) are considered "successful" for balance calculations
- Status 4 (Refunded) reduces the balance (negative amount refunds add back to balance)
- Always filter by `type = 'order'` when querying order transactions
- The same table structure is used for PO transactions with `type = 'po'`

---

### Table: po_ (purchase_orders)

**Purpose:** Purchase orders placed with vendors for restocking inventory or fulfilling customer orders via dropship.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique PO identifier
- `vendor_id` (INT) - FK to `po_vendors`
- `is_dropship` (ENUM('1','0')) - Whether this PO is a dropship order
- `store` (TINYINT) - FK to `stores`
- `status_id` (INT) - FK to `po_statuses`
- `total` (DECIMAL) - PO total
- `value_received` (DECIMAL) - Value of goods received
- `outstanding_balance` (DECIMAL) - Outstanding balance
- `shipping_fee` (DECIMAL) - Shipping charge
- `ship_id` (BIGINT) - FK to `addresses` (shipping address)
- `bill_id` (BIGINT) - FK to `addresses` (billing address)
- `tracking_num` (VARCHAR) - Tracking number
- `external_notes` (TEXT) - Vendor-facing notes
- `packing_slip_notes` (TEXT) - Packing slip notes
- `admin_notes` (TEXT) - Internal admin notes
- `sales_rep` (INT) - FK to `synced_users`
- `received_by` (INT) - FK to `synced_users`
- `time` (DATETIME) - Creation timestamp (API field: `created_at`)
- `modified_on` (DATETIME) - Last modification
- `receive_date` (DATE) - Date goods were received
- `bill_date` (DATE) - Billing date

**Important Notes:**
- The actual table name is `po_` (with trailing underscore) - this is intentional
- `is_dropship = '1'` means the vendor ships directly to the customer
- POs can be linked to sales orders via `purchase_order_sources` link table
- PO line items are in `po_details` table

---

### Table: po_details (purchase_order_details)

**Purpose:** Line items on a purchase order. Each row represents one product being ordered from a vendor.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `po_id` (INT) - FK to `po_`
- `real_product_id` (INT) - FK to `products`
- `product_name` (VARCHAR) - Product name snapshot
- `product_sku` (VARCHAR) - SKU snapshot
- `note` (TEXT) - Line item notes
- `qty` (DECIMAL) - Ordered quantity (in packs)
- `qty_pass` (DECIMAL) - Qty that passed QC
- `qty_fail` (DECIMAL) - Qty that failed QC
- `unit` (INT) - Units per pack
- `cost` (DECIMAL) - Unit cost
- `order_detail_id` (INT) - FK to `orders_details` (links PO line to sales order line)
- `promise_shipment_date` (DATE) - Expected ship date from vendor
- `promise_delivery_date` (DATE) - Expected delivery date
- `product_cross_reference_id` (INT) - FK to product_cross_references

**Calculated Expressions:**
- `total_units` = `qty * pack_qty`
- `cost_total` = `cost * total_units`
- `total_dropship_units` = units for dropship POs only
- `dropship_cost_total` = cost total for dropship POs only

---

### Table: po_vendors (vendors)

**Purpose:** Vendor/supplier master records from whom purchase orders are placed.

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `name` (VARCHAR) - Vendor name
- `email` (VARCHAR) - Vendor email
- `website` (VARCHAR) - Website URL
- `phone` (VARCHAR) - Phone number
- `address_id` (INT) - FK to `addresses`
- `account_number` (VARCHAR) - Vendor account number
- `admin_notes` (TEXT) - Internal notes
- `status` (BOOLEAN) - Active/inactive (ENUM '1'/'0')
- `created_at` (DATETIME)
- `modified_at` (DATETIME)

---

### Table: quotes

**Purpose:** Customer quotes/estimates that can be converted to orders.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `customer_id` (BIGINT) - FK to `customers`
- `status` (TINYINT) - FK to `quote_statuses`
- `total` (DECIMAL) - Quote total
- `original_total` (DECIMAL) - Original total before discounts
- `tax_fee` (DECIMAL) - Tax amount
- `shipping_fee` (DECIMAL) - Shipping estimate
- `discount_amount` (DECIMAL) - Total discount
- `coupon_id` (INT) - FK to `coupons`
- `ship_id` (BIGINT) - FK to `addresses`
- `bill_id` (BIGINT) - FK to `addresses`
- `customer_notes` (TEXT) - Customer-facing notes
- `admin_notes` (TEXT) - Admin notes
- `payment_term_id` (INT) - FK to `payment_terms_statuses`
- `generation_time` (DATETIME) - Creation timestamp (API field: `created_at`)
- `expiry_date` (DATETIME) - Expiration date (API field: `expires_at`)
- `reminder_date` (DATETIME) - Reminder date
- `sales_rep` (INT) - FK to `synced_users`
- `store` (TINYINT) - FK to `stores`
- `order_id` (INT) - FK to `orders` (populated when quote is converted to order)

**Important Notes:**
- When a quote is accepted and converted, `order_id` is set to the new order's ID
- Quote line items are in `quotes_details` table

---

### Table: quotes_details (quote_details)

**Purpose:** Line items on a quote.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `quote_id` (BIGINT) - FK to `quotes`
- `real_product_id` (INT) - FK to `products`
- `product_name` (VARCHAR) - Product name snapshot
- `product_sku` (VARCHAR) - SKU snapshot
- `product_type` (VARCHAR)
- `qty` (DECIMAL) - Quoted quantity
- `price` (DECIMAL) - Unit price
- `original_price` (DECIMAL) - Original price
- `note` (TEXT) - Line notes
- `sort` (INT) - Display order

---

### Table: rmas

**Purpose:** Return Merchandise Authorizations. Tracks customer returns and refunds.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME)
- `created_by_user_id` (INT) - FK to `synced_users`
- `modified_at` (DATETIME)
- `modified_by_user_id` (INT) - FK to `synced_users`
- `frozen_at` (DATETIME) - When the RMA was finalized
- `rma_reason_id` (INT) - FK to `rma_reasons`
- `admin_notes` (TEXT) - Internal notes
- `customer_notes` (TEXT) - Customer-visible notes
- `delivery_route_id` (INT) - FK to delivery_routes
- `delivery_route_sequence` (INT) - Sequence in delivery route

**Important Notes:**
- RMA details (returned items) are in `rma_details` table
- RMA-to-order links are in `rma_orders` table (an RMA can span multiple orders)
- Customer credits issued from RMAs are in `customers_credit` table
- `total_refund_amount` = `price_total + tax_refund`

---

### Table: rma_details

**Purpose:** Individual returned items within an RMA.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `rma_id` (INT) - FK to `rmas`
- `order_detail_id` (INT) - FK to `orders_details` (which line item was returned)
- `quantity_returned` (DECIMAL) - Quantity returned
- `quantity_restocked` (DECIMAL) - Quantity restocked to inventory
- `created_at` (DATETIME)
- `created_by_user_id` (INT) - FK to `synced_users`

**Calculated:** `price_total` = `unit_price * quantity_returned`

---

### Table: products_stock (stock_locations)

**Purpose:** Inventory levels per product per warehouse location. Each row represents a specific bin/shelf location in a warehouse.

**Key Columns:**
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT)
- `product_id` (INT) - FK to `products`
- `location_warehouse_id` (INT) - FK to `location_warehouses` (0 = no specific warehouse)
- `qty` (INT) - Quantity on hand (API field: `quantity`)
- `location_row` (VARCHAR) - Row identifier
- `location_column` (VARCHAR) - Column identifier
- `location_shelf` (VARCHAR) - Shelf identifier
- `location_bin` (VARCHAR) - Bin identifier
- `origin` (INT) - FK to `location_countries` (origin country for ITAR)
- `admin_notes` (TEXT)
- `virtual` (BOOLEAN) - Virtual stock flag
- `po_id` (INT) - FK to `po_` (related purchase order)
- `user_id` (INT) - FK to `synced_users` (last modified by)
- `modified_at` (DATETIME)

**Important Notes:**
- Location is formatted as: `warehouse_name: row-column-shelf-bin`
- Total stock for a product = `SUM(qty)` across all stock locations
- Physical stock excludes customer warehouses and sales rep warehouses: `WHERE warehouse_customer IS NULL AND warehouse_sales_rep_user IS NULL`

---

### Table: location_warehouses (warehouses)

**Purpose:** Warehouse definitions for inventory management. Can be physical warehouses, customer-specific virtual warehouses, or sales rep warehouses.

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `name` (VARCHAR) - Warehouse name
- `address_id` (INT) - FK to `addresses`
- `sort` (INT) - Display order
- `status` (INT) - Active/inactive
- `sales_rep_user_id` (INT) - FK to `synced_users` (NULL for regular warehouses)
- `customer_id` (INT) - FK to `customers` (NULL for regular warehouses)

**Important Notes:**
- `sales_rep_user_id IS NOT NULL` = sales rep warehouse (consignment)
- `customer_id IS NOT NULL` = customer-specific warehouse
- Both NULL = standard physical warehouse

---

### Table: customers_credit (customer_credits)

**Purpose:** Store credit/credit memo records for customers, often created from RMA returns.

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `customer_id` (INT) - FK to `customers`
- `status` (INT) - FK to `customers_credit_statuses` (1=Open, 2=Used, 3=Partially Used, 4=Closed, 5=Cancelled)
- `amount` (DECIMAL) - Credit amount
- `credit_reason` (INT) - FK to `customers_credit_reasons`
- `rma_id` (INT) - FK to `rmas`
- `sales_rep` (INT) - FK to `synced_users` (created by)
- `approved_by` (INT) - FK to `synced_users`
- `customer_notes` (VARCHAR(200))
- `admin_notes` (VARCHAR(200))
- `time` (DATETIME) - Creation timestamp (API field: `created_at`)

**Calculated:** `balance` = `amount - SUM(related transaction_log payments)`

---

### Table: customer_companies

**Purpose:** Company records that customers belong to. Multiple customers can belong to one company.

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `name` (VARCHAR) - Company name
- `address_id` (INT) - FK to `addresses`
- `accounting_email` (VARCHAR) - Accounting department email
- `payment_term_id` (INT) - FK to `payment_terms_statuses`
- `tax_id` (INT) - Tax ID number
- `primary_customer_id` (INT) - FK to `customers` (primary contact)
- `admin_notes` (VARCHAR(300))
- `created_at` (DATETIME)
- `modified_at` (DATETIME)

---

### Table: synced_users (users)

**Purpose:** System users (employees/admins). Referenced as sales reps, order creators, fulfillment pickers, etc.

**Key Columns:**
- `id` (INT, PRIMARY KEY, AUTO_INCREMENT)
- `fname` (VARCHAR) - First name (API field: `first_name`)
- `lname` (VARCHAR) - Last name (API field: `last_name`)
- `title` (VARCHAR) - Job title
- `email` (VARCHAR) - Email address
- `status` (INT) - User status (1=active)
- `last_login` (DATETIME)
- `permission` (INT) - FK to `user_groups` (permission level)
- `address_id` (INT) - FK to `addresses`
- `user_type_id` (INT) - User type
- `role_id` (INT) - FK to `user_roles`
- `default_warehouse_id` (INT) - FK to `location_warehouses`
- `default_store_id` (INT) - FK to `stores`
- `account_id` (INT) - Zangerine account ID

**Important Notes:**
- Users are synced from the admin database to client databases
- `label` = `CONCAT(first_name, ' ', last_name)`
- Used as `sales_rep` in orders, quotes, POs, and customer assignments

---

## SECTION 3: Table Relationships

### Foreign Key Relationships

1. **orders → customers**
   - `orders.customer_id` → `customers.id`
   - Relationship: Many orders per customer
   - Join Pattern: `LEFT JOIN \`customers\` c ON o.\`customer_id\` = c.\`id\``

2. **orders → addresses (shipping)**
   - `orders.ship_id` → `addresses.id`
   - Relationship: One shipping address per order
   - Join Pattern: `LEFT JOIN \`addresses\` sa ON o.\`ship_id\` = sa.\`id\``

3. **orders → addresses (billing)**
   - `orders.bill_id` → `addresses.id`
   - Relationship: One billing address per order
   - Join Pattern: `LEFT JOIN \`addresses\` ba ON o.\`bill_id\` = ba.\`id\``

4. **orders → order_status**
   - `orders.status` → `order_status.id`
   - Relationship: One status per order
   - Join Pattern: `LEFT JOIN \`order_status\` os ON o.\`status\` = os.\`id\``

5. **orders_details → orders**
   - `orders_details.order_id` → `orders.id`
   - Relationship: Many line items per order
   - Join Pattern: `INNER JOIN \`orders\` o ON od.\`order_id\` = o.\`id\``

6. **orders_details → products**
   - `orders_details.real_product_id` → `products.id`
   - Relationship: Each line item references one product
   - Join Pattern: `LEFT JOIN \`products\` p ON od.\`real_product_id\` = p.\`id\``

7. **transaction_log → orders**
   - `transaction_log.type_id` → `orders.id` (WHERE `type = 'order'`)
   - Relationship: Many transactions per order
   - Join Pattern: `LEFT JOIN \`transaction_log\` tl ON tl.\`type_id\` = o.\`id\` AND tl.\`type\` = 'order'`

8. **po_ → po_vendors**
   - `po_.vendor_id` → `po_vendors.id`
   - Relationship: Many POs per vendor
   - Join Pattern: `LEFT JOIN \`po_vendors\` v ON po.\`vendor_id\` = v.\`id\``

9. **po_details → po_**
   - `po_details.po_id` → `po_.id`
   - Relationship: Many line items per PO
   - Join Pattern: `INNER JOIN \`po_\` po ON pd.\`po_id\` = po.\`id\``

10. **po_details → orders_details**
    - `po_details.order_detail_id` → `orders_details.id`
    - Relationship: Links PO line items to sales order line items
    - Join Pattern: `LEFT JOIN \`orders_details\` od ON pd.\`order_detail_id\` = od.\`id\``

11. **quotes → customers**
    - `quotes.customer_id` → `customers.id`
    - Relationship: Many quotes per customer
    - Join Pattern: `LEFT JOIN \`customers\` c ON q.\`customer_id\` = c.\`id\``

12. **quotes → orders**
    - `quotes.order_id` → `orders.id`
    - Relationship: One order per converted quote
    - Join Pattern: `LEFT JOIN \`orders\` o ON q.\`order_id\` = o.\`id\``

13. **rma_details → orders_details**
    - `rma_details.order_detail_id` → `orders_details.id`
    - Relationship: Returns reference original order line items
    - Join Pattern: `INNER JOIN \`orders_details\` od ON rd.\`order_detail_id\` = od.\`id\``

14. **customers → customer_companies**
    - `customers.company_id` → `customer_companies.id`
    - Relationship: Many customers per company
    - Join Pattern: `LEFT JOIN \`customer_companies\` cc ON c.\`company_id\` = cc.\`id\``

15. **products_stock → products**
    - `products_stock.product_id` → `products.id`
    - Relationship: Many stock locations per product
    - Join Pattern: `LEFT JOIN \`products_stock\` ps ON ps.\`product_id\` = p.\`id\``

16. **products_stock → location_warehouses**
    - `products_stock.location_warehouse_id` → `location_warehouses.id`
    - Relationship: Stock location belongs to a warehouse
    - Join Pattern: `LEFT JOIN \`location_warehouses\` w ON ps.\`location_warehouse_id\` = w.\`id\``

17. **orders → synced_users (sales rep)**
    - `orders.sales_rep` → `synced_users.id`
    - Relationship: One primary sales rep per order
    - Join Pattern: `LEFT JOIN \`synced_users\` sr ON o.\`sales_rep\` = sr.\`id\``

18. **order_fulfillments → orders**
    - `order_fulfillments.order_id` → `orders.id`
    - Relationship: Many fulfillments per order (one per warehouse)
    - Join Pattern: `INNER JOIN \`orders\` o ON of.\`order_id\` = o.\`id\``

19. **orders_details_picked → order_fulfillments**
    - `orders_details_picked.order_fulfillment_id` → `order_fulfillments.id`
    - Relationship: Picking records for fulfillment
    - Join Pattern: `INNER JOIN \`order_fulfillments\` of ON odp.\`order_fulfillment_id\` = of.\`id\``

20. **customers_credit → customers**
    - `customers_credit.customer_id` → `customers.id`
    - Relationship: Many credits per customer
    - Join Pattern: `LEFT JOIN \`customers\` c ON cc.\`customer_id\` = c.\`id\``

### Link Tables (Many-to-Many)

| Link Table | From | To | Purpose |
|---|---|---|---|
| `customer_group_relations` | `customers` (customer_id) | `customer_groups` (group_id) | Customer group memberships |
| `customer_address_relation` | `customers` (customer_id) | `addresses` (address_id) | Customer address book |
| `product_category_relations` | `products` (product_id) | `product_categories` (category_id) | Product categorization |
| `po_vendor_product_relations` | `products` (product_id) | `po_vendors` (vendor_id) | Which vendors supply which products |
| `sellers_customers_relation` | `sellers` (seller_id) | `customers` (customer_id) | Seller-customer assignments |
| `colored_tags_relations` | various (type_id) | `colored_tags` (colored_tag_id) | Color tag system (segmented by type) |
| `order_additional_sales_rep_users` | `orders` (order_id) | `synced_users` (sales_rep_user_id) | Additional sales reps on orders |
| `customer_additional_sales_rep_users` | `customers` (customer_id) | `synced_users` (sales_rep_user_id) | Additional sales reps on customers |
| `purchase_order_sources` | `po_` (purchase_order_id) | `orders` (order_id) | PO-to-order links |
| `products_stores_relations` | `products` (product_id) | `stores` (store_id) | Product-store visibility |
| `order_sellers` | `orders` (order_id) | `sellers` (seller_id) | Seller-order associations |

---

## SECTION 4: Common Query Patterns (20 Examples)

```python
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
```

---

## SECTION 5: Business Logic Definitions

```python
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

    "quote_conversion": "When a quote is accepted and converted to an order, the quotes.order_id field is populated with the new order's ID."
}
```

---

## SECTION 6: SQL Conventions & Best Practices

```python
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
    "pass → password_hash (customers)"
]
```

---

## SECTION 7: Performance Characteristics

```python
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
    "For customer lookups, email index is available but may have duplicates across guest accounts"
]
```

---

## SECTION 8: Data Quality Notes

```python
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
    "Commission data links through commission_period → sales_rep_user, not directly to orders.sales_rep"
]
```

---

## SECTION 9: Enum/Categorical Values

```python
ENUM_VALUES = {
    "order_status": {
        1:  "Abandoned - Cart was abandoned, never completed",
        2:  "Completed - Order processing complete",
        3:  "Shipped - All items shipped",
        4:  "Unknown - Legacy/undefined status",
        5:  "Declined - Payment declined",
        6:  "Approved - Order approved for processing",
        7:  "Pending Shipment - Approved, awaiting shipment",
        8:  "Pending Payment - Awaiting payment",
        9:  "Paid in Full - Payment received in full",
        10: "Pro Forma - Proforma invoice",
        11: "Cancelled - Order cancelled",
        12: "Refunded - Fully refunded",
        13: "Refunded Partially - Partial refund issued",
        14: "Pending Approval - Awaiting approval",
        15: "Paid Partially - Partial payment received",
        30: "Pending Fulfillment - Ready for warehouse picking",
        31: "Picking - Currently being picked",
        32: "Packed - Packed and ready for shipment",
        33: "Picked - All items picked",
        34: "Picked Partially - Some items picked",
        40: "Shipped Partially - Some items shipped",
        50: "Backordered - Items on backorder",
        51: "On Hold - Order on hold",
    },

    "order_status_for_reports": "Exclude status 1 (Abandoned) and 11 (Cancelled). Common report statuses: 2,3,6,7,8,9,10,12,13,14,15,30,31,32,33,34,40,50,51",

    "quote_status": {
        1:  "Created - New quote created",
        2:  "Sent - Quote sent to customer",
        3:  "On Hold - Quote on hold",
        4:  "Cancelled - Quote cancelled",
        5:  "Rejected - Customer rejected quote",
        6:  "Expired - Quote passed expiration date",
        7:  "Accepted - Customer accepted quote",
        8:  "Pro Forma - Proforma quote",
        9:  "Changes Requested - Customer requested changes",
        10: "Requested - Quote requested by customer",
        11: "No Sale - Quote did not result in sale",
    },

    "purchase_order_status": {
        1:  "Pending - New PO created",
        2:  "Cancelled - PO cancelled",
        3:  "Approved - PO approved internally",
        4:  "Sent - PO sent to vendor",
        5:  "Accepted - Vendor accepted PO",
        6:  "Rejected - Vendor rejected PO",
        7:  "Shipped - Vendor shipped goods",
        8:  "Received - All goods received",
        9:  "Received Partially - Some goods received",
        10: "Paid - PO fully paid",
        11: "Paid Partially - PO partially paid",
        12: "Delivered - Goods delivered to destination",
        13: "Shipped Partially - Vendor partially shipped",
    },

    "transaction_status": {
        1: "Pending - Transaction initiated, awaiting settlement",
        2: "Succeeded - Payment successfully processed",
        3: "Declined - Payment declined by processor",
        4: "Refunded - Payment refunded",
        5: "Voided - Transaction voided before settlement",
    },

    "rma_status": {
        0: "Created - RMA created",
        1: "Pending - Awaiting return",
        2: "Received - Return received",
        3: "Accepted - Return accepted",
        4: "Rejected - Return rejected",
        5: "Cancelled - RMA cancelled",
    },

    "customer_credit_status": {
        1: "Open - Credit available for use",
        2: "Used - Credit fully applied",
        3: "Used Partial - Credit partially applied",
        4: "Closed - Credit closed/expired",
        5: "Cancelled - Credit cancelled",
    },

    "order_fulfillment_status": {
        1: "Open - Fulfillment created",
        2: "Picked - Items picked from warehouse",
        3: "Inspected - Items inspected/QC'd",
        4: "Packed - Items packed for shipment",
        5: "Shipped - Fulfillment shipped",
        6: "Pending - Awaiting processing",
        7: "In Progress - Currently being processed",
        8: "Fulfilled - Completely fulfilled",
        9: "Will Call - Customer pickup",
    },

    "recurring_profile_status": {
        1: "Active - Profile is active and generating orders",
        2: "Cancelled - Profile cancelled",
        3: "Complete - All occurrences completed",
    },

    "order_picking_status": {
        "'0'": "Not Picked",
        "'1'": "Picked (all items)",
        "'2'": "Picked Partially",
    },

    "order_shipping_status": {
        "'0'": "Not Shipped",
        "'1'": "Shipped (all items)",
        "'2'": "Shipped Partially",
    },

    "order_type": {
        "sales_order":    "Standard customer sales order",
        "rental_order":   "Rental/lease order",
        "transfer_order": "Warehouse-to-warehouse transfer",
    },

    "customer_gender": {
        0: "Not specified",
        1: "Male (M)",
        2: "Female (F)",
    },

    "inventory_type": {
        1: "FIFO - First In First Out cost tracking",
        2: "Serial Number - Individual serial number tracking",
        3: "Standard Cost - Fixed cost per unit",
    },

    "product_boolean_enums": "Many product boolean fields use ENUM('1','0') strings, NOT actual boolean/tinyint: manage_stock, allow_backorder, status (is_published), drop_ship, special_order_item, not_for_sale, visible, taxable, is_child"
}
```

---

## SECTION 10: Sample Schema Export (SQL DDL)

```sql
-- Core tables DDL (simplified from schema JSON definitions)

CREATE TABLE `orders` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `customer_id` BIGINT NOT NULL,
    `status` TINYINT NOT NULL DEFAULT 1,
    `total` DECIMAL(15,5) NOT NULL DEFAULT 0.00000,
    `tax_fee` DECIMAL(15,5) NOT NULL DEFAULT 0.00000,
    `state_tax_fees` DECIMAL(15,5) NOT NULL,
    `shipping_fee` DECIMAL(15,5) NOT NULL DEFAULT 0.00000,
    `discount_amount` DECIMAL(15,5) NOT NULL DEFAULT 0.00000,
    `coupon_id` INT NOT NULL DEFAULT 0,
    `ship_id` BIGINT NOT NULL DEFAULT 0,
    `bill_id` BIGINT DEFAULT 0,
    `shipping_method` INT DEFAULT 0,
    `shipping_notes` VARCHAR(200) DEFAULT NULL,
    `payment_term_id` INT NOT NULL DEFAULT 1,
    `tracking_num` TEXT,
    `po_num` TEXT,
    `time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `invoice_date` DATETIME DEFAULT NULL,
    `due_date` DATE DEFAULT NULL,
    `ship_date` DATE DEFAULT NULL,
    `invoice_number` INT DEFAULT NULL,
    `customer_notes` TEXT,
    `admin_notes` TEXT,
    `sales_rep` INT NOT NULL DEFAULT 0,
    `store` TINYINT NOT NULL DEFAULT 0,
    `marketing_source` TINYINT DEFAULT 0,
    `picked` ENUM('0','1','2') NOT NULL DEFAULT '0',
    `shipped` ENUM('0','1','2') NOT NULL DEFAULT '0',
    `modified_on` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `last_edited_by` INT DEFAULT NULL,
    `order_type` VARCHAR(255) NOT NULL DEFAULT 'sales_order',
    `integration_id` INT UNSIGNED NOT NULL DEFAULT 0,
    `integration_order_id` VARCHAR(128) DEFAULT NULL,
    `integration_order_number` VARCHAR(128) DEFAULT NULL,
    `recurring_profile_id` BIGINT DEFAULT NULL,
    `payment_account_id` INT DEFAULT NULL,
    `shipping_service_id` INT DEFAULT NULL,
    `currency_id` INT DEFAULT NULL,
    `reference_id` VARCHAR(20) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `time` (`time`),
    KEY `status` (`status`),
    KEY `customer_id` (`customer_id`),
    KEY `my_idx` (`status`, `customer_id`),
    KEY `ship_id` (`ship_id`),
    KEY `bill_id` (`bill_id`),
    KEY `reference_id` (`reference_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `orders_details` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `order_id` BIGINT NOT NULL,
    `real_product_id` BIGINT,
    `product_sku` VARCHAR(255),
    `product_name` VARCHAR(255),
    `product_type` VARCHAR(255),
    `qty` DECIMAL(15,5),
    `price` DECIMAL(15,5),
    `original_price` DECIMAL(15,5),
    `credit_card_price` DECIMAL(15,5),
    `costs` DECIMAL(15,5),
    `warehouse_id` INT,
    `quantity_backordered` INT,
    `sample_product` TINYINT DEFAULT 0,
    `note` TEXT,
    `sort` INT,
    `product_cross_reference_id` INT DEFAULT NULL,
    `x_rewards_customer_product_id` INT DEFAULT NULL,
    `integration_order_line_item_id` VARCHAR(128) DEFAULT NULL,
    `integration_item_id` VARCHAR(128) DEFAULT NULL,
    `sales_order_detail_display_price_id` BIGINT DEFAULT NULL,
    `currency_id` INT DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `order_id` (`order_id`),
    KEY `real_product_id` (`real_product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `customers` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `fname` VARCHAR(100) NOT NULL,
    `lname` VARCHAR(50) NOT NULL,
    `title` VARCHAR(50) DEFAULT NULL,
    `company_id` INT NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(30) NOT NULL,
    `phone_ext` VARCHAR(11) NOT NULL,
    `secondary_phone` VARCHAR(30) DEFAULT NULL,
    `fax` VARCHAR(30) DEFAULT NULL,
    `website` VARCHAR(255) NOT NULL,
    `birthdate` VARCHAR(15) DEFAULT NULL,
    `notes` TEXT NOT NULL,
    `creation_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `modified_at` DATETIME NOT NULL,
    `gender` INT NOT NULL COMMENT '1: Male, 2: Female',
    `status` INT NOT NULL DEFAULT 1,
    `automated_payment_reminders` INT NOT NULL DEFAULT 1,
    `sales_rep_id` INT NOT NULL DEFAULT 0,
    `default_ship_id` INT NOT NULL DEFAULT 0,
    `default_bill_id` INT NOT NULL DEFAULT 0,
    `currency_id` INT NOT NULL DEFAULT 5,
    `integration_id` INT UNSIGNED NOT NULL DEFAULT 0,
    `guest` TINYINT UNSIGNED DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `idx_email` (`email`),
    KEY `idx_phone` (`phone`),
    KEY `idx_fname` (`fname`),
    KEY `idx_lname` (`lname`),
    KEY `idx_company_id` (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `products` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `sku` VARCHAR(255),
    `name` VARCHAR(255),
    `price` DECIMAL(15,5),
    `cost` DECIMAL(15,5),
    `list_price` DECIMAL(15,5),
    `manufacturer_id` INT,
    `status` ENUM('1','0') DEFAULT '1',
    `visible` ENUM('1','0') DEFAULT '1',
    `manage_stock` ENUM('1','0') DEFAULT '0',
    `allow_backorder` ENUM('1','0') DEFAULT '0',
    `taxable` ENUM('1','0') DEFAULT '1',
    `drop_ship` ENUM('1','0') DEFAULT '0',
    `is_child` ENUM('1','0') DEFAULT '0',
    `master_product_id` INT,
    `inventory_type_id` INT,
    `min_stock_level` INT,
    `weight` DECIMAL(10,4),
    `weight_unit` VARCHAR(20),
    `date_added` DATETIME,
    `date_modified` DATETIME,
    `deleted_by` INT DEFAULT NULL,
    `sort` INT,
    PRIMARY KEY (`id`),
    KEY `idx_sku` (`sku`),
    KEY `idx_name` (`name`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `addresses` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `fname` VARCHAR(100) NOT NULL,
    `lname` VARCHAR(50) NOT NULL,
    `company` VARCHAR(255),
    `address1` VARCHAR(255),
    `address2` VARCHAR(255),
    `city` VARCHAR(100),
    `state` VARCHAR(100),
    `zip` VARCHAR(20),
    `country` VARCHAR(50),
    `phone` VARCHAR(30),
    `phone_ext` INT,
    `secondary_phone` VARCHAR(30),
    `fax` VARCHAR(30),
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `transaction_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `type` VARCHAR(50) NOT NULL,
    `type_id` BIGINT NOT NULL,
    `amount` DECIMAL(15,5),
    `payment_method_id` INT,
    `transaction_id` VARCHAR(200),
    `reference_number` VARCHAR(200),
    `parent_transaction_log_id` INT,
    `customer_credit_id` INT,
    `bill_addr` INT,
    `last_four_digits` INT,
    `log` TEXT,
    `time` DATETIME NOT NULL,
    `modified_at` DATETIME,
    `status` TINYINT,
    `status_message` VARCHAR(255),
    `payment_account_id` INT,
    `payment_gateway_type_id` INT,
    `currency_id` INT,
    PRIMARY KEY (`id`),
    KEY `type_type_id` (`type`, `type_id`),
    KEY `time` (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `po_` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `vendor_id` INT,
    `is_dropship` ENUM('1','0') DEFAULT '0',
    `store` TINYINT NOT NULL DEFAULT 0,
    `status_id` INT,
    `total` DECIMAL(15,5),
    `value_received` DECIMAL(15,5),
    `outstanding_balance` DECIMAL(15,5),
    `shipping_fee` DECIMAL(15,5),
    `ship_id` BIGINT,
    `bill_id` BIGINT,
    `tracking_num` VARCHAR(255),
    `external_notes` TEXT,
    `admin_notes` TEXT,
    `sales_rep` INT,
    `received_by` INT,
    `time` DATETIME NOT NULL,
    `modified_on` DATETIME,
    `receive_date` DATE,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

CREATE TABLE `products_stock` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `product_id` INT NOT NULL,
    `location_warehouse_id` INT NOT NULL DEFAULT 0,
    `qty` INT NOT NULL DEFAULT 0,
    `location_row` VARCHAR(50),
    `location_column` VARCHAR(50),
    `location_shelf` VARCHAR(50),
    `location_bin` VARCHAR(50),
    `admin_notes` TEXT,
    `virtual` TINYINT DEFAULT 0,
    `po_id` INT DEFAULT 0,
    `user_id` INT,
    `modified_at` DATETIME,
    PRIMARY KEY (`id`),
    KEY `product_id` (`product_id`),
    KEY `location_warehouse_id` (`location_warehouse_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

---

## SECTION 11: Access Patterns & User Groups

### User Groups

1. **Administrators** (full access)
   - Can view all data across all stores
   - Run financial reports (sales, AR, margins, commissions)
   - Manage all entities (orders, customers, products, POs, etc.)
   - Typical queries: aggregate reports, aging, margin analysis

2. **Sales Representatives**
   - View orders/quotes/customers assigned to them (filtered by sales_rep)
   - Commission reports for their own sales
   - Customer relationship data
   - Typical queries: my orders, my customers, my quotes, my commissions

3. **Warehouse Staff**
   - Inventory levels and stock locations
   - Order fulfillment and picking lists
   - Purchase order receiving
   - Typical queries: stock levels, unfulfilled orders, picking lists

4. **Accounting**
   - Accounts receivable and aging reports
   - Transaction/payment reports
   - Customer statements and credit reports
   - QuickBooks sync status
   - Typical queries: AR aging, payment summaries, customer credit balances

5. **Management/Executives**
   - High-level sales metrics and trends
   - Store comparison reports
   - Sales rep performance
   - Product performance analysis
   - Typical queries: sales by period, top customers, top products, conversion rates

### Common Query Categories by Role

| Category | Tables Involved | Typical Filters |
|---|---|---|
| Sales Reports | orders, orders_details, customers, products | invoice_date range, status NOT IN (1,11) |
| AR/Financial | orders, transaction_log, customers | balance > 0, due_date ranges |
| Inventory | products, products_stock, location_warehouses | deleted_by IS NULL, manage_stock='1' |
| Fulfillment | orders, order_fulfillments, orders_details_picked | shipped != '1', status active |
| Purchasing | po_, po_details, po_vendors, products | status_id active, date ranges |
| Returns | rmas, rma_details, orders_details, customers_credit | date ranges, status filters |
| CRM | customers, customer_companies, customer_group_relations | status=1 (active) |
| Commissions | commissions, commission_periods, synced_users | cutoff_date ranges, period status |
