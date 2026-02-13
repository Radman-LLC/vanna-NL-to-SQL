# Testing Guide for Vanna Optimization Features

This guide walks you through testing all the new optimization features we implemented.

## ✅ Pre-Test Checklist

- [x] ChromaDB installed
- [x] All imports verified
- [x] Memory seeded with 23 training items
- [ ] .env file configured with ANTHROPIC_API_KEY and MYSQL_HOST
- [ ] Server ready to start

---

## Test Plan

### Test 1: Persistent Memory Verification

**What we're testing:** Memory persists across server restarts

**Steps:**
1. Note the current memory count (23 items)
2. Start the server, ask a question
3. Stop the server
4. Restart the server
5. Verify memory still has same count

**Expected:** Memory directory `./vanna_memory/` exists and persists data

---

### Test 2: Memory-Based Context Enhancement

**What we're testing:** Similar queries automatically injected into LLM context

**Steps:**
1. Start the server
2. Ask: "What was our revenue last month?"
3. Check the generated SQL
4. Look for similarity to training pair:
   ```sql
   SELECT SUM(amount) as revenue
   FROM transactions
   WHERE transaction_date >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m-01')
   ```

**Expected:**
- SQL should use similar patterns (DATE_FORMAT, DATE_SUB, INTERVAL)
- Query should filter by is_test = FALSE (from training)
- Should reference similar table/column names

**How it works:**
- DefaultLlmContextEnhancer searches memory for "revenue last month"
- Finds relevant text memories from ChromaDB
- Injects matching context into system prompt
- LLM sees proven pattern and generates similar SQL

---

### Test 3: Domain-Specific System Prompt

**What we're testing:** Domain knowledge affects SQL generation

**Current domain_config.py is mostly empty, so:**

**Steps:**
1. Ask: "Show me churned users"
2. Note the SQL generated (baseline)
3. Stop server
4. Edit `domain_config.py` and add:
   ```python
   BUSINESS_DEFINITIONS = {
       "churn": "A user is churned if they have no transactions in the last 90 days"
   }
   SQL_PATTERNS = [
       "Always filter out test data: WHERE is_test = FALSE"
   ]
   ```
5. Restart server
6. Ask: "Show me churned users" again
7. Compare new SQL

**Expected:**
- New SQL should reference the 90-day definition
- Should include is_test = FALSE filter
- Should be more accurate to business definition

---

### Test 4: Agent Memory Tools

**What we're testing:** Users can save queries during chat

**Steps:**
1. Start server
2. Log in as admin (email: admin@example.com)
3. Ask a question and get SQL
4. In chat, say: "save this query"
5. The SaveQuestionToolArgsTool should be called
6. Check `./vanna_memory/` for new entry
7. Ask similar question
8. New query should benefit from saved pattern

**Expected:**
- Admin can use memory tools
- Non-admin users can search but not save
- Saved patterns appear in future similar queries

---

### Test 5: Query Logging

**What we're testing:** All queries logged to file

**Steps:**
1. Start server
2. Ask 3-5 different questions
3. Check file: `vanna_query_log.jsonl`
4. Each line should be valid JSON with:
   - timestamp
   - user_id
   - question
   - SQL
   - success/failure

**Analyze logs:**
```bash
python -c "from vanna.core.lifecycle.query_logging_hook import analyze_query_log; analyze_query_log()"
```

**Expected:**
- One JSON line per query
- Success/failure tracked
- User info captured
- Errors logged

---

### Test 6: Training Data Categories

**What we're testing:** Training pairs cover diverse query types

**Steps:**
Ask questions from each category and check SQL quality:

1. **Schema exploration:** "What tables are in this database?"
2. **Simple lookup:** "Show me the first 10 users"
3. **Aggregation:** "What is our total revenue?"
4. **Time-based:** "What were sales yesterday?"
5. **JOIN:** "Show top 10 customers by spend"
6. **Business metric:** "How many active customers do we have?"

**Expected:**
- Each query type generates appropriate SQL
- Patterns match training examples
- No hallucinated tables/columns (if using mock/template data)

---

## Quick Start Server Test

**Option A: With MySQL Database**

If you have MySQL configured in `.env`:

```bash
# Test connection first
python test_mysql_connection.py

# If that works, start server
python run_web_ui.py
```

Visit http://localhost:8000 and start testing!

**Option B: Without MySQL (Mock Test)**

If you don't have MySQL set up yet:

```bash
# Use the mock example
python -m vanna.examples.mock_sqlite_example
```

This tests the agent with sample data (no API key needed for mock).

---

## Verification Checklist

After running tests, verify:

- [ ] Memory directory exists: `./vanna_memory/`
- [ ] Memory persists after restart
- [ ] Log file created: `vanna_query_log.jsonl`
- [ ] Similar queries produce consistent SQL
- [ ] Domain config affects SQL generation
- [ ] Admin users can save queries
- [ ] All tools are registered and accessible

---

## Test Questions to Try

### Revenue Queries (should match training)
- "What was revenue last month?"
- "Show revenue by month for last 6 months"
- "What were sales yesterday?"

### Customer Queries (should match training)
- "How many users do we have?"
- "Show top 10 customers by spend"
- "How many active customers?"

### Exploration (should use training patterns)
- "What tables exist?"
- "What columns are in users?"
- "List all product categories"

### Custom (tests memory enhancement)
- "Show me transactions over $100" (should filter is_test)
- "Find users in the US" (should use proper joins)
- "Calculate average revenue per customer" (should use patterns)

---

## Success Indicators

✅ **Good signs:**
- SQL uses patterns from training data
- Queries include filters like `is_test = FALSE`
- JOINs use table aliases (u, t, etc.)
- Time queries use indexed columns
- Business logic correctly applied

❌ **Issues to watch for:**
- Hallucinated table/column names (if using templates)
- Missing important filters (test data, status)
- Incorrect JOIN patterns
- Slow performance (if so, reduce max_examples)

---

## Troubleshooting

**"No similar queries found"**
- Normal for questions very different from training data
- Add more training pairs for that question type
- Add more training data to ChromaDB memory

**"Memory not working"**
- Check `./vanna_memory/` directory exists
- Verify ChromaDB installed: `pip show chromadb`
- Check logs for errors

**"Poor SQL quality"**
- Add domain definitions to domain_config.py
- Expand training data
- Check system prompt includes rules

**"Tools not appearing"**
- Check user group membership
- Verify tools registered in run_web_ui.py
- Check access_groups configuration

---

## After Testing

If everything works:

1. **Customize for your database:**
   - Edit `domain_config.py`
   - Add real training pairs to `sample_query_library.py`
   - Fill out `schema_documentation_template.md`

2. **Re-seed memory:**
   ```bash
   python -m training.seed_agent_memory --clear --verify
   ```

3. **Start production server:**
   ```bash
   python run_web_ui.py
   ```

4. **Monitor and iterate:**
   - Review `vanna_query_log.jsonl` daily
   - Export successful queries weekly
   - Add new patterns to training monthly

---

## Metrics to Track

After 1 week of use:

- Total queries executed
- Success vs failure rate
- Most common questions
- Errors by type
- Memory growth (new saved patterns)

Use the analysis script:
```bash
python -c "from vanna.core.lifecycle.query_logging_hook import analyze_query_log; analyze_query_log()"
```

---

**Ready to test? Start with Test 1 above and work through the list!**
