# Memory Viewing & Automatic Learning Implementation Plan

## Context

**Problem:** User cannot see what's in the agent's memory (21 ChromaDB entries) or optimize it. Additionally, successful queries are logged but not automatically fed back into memory for continuous learning.

**Current State:**
- ChromaDB persistent storage at `./vanna_memory/` with 21 memories (1 schema doc + 20 training queries)
- No built-in UI or tool to browse/inspect memories
- QueryLoggingHook captures queries to `vanna_query_log.jsonl` but no feedback loop
- MemoryBasedEnhancer exists but is disabled due to interface limitations (no access to agent_memory)
- Manual workflow: LLM can call save/search tools, but it's unreliable

**Goal:** Enable users to view/manage memories and implement automatic learning from successful queries.

---

## Solution Overview

### Two-Part Solution:

1. **Memory Viewing Tool** - Standalone CLI script to list, search, export, and analyze memories
2. **Automatic Learning System** - Three-phase approach:
   - Phase 1: Auto-save successful queries via lifecycle hook (immediate value)
   - Phase 2: Enable MemoryBasedEnhancer via constructor injection (auto-inject examples)
   - Phase 3: Batch import utility for historical data (backfill)

---

## Implementation Plan

### Part 1: Memory Viewer (Week 1)

**Create:** `tools/memory_viewer.py` - Standalone CLI tool

**Features:**
```bash
# View statistics
python tools/memory_viewer.py stats

# List all memories with pagination
python tools/memory_viewer.py list [--limit 50] [--category aggregation]

# Search by similarity
python tools/memory_viewer.py search "revenue query"

# Export for backup
python tools/memory_viewer.py export memories_backup.json

# Find and remove duplicates
python tools/memory_viewer.py deduplicate [--dry-run]
```

**Implementation:**
- Reuse `ChromaAgentMemory` class (same instance the agent uses)
- No server changes required - runs standalone
- Output formats: JSON, CSV, pretty-printed tables
- Admin-only access (inherits filesystem permissions)

**Key Methods to Use:**
- `agent_memory.get_recent_memories(context, limit=100)`
- `agent_memory.search_similar_usage(question, context, limit=10)`
- `agent_memory.get_recent_text_memories(context, limit=10)`

---

### Part 2: Automatic Learning

#### Phase 1: Auto-Save Hook (Week 2)

**Create:** `src/vanna/core/lifecycle/auto_save_memory_hook.py`

**Purpose:** Automatically save successful SQL queries to memory without LLM involvement.

```python
class AutoSaveSuccessfulQueriesHook(LifecycleHook):
    """
    Lifecycle hook that saves successful run_sql executions to agent memory.

    Feedback loop: User asks → SQL executes successfully → Hook saves to memory

    This eliminates reliance on the LLM calling save_question_tool_args.
    """

    def __init__(
        self,
        agent_memory: AgentMemory,
        enabled: bool = True,
        save_only_successful: bool = True,
    ):
        self._memory = agent_memory
        self._enabled = enabled
        self._save_only_successful = save_only_successful

    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        """
        Save to memory after successful tool execution.

        Extracts from result.metadata (added by registry):
        - tool_name: Which tool was executed
        - arguments: Tool arguments (includes SQL for run_sql)

        Extracts from context (via metadata):
        - User's question
        - Conversation ID
        - Timestamp
        """
        if not self._enabled:
            return None

        # Get tool name from metadata (added by registry at line 257)
        tool_name = result.metadata.get("tool_name")
        if tool_name != "run_sql":
            return None

        # Filter by success
        if self._save_only_successful and not result.success:
            return None

        # Extract SQL from arguments
        arguments = result.metadata.get("arguments", {})
        sql = arguments.get("sql")
        if not sql:
            return None

        # Save to memory with metadata
        await self._memory.save_tool_usage(
            question="[Auto-saved from execution]",  # TODO: Extract from conversation
            tool_name="run_sql",
            args={"sql": sql},
            success=True,
            metadata={
                "category": "auto_saved_query",
                "execution_time_ms": result.metadata.get("execution_time_ms"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return None  # Don't modify result
```

**Integration in `run_web_ui.py`** (after line 160):
```python
# Create auto-save hook
auto_save_hook = AutoSaveSuccessfulQueriesHook(
    agent_memory=agent_memory,
    enabled=True,  # Feature flag
)

# Add to lifecycle hooks (line 208)
lifecycle_hooks=[query_logger, auto_save_hook]
```

**Note:** Hook needs access to user's question. Options:
1. Store in result.metadata during tool execution
2. Pass conversation context to hook
3. For Phase 1: Save SQL without question, add question extraction in Phase 2

---

#### Phase 2: Enable MemoryBasedEnhancer (Week 3)

**Modify:** `src/vanna/core/enhancer/memory_enhancer.py`

**Change constructor to accept agent_memory** (line 56-71):

```python
def __init__(
    self,
    agent_memory: AgentMemory,  # NEW: Dependency injection
    max_examples: int = 5,
    similarity_threshold: float = 0.7,
    include_metadata: bool = False,
    example_format: Optional[str] = None
):
    self._memory = agent_memory  # NEW: Store as instance variable
    self.max_examples = max_examples
    self.similarity_threshold = similarity_threshold
    self.include_metadata = include_metadata
    self.example_format = example_format

    # Remove warning - feature is now functional
```

**Implement `enhance_system_prompt`** (line 73-98):

```python
async def enhance_system_prompt(
    self, system_prompt: str, user_message: str, user: "User"
) -> str:
    """Inject similar past queries into system prompt."""

    # Search memory for similar questions
    similar_queries = await self._search_similar_queries(
        question=user_message,
        # Create minimal context for memory search
        context=self._create_search_context(user)
    )

    if not similar_queries:
        return system_prompt

    # Format examples and inject
    examples_text = self._format_examples(similar_queries)
    return self._inject_examples(system_prompt, examples_text, len(similar_queries))
```

**Enable in `run_web_ui.py`** (line 162-173):

```python
# BEFORE (disabled):
# context_enhancer = None

# AFTER (enabled):
context_enhancer = MemoryBasedEnhancer(
    agent_memory=agent_memory,  # Pass same instance
    max_examples=5,
    similarity_threshold=0.7,
)
```

**Key Implementation Detail:**
- Constructor injection follows Dependency Inversion Principle
- No changes to `LlmContextEnhancer` base interface
- Non-breaking change - existing enhancers unaffected

---

#### Phase 3: Log Import Utility (Week 4)

**Create:** `tools/import_query_logs.py`

**Purpose:** Batch import successful queries from `vanna_query_log.jsonl` into memory.

```python
class QueryLogImporter:
    """Import successful queries from query log JSONL files into agent memory."""

    async def import_logs(
        self,
        log_file: Path,
        since: datetime | None = None,
        only_successful: bool = True,
        deduplicate: bool = True,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """
        Read JSONL logs, filter by success/date, check for duplicates,
        and save to agent memory.

        Returns:
            {"imported": N, "skipped": M, "duplicates": K, "errors": L}
        """
```

**Usage:**
```bash
# Preview import
python tools/import_query_logs.py --log-file vanna_query_log.jsonl --dry-run

# Import logs from last month
python tools/import_query_logs.py --since 2025-01-01

# Import with deduplication
python tools/import_query_logs.py --deduplicate
```

**Deduplication Strategy:**
- Search memory for similar question (cosine similarity > 0.95)
- Skip if near-duplicate found
- Use timestamp to import only newer logs

---

## Critical Files

### Files to Create:

1. **`tools/memory_viewer.py`** (Week 1)
   - CLI tool for memory inspection
   - ~300 lines
   - Dependencies: ChromaAgentMemory, argparse, tabulate

2. **`src/vanna/core/lifecycle/auto_save_memory_hook.py`** (Week 2)
   - Lifecycle hook for automatic memory saving
   - ~120 lines
   - Dependencies: LifecycleHook, AgentMemory, ToolResult

3. **`tools/import_query_logs.py`** (Week 4)
   - Batch import utility
   - ~200 lines
   - Dependencies: ChromaAgentMemory, json, pathlib

4. **`tests/test_auto_save_memory_hook.py`** (Week 2)
   - Unit tests for auto-save hook
   - ~150 lines
   - Mock AgentMemory, verify save behavior

### Files to Modify:

1. **`src/vanna/core/enhancer/memory_enhancer.py`** (Week 3)
   - **Lines 56-71**: Add `agent_memory` parameter to `__init__`
   - **Lines 67-71**: Remove warning (feature now functional)
   - **Lines 73-98**: Implement `enhance_system_prompt` with actual memory search
   - **Lines 131-230**: Already implemented, just needs agent_memory access
   - Estimated changes: ~30 lines modified

2. **`run_web_ui.py`** (Week 2-3)
   - **After line 160**: Instantiate `AutoSaveSuccessfulQueriesHook`
   - **Line 173**: Enable `MemoryBasedEnhancer` with agent_memory
   - **Line 208**: Add auto_save_hook to lifecycle_hooks list
   - Estimated changes: ~15 lines added

---

## Verification & Testing

### Week 1: Memory Viewer
```bash
# Test against existing ChromaDB
python tools/memory_viewer.py stats
# Expected: 21 memories (1 schema + 20 queries)

python tools/memory_viewer.py list --limit 5
# Expected: Table with question, SQL, category, timestamp

python tools/memory_viewer.py search "total sales"
# Expected: Semantically similar revenue/sales queries

python tools/memory_viewer.py export backup.json
# Expected: JSON file with all 21 memories
```

### Week 2: Auto-Save Hook
```bash
# Check initial memory count
python tools/memory_viewer.py stats

# Start server with auto-save enabled
python run_web_ui.py

# Via web UI, execute successful query: "Show me all customers"
# Expected: Memory count increases by 1

python tools/memory_viewer.py list --category auto_saved_query
# Expected: Shows newly auto-saved query

# Execute failing query (syntax error)
# Expected: Memory count unchanged (only successful queries saved)
```

### Week 3: Memory Enhancement
```bash
# Enable debug logging to see enhanced prompts
export LOG_LEVEL=DEBUG

# Ask question similar to one in memory
# e.g., if memory has "What were total sales last month?"
# Ask: "Show me revenue from January"

# Check logs for injected examples in system prompt
# Expected: See "RELEVANT PAST QUERIES" section with similar query

# Verify generated SQL uses patterns from injected example
```

### Week 4: Log Import
```bash
# Export current successful queries
python -c "from vanna.core.lifecycle.query_logging_hook import export_successful_queries; export_successful_queries()"

# Preview import
python tools/import_query_logs.py --log-file vanna_query_log.jsonl --dry-run
# Expected: Shows N queries would be imported

# Import
python tools/import_query_logs.py --log-file vanna_query_log.jsonl
# Expected: Imports N memories

# Verify
python tools/memory_viewer.py stats
# Expected: Total count increased by N
```

---

## Configuration & Feature Flags

Add to `run_web_ui.py` (top of file):

```python
# Auto-save successful queries to memory
ENABLE_AUTO_SAVE_MEMORY = os.getenv("ENABLE_AUTO_SAVE_MEMORY", "true").lower() == "true"

# Inject similar past queries into LLM prompts
ENABLE_MEMORY_ENHANCEMENT = os.getenv("ENABLE_MEMORY_ENHANCEMENT", "true").lower() == "true"

# Memory enhancement parameters
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))
MEMORY_SIMILARITY = float(os.getenv("MEMORY_SIMILARITY", "0.7"))
```

**Usage:**
```bash
# Disable auto-save
export ENABLE_AUTO_SAVE_MEMORY=false
python run_web_ui.py

# Adjust similarity threshold (stricter matching)
export MEMORY_SIMILARITY=0.85
python run_web_ui.py
```

---

## Rollback Plan

If issues arise:

1. **Disable via environment variables** (no code changes):
   ```bash
   export ENABLE_AUTO_SAVE_MEMORY=false
   export ENABLE_MEMORY_ENHANCEMENT=false
   # Restart server
   ```

2. **Restore memory from backup**:
   ```bash
   python tools/memory_viewer.py export pre_feature_backup.json
   # If needed, restore by re-seeding
   python -m training.seed_agent_memory --clear
   ```

3. **Remove auto-saved memories**:
   ```bash
   # List auto-saved memories
   python tools/memory_viewer.py list --category auto_saved_query

   # Delete via ChromaDB if needed (manual intervention)
   ```

---

## Success Metrics

Track these to measure impact:

1. **Memory Growth**:
   - Queries auto-saved per day
   - Memory size over time
   - Deduplication effectiveness

2. **SQL Accuracy** (before vs after):
   - % successful query executions
   - % queries requiring user correction
   - User satisfaction ratings

3. **Performance**:
   - Memory search latency (target: < 100ms)
   - Impact on total query response time
   - Embedding generation time

4. **Memory Quality**:
   - % memories with high similarity to new queries
   - Duplicate ratio in memory
   - % injected examples that improved results

---

## Security Considerations

1. **Memory Viewer Access**:
   - Script inherits OS-level permissions (admin only)
   - Future web endpoint requires authentication
   - Audit logging recommended

2. **Auto-Save Filtering**:
   - Only saves successful queries (configurable)
   - Future: Add confidence scoring threshold
   - Future: Regex patterns to exclude sensitive queries

3. **Memory Injection**:
   - Similarity threshold prevents irrelevant injection
   - Future: User-scoped memory for multi-tenant setups
   - Future: Sanitize examples before injection

---

## Dependencies

All required dependencies already installed:
- `chromadb` - Vector database backend
- `pydantic` - Data models
- `tabulate` (add) - Pretty-print tables for memory_viewer.py

Add to `pyproject.toml` if needed:
```toml
[project.optional-dependencies]
all = [
    "chromadb>=0.4.0",
    "tabulate>=0.9.0",  # For memory viewer tables
]
```

---

## Timeline Summary

- **Week 1**: Memory viewer tool (immediate visibility)
- **Week 2**: Auto-save hook (automatic learning begins)
- **Week 3**: Enable memory enhancement (auto-inject examples)
- **Week 4**: Log import utility (backfill historical data)

**Estimated Total Effort**: 4 weeks (1 developer)

**Quick Win**: Memory viewer (Week 1) provides immediate value with zero risk.

---

## Next Steps After Implementation

1. **Monitor memory growth rate** - Track auto-saved queries per day
2. **Measure SQL accuracy improvement** - Before/after comparison
3. **Collect user feedback** - Are injected examples helpful?
4. **Optimize similarity threshold** - A/B test 0.6 vs 0.7 vs 0.8
5. **Add web-based memory manager** - Full CRUD UI (future)
6. **Implement confidence scoring** - Only save high-confidence queries
7. **Add memory analytics dashboard** - Visualize memory usage patterns
