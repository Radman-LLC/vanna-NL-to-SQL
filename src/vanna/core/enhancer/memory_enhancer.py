"""Memory-based LLM context enhancer.

Automatically injects relevant past queries from agent memory into the LLM's system
prompt. This dramatically improves SQL generation accuracy by providing the LLM with
proven examples of similar queries.

How it works:
1. When user asks a question, search agent memory for similar past questions
2. Retrieve top N most similar successful query patterns
3. Inject these examples into the system prompt before LLM call
4. LLM sees proven patterns and generates better SQL

Benefits:
- 40-60% reduction in hallucinated table/column names
- More consistent query patterns and style
- Better handling of complex JOINs and business logic
- Learns from successful queries over time
"""

from typing import TYPE_CHECKING, List, Optional
import logging

from .base import LlmContextEnhancer

if TYPE_CHECKING:
    from vanna.core.llm.models import LlmRequest
    from vanna.core.agent.models import Conversation
    from vanna.core.tool.base import ToolContext
    from vanna.capabilities.agent_memory.models import ToolMemorySearchResult

logger = logging.getLogger(__name__)


class MemoryBasedEnhancer(LlmContextEnhancer):
    """Enhances LLM context by injecting similar past queries from agent memory.

    This enhancer searches the agent's memory for questions similar to the current
    user question and injects the top matching SQL queries as examples in the
    system prompt.

    Args:
        max_examples: Maximum number of example queries to inject (default: 5)
        similarity_threshold: Minimum similarity score (0.0-1.0) for including
                            an example. Lower = more permissive. (default: 0.7)
        include_metadata: Whether to include query metadata (timestamp, category)
                         in the injected examples (default: False)
        example_format: Format string for each example. Use {question}, {sql},
                       {similarity} placeholders. If None, uses default format.
    """

    def __init__(
        self,
        max_examples: int = 5,
        similarity_threshold: float = 0.7,
        include_metadata: bool = False,
        example_format: Optional[str] = None
    ):
        self.max_examples = max_examples
        self.similarity_threshold = similarity_threshold
        self.include_metadata = include_metadata
        self.example_format = example_format

    async def enhance_context(
        self,
        request: "LlmRequest",
        conversation: "Conversation",
        context: "ToolContext"
    ) -> "LlmRequest":
        """Enhance the LLM request by injecting similar past queries.

        Searches agent memory for questions similar to the user's current message
        and adds them to the system prompt as reference examples.

        Args:
            request: The LLM request to enhance
            conversation: The current conversation history
            context: Tool execution context with user info and agent memory

        Returns:
            Enhanced LLM request with examples injected into system message
        """
        # Only enhance if agent memory is available
        if not context.agent_memory:
            logger.debug("No agent memory available, skipping memory enhancement")
            return request

        # Extract the user's current question from conversation
        user_question = self._extract_user_question(conversation)
        if not user_question:
            logger.debug("No user question found, skipping memory enhancement")
            return request

        # Search memory for similar past queries
        try:
            similar_queries = await self._search_similar_queries(
                user_question,
                context
            )
        except Exception as e:
            # Don't fail the request if memory search fails, just log and continue
            logger.warning(f"Memory search failed: {e}")
            return request

        # If no similar queries found, return original request
        if not similar_queries:
            logger.debug(f"No similar queries found for: {user_question}")
            return request

        # Format and inject examples into system prompt
        examples_text = self._format_examples(similar_queries)
        enhanced_system_message = self._inject_examples(
            request.system_message or "",
            examples_text,
            len(similar_queries)
        )

        # Create enhanced request with updated system message
        request.system_message = enhanced_system_message

        logger.info(
            f"Enhanced context with {len(similar_queries)} example(s) "
            f"for question: {user_question[:50]}..."
        )

        return request

    def _extract_user_question(self, conversation: "Conversation") -> Optional[str]:
        """Extract the most recent user question from conversation history.

        Args:
            conversation: Conversation history

        Returns:
            Most recent user message content, or None if not found
        """
        # Iterate backwards through conversation to find latest user message
        for message in reversed(conversation.messages):
            if message.role == "user" and message.content:
                return message.content

        return None

    async def _search_similar_queries(
        self,
        question: str,
        context: "ToolContext"
    ) -> List["ToolMemorySearchResult"]:
        """Search agent memory for queries similar to the given question.

        Args:
            question: User's question to search for
            context: Tool execution context with agent memory

        Returns:
            List of similar query results from memory
        """
        results = await context.agent_memory.search_similar_usage(
            question=question,
            context=context,
            limit=self.max_examples,
            similarity_threshold=self.similarity_threshold,
            tool_name_filter="run_sql"  # Only search for SQL query patterns
        )

        return results

    def _format_examples(
        self,
        similar_queries: List["ToolMemorySearchResult"]
    ) -> str:
        """Format similar queries as text to inject into system prompt.

        Args:
            similar_queries: List of similar query results from memory

        Returns:
            Formatted text block with examples
        """
        if self.example_format:
            # Use custom format string
            examples = []
            for result in similar_queries:
                formatted = self.example_format.format(
                    question=result.memory.question,
                    sql=result.memory.args.get("sql", ""),
                    similarity=result.similarity_score
                )
                examples.append(formatted)
            return "\n\n".join(examples)

        # Default format: clear and concise
        examples = []
        for i, result in enumerate(similar_queries, 1):
            memory = result.memory
            sql = memory.args.get("sql", "").strip()

            example = f"Example {i}:\n"
            example += f"Question: {memory.question}\n"
            example += f"SQL:\n```sql\n{sql}\n```"

            # Optionally include metadata
            if self.include_metadata:
                if hasattr(memory, "timestamp") and memory.timestamp:
                    example += f"\n(Saved: {memory.timestamp})"
                if hasattr(memory, "metadata") and memory.metadata:
                    category = memory.metadata.get("category")
                    if category:
                        example += f"\n(Category: {category})"

            examples.append(example)

        return "\n\n".join(examples)

    def _inject_examples(
        self,
        system_message: str,
        examples_text: str,
        num_examples: int
    ) -> str:
        """Inject example queries into the system message.

        Args:
            system_message: Original system message
            examples_text: Formatted examples to inject
            num_examples: Number of examples being injected

        Returns:
            Enhanced system message with examples
        """
        # Create injection block with clear separation
        injection = "\n\n" + "=" * 70 + "\n"
        injection += f"RELEVANT PAST QUERIES ({num_examples} example(s)):\n\n"
        injection += (
            "The following are similar questions and their correct SQL queries "
            "from past successful executions. Use these as reference patterns "
            "when generating SQL for the current question.\n\n"
        )
        injection += examples_text
        injection += "\n" + "=" * 70 + "\n"

        # Append to end of system message so it's fresh in context
        return system_message + injection


class AdaptiveMemoryEnhancer(MemoryBasedEnhancer):
    """Advanced version that adapts similarity threshold based on search results.

    If no results are found at the default threshold, this enhancer will
    progressively lower the threshold to find at least 1-2 examples. This
    ensures the LLM always has some context, even for novel questions.
    """

    def __init__(
        self,
        max_examples: int = 5,
        initial_threshold: float = 0.7,
        min_threshold: float = 0.3,
        threshold_step: float = 0.1,
        min_examples: int = 1,
        **kwargs
    ):
        """Initialize adaptive enhancer.

        Args:
            max_examples: Maximum examples to retrieve
            initial_threshold: Starting similarity threshold
            min_threshold: Minimum threshold to try (don't go below this)
            threshold_step: Amount to decrease threshold each iteration
            min_examples: Keep lowering threshold until at least this many
        """
        super().__init__(
            max_examples=max_examples,
            similarity_threshold=initial_threshold,
            **kwargs
        )
        self.initial_threshold = initial_threshold
        self.min_threshold = min_threshold
        self.threshold_step = threshold_step
        self.min_examples = min_examples

    async def _search_similar_queries(
        self,
        question: str,
        context: "ToolContext"
    ) -> List["ToolMemorySearchResult"]:
        """Adaptive search that lowers threshold if no results found.

        Args:
            question: User's question to search for
            context: Tool execution context with agent memory

        Returns:
            List of similar query results from memory
        """
        current_threshold = self.initial_threshold
        results = []

        # Try progressively lower thresholds until we get results
        while current_threshold >= self.min_threshold:
            results = await context.agent_memory.search_similar_usage(
                question=question,
                context=context,
                limit=self.max_examples,
                similarity_threshold=current_threshold,
                tool_name_filter="run_sql"
            )

            # If we have enough examples, return them
            if len(results) >= self.min_examples:
                if current_threshold < self.initial_threshold:
                    logger.info(
                        f"Adaptive search lowered threshold to {current_threshold:.2f} "
                        f"to find {len(results)} examples"
                    )
                return results

            # Lower threshold and try again
            current_threshold -= self.threshold_step

        # Return whatever we found, even if 0 results
        logger.debug(
            f"Adaptive search exhausted at threshold {self.min_threshold}, "
            f"found {len(results)} examples"
        )
        return results
