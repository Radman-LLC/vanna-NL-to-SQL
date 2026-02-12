# ADR (Zangerine) Database — Report-Specific Training Data Supplement

This document supplements `nl-to-sql-training-data-response.md` with complete table definitions, relationships, business logic, and query patterns for the following reports:

- `/reports/sales/revenue-performance`
- `/reports/jbd-commission`
- `/plugin-rewards/reports/*` (20 reports)

---

## SECTION 1: Report Inventory

### Revenue Performance Report

| Attribute | Value |
|-----------|-------|
| Route | `/reports/sales/revenue-performance` |
| React Component | `RevenuePerformanceReportScreen.jsx` |
| Backend Service | `ReportAjax.php → loadRevenuePerformanceReportData()` |
| Permission | `report/sales` |

### JBD Commission Report

| Attribute | Value |
|-----------|-------|
| Route | `/reports/jbd-commission` |
| React Component | `JbdCommissionReportScreen.jsx` |
| Backend Service | `ReportAjax.php → loadJbdCommissionReportData()` |
| Permission | `x_rewards/commission_report/all` |

### Plugin Rewards Reports (20 total)

| # | Route | Report Name | React Component |
|---|-------|-------------|-----------------|
| 1 | `/plugin-rewards/reports/commission` | Commission Report | `XRewardsCommissionReportScreen.jsx` |
| 2 | `/plugin-rewards/reports/sales-by-reps-commission` | Sales by Reps Commission | `XRewardsSalesByRepsCommissionReportScreen.jsx` |
| 3 | `/plugin-rewards/reports/adjustment-detail` | Adjustment Detail | `XRewardsAdjustmentDetailReportScreen.jsx` |
| 4 | `/plugin-rewards/reports/adjustment-totals` | Adjustment Totals | `XRewardsAdjustmentTotalsReportScreen.jsx` |
| 5 | `/plugin-rewards/reports/net-profit` | Net Profit | `XRewardsNetProfitReportScreen.jsx` |
| 6 | `/plugin-rewards/reports/label-sales` | Label Sales | `XRewardsLabelSalesReportScreen.jsx` |
| 7 | `/plugin-rewards/reports/reward` | Reward Report | `XRewardsRewardReportScreen.jsx` |
| 8 | `/plugin-rewards/reports/liability-summary` | Liability Summary | `XRewardsLiabilitySummaryReportScreen.jsx` |
| 9 | `/plugin-rewards/reports/liability` | Liability Detail | `XRewardsLiabilityReportScreen.jsx` |
| 10 | `/plugin-rewards/reports/to-date-sales-comparison` | YTD Sales Comparison | `XRewardsToDateSalesComparisonReportScreen.jsx` |
| 11 | `/plugin-rewards/reports/paid-pay-sheets` | Paid Pay Sheets | `XRewardsPaidPaySheetsReportScreen.jsx` |
| 12 | `/plugin-rewards/reports/profit-loss-by-customer-association` | P&L by Customer Association | `XRewardsProfitLossByCustomerAssociationReportScreen.jsx` |
| 13 | `/plugin-rewards/reports/profit-loss-by-customer` | P&L by Customer | `XRewardsProfitLossByCustomerReportScreen.jsx` |
| 14 | `/plugin-rewards/reports/customer-product-inventory` | Customer Product Inventory | `XRewardsCustomerProductInventoryReportScreen.jsx` |
| 15 | `/plugin-rewards/reports/1099-report` | 1099 Tax Report | `XRewards1099ReportScreen.jsx` |
| 16 | `/plugin-rewards/reports/customer-purchase-obligations` | Customer Purchase Obligations | `XRewardsCustomerPurchaseObligationsReportScreen.jsx` |
| 17 | `/plugin-rewards/reports/connecticut-sales` | Connecticut Sales | `XRewardsConnecticutSalesReportScreen.jsx` |
| 18 | `/plugin-rewards/reports/total-sold` | Total Sold | `XRewardsTotalSoldReportScreen.jsx` |
| 19 | `/plugin-rewards/reports/retail-profit-management` | Retail Profit Management (RPM) | `XRewardsRetailProfitManagementReportScreen.jsx` |
| 20 | `/plugin-rewards/reports/rpm-csv-download` | RPM CSV Download | (server-side CSV export) |

**Backend Service for all Plugin Rewards reports:** `XRewardsReportService.php` (4700+ lines) via `XRewardsReportAjax.php`

---

## SECTION 2: Additional Database Tables

These tables are used by the reports above and were NOT included in the base training data response.

### Table: commissions

**Purpose:** Stores individual commission records per sales rep per order/RMA line item. Each commission links a sales rep (via commission_period) to a specific order_detail or rma_detail, recording the negotiated price, commission percentage, and calculated amount.

**Key Columns:**
- `id` (BIGINT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT) - Unique commission record ID
- `created_at` (DATETIME, NOT NULL) - Record creation timestamp
- `created_by_user_id` (INT, DEFAULT NULL) - FK to `synced_users`
- `modified_at` (DATETIME, NOT NULL) - Last modification timestamp
- `modified_by_user_id` (INT, DEFAULT NULL) - FK to `synced_users`
- `commission_period_id` (BIGINT UNSIGNED, DEFAULT NULL, INDEXED) - FK to `commission_periods`
- `commission_date` (DATE, NOT NULL) - Effective commission date
- `order_id` (BIGINT UNSIGNED, DEFAULT NULL, INDEXED) - FK to `orders`
- `order_detail_id` (BIGINT UNSIGNED, DEFAULT NULL) - FK to `orders_details`
- `rma_detail_id` (BIGINT UNSIGNED, DEFAULT NULL) - FK to `rma_details` (populated for return commissions)
- `quantity` (INT, DEFAULT NULL) - Quantity sold or returned
- `commission_price` (DECIMAL(12,4), DEFAULT NULL) - Unit price used for commission calculation (after rewards deducted)
- `commission_percent` (DECIMAL(7,4), DEFAULT NULL) - Commission percentage for this rep
- `unit_commission` (DECIMAL(12,4), DEFAULT NULL) - Commission amount per unit
- `amount` (DECIMAL(12,4), NOT NULL) - Total commission amount
- `category_id` (INT UNSIGNED, NOT NULL) - FK to `commission_categories` (1=SALE, 2=QUOTA)
- `note` (VARCHAR(255), NOT NULL) - Commission note

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `commission_period_id`
- INDEX on `order_id`

**Dynamic Fields (EAV Pattern):**
- Custom fields stored in `commission_custom_field_values` (reference_column=`commission_id`, key_column=`field_name`, value_column=`field_value`)

**Lookup Fields (via entity relationships):**
- `sales_rep_user` — looked up via `commission_period → sales_rep_user`
- `order_invoice_date` — looked up via `order → invoice_date`
- `order_balance` — looked up via `order → balance`
- `company` — looked up via `order_detail → customer_company`
- `sku` — looked up via `order_detail → sku`
- `product_name` — looked up via `order_detail → product_name`
- `product_description` — looked up via `order_detail → product_description`
- `price` — looked up via `order_detail → price`
- `cost_total` — looked up via `order_detail → total_cost` (SUM_NEVER_NULL aggregation)
- `rma` — looked up via `rma_detail → rma`
- `rma_created_at` — looked up via `rma_detail → created_at`

---

### Table: commission_periods

**Purpose:** Groups commissions by sales rep and cutoff date. Each period represents a payment cycle for a specific sales rep.

**Key Columns:**
- `id` (BIGINT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT) - Period ID
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL) - FK to `synced_users`
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL) - FK to `synced_users`
- `sales_rep_user_id` (INT UNSIGNED, NOT NULL) - FK to `synced_users`
- `cutoff_date` (DATE, NOT NULL) - Period cutoff date
- `status_id` (INT UNSIGNED, NOT NULL) - FK to `commission_period_statuses`

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on (`sales_rep_user_id`, `cutoff_date`)
- INDEX on `status_id`

**Computed Fields:**
- `label` = `CONCAT(id, ': ', sales_rep_user_label, ', ', cutoff_date)`
- `total_commissions` = SUM of related commissions.amount
- `total_payments` = SUM of related commission_payments.amount
- `balance` = `total_commissions - total_payments`

---

### Table: commission_period_statuses

**Purpose:** Lookup table for commission period payment states.

**Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `label` (VARCHAR(255), NOT NULL)

**Seed Data:**

| id | label |
|----|-------|
| 1 | Unpaid |
| 2 | Paid |
| 3 | On Hold |

---

### Table: commission_payments

**Purpose:** Records payments made against commission periods.

**Key Columns:**
- `id` (BIGINT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `commission_period_id` (BIGINT UNSIGNED, NOT NULL, INDEXED) - FK to `commission_periods`
- `amount` (DECIMAL(12,4), NOT NULL) - Payment amount
- `note` (VARCHAR(255), NOT NULL)

---

### Table: commission_categories

**Purpose:** Categorizes commission line items.

**Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `label` (VARCHAR(255), NOT NULL)

**Known Values:**

| id | label |
|----|-------|
| 1 | SALE |
| 2 | QUOTA |

**Source:** `lib/Zangerine/XRewardsCommissionCategory.php`

---

### Table: commission_custom_field_values

**Purpose:** EAV (Entity-Attribute-Value) table for custom fields on commission records.

**Columns:**
- `commission_id` (BIGINT UNSIGNED, NOT NULL) - FK to `commissions`
- `field_name` (VARCHAR(255), NOT NULL) - Custom field name
- `field_value` (VARCHAR(255), NOT NULL) - Custom field value

**Primary Key:** (`commission_id`, `field_name`)

---

### Table: x_rewards_rewards

**Purpose:** Tracks individual reward/rebate entries generated when order fulfillment details are processed. Each reward links to a specific profile (customer reward program) and can optionally be associated with a serial number.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL) - When reward was created
- `created_by_user_id` (INT, DEFAULT NULL) - FK to `synced_users`
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `order_fulfillment_detail_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `orders_details_picked`
- `quantity_index` (INT UNSIGNED, NOT NULL, INDEXED) - Index within the fulfillment quantity
- `pack_index` (INT UNSIGNED, NOT NULL) - Pack index for multi-pack products
- `serial_number` (VARCHAR(255), NOT NULL, UNIQUE) - Reward serial number
- `profile_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `x_rewards_profiles`
- `amount` (DECIMAL(12,4), NOT NULL, INDEXED) - Reward dollar amount
- `redeemed_at` (DATETIME, DEFAULT NULL, INDEXED) - When reward was redeemed
- `redemption_period_id` (INT UNSIGNED, DEFAULT NULL, INDEXED) - FK to `x_rewards_redemption_periods` (NULL = unredeemed)
- `is_void` (TINYINT, NOT NULL, INDEXED) - 0=active, 1=voided
- `is_imported_label` (TINYINT, NOT NULL) - 1=imported from external system
- `import_order_id` (INT UNSIGNED, DEFAULT NULL, INDEXED) - External order ID if imported
- `import_order_date` (DATE, DEFAULT NULL) - External order date if imported
- `import_item_id` (INT UNSIGNED, DEFAULT NULL, INDEXED) - External line item ID if imported
- `import_sku` (VARCHAR(255), DEFAULT NULL, INDEXED) - External SKU if imported

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `serial_number`
- INDEX on `order_fulfillment_detail_id`
- INDEX on `profile_id`
- INDEX on `redemption_period_id`
- INDEX on `is_void`
- INDEX on `redeemed_at`
- COMPOSITE INDEX on (`redeemed_at`, `is_void`)
- INDEX on `amount`
- INDEX on `quantity_index`

**Computed/Expression Fields:**
- `import_order_id_or_order_id` = `IF(is_imported_label, import_order_id, order_id)`
- `import_order_date_or_order_created_at` = `IF(is_imported_label, import_order_date, order_created_at)`
- `import_sku_or_product_sku` = `IF(is_imported_label, import_sku, product_sku)`

**Lookup Fields (via entity relationships):**
- `order_fulfillment_detail → order_detail, product, product_sku, product_name, order, order_created_at, order_total, cost_total`
- `profile → customer, profile_title, redemption_method, hide_on_rpm, hide_on_executive_portal`
- `redemption_period → recipient, recipient_first_name, recipient_last_name`

**Important Notes:**
- `is_void = 0` is required in almost all report queries to exclude voided rewards
- `redemption_period_id IS NULL` indicates unredeemed (liability)
- `redemption_period_id IS NOT NULL` indicates redeemed (paid out)

---

### Table: x_rewards_profiles

**Purpose:** Defines a customer's reward program configuration. Each profile links a customer to a specific reward/rebate program with a redemption method.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `customer_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `customers`
- `title` (VARCHAR(255), NOT NULL, INDEXED) - Profile name/title
- `redemption_method` (VARCHAR(255), NOT NULL, INDEXED) - How rewards are redeemed
- `status` (TINYINT UNSIGNED, NOT NULL) - 0=inactive, 1=active
- `hide_on_rpm` (TINYINT UNSIGNED, NOT NULL) - Hide from RPM reports
- `hide_on_executive_portal` (TINYINT UNSIGNED, NOT NULL) - Hide from executive portal

**Redemption Method Values:**
- `serial_number` — Reward tracked via physical serial number labels
- `manual` — Manually triggered redemption
- `on_payment` — Redeemed when order is paid
- `on_redemption` — Redeemed on explicit request
- `on_first_of_month` — Auto-redeemed on 1st of month
- `on_15_of_month` — Auto-redeemed on 15th of month

**Computed Fields:**
- `label` = `CONCAT(title, ' (', customer_label, ')')`

**Relationships:**
- Has many `x_rewards_rewards` via `profile_id`
- Has many `x_rewards_recipients` via `x_rewards_recipient_profiles` link table

---

### Table: x_rewards_recipients

**Purpose:** Stores individuals who receive reward payments. A recipient can be linked to multiple profiles via the link table.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `first_name` (VARCHAR(255), NOT NULL)
- `middle_name` (VARCHAR(255), NOT NULL)
- `last_name` (VARCHAR(255), NOT NULL)
- `phone` (VARCHAR(20), NOT NULL)
- `email` (VARCHAR(255), NOT NULL)
- `address1` (VARCHAR(255), NOT NULL)
- `address2` (VARCHAR(255), NOT NULL)
- `city` (VARCHAR(255), NOT NULL)
- `state` (VARCHAR(255), NOT NULL)
- `country` (CHAR(2), DEFAULT NULL)
- `zip` (VARCHAR(255), NOT NULL)
- `password_hash` (VARCHAR(255), NOT NULL)
- `reset_password_sent_at` (DATETIME, DEFAULT NULL)
- `force_password_reset` (TINYINT, NOT NULL)
- `ssn_encrypted` (VARCHAR(255), DEFAULT NULL) - Encrypted SSN for 1099 reporting
- `date_of_birth` (DATE, DEFAULT NULL)
- `w9_received` (TINYINT, NOT NULL) - W-9 tax form received flag
- `preferred_payment_type` (VARCHAR(255), NOT NULL) - e.g., 'check', 'ach'
- `payment_account_number` (VARCHAR(255), NOT NULL)
- `payment_account_verified` (TINYINT, NOT NULL)
- `note` (TEXT)
- `status` (TINYINT UNSIGNED, NOT NULL) - 0=inactive, 1=active
- `executive_portal_access` (TINYINT UNSIGNED, NOT NULL)

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on (`first_name`, `middle_name`, `last_name`)

---

### Table: x_rewards_recipient_profiles (Link Table)

**Purpose:** Many-to-many relationship between recipients and profiles.

**Columns:**
- `recipient_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_recipients`
- `profile_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_profiles`

**Primary Key:** (`recipient_id`, `profile_id`)

---

### Table: x_rewards_redemption_periods

**Purpose:** Represents a payment cycle for reward payouts. Groups rewards by recipient, customer, and cutoff date. Used for pay sheet management and liability tracking.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `recipient_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_recipients`
- `customer_id` (INT UNSIGNED, NOT NULL) - FK to `customers`
- `cutoff_date` (DATE, NOT NULL) - Period cutoff date
- `balance` (DECIMAL(12,4), NOT NULL) - Remaining balance

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on (`recipient_id`, `customer_id`, `cutoff_date`)

**Computed Fields:**
- `has_balance` = `balance > 0`
- `rewards_total` = SUM of related non-void rewards amounts
- `approved_adjustments_total` = SUM of related approved adjustment amounts
- `payments_total` = SUM of related non-void payment amounts
- `total` = `rewards_total + approved_adjustments_total`

---

### Table: x_rewards_adjustments

**Purpose:** Manual adjustments to reward balances (additions or deductions) within a redemption period.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `redemption_period_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `x_rewards_redemption_periods`
- `amount` (DECIMAL(12,4), NOT NULL) - Adjustment amount (positive or negative)
- `note` (VARCHAR(255), NOT NULL) - Reason for adjustment
- `is_approved` (TINYINT, NOT NULL) - 0=pending, 1=approved

**Important:** Only adjustments with `is_approved = 1` are included in report calculations.

---

### Table: x_rewards_payments

**Purpose:** Records actual payments made against redemption periods (checks, ACH, etc.).

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `redemption_period_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `x_rewards_redemption_periods`
- `amount` (DECIMAL(12,4), NOT NULL) - Payment amount
- `payment_type` (VARCHAR(255), NOT NULL) - e.g., 'check', 'ach'
- `payment_account_number` (VARCHAR(255), NOT NULL)
- `note` (VARCHAR(255), NOT NULL)
- `check_number` (INT UNSIGNED, DEFAULT NULL) - Check number if payment type is check
- `void` (TINYINT UNSIGNED, DEFAULT 0) - 0=valid, 1=voided

**Important:** Only payments with `void = 0` are included in report calculations.

---

### Table: x_rewards_customer_products

**Purpose:** Customer-specific product configurations for the rewards program. Defines the customer's price, reward amounts per profile, and commission percentages per sales rep for each product.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `deleted_at` (DATETIME, NOT NULL) - Soft delete timestamp
- `deleted_by_user_id` (INT, DEFAULT NULL) - FK to `synced_users` (soft delete)
- `customer_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `customers`
- `product_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `products`
- `product_cross_reference_id` (INT UNSIGNED, DEFAULT NULL) - FK to `product_cross_references`
- `price` (DECIMAL(12,4), NOT NULL) - Customer-specific unit price
- `low_inventory_quantity` (INT UNSIGNED, DEFAULT NULL) - Low stock alert threshold
- `preferred_inventory_quantity` (INT UNSIGNED, DEFAULT NULL) - Preferred stock level
- `inventory_quantity_override` (INT, NOT NULL, DEFAULT 0) - Manual inventory override
- `reorder` (TINYINT UNSIGNED, DEFAULT 0) - Reorder flag
- `box_label` (VARCHAR(255), DEFAULT NULL) - Label for box packaging
- `commission_quota_id` (INT UNSIGNED, DEFAULT NULL) - FK to `x_rewards_commission_quotas`
- `purchase_obligation_id` (INT UNSIGNED, DEFAULT NULL) - FK to `x_rewards_purchase_obligations`
- `customer_product_name` (VARCHAR(255), DEFAULT NULL) - Custom product name override
- `customer_additional_price` (DECIMAL(12,4), DEFAULT NULL) - Additional price component
- `customer_labor_hours` (DECIMAL(5,2), DEFAULT NULL) - Labor hours per unit (for RPM)
- `customer_retail_price` (DECIMAL(12,4), DEFAULT NULL) - Customer retail price (for RPM)
- `customer_gross_profit_percent` (DECIMAL(7,4), DEFAULT NULL) - Target gross profit %
- `hidden` (TINYINT UNSIGNED, DEFAULT 0, INDEXED) - Hidden from UI
- `maintenance_service_penetration_rate` (TINYINT UNSIGNED, DEFAULT 1) - MSR flag for RPM
- `performance_product_penetration_rate` (TINYINT UNSIGNED, DEFAULT 0) - PPR flag for RPM
- `backfill_created_at` (DATETIME, DEFAULT NULL) - Backfill timestamp
- `activated_at` (DATETIME, DEFAULT NULL) - Activation timestamp
- `deactivated` (TINYINT UNSIGNED, DEFAULT 0) - Deactivation flag
- `hide_from_rpm` (TINYINT UNSIGNED, DEFAULT 0) - Hide from RPM reports
- `fortellis_cdk_drive_op_code_id` (BIGINT UNSIGNED, DEFAULT NULL) - External integration ID

**Dynamic Fields (EAV Pattern):**
- `reward_amount` — per-profile reward amounts stored in `x_rewards_customer_product_reward_amounts`
- `commission_percent` — per-sales-rep commission percentages stored in `x_rewards_customer_product_commission_percents`
- `future_commission_percent` — future commission rates in `x_rewards_future_commission_percents`
- `future_commission_effective_date` — effective dates for future rates in `x_rewards_future_commission_effective_dates`

**Important Notes:**
- Soft-deleted records have `deleted_by_user_id IS NOT NULL`
- JBD Commission Report filters: `deleted_by_user IS NULL`

---

### Table: x_rewards_customer_product_reward_amounts

**Purpose:** Stores the reward/rebate amount for each customer-product-profile combination.

**Columns:**
- `customer_product_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_customer_products`
- `profile_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_profiles`
- `reward_amount` (DECIMAL(12,4), NOT NULL) - Reward amount per unit

**Primary Key:** (`customer_product_id`, `profile_id`)

---

### Table: x_rewards_customer_product_commission_percents

**Purpose:** Stores per-sales-rep commission percentage for each customer-product combination.

**Columns:**
- `customer_product_id` (INT UNSIGNED, NOT NULL) - FK to `x_rewards_customer_products`
- `sales_rep_user_id` (INT UNSIGNED, NOT NULL) - FK to `synced_users`
- `commission_percent` (DECIMAL(7,4), DEFAULT NULL) - Commission percentage

**Primary Key:** (`customer_product_id`, `sales_rep_user_id`)

---

### Table: x_rewards_commission_quotas

**Purpose:** Tracks quota-based commission targets per customer. When a customer's purchase quantity meets the quota threshold, commission may change.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `deleted_at` (DATETIME, NOT NULL) - Soft delete
- `deleted_by_user_id` (INT, DEFAULT NULL) - Soft delete user
- `customer_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `customers`
- `label` (VARCHAR(255), NOT NULL) - Quota label/name
- `quantity_required` (INT UNSIGNED, NOT NULL) - Qty needed to meet quota
- `quantity_fulfilled` (INT, NOT NULL) - Qty fulfilled so far (can go negative during unwinding)
- `fulfilled_at` (DATETIME, DEFAULT NULL) - When quota was met

---

### Table: x_rewards_purchase_obligations

**Purpose:** Tracks customer purchase obligation agreements with required quantities and rental pricing.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `deleted_at` (DATETIME, NOT NULL) - Soft delete
- `deleted_by_user_id` (INT, DEFAULT NULL) - Soft delete user
- `customer_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `customers`
- `label` (VARCHAR(255), NOT NULL) - Obligation label
- `quantity_required` (INT UNSIGNED, NOT NULL) - Required purchase quantity
- `rental_price` (DECIMAL(12,4), NOT NULL) - Rental price per unit
- `agreement_date` (DATE, DEFAULT NULL) - Agreement date

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `customer_id`
- UNIQUE on (`customer_id`, `label`)

---

### Table: x_rewards_rpm_data

**Purpose:** Stores Retail Profit Management (RPM) data snapshots. Each row captures revenue and labor metrics for a single fulfillment-reward-product combination, used for RPM analysis reports.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `order_fulfillment_detail_id` (INT UNSIGNED, DEFAULT NULL, INDEXED) - FK to `orders_details_picked`
- `reward_id` (INT UNSIGNED, DEFAULT NULL, INDEXED) - FK to `x_rewards_rewards`
- `product_id` (INT UNSIGNED, NOT NULL) - FK to `products`
- `product_sku` (VARCHAR(100), DEFAULT NULL) - Product SKU snapshot
- `product_name` (VARCHAR(100), DEFAULT NULL) - Product name snapshot
- `parts_sold` (DECIMAL(12,4), DEFAULT NULL) - Parts quantity sold
- `gross_parts_revenue` (DECIMAL(12,4), DEFAULT NULL) - Gross revenue from parts
- `net_parts_revenue` (DECIMAL(12,4), DEFAULT NULL) - Net revenue (after rewards)
- `labor_hours` (DECIMAL(10,2), DEFAULT NULL) - Associated labor hours
- `gross_labor_revenue` (DECIMAL(12,4), DEFAULT NULL) - Gross labor revenue
- `net_labor_revenue` (DECIMAL(12,4), DEFAULT NULL) - Net labor revenue
- `customer_retail_price` (DECIMAL(12,4), DEFAULT NULL) - Customer retail price
- `maintenance_service_penetration_rate` (TINYINT, DEFAULT NULL) - MSR flag
- `performance_product_penetration_rate` (TINYINT, DEFAULT NULL) - PPR flag

**Relationships:**
- Has categories via `x_rewards_rpm_category_relations` link table

---

### Table: x_rewards_rpm_category_relations (Link Table)

**Purpose:** Links RPM data rows to product categories for category-based RPM analysis.

**Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `rpm_data_id` (INT UNSIGNED, NOT NULL, INDEXED) - FK to `x_rewards_rpm_data`
- `category_id` (INT, NOT NULL, INDEXED) - FK to `product_categories`

---

### Table: x_rewards_cron_status

**Purpose:** Key-value store tracking system state for reward processing automation, including the frozen commission date.

**Columns:**
- `id` (VARCHAR(255), PRIMARY KEY) - Status key name
- `value` (VARCHAR(255), DEFAULT NULL) - Status value

**Known Keys:**
- `frozen_commission_date` — Date up to which commissions are finalized/frozen

---

### Table: x_rewards_finalized_orders

**Purpose:** Tracks which orders have been finalized for reward/commission processing. Prevents re-processing.

**Key Columns:**
- `id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `created_at` (DATETIME, NOT NULL)
- `created_by_user_id` (INT, DEFAULT NULL)
- `modified_at` (DATETIME, NOT NULL)
- `modified_by_user_id` (INT, DEFAULT NULL)
- `last_printed_labels_at` (DATETIME, DEFAULT NULL) - When labels were last printed
- `order_id` (INT UNSIGNED, NOT NULL, UNIQUE) - FK to `orders`

---

### Table: orders_details_picked

**Purpose:** Order fulfillment detail records representing picked/packed line items. This is the actual table name for the `order_fulfillment_detail` entity. Links fulfillments to order details with picked quantities.

**Key Columns:**
- `id` (INT, PRIMARY KEY)
- `order_fulfillment_id` — FK to `order_fulfillments`
- `orders_details_id` — FK to `orders_details` (note: column name uses `orders_details_id`, not `order_detail_id`)
- `qty_picked` (DECIMAL) — Quantity picked in this fulfillment
- `created_at` (DATETIME)
- `user_id` (INT) — FK to `synced_users` (created by)
- `integration_update_status` (VARCHAR)
- `integration_update_retry_count` (INT)

**Computed Fields:**
- `cost_total` = complex formula based on inventory type:
  - For orders before 2019-11-01: `order_detail_cost * quantity_picked`
  - For FIFO inventory (type 1): `fifo_cost_total` (from stock_location_history)
  - For serial number inventory (type 2): `serial_number_cost_total`
  - Plus `dropship_cost_total`

**Reward-Related Lookup Fields:**
- `x_rewards_reward_total` = SUM of non-void reward amounts
- `x_rewards_paid_reward_total` = SUM of redeemed + non-void reward amounts
- `x_rewards_unpaid_reward_total` = SUM of unredeemed + non-void reward amounts

---

## SECTION 3: Table Relationships for Reports

### Revenue Performance Report

```
orders ──→ order_status (orders.status = order_status.id)
```

### JBD Commission Report

```
transaction_log ──→ orders (transaction_log.type_id = orders.id, WHERE type = 'order')
orders ──→ customers (orders.customer_id = customers.id)
orders ──→ customer_companies (orders.customer_company_id = customer_companies.id)
orders ──→ orders_details (orders_details.order_id = orders.id)
orders_details ──→ products (orders_details.real_product_id = products.id)
products ──→ product_categories (via colored_tags_relations link table)
customers ──→ x_rewards_profiles (x_rewards_profiles.customer_id = customers.id)
x_rewards_customer_products ──→ customers (x_rewards_customer_products.customer_id = customers.id)
x_rewards_customer_products ──→ products (x_rewards_customer_products.product_id = products.id)
x_rewards_customer_products ──→ x_rewards_customer_product_reward_amounts (customer_product_id)
customer_companies ──→ custom_fields (for custom_jbd_commission_rate)
```

### Plugin Rewards Commission Reports

```
commissions ──→ commission_periods (commissions.commission_period_id = commission_periods.id)
commission_periods ──→ synced_users (commission_periods.sales_rep_user_id = synced_users.id)
commission_periods ──→ commission_period_statuses (commission_periods.status_id)
commission_periods ──→ commission_payments (commission_payments.commission_period_id)
commissions ──→ orders (commissions.order_id = orders.id)
commissions ──→ orders_details (commissions.order_detail_id = orders_details.id)
commissions ──→ rma_details (commissions.rma_detail_id = rma_details.id)
commissions ──→ commission_categories (commissions.category_id = commission_categories.id)
commissions ──→ commission_custom_field_values (commission_id)
```

### Plugin Rewards Reward/Liability Reports

```
x_rewards_rewards ──→ orders_details_picked (order_fulfillment_detail_id)
x_rewards_rewards ──→ x_rewards_profiles (profile_id)
x_rewards_rewards ──→ x_rewards_redemption_periods (redemption_period_id)
x_rewards_profiles ──→ customers (customer_id)
x_rewards_profiles ──→ x_rewards_recipients (via x_rewards_recipient_profiles link)
x_rewards_redemption_periods ──→ x_rewards_recipients (recipient_id)
x_rewards_redemption_periods ──→ customers (customer_id)
x_rewards_redemption_periods ──→ x_rewards_adjustments (redemption_period_id)
x_rewards_redemption_periods ──→ x_rewards_payments (redemption_period_id)
x_rewards_adjustments ──→ x_rewards_redemption_periods (redemption_period_id)
x_rewards_payments ──→ x_rewards_redemption_periods (redemption_period_id)
```

### Plugin Rewards RPM Reports

```
x_rewards_rpm_data ──→ orders_details_picked (order_fulfillment_detail_id)
x_rewards_rpm_data ──→ x_rewards_rewards (reward_id)
x_rewards_rpm_data ──→ products (product_id)
x_rewards_rpm_data ──→ product_categories (via x_rewards_rpm_category_relations link)
```

### Plugin Rewards Customer Product Reports

```
x_rewards_customer_products ──→ customers (customer_id)
x_rewards_customer_products ──→ products (product_id)
x_rewards_customer_products ──→ x_rewards_customer_product_reward_amounts (customer_product_id)
x_rewards_customer_products ──→ x_rewards_customer_product_commission_percents (customer_product_id)
x_rewards_customer_products ──→ x_rewards_commission_quotas (commission_quota_id)
x_rewards_customer_products ──→ x_rewards_purchase_obligations (purchase_obligation_id)
x_rewards_customer_products ──→ product_categories (via x_rewards_customer_product_category_relations link)
```

---

## SECTION 4: Common Query Patterns

### Revenue Performance Report Queries

**Q1: Monthly order count and revenue by status within a date range**
```sql
SELECT
    YEAR(`invoice_date`) AS `year`,
    MONTH(`invoice_date`) AS `month`,
    os.`title` AS `status_label`,
    COUNT(*) AS `order_count`,
    COALESCE(SUM(`total`), 0) AS `revenue`
FROM `orders` o
INNER JOIN `order_status` os ON o.`status` = os.`id`
WHERE `invoice_date` >= '2025-01-01 00:00:00'
  AND `invoice_date` <= '2025-12-31 23:59:59'
  AND (`status` = 2 OR `status` = 3 OR `status` = 4)
GROUP BY `year`, `month`, `status_label`
ORDER BY `year`, `month`
```

**Q2: Revenue performance by creation date instead of invoice date**
```sql
SELECT
    YEAR(`time`) AS `year`,
    MONTH(`time`) AS `month`,
    COUNT(*) AS `order_count`,
    COALESCE(SUM(`total`), 0) AS `revenue`
FROM `orders`
WHERE `time` >= '2025-01-01 00:00:00'
  AND `time` <= '2025-06-30 23:59:59'
  AND (`status` = 2 OR `status` = 3)
GROUP BY `year`, `month`
ORDER BY `year`, `month`
```

### JBD Commission Report Queries

**Q3: Find paid orders for JBD commission calculation**
```sql
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
```

**Q4: Get order line items with customer product pricing for JBD commission**
```sql
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
    ON xrcp.`customer_id` = :customer_id
    AND xrcp.`product_id` = p.`id`
    AND xrcp.`deleted_by_user_id` IS NULL
WHERE od.`order_id` = :order_id
```

**Q5: Get reward amounts per profile for a customer product**
```sql
SELECT
    `profile_id`,
    `reward_amount`
FROM `x_rewards_customer_product_reward_amounts`
WHERE `customer_product_id` = :customer_product_id
```

**Q6: Get custom JBD commission rate for a company**
```sql
SELECT `value`
FROM `custom_fields`
WHERE `type` = 'customer_company'
  AND `type_id` = :company_id
  AND `name` = 'custom_jbd_commission_rate'
```

### Commission Report Queries

**Q7: Load commissions for a date range and optional sales rep**
```sql
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
WHERE c.`commission_date` >= :from_date
  AND c.`commission_date` <= :to_date
  AND cp.`sales_rep_user_id` = :sales_rep_user_id
ORDER BY c.`order_id`
```

**Q8: Sum commission percentages per order_detail for contribution calculation**
```sql
SELECT
    `order_detail_id`,
    SUM(`commission_percent`) AS `total_percent`
FROM `commissions`
WHERE `order_detail_id` IN (:order_detail_ids)
GROUP BY `order_detail_id`
```

### Liability Report Queries

**Q9: Unredeemed reward liability (opening balance)**
```sql
SELECT
    COALESCE(SUM(`amount`), 0) AS `opening_liability`
FROM `x_rewards_rewards`
WHERE `created_at` < :from_date
  AND `is_void` = 0
  AND `redemption_period_id` IS NULL
  AND `redemption_method` = 'serial_number'
```

**Q10: Reward liability by customer for a period**
```sql
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
WHERE xrr.`created_at` >= :from_date
  AND xrr.`created_at` <= :to_date
  AND xrr.`is_void` = 0
  AND xrr.`redemption_period_id` IS NULL
GROUP BY xrp.`customer_id`
ORDER BY cc.`name`
```

### Adjustment Report Queries

**Q11: Adjustment details by customer within a date range**
```sql
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
WHERE xa.`created_at` >= :from_date
  AND xa.`created_at` <= :to_date
  AND xa.`is_approved` = 1
ORDER BY cc.`name`
```

### Pay Sheet / 1099 Queries

**Q12: Paid pay sheets with recipient and payment details**
```sql
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
WHERE xrp.`cutoff_date` >= :from_date
  AND xrp.`cutoff_date` <= :to_date
GROUP BY xrp.`id`
ORDER BY cc.`name`, xrr.`last_name`
```

**Q13: 1099 totals by recipient for a tax year**
```sql
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
```

### RPM (Retail Profit Management) Queries

**Q14: RPM data aggregated by product**
```sql
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
WHERE xrr.`created_at` >= :from_date
  AND xrr.`created_at` <= :to_date
  AND xrr.`is_void` = 0
GROUP BY rpm.`product_id`
ORDER BY rpm.`product_sku`
```

### Customer Product Inventory Query

**Q15: Customer product inventory with stock levels**
```sql
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
```

### Customer Purchase Obligations Query

**Q16: Active purchase obligations by customer**
```sql
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
```

---

## SECTION 5: Business Logic Definitions

### Revenue Performance Report

| Term | Definition |
|------|-----------|
| **Revenue Performance** | Monthly trend of order counts and revenue totals, segmented by order status |
| **Search by Creation Date** | Optional toggle: when enabled, filters orders by `time` (creation timestamp) instead of `invoice_date` |
| **Order Enabled Statuses** | Configurable list of order status IDs that appear in the report's status filter (stored in `options` table as `order_enabled_statuses`) |
| **Time Bucketing** | Orders are grouped by Year-Month (format: 'Y-M' e.g. '2025-02') |

### JBD Commission Report

| Term | Definition |
|------|-----------|
| **JBD Commission** | A profit-sharing commission calculated as: `(company_rate / 100) × net_profit_per_unit × quantity` |
| **Net Price** | Customer product price minus the sum of all active profile reward amounts: `customer_product.price - SUM(profile_reward_amounts)` |
| **Net Profit** | Net price minus product cost: `net_price - cost` |
| **Cost** | Uses `product_kit_components_total_cost` if available, otherwise falls back to `order_detail.costs` |
| **Commission Rate** | Company-specific rate stored as custom field `custom_jbd_commission_rate` on `customer_companies` |
| **Paid Order** | An order where `order_balance = 0` (total minus sum of successful transactions equals zero) |
| **Frozen Commission Date** | Stored in `x_rewards_cron_status` table as key `frozen_commission_date`; commissions before this date are finalized |

### Plugin Rewards — Commission System

| Term | Definition |
|------|-----------|
| **Commission** | A record in `commissions` table representing earnings for a sales rep on a specific order or RMA line item |
| **Commission Period** | A payment cycle (`commission_periods`) grouping commissions by sales rep and cutoff date |
| **Commission Price** | The unit price after reward deductions, used as the base for commission calculation |
| **Commission Percent** | The percentage of net sales the rep earns as commission (stored in `commissions.commission_percent`) |
| **Unit Commission** | Commission amount per single unit sold: `commission_price × (commission_percent / 100)` |
| **Commission Amount** | Total commission: `net_sales × (commission_percent / 100)`, rounded to 2 decimals |
| **Total Sales** | Gross sales: `quantity × price` |
| **Net Sales** | After-reward sales: `quantity × commission_price` |
| **Total Rewards** | `total_sales - net_sales` |
| **Reward Amount Per Unit** | `total_rewards / quantity` (0 when quantity is 0) |
| **Paid Indicator** | "P" if order balance is exactly $0.0000 (to 4 decimal places), "U" otherwise |
| **SALE Category** | Commission category ID 1 — standard sale commission |
| **QUOTA Category** | Commission category ID 2 — quota-based commission (highlighted yellow in PDF) |
| **Contribution Percent** | In Sales by Reps report: `this_rep_commission_percent / SUM(all_reps_commission_percent)` — proportional share |

### Plugin Rewards — Reward/Liability System

| Term | Definition |
|------|-----------|
| **Reward** | A record in `x_rewards_rewards` representing a rebate/reward earned on a fulfilled order item |
| **Profile** | A customer reward program configuration (`x_rewards_profiles`) defining the redemption method and linked recipients |
| **Recipient** | An individual who receives reward payments (`x_rewards_recipients`) |
| **Redemption Period** | A payment cycle (`x_rewards_redemption_periods`) grouping rewards by recipient, customer, and cutoff date |
| **Redemption Method** | How rewards are triggered: `serial_number`, `manual`, `on_payment`, `on_redemption`, `on_first_of_month`, `on_15_of_month` |
| **Unredeemed Reward** | A reward where `redemption_period_id IS NULL` — represents outstanding liability |
| **Redeemed Reward** | A reward where `redemption_period_id IS NOT NULL` — has been included in a pay sheet |
| **Voided Reward** | A reward where `is_void = 1` — excluded from all calculations |
| **Liability** | Total unredeemed, non-void reward amounts — represents the company's financial obligation |
| **Adjustment** | A manual addition or deduction (`x_rewards_adjustments`) applied to a redemption period; only `is_approved = 1` adjustments count |
| **Pay Sheet** | A redemption period with associated payments — represents the payout document |
| **RPM (Retail Profit Management)** | Analysis of gross/net revenue, labor hours, and penetration rates per product |
| **MSR (Maintenance Service Penetration Rate)** | Boolean flag on customer products indicating maintenance service classification |
| **PPR (Performance Product Penetration Rate)** | Boolean flag on customer products indicating performance product classification |
| **Customer Product** | A customer-specific product configuration (`x_rewards_customer_products`) with custom pricing, reward amounts, and commission percents |
| **Purchase Obligation** | A contractual requirement for a customer to purchase a minimum quantity (`x_rewards_purchase_obligations`) |
| **Commission Quota** | A sales target that changes commission calculation once met (`x_rewards_commission_quotas`) |

---

## SECTION 6: SQL Conventions Specific to These Reports

1. **Reward void filtering**: Always include `is_void = 0` when querying `x_rewards_rewards`
2. **Unredeemed filter**: `redemption_period_id IS NULL` for liability/unredeemed rewards
3. **Redeemed filter**: `redemption_period_id IS NOT NULL` for paid/redeemed rewards
4. **Adjustment approval**: Always include `is_approved = 1` when summing adjustments
5. **Payment void filtering**: Always include `void = 0` when querying `x_rewards_payments`
6. **Soft delete on customer products**: Filter `deleted_by_user_id IS NULL` for active records
7. **Transaction log segmentation**: Always include `type = 'order'` when querying order transactions
8. **Decimal precision**: Commission amounts use DECIMAL(12,4); display rounded to 2 decimals
9. **Commission percent precision**: Uses DECIMAL(7,4) — supports up to 999.9999%
10. **Paid status check**: Use `sprintf("%.4f", abs($balance)) === '0.0000'` logic — order is paid when balance rounds to 0 at 4 decimal places
11. **Date range inclusivity**: All date filters use `>=` and `<=` (inclusive on both ends)
12. **Revenue performance date field**: Default is `invoice_date`; user can toggle to `time` (creation date)
13. **Reward serial_number column**: Despite being VARCHAR(255), it is UNIQUE — each reward has a distinct serial number
14. **RPM data denormalization**: `x_rewards_rpm_data` stores snapshot values (product_sku, product_name) rather than joining to products table at query time

---

## SECTION 7: Calculation Formulas

### JBD Commission Calculation

```
For each order line item:
  1. customer_product = lookup x_rewards_customer_products WHERE customer_id AND product_id AND deleted_by_user_id IS NULL
  2. net_price = customer_product.price - SUM(x_rewards_customer_product_reward_amounts.reward_amount WHERE customer_product_id)
  3. cost = customer_product.product_kit_components_total_cost ?? order_detail.costs
  4. net_profit = net_price - cost
  5. rate = custom_fields.value WHERE type='customer_company' AND name='custom_jbd_commission_rate'
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
  6. paid = abs(order_balance) formatted to 4 decimals === '0.0000'
```

### Sales by Reps Contribution Calculation

```
For each commission record:
  1. all_reps_sum_percent = SUM(commission_percent) across ALL reps for same order_detail_id
  2. contribution_percent = this_rep_commission_percent / all_reps_sum_percent
  3. rep_gross_sales_contribution = total_sales × contribution_percent
  4. rep_net_sales_contribution = net_sales × contribution_percent
```

### Liability Balance Calculation

```
For a redemption period:
  1. rewards_total = SUM(x_rewards_rewards.amount WHERE redemption_period_id AND is_void = 0)
  2. approved_adjustments_total = SUM(x_rewards_adjustments.amount WHERE redemption_period_id AND is_approved = 1)
  3. payments_total = SUM(x_rewards_payments.amount WHERE redemption_period_id AND void = 0)
  4. total_owed = rewards_total + approved_adjustments_total
  5. balance = total_owed - payments_total
```

---

## SECTION 8: Schema DDL for Report-Specific Tables

### commissions

```sql
CREATE TABLE `commissions` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `commission_period_id` bigint unsigned DEFAULT NULL,
    `commission_date` date NOT NULL,
    `order_id` bigint unsigned DEFAULT NULL,
    `order_detail_id` bigint unsigned DEFAULT NULL,
    `rma_detail_id` bigint unsigned DEFAULT NULL,
    `quantity` int DEFAULT NULL,
    `commission_price` decimal(12,4) DEFAULT NULL,
    `commission_percent` decimal(7,4) DEFAULT NULL,
    `unit_commission` decimal(12,4) DEFAULT NULL,
    `amount` decimal(12,4) NOT NULL,
    `category_id` int unsigned NOT NULL,
    `note` varchar(255) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_commission_period_id` (`commission_period_id`),
    KEY `idx_order_id` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### commission_periods

```sql
CREATE TABLE `commission_periods` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `sales_rep_user_id` int unsigned NOT NULL,
    `cutoff_date` date NOT NULL,
    `status_id` int unsigned NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_unique` (`sales_rep_user_id`, `cutoff_date`),
    KEY `idx_status` (`status_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_rewards

```sql
CREATE TABLE `x_rewards_rewards` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `order_fulfillment_detail_id` int unsigned NOT NULL,
    `quantity_index` int unsigned NOT NULL,
    `pack_index` int unsigned NOT NULL,
    `serial_number` varchar(255) NOT NULL,
    `profile_id` int unsigned NOT NULL,
    `amount` decimal(12,4) NOT NULL,
    `redeemed_at` datetime DEFAULT NULL,
    `redemption_period_id` int unsigned DEFAULT NULL,
    `is_void` tinyint NOT NULL,
    `is_imported_label` tinyint NOT NULL,
    `import_order_id` int unsigned DEFAULT NULL,
    `import_order_date` date DEFAULT NULL,
    `import_item_id` int unsigned DEFAULT NULL,
    `import_sku` varchar(255) DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_serial_number` (`serial_number`),
    KEY `idx_order_fulfillment_detail_id` (`order_fulfillment_detail_id`),
    KEY `idx_profile_id` (`profile_id`),
    KEY `idx_redemption_period_id` (`redemption_period_id`),
    KEY `idx_is_void` (`is_void`),
    KEY `idx_redeemed_at` (`redeemed_at`),
    KEY `idx_redeemed_at_is_void` (`redeemed_at`, `is_void`),
    KEY `idx_amount` (`amount`),
    KEY `idx_quantity_index` (`quantity_index`),
    KEY `idx_import_sku` (`import_sku`),
    KEY `idx_import_order_id` (`import_order_id`),
    KEY `idx_import_item_id` (`import_item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_profiles

```sql
CREATE TABLE `x_rewards_profiles` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `customer_id` int unsigned NOT NULL,
    `title` varchar(255) NOT NULL,
    `redemption_method` varchar(255) NOT NULL COMMENT 'serial_number, manual, on_payment, on_redemption, on_first_of_month, on_15_of_month',
    `status` tinyint unsigned NOT NULL,
    `hide_on_rpm` tinyint unsigned NOT NULL,
    `hide_on_executive_portal` tinyint unsigned NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_customer_id` (`customer_id`),
    KEY `idx_redemption_method` (`redemption_method`),
    KEY `idx_title` (`title`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_customer_products

```sql
CREATE TABLE `x_rewards_customer_products` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `deleted_at` datetime NOT NULL,
    `deleted_by_user_id` int DEFAULT NULL,
    `customer_id` int unsigned NOT NULL,
    `product_id` int unsigned NOT NULL,
    `product_cross_reference_id` int unsigned DEFAULT NULL,
    `price` decimal(12,4) NOT NULL,
    `low_inventory_quantity` int unsigned DEFAULT NULL,
    `preferred_inventory_quantity` int unsigned DEFAULT NULL,
    `inventory_quantity_override` int NOT NULL DEFAULT '0',
    `reorder` tinyint unsigned DEFAULT '0',
    `box_label` varchar(255) DEFAULT NULL,
    `commission_quota_id` int unsigned DEFAULT NULL,
    `purchase_obligation_id` int unsigned DEFAULT NULL,
    `customer_product_name` varchar(255) DEFAULT NULL,
    `customer_additional_price` decimal(12,4) DEFAULT NULL,
    `customer_labor_hours` decimal(5,2) DEFAULT NULL,
    `customer_retail_price` decimal(12,4) DEFAULT NULL,
    `customer_gross_profit_percent` decimal(7,4) DEFAULT NULL,
    `hidden` tinyint unsigned DEFAULT '0',
    `maintenance_service_penetration_rate` tinyint unsigned DEFAULT '1',
    `performance_product_penetration_rate` tinyint unsigned DEFAULT '0',
    `backfill_created_at` datetime DEFAULT NULL,
    `activated_at` datetime DEFAULT NULL,
    `deactivated` tinyint unsigned DEFAULT '0',
    `hide_from_rpm` tinyint unsigned DEFAULT '0',
    `fortellis_cdk_drive_op_code_id` bigint unsigned DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `customer_id` (`customer_id`),
    KEY `product_id` (`product_id`),
    KEY `idx_hidden` (`hidden`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_redemption_periods

```sql
CREATE TABLE `x_rewards_redemption_periods` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `recipient_id` int unsigned NOT NULL,
    `customer_id` int unsigned NOT NULL,
    `cutoff_date` date NOT NULL,
    `balance` decimal(12,4) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_unique` (`recipient_id`, `customer_id`, `cutoff_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_adjustments

```sql
CREATE TABLE `x_rewards_adjustments` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `redemption_period_id` int unsigned NOT NULL,
    `amount` decimal(12,4) NOT NULL,
    `note` varchar(255) NOT NULL,
    `is_approved` tinyint NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_redemption_period_id` (`redemption_period_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_payments

```sql
CREATE TABLE `x_rewards_payments` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `redemption_period_id` int unsigned NOT NULL,
    `amount` decimal(12,4) NOT NULL,
    `payment_type` varchar(255) NOT NULL,
    `payment_account_number` varchar(255) NOT NULL,
    `note` varchar(255) NOT NULL,
    `check_number` int unsigned DEFAULT NULL,
    `void` tinyint unsigned DEFAULT '0',
    PRIMARY KEY (`id`),
    KEY `idx_redemption_period_id` (`redemption_period_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_customer_product_reward_amounts

```sql
CREATE TABLE `x_rewards_customer_product_reward_amounts` (
    `customer_product_id` int unsigned NOT NULL,
    `profile_id` int unsigned NOT NULL,
    `reward_amount` decimal(12,4) NOT NULL,
    PRIMARY KEY (`customer_product_id`, `profile_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_customer_product_commission_percents

```sql
CREATE TABLE `x_rewards_customer_product_commission_percents` (
    `customer_product_id` int unsigned NOT NULL,
    `sales_rep_user_id` int unsigned NOT NULL,
    `commission_percent` decimal(7,4) DEFAULT NULL,
    PRIMARY KEY (`customer_product_id`, `sales_rep_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### x_rewards_rpm_data

```sql
CREATE TABLE `x_rewards_rpm_data` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `created_at` datetime NOT NULL,
    `created_by_user_id` int DEFAULT NULL,
    `modified_at` datetime NOT NULL,
    `modified_by_user_id` int DEFAULT NULL,
    `order_fulfillment_detail_id` int unsigned DEFAULT NULL,
    `reward_id` int unsigned DEFAULT NULL,
    `product_id` int unsigned NOT NULL,
    `product_sku` varchar(100) DEFAULT NULL,
    `product_name` varchar(100) DEFAULT NULL,
    `parts_sold` decimal(12,4) DEFAULT NULL,
    `gross_parts_revenue` decimal(12,4) DEFAULT NULL,
    `net_parts_revenue` decimal(12,4) DEFAULT NULL,
    `labor_hours` decimal(10,2) DEFAULT NULL,
    `gross_labor_revenue` decimal(12,4) DEFAULT NULL,
    `net_labor_revenue` decimal(12,4) DEFAULT NULL,
    `customer_retail_price` decimal(12,4) DEFAULT NULL,
    `maintenance_service_penetration_rate` tinyint DEFAULT NULL,
    `performance_product_penetration_rate` tinyint DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_order_fulfillment_detail_id` (`order_fulfillment_detail_id`),
    KEY `idx_reward_id` (`reward_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

---

## SECTION 9: Access Patterns by Report

### Revenue Performance Report

| Filter | Column | Operator |
|--------|--------|----------|
| Date Range | `invoice_date` or `time` | `>= AND <=` |
| Order Status | `status` | Multiple OR equality checks |

**Aggregation:** COUNT and SUM grouped by Year-Month and status label

### JBD Commission Report

| Filter | Column | Operator |
|--------|--------|----------|
| Payment Date Range | `transaction_log.time` | `>= AND <=` |
| Paid Orders Only | `order.balance` | `= 0` |
| Exclude Abandoned/Cancelled | `order.status` | `!= 1 AND != 10` |
| Sales Rep (optional) | `order.sales_rep` or additional_sales_rep_users | `=` or `REFERENCES()` |
| Product Categories (optional) | product categories link | `REFERENCES()` |
| Active Customer Products | `deleted_by_user_id` | `IS NULL` |
| Active Profiles | `x_rewards_profiles.status` | `= 1` |

### Commission Report

| Filter | Column | Operator |
|--------|--------|----------|
| Date Range | `commissions.commission_date` | `>= AND <=` |
| Sales Rep (optional) | `commission_periods.sales_rep_user_id` | `=` |

**Aggregation:** SUM of total_sales, total_rewards, net_sales, commission; grouped by company

### Liability Report

| Filter | Column | Operator |
|--------|--------|----------|
| Date Range | `x_rewards_rewards.created_at` | `>= AND <=` |
| Non-voided | `x_rewards_rewards.is_void` | `= 0` |
| Unredeemed | `x_rewards_rewards.redemption_period_id` | `IS NULL` |
| Redemption Method | `x_rewards_profiles.redemption_method` | `= 'serial_number'` or `!= 'serial_number'` |

**Aggregation:** SUM of amount, COUNT of id; grouped by customer

### Adjustment Reports

| Filter | Column | Operator |
|--------|--------|----------|
| Date Range | `x_rewards_adjustments.created_at` | `>= AND <=` |
| Approved Only | `x_rewards_adjustments.is_approved` | `= 1` |

**Aggregation:** SUM of amount; grouped by customer or redemption period

### Pay Sheet / 1099 Reports

| Filter | Column | Operator |
|--------|--------|----------|
| Date Range | `x_rewards_redemption_periods.cutoff_date` | `>= AND <=` |
| Non-voided Payments | `x_rewards_payments.void` | `= 0` |

**Aggregation:** SUM of payment amounts; grouped by recipient

### RPM Reports

| Filter | Column | Operator |
|--------|--------|----------|
| Date Range | `x_rewards_rewards.created_at` | `>= AND <=` |
| Non-voided | `x_rewards_rewards.is_void` | `= 0` |
| Hide from RPM | `x_rewards_profiles.hide_on_rpm` | `= 0` |
| Product Categories (optional) | `x_rewards_rpm_category_relations` | JOIN filter |

**Aggregation:** SUM of parts_sold, gross/net revenue, labor_hours; grouped by product or category

### Customer Product Inventory

| Filter | Column | Operator |
|--------|--------|----------|
| Active Products | `deleted_by_user_id` | `IS NULL` |
| Not Deactivated | `deactivated` | `= 0` |
| Customer (optional) | `customer_id` | `=` |

### Purchase Obligations

| Filter | Column | Operator |
|--------|--------|----------|
| Active Obligations | `deleted_by_user_id` | `IS NULL` |
| Customer (optional) | `customer_id` | `=` |

---

## SECTION 10: Permissions Reference

| Permission Key | Scope | Used By |
|----------------|-------|---------|
| `report/sales` | View revenue performance report | Revenue Performance |
| `x_rewards/commission_report` | View own commission data | Commission Report, JBD Commission |
| `x_rewards/commission_report/all` | View all reps' commission data | Commission Report, JBD Commission |
| `x_rewards/sales_by_reps_commission_report` | View own sales by reps data | Sales by Reps Commission |
| `x_rewards/sales_by_reps_commission_report/all` | View any rep's sales by reps data | Sales by Reps Commission |

---

## SECTION 11: Complete Table Cross-Reference

Summary of all database tables involved in these reports:

| Table Name | Entity Type | Used By Reports |
|------------|-------------|-----------------|
| `orders` | `order` | Revenue Performance, JBD Commission, Commission (via lookup) |
| `order_status` | `order_status` | Revenue Performance |
| `orders_details` | `order_detail` | JBD Commission, Commission (via lookup) |
| `orders_details_picked` | `order_fulfillment_detail` | Reward reports, RPM |
| `order_fulfillments` | `order_fulfillment` | Reward reports (via fulfillment details) |
| `transaction_log` | `order_transaction` | JBD Commission |
| `customers` | `customer` | JBD Commission, Reward reports, Commission (via lookup) |
| `customer_companies` | `customer_company` | JBD Commission, Commission (via lookup) |
| `products` | `product` | JBD Commission, RPM, Inventory |
| `product_categories` | `product_category` | JBD Commission, RPM |
| `synced_users` | `user` | Commission (sales reps) |
| `commissions` | `commission` | Commission, Sales by Reps Commission |
| `commission_periods` | `commission_period` | Commission, Sales by Reps Commission |
| `commission_payments` | `commission_payment` | Commission Period balance |
| `commission_period_statuses` | `commission_period_status` | Commission Period status |
| `commission_categories` | `commission_category` | Commission (SALE/QUOTA) |
| `commission_custom_field_values` | (dynamic fields) | Commission custom fields |
| `x_rewards_rewards` | `x_rewards_reward` | Reward, Liability, Label Sales, RPM, Net Profit |
| `x_rewards_profiles` | `x_rewards_profile` | All reward reports |
| `x_rewards_recipients` | `x_rewards_recipient` | Pay Sheets, 1099, Liability |
| `x_rewards_recipient_profiles` | (link table) | Profile-Recipient mapping |
| `x_rewards_redemption_periods` | `x_rewards_redemption_period` | Pay Sheets, Liability, Adjustments, 1099 |
| `x_rewards_adjustments` | `x_rewards_adjustment` | Adjustment Detail, Adjustment Totals |
| `x_rewards_payments` | `x_rewards_payment` | Pay Sheets, 1099 |
| `x_rewards_customer_products` | `x_rewards_customer_product` | JBD Commission, Inventory, Purchase Obligations |
| `x_rewards_customer_product_reward_amounts` | (dynamic fields) | JBD Commission, Net Profit |
| `x_rewards_customer_product_commission_percents` | (dynamic fields) | Commission configuration |
| `x_rewards_commission_quotas` | `x_rewards_commission_quota` | Quota tracking |
| `x_rewards_purchase_obligations` | `x_rewards_purchase_obligation` | Purchase Obligations report |
| `x_rewards_rpm_data` | `x_rewards_rpm_data` | RPM reports |
| `x_rewards_rpm_category_relations` | (link table) | RPM category filtering |
| `x_rewards_cron_status` | (key-value) | Frozen commission date tracking |
| `x_rewards_finalized_orders` | (tracking) | Order finalization tracking |
| `custom_fields` | (EAV) | JBD Commission (company commission rate) |
