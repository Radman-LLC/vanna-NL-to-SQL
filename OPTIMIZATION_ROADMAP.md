# Vanna 2.0 Database Optimization Roadmap

This document outlines the prioritized optimization strategy for maximizing Vanna's performance with your specific SQL database project.

## 🎯 Quick Wins (Priority 1 - Implement First)

### ✅ Task 1: Switch to Persistent ChromaDB Memory
**Status:** Planned
**Timeline:** Day 1
**Impact:** High - Enables learning across sessions

Replace `DemoAgentMemory` with `ChromaAgentMemory` to persist learned query patterns across server restarts.

**Implementation:**
```python
# In run_web_ui.py
from vanna.integrations.chromadb import ChromaAgentMemory

agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory_prod",
    collection_name="database_queries"
)
```

**Benefits:**
- Permanent storage of successful query patterns
- Automatic similarity search using embeddings
- No external service dependencies
- Optional GPU acceleration support

---

### ✅ Task 2: Create Training Data Structure
**Status:** Planned
**Timeline:** Days 1-2
**Impact:** High - Foundation for accuracy

Build a library of high-quality question-SQL pairs specific to your database schema.

**Components:**
1. **Schema Documentation Template** - Database structure, key tables, business context
2. **Sample Query Library** - 20-30 representative examples covering common patterns
3. **Seed Script** - Automated population of agent memory

**Question Categories to Cover:**
- Simple aggregations (COUNT, SUM, AVG)
- Multi-table JOINs
- Time-based queries and date ranges
- GROUP BY analyses
- Subqueries and CTEs
- Common business metrics

---

### ✅ Task 3: Enable LLM Context Enhancement
**Status:** Planned
**Timeline:** Day 3
**Impact:** High - Dramatically improves accuracy

Automatically inject relevant past queries into the LLM's context for every new question.

**Implementation:**
- Create `MemoryBasedEnhancer` class
- Search memory for top 5 similar past queries
- Inject examples into system prompt
- LLM sees proven patterns before generating SQL

**Expected Impact:**
- 40-60% reduction in hallucinated SQL
- Better handling of complex JOINs and business logic
- More consistent query patterns

---

### ✅ Task 4: Enhance System Prompt with Domain Rules
**Status:** Planned
**Timeline:** Day 4
**Impact:** Medium-High - Enforces best practices

Extend the base read-only system prompt with domain-specific knowledge.

**Add:**
- Database type and purpose
- Common patterns and conventions (date formats, aliases)
- Business logic definitions (churn, active customer, etc.)
- Performance hints (indexed columns, partitioning)
- Data quality rules (filter test transactions, handle nulls)

---

### ✅ Task 5: Enable Agent Memory Tools
**Status:** Planned
**Timeline:** Day 5
**Impact:** Medium - Enables continuous improvement

Allow users to save successful queries during conversations.

**Tools to Register:**
- `SaveQuestionToolArgsTool` - Saves question-SQL pairs
- `SearchSavedCorrectToolUsesTool` - Finds similar patterns
- `SaveTextMemoryTool` - Stores free-form insights

**User Flow:**
1. User asks question
2. Agent generates correct SQL
3. User says "save this query"
4. Pattern added to memory automatically

---

## 🔧 Advanced Optimizations (Priority 2)

### Task 6: Row-Level Security (If Needed)
**Timeline:** Days 10-12
**Impact:** High for multi-tenant scenarios

Implement user-aware query filtering based on roles and permissions.

**Use Cases:**
- Sales users only see their region's data
- Departments have isolated data access
- Manager vs. employee visibility

---

### Task 7: Query Logging & Analytics
**Timeline:** Days 7-10
**Impact:** Medium - Monitoring and debugging

Track all queries for:
- Performance monitoring
- Error pattern identification
- User behavior analytics
- Continuous improvement feedback

**Implementation:**
- Lifecycle hook for post-tool execution
- Log: user, question, SQL, success/failure, timestamp
- Store in database or append to file

---

### Task 8: GPU Acceleration (Optional)
**Timeline:** Days 15+
**Impact:** Low-Medium - Faster embeddings for large memory

Use GPU for embedding generation if:
- Memory contains 10,000+ examples
- Hardware has CUDA-capable GPU
- Sub-100ms search latency is required

---

### Task 9: LLM Response Caching
**Timeline:** Days 15+
**Impact:** Medium - Cost and latency reduction

Cache responses for common questions to avoid redundant LLM calls.

**Benefits:**
- Instant responses for repeated questions
- Reduced API costs
- Lower latency

---

## 📊 Success Metrics

Track these KPIs to measure optimization effectiveness:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| First-Try Accuracy | >85% | % queries correct without revision |
| SQL Quality | >90% | % generated SQL passes validation |
| Memory Growth | +50/week | New saved patterns per week |
| Response Time | <3s | P95 latency for simple queries |
| User Satisfaction | >4.0/5 | Thumbs up/down ratings |

---

## 🚀 Implementation Phases

### **Phase 1: Foundation (Days 1-5)** ⭐ START HERE
- [x] Switch to ChromaDB persistent memory
- [x] Create training data templates
- [x] Seed memory with 20-30 examples
- [x] Enable LLM context enhancement
- [x] Add domain-specific system prompt
- [x] Register memory tools

**Success Criteria:** Agent remembers past queries, accuracy improves noticeably

---

### **Phase 2: Monitoring & Security (Days 7-12)**
- [ ] Implement query logging hooks
- [ ] Add row-level security (if applicable)
- [ ] Create analytics dashboard
- [ ] Set up error alerting

**Success Criteria:** Full visibility into query patterns, secure multi-user access

---

### **Phase 3: Performance (Days 15+)**
- [ ] GPU acceleration for embeddings
- [ ] LLM response caching
- [ ] Query result caching
- [ ] Performance profiling

**Success Criteria:** Sub-second response times for common queries

---

## 📝 Customization Checklist

Before going live, customize these components for your specific database:

- [ ] **Schema Documentation** - Document your tables, columns, relationships
- [ ] **Training Pairs** - Create 20-30 question-SQL examples from your domain
- [ ] **Business Logic** - Define domain terms (churn, conversion, etc.)
- [ ] **System Prompt** - Add database-specific rules and patterns
- [ ] **Access Control** - Configure user groups and permissions
- [ ] **Test Queries** - Create test suite covering key scenarios

---

## 🆘 Troubleshooting

### Poor Query Quality
1. Check memory contains relevant examples (`SearchSavedCorrectToolUsesTool`)
2. Review system prompt for clarity and completeness
3. Verify LLM context enhancer is injecting examples
4. Add more training pairs for problematic query types

### Slow Response Times
1. Check embedding generation time (consider GPU)
2. Review LLM model choice (Haiku for speed, Opus for quality)
3. Implement caching for common questions
4. Reduce context enhancer limit (5 → 3 examples)

### Memory Not Persisting
1. Verify ChromaDB persist_directory exists and is writable
2. Check ChromaAgentMemory initialization
3. Confirm save_tool_usage is being called
4. Review error logs for persistence failures

---

## 📚 Additional Resources

- **Vanna Documentation:** https://vanna.ai/docs
- **ChromaDB Docs:** https://docs.trychroma.com/
- **Sentence Transformers:** https://www.sbert.net/
- **Example Code:** `examples/chromadb_gpu_example.py`
- **Architecture:** See `CLAUDE.md` for detailed system design

---

**Last Updated:** 2026-02-11
**Status:** Implementation in progress
**Branch:** `feature/database-optimization-roadmap`
