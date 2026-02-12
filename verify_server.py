"""Quick verification script to test server features."""

import asyncio
import httpx

async def test_server():
    """Test that server is running and responding."""
    print("="*70)
    print("Vanna Server Verification Tests")
    print("="*70)

    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test 1: Server is running
        print("\n[Test 1] Checking if server is running...")
        try:
            response = await client.get(base_url)
            if response.status_code == 200:
                print("  ✓ Server is running at", base_url)
            else:
                print(f"  ✗ Server returned status {response.status_code}")
        except Exception as e:
            print(f"  ✗ Server not accessible: {e}")
            return

        # Test 2: Check if memory directory exists
        print("\n[Test 2] Checking memory persistence...")
        import os
        if os.path.exists("./vanna_memory"):
            print("  ✓ Memory directory exists")
            # Count files in memory directory
            chroma_files = []
            for root, dirs, files in os.walk("./vanna_memory"):
                chroma_files.extend(files)
            print(f"  ✓ Found {len(chroma_files)} files in memory directory")
        else:
            print("  ✗ Memory directory not found")

        # Test 3: Check if domain config is loaded
        print("\n[Test 3] Checking domain configuration...")
        try:
            import domain_config
            has_db_info = hasattr(domain_config, 'DATABASE_INFO')
            has_definitions = hasattr(domain_config, 'BUSINESS_DEFINITIONS')
            print(f"  ✓ Domain config loaded")
            print(f"  - DATABASE_INFO: {has_db_info}")
            print(f"  - BUSINESS_DEFINITIONS: {has_definitions}")
        except Exception as e:
            print(f"  ✗ Domain config error: {e}")

        # Test 4: Check imports
        print("\n[Test 4] Checking feature imports...")
        try:
            from vanna.integrations.chromadb import ChromaAgentMemory
            from vanna.core.enhancer import DefaultLlmContextEnhancer
            from vanna.core.system_prompt.domain_prompt_builder import DomainPromptBuilder
            from vanna.core.lifecycle.query_logging_hook import QueryLoggingHook
            print("  ✓ All optimization features imported successfully")
        except Exception as e:
            print(f"  ✗ Import error: {e}")

        # Test 5: Check training data
        print("\n[Test 5] Checking training data...")
        try:
            from training import sample_query_library
            pairs = sample_query_library.get_training_pairs()
            categories = sample_query_library.get_categories()
            print(f"  ✓ Training library loaded")
            print(f"  - Total pairs: {len(pairs)}")
            print(f"  - Categories: {', '.join(sorted(categories))}")
        except Exception as e:
            print(f"  ✗ Training data error: {e}")

    print("\n" + "="*70)
    print("Verification Complete!")
    print("="*70)
    print("\nServer is running at: http://localhost:8000")
    print("You can now test the UI in your browser!")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(test_server())
