# Evaluation Framework

## Overview

The evaluation framework provides systematic testing of agent behavior. It supports defining test cases with expected outcomes, running evaluations with multiple evaluator types, and comparing different agent configurations.

**Location:** `src/vanna/core/evaluation/`

## Core Models

### TestCase (`evaluation/base.py`)

Defines a single evaluation scenario:

```python
class TestCase(BaseModel):
    id: str                                    # Unique test case identifier
    user: User                                 # User context for the test
    message: str                               # Message to send to the agent
    conversation_id: Optional[str] = None      # For multi-turn tests
    expected_outcome: Optional[ExpectedOutcome] = None
    metadata: Dict[str, Any] = {}              # Categorization/filtering
```

### ExpectedOutcome

Defines what the agent should do:

```python
class ExpectedOutcome(BaseModel):
    tools_called: Optional[List[str]] = None           # Tools that SHOULD be called
    tools_not_called: Optional[List[str]] = None       # Tools that should NOT be called
    final_answer_contains: Optional[List[str]] = None  # Keywords in output
    final_answer_not_contains: Optional[List[str]] = None
    min_components: Optional[int] = None               # Min UI components
    max_components: Optional[int] = None               # Max UI components
    max_execution_time_ms: Optional[float] = None      # Performance constraint
    metadata: Dict[str, Any] = {}
```

### AgentResult

Captures everything that happened during execution:

```python
@dataclass
class AgentResult:
    test_case_id: str
    components: List[UiComponent]              # All yielded UI components
    tool_calls: List[Dict[str, Any]] = []      # Tool calls made
    llm_requests: List[Dict[str, Any]] = []    # LLM requests sent
    execution_time_ms: float = 0.0
    total_tokens: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
```

Helper methods:
- `get_final_answer() -> str` - Extracts text from RichTextComponents
- `get_tool_names_called() -> List[str]` - Lists tool names from tool_calls

### EvaluationResult

Result of a single evaluator on a single test case:

```python
class EvaluationResult(BaseModel):
    test_case_id: str
    evaluator_name: str
    passed: bool
    score: float           # 0.0 to 1.0
    reasoning: str         # Explanation of the evaluation
    metrics: Dict[str, Any] = {}
    timestamp: datetime
```

### TestCaseResult

Complete result including all evaluations:

```python
@dataclass
class TestCaseResult:
    test_case: TestCase
    agent_result: AgentResult
    evaluations: List[EvaluationResult]
    execution_time_ms: float
```

Methods:
- `overall_passed() -> bool` - All evaluations passed
- `overall_score() -> float` - Average score across evaluations

### AgentVariant

For comparing different agent configurations:

```python
@dataclass
class AgentVariant:
    name: str                          # Human-readable name
    agent: Agent                       # Agent instance to test
    metadata: Dict[str, Any] = {}      # Model name, config, etc.
```

## Evaluators

**Location:** `src/vanna/core/evaluation/evaluators.py`

All evaluators implement:

```python
class Evaluator(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def evaluate(self, test_case: TestCase, agent_result: AgentResult) -> EvaluationResult: ...
```

### Built-in Evaluators

| Evaluator | What It Checks |
|-----------|---------------|
| `TrajectoryEvaluator` | Tool call sequence matches `tools_called` / `tools_not_called` |
| `OutputEvaluator` | Final answer contains/excludes expected keywords |
| `LLMAsJudgeEvaluator` | Uses an LLM to judge result quality (requires LLM service) |
| `EfficiencyEvaluator` | Execution time within `max_execution_time_ms`, component count within bounds |

## Runner and Reports

### EvaluationRunner (`evaluation/runner.py`)
Runs evaluations against test datasets:
- Execute agent for each test case
- Apply all evaluators to each result
- Compare multiple AgentVariants

### EvaluationDataset (`evaluation/dataset.py`)
Collection of `TestCase` objects for systematic testing.

### Reports (`evaluation/report.py`)
- `EvaluationReport` - Full evaluation results for one agent variant
- `ComparisonReport` - Side-by-side comparison of multiple variants

## Usage Example

```python
from vanna.core.evaluation import (
    TestCase, ExpectedOutcome, AgentVariant,
    TrajectoryEvaluator, OutputEvaluator, EfficiencyEvaluator,
    EvaluationRunner, EvaluationDataset,
)

# Define test cases
dataset = EvaluationDataset(test_cases=[
    TestCase(
        id="revenue_query",
        user=User(id="test", group_memberships=["admin"]),
        message="What was our revenue last month?",
        expected_outcome=ExpectedOutcome(
            tools_called=["run_sql"],
            final_answer_contains=["revenue", "SELECT"],
            max_execution_time_ms=10000,
        )
    ),
])

# Define evaluators
evaluators = [
    TrajectoryEvaluator(),
    OutputEvaluator(),
    EfficiencyEvaluator(),
]

# Define agent variants to compare
variants = [
    AgentVariant(name="claude-3.5", agent=agent_claude, metadata={"model": "claude-3.5-sonnet"}),
    AgentVariant(name="gpt-4", agent=agent_gpt4, metadata={"model": "gpt-4"}),
]

# Run evaluation
runner = EvaluationRunner(evaluators=evaluators)
report = await runner.run(dataset, variants)
```

## Related Files

- `src/vanna/core/evaluation/__init__.py` - Module exports
- `src/vanna/examples/evaluation_example.py` - Working example
- `docs/internal/testing/TESTING_GUIDE.md` - Manual testing guide
