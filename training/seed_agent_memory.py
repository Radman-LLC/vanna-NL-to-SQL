"""Seed Agent Memory Script

Populates the ChromaDB agent memory with:
1. Schema documentation from markdown template
2. High-quality question-SQL training pairs
3. Business context and domain knowledge

This creates a knowledge base that the agent can reference when generating SQL queries.

Usage:
    python -m training.seed_agent_memory

    # Or with custom memory directory:
    python -m training.seed_agent_memory --memory-dir ./custom_memory

Prerequisites:
1. ChromaDB must be installed: pip install chromadb
2. Fill out training/schema_documentation_template.md with your database details
3. Customize training/sample_query_library.py with your actual queries
"""

import asyncio
import argparse
import os
from pathlib import Path
from typing import Dict, Any

from vanna.integrations.chromadb import ChromaAgentMemory
from vanna.core.tool import ToolContext
from vanna.core.user import User


def load_schema_documentation(filepath: str = None) -> str:
    """Load schema documentation from markdown file.

    Args:
        filepath: Path to schema documentation markdown file.
                  Defaults to training/schema_documentation_template.md

    Returns:
        String content of the schema documentation
    """
    if filepath is None:
        # Default to template in same directory as this script
        script_dir = Path(__file__).parent
        filepath = script_dir / "schema_documentation_template.md"

    if not os.path.exists(filepath):
        print(f"[warning] Schema documentation not found at: {filepath}")
        print("          Using placeholder documentation.")
        return """
        Database Schema Documentation

        This is placeholder documentation. Please fill out the template at:
        training/schema_documentation_template.md

        Include:
        - Table descriptions and relationships
        - Key columns and indexes
        - Business definitions (churn, active customer, etc.)
        - SQL best practices for your database
        """

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def load_training_pairs(module_path: str = None):
    """Load training pairs from Python module.

    Args:
        module_path: Path to Python module with TRAINING_PAIRS list.
                     Defaults to training.sample_query_library

    Returns:
        List of training pair dictionaries
    """
    if module_path is None:
        # Import from same package
        from . import sample_query_library
        return sample_query_library.get_training_pairs()
    else:
        # Dynamic import from custom path
        import importlib.util
        spec = importlib.util.spec_from_file_location("custom_library", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.get_training_pairs()


async def seed_memory(
    memory_dir: str = "./vanna_memory",
    collection_name: str = "mysql_queries",
    schema_doc_path: str = None,
    training_pairs_path: str = None,
    clear_existing: bool = False
):
    """Seed the agent memory with schema documentation and training pairs.

    Args:
        memory_dir: Directory for ChromaDB persistence
        collection_name: ChromaDB collection name
        schema_doc_path: Path to schema documentation markdown file
        training_pairs_path: Path to training pairs Python module
        clear_existing: If True, clear existing memories before seeding
    """
    print("=" * 70)
    print("Seeding Agent Memory")
    print("=" * 70)
    print(f"Memory directory: {memory_dir}")
    print(f"Collection: {collection_name}")
    print()

    # Initialize ChromaDB agent memory
    print("[1/4] Initializing ChromaDB...")
    memory = ChromaAgentMemory(
        persist_directory=memory_dir,
        collection_name=collection_name
    )
    print("[OK] ChromaDB initialized")

    # Create a system user context for seeding
    system_user = User(
        id="system",
        email="system@vanna.ai",
        group_memberships=["admin", "system"]
    )
    context = ToolContext(
        user=system_user,
        conversation_id="seed_session",
        request_id="seed_operation",
        agent_memory=memory  # Required field
    )

    # Clear existing memories if requested
    if clear_existing:
        print("\n[2/4] Clearing existing memories...")
        deleted_count = await memory.clear_memories(context)
        print(f"[OK] Cleared {deleted_count} existing memories")
    else:
        print("\n[2/4] Preserving existing memories")

    # Load and save schema documentation
    print("\n[3/4] Loading schema documentation...")
    schema_doc = load_schema_documentation(schema_doc_path)

    # Save schema documentation as text memory
    await memory.save_text_memory(
        content=schema_doc,
        context=context
    )
    print(f"[OK] Saved schema documentation ({len(schema_doc)} characters)")

    # Load and save training pairs
    print("\n[4/4] Loading training pairs...")
    training_pairs = load_training_pairs(training_pairs_path)
    print(f"Found {len(training_pairs)} training pairs")

    # Group by category for better output
    from collections import defaultdict
    by_category = defaultdict(list)
    for pair in training_pairs:
        category = pair.get("category", "uncategorized")
        by_category[category].append(pair)

    # Save each training pair to memory
    saved_count = 0
    for category, pairs in sorted(by_category.items()):
        print(f"\n  Saving {category} ({len(pairs)} queries)...")
        for pair in pairs:
            await memory.save_tool_usage(
                question=pair["question"],
                tool_name="run_sql",
                args={"sql": pair["sql"].strip()},
                context=context,
                success=True,
                metadata={
                    "category": category,
                    "notes": pair.get("notes", ""),
                    "source": "seed_script"
                }
            )
            saved_count += 1
        print(f"  [OK] Saved {len(pairs)} {category} queries")

    print("\n" + "=" * 70)
    print("Seeding Complete!")
    print("=" * 70)
    print(f"[OK] Saved 1 schema documentation")
    print(f"[OK] Saved {saved_count} training pairs")
    print(f"[OK] Total memories: {saved_count + 1}")
    print()
    print("Next steps:")
    print("1. Customize training/schema_documentation_template.md for your database")
    print("2. Add more training pairs to training/sample_query_library.py")
    print("3. Run this script again to update the memory")
    print("4. Start your Vanna server with: python run_web_ui.py")
    print()


async def verify_seeded_data(
    memory_dir: str = "./vanna_memory",
    collection_name: str = "mysql_queries"
):
    """Verify the seeded data by searching for a sample query.

    This is useful to confirm that the memory was populated correctly.
    """
    print("\n" + "=" * 70)
    print("Verifying Seeded Data")
    print("=" * 70)

    memory = ChromaAgentMemory(
        persist_directory=memory_dir,
        collection_name=collection_name
    )

    system_user = User(
        id="system",
        email="system@vanna.ai",
        group_memberships=["admin"]
    )
    context = ToolContext(
        user=system_user,
        conversation_id="verify_session",
        request_id="verify_operation",
        agent_memory=memory  # Required field
    )

    # Try searching for a common query
    test_question = "show me total revenue"
    print(f"\nSearching for similar queries to: '{test_question}'")

    results = await memory.search_similar_usage(
        question=test_question,
        context=context,
        limit=3,
        similarity_threshold=0.3  # Lower threshold for testing
    )

    if results:
        print(f"\n[OK] Found {len(results)} similar queries:")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. Similarity: {result.similarity_score:.2f}")
            print(f"     Question: {result.memory.question}")
            print(f"     SQL: {result.memory.args.get('sql', '')[:100]}...")
    else:
        print("\n[WARN] No similar queries found - memory may be empty or search failed")

    # Check text memories (schema documentation)
    print("\n\nChecking text memories (schema documentation)...")
    text_memories = await memory.get_recent_text_memories(context, limit=5)

    if text_memories:
        print(f"[OK] Found {len(text_memories)} text memories:")
        for i, mem in enumerate(text_memories, 1):
            content_preview = mem.content[:150].replace("\n", " ")
            print(f"  {i}. {content_preview}...")
    else:
        print("[WARN] No text memories found")

    print("\n" + "=" * 70)


def main():
    """Main entry point for the seed script."""
    parser = argparse.ArgumentParser(
        description="Seed Vanna agent memory with schema docs and training queries"
    )
    parser.add_argument(
        "--memory-dir",
        default="./vanna_memory",
        help="Directory for ChromaDB persistence (default: ./vanna_memory)"
    )
    parser.add_argument(
        "--collection",
        default="mysql_queries",
        help="ChromaDB collection name (default: mysql_queries)"
    )
    parser.add_argument(
        "--schema-doc",
        help="Path to schema documentation markdown file"
    )
    parser.add_argument(
        "--training-pairs",
        help="Path to training pairs Python module"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing memories before seeding"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify seeded data after completion"
    )

    args = parser.parse_args()

    # Run the seeding process
    asyncio.run(seed_memory(
        memory_dir=args.memory_dir,
        collection_name=args.collection,
        schema_doc_path=args.schema_doc,
        training_pairs_path=args.training_pairs,
        clear_existing=args.clear
    ))

    # Optionally verify the seeded data
    if args.verify:
        asyncio.run(verify_seeded_data(
            memory_dir=args.memory_dir,
            collection_name=args.collection
        ))


if __name__ == "__main__":
    main()
