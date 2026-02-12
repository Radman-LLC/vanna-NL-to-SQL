# ADR Database Information Request

## Purpose
This document requests structured information about your ADR database to customize the Vanna training data, domain configuration, and schema documentation for optimal SQL generation accuracy.

---

## Instructions for ADR Coding Agent

Please analyze the ADR database and provide information in the following format. Be as comprehensive as possible - the more details you provide, the better the SQL agent will perform.

---

## SECTION 1: Database Metadata

**Format: Simple key-value pairs**

```
Database Type: [MySQL / PostgreSQL / SQL Server / etc.]
Database Version: [e.g., MySQL 8.0.35]
Database Name: [e.g., adr_production]
Character Set: [e.g., utf8mb4]
Timezone: [e.g., UTC, America/New_York]
Total Tables: [number]
Approximate Database Size: [e.g., 50GB]
```

---

## SECTION 2: Core Tables (Top 10-15 Most Important)

**Format: For each table, provide:**

```markdown
### Table: [table_name]

**Purpose:** [1-2 sentence description of what this table stores]

**Row Count:** [approximate number, e.g., ~500,000]

**Key Columns:**
- `column_name` (TYPE, CONSTRAINTS) - Description
- `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT) - Unique identifier
- `created_at` (DATETIME, NOT NULL, DEFAULT CURRENT_TIMESTAMP) - Record creation time
- [etc.]

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `user_id`, `created_at`
- UNIQUE INDEX on `email`
- [etc.]

**Partitioning:** [If applicable, e.g., "Partitioned by MONTH on created_at"]

**Important Notes:**
- [Any special handling, gotchas, or important details]
- [e.g., "Soft deletes use status='deleted' instead of DELETE"]
- [e.g., "All monetary values are in USD cents (integer)"]
```

**Example:**

```markdown
### Table: adverse_events

**Purpose:** Stores all reported adverse drug reaction events submitted by healthcare providers

**Row Count:** ~2,500,000

**Key Columns:**
- `event_id` (BIGINT, PRIMARY KEY) - Unique event identifier
- `patient_id` (BIGINT, FOREIGN KEY) - References patients table
- `drug_id` (INT, FOREIGN KEY) - References drugs table
- `event_date` (DATE, NOT NULL) - When the adverse event occurred
- `severity` (ENUM('mild','moderate','severe','life_threatening'), NOT NULL) - Event severity classification
- `status` (ENUM('reported','under_review','validated','closed'), DEFAULT 'reported') - Current status
- `description` (TEXT) - Detailed event description
- `reporter_id` (BIGINT, FOREIGN KEY) - Healthcare provider who reported
- `is_test` (BOOLEAN, DEFAULT FALSE) - Flag for test/training data
- `created_at` (DATETIME, NOT NULL) - Record creation timestamp
- `updated_at` (DATETIME) - Last modification timestamp

**Indexes:**
- PRIMARY KEY on `event_id`
- INDEX on `patient_id`, `drug_id`, `event_date`
- INDEX on `status`, `severity`
- FULLTEXT INDEX on `description` (if MySQL 5.7+)

**Partitioning:** Partitioned by MONTH on `event_date` (36-month retention)

**Important Notes:**
- Test data is flagged with `is_test = TRUE` and should always be filtered out
- Severity is classified according to FDA MedWatch categories
- Events in 'under_review' status may have incomplete data
- Patient info is de-identified in this table (use patient_id to join for demographics)
```

---

## SECTION 3: Table Relationships

**Format: List all foreign key relationships**

```markdown
### Foreign Key Relationships

1. **adverse_events → patients**
   - `adverse_events.patient_id` → `patients.patient_id`
   - Relationship: Many adverse events per patient
   - Join Pattern: `LEFT JOIN patients p ON ae.patient_id = p.patient_id`

2. **adverse_events → drugs**
   - `adverse_events.drug_id` → `drugs.drug_id`
   - Relationship: Many events per drug
   - Join Pattern: `LEFT JOIN drugs d ON ae.drug_id = d.drug_id`

[Continue for all major relationships...]
```

---

## SECTION 4: Common Query Patterns (10-20 Examples)

**Format: Provide real queries that are frequently run**

```python
# Pattern 1: [Category - e.g., "Event Counts by Severity"]
{
    "question": "How many severe adverse events were reported last month?",
    "sql": """
        SELECT COUNT(*) as severe_events
        FROM adverse_events
        WHERE severity = 'severe'
          AND event_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
          AND is_test = FALSE
          AND status != 'closed'
    """,
    "category": "aggregation",
    "notes": "Always filter test data and include status check"
},

# Pattern 2: [Category - e.g., "Drug Safety Analysis"]
{
    "question": "Which drugs have the most adverse events this year?",
    "sql": """
        SELECT
            d.drug_name,
            d.generic_name,
            COUNT(ae.event_id) as event_count,
            SUM(CASE WHEN ae.severity IN ('severe', 'life_threatening') THEN 1 ELSE 0 END) as serious_events
        FROM drugs d
        LEFT JOIN adverse_events ae ON d.drug_id = ae.drug_id
        WHERE YEAR(ae.event_date) = YEAR(CURDATE())
          AND ae.is_test = FALSE
        GROUP BY d.drug_id, d.drug_name, d.generic_name
        ORDER BY event_count DESC
        LIMIT 20
    """,
    "category": "join_aggregation",
    "notes": "Use LEFT JOIN to include drugs with zero events if needed"
},

# Add 10-20 more examples covering:
# - Time-based queries
# - Patient demographics
# - Reporter analysis
# - Trend analysis
# - Status workflows
# - Geographic distribution
# - etc.
```

---

## SECTION 5: Business Logic Definitions

**Format: Define domain-specific terms**

```python
BUSINESS_DEFINITIONS = {
    "serious_event": "An adverse event with severity 'severe' or 'life_threatening', or resulting in hospitalization",

    "active_event": "An adverse event with status 'reported' or 'under_review' (not closed or archived)",

    "signal_detection": "Pattern of >=5 similar adverse events for same drug within 30-day window",

    "time_to_resolution": "Days between event_date and when status changed to 'closed'",

    # Add 5-10 more key business concepts
}
```

---

## SECTION 6: SQL Conventions & Best Practices

**Format: List patterns that should always be followed**

```python
SQL_PATTERNS = [
    # Data Filtering
    "Always filter out test data: WHERE is_test = FALSE",
    "Exclude closed events by default: AND status != 'closed'",
    "Use date ranges with >= and < (not YEAR/MONTH functions): WHERE event_date >= '2024-01-01' AND event_date < '2024-02-01'",

    # JOIN Patterns
    "Always use table aliases: adverse_events ae, drugs d, patients p",
    "Use LEFT JOIN for optional relationships",
    "Use INNER JOIN only when relationship is required",

    # Performance
    "Include event_date in WHERE clause for partitioned queries",
    "Limit large result sets: LIMIT 1000 for exploratory queries",
    "Use EXPLAIN for complex multi-join queries",

    # Data Quality
    "Check for NULL in reporter_id (some events auto-generated)",
    "Patient demographics may be incomplete - use COALESCE",
    "Drug names can have variations - use LIKE with wildcards carefully",

    # Add 10-15 more patterns specific to ADR database
]
```

---

## SECTION 7: Performance Characteristics

**Format: List performance tips**

```python
PERFORMANCE_HINTS = [
    "adverse_events table is partitioned by MONTH on event_date",
    "Queries without date filters on adverse_events scan all partitions (slow)",
    "Optimal date range: 1-6 months (queries >12 months may timeout)",
    "event_id, patient_id, drug_id are indexed - use in WHERE clauses",
    "FULLTEXT search on description is available but slow on >1M rows",
    "Consider using summary tables (event_summaries) for large date ranges",

    # Add database-specific performance notes
]
```

---

## SECTION 8: Data Quality Notes

**Format: List gotchas and edge cases**

```python
DATA_QUALITY_NOTES = [
    "Events before 2020-01-01 may have incomplete patient demographics",
    "Some drug_id values are NULL for 'unknown medication' cases",
    "Severity can change over time - use latest value from event_updates table",
    "Description field may contain PHI - never expose in public queries",
    "Test events have is_test=TRUE but also identifiable by reporter_id=-1",
    "Events from automated systems have reporter_id=0",
    "Time zone conversions: created_at is UTC, event_date is in reporter's local time",

    # Add 5-10 more data quality issues
]
```

---

## SECTION 9: Enum/Categorical Values

**Format: List all enum values and their meanings**

```python
ENUM_VALUES = {
    "severity": {
        "mild": "Minor symptoms, no medical intervention required",
        "moderate": "Symptoms requiring medical attention",
        "severe": "Significant symptoms, may require hospitalization",
        "life_threatening": "Immediate risk to patient life"
    },

    "status": {
        "reported": "Initial submission, pending review",
        "under_review": "Being analyzed by safety team",
        "validated": "Confirmed as legitimate ADR",
        "closed": "Case closed, no further action needed"
    },

    # Add all other enums from the database
}
```

---

## SECTION 10: Sample Schema Export (SQL DDL)

**Format: Provide CREATE TABLE statements for top 5-10 tables**

```sql
-- This helps understand exact types, constraints, and relationships

CREATE TABLE adverse_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    patient_id BIGINT NOT NULL,
    drug_id INT,
    event_date DATE NOT NULL,
    severity ENUM('mild','moderate','severe','life_threatening') NOT NULL,
    status ENUM('reported','under_review','validated','closed') DEFAULT 'reported',
    description TEXT,
    reporter_id BIGINT NOT NULL,
    is_test BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,

    KEY idx_patient_drug_date (patient_id, drug_id, event_date),
    KEY idx_status_severity (status, severity),

    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (drug_id) REFERENCES drugs(drug_id),
    FOREIGN KEY (reporter_id) REFERENCES reporters(reporter_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  PARTITION BY RANGE (YEAR(event_date) * 100 + MONTH(event_date)) (
    PARTITION p202401 VALUES LESS THAN (202402),
    PARTITION p202402 VALUES LESS THAN (202403),
    -- etc.
  );

-- [Add DDL for other core tables]
```

---

## SECTION 11: Access Patterns & User Groups

**Format: Describe who queries what**

```markdown
### User Groups

1. **Safety Analysts** (group: `safety_team`)
   - Can view all events including sensitive descriptions
   - Frequently run trend analysis and signal detection queries
   - Need access to patient demographics

2. **Researchers** (group: `research`)
   - Can view de-identified data only
   - Run statistical analyses over large date ranges
   - No access to patient names or contact info

3. **Executives** (group: `executive`)
   - View only summary statistics and dashboards
   - Need high-level metrics (total events, trends, etc.)
   - No access to individual event details

[Add all relevant user groups and their typical query patterns]
```

---

## DELIVERY FORMAT

Please provide all sections above in a single structured document with:

1. **Completeness**: Cover at least top 10-15 tables
2. **Real Examples**: Use actual table/column names from ADR database
3. **Tested Queries**: Ensure SQL examples are valid and tested
4. **Context**: Explain WHY patterns exist, not just WHAT they are
5. **Edge Cases**: Document known issues, limitations, workarounds

---

## Questions to Consider

When gathering this information, think about:

- What are the most frequent questions users ask?
- What SQL patterns cause the most issues/errors?
- What business logic is hardest for new users to understand?
- What performance pitfalls should the AI avoid?
- What data quality issues lead to incorrect results?

---

## Next Steps

Once you provide this information, I will:

1. ✅ Update `training/sample_query_library.py` with ADR-specific queries
2. ✅ Fill `training/schema_documentation_template.md` with ADR schema
3. ✅ Customize `domain_config.py` with ADR business logic
4. ✅ Re-seed the agent memory with ADR-specific training data
5. ✅ Test and validate SQL generation quality

**This will transform the generic Vanna agent into an ADR database expert!**
