#!/usr/bin/env python3
"""
Debug why Memory Bank searches return no results
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

async def debug_memory_search():
    """Debug why searches return no results"""
    try:
        from hooks.save_and_load_context import get_memory_and_session_services
        
        # Get services
        memory_service, session_service = await get_memory_and_session_services()
        
        if not memory_service or not session_service:
            print("❌ Failed to get services")
            return
        
        print("="*80)
        print("🔍 DEBUGGING MEMORY BANK SEARCH PROCESS")
        print("="*80)
        
        # These are the exact parameters used by the hooks
        app_name = "claude-code"
        user_id = "a649ac00-90d0-412b-a1d1-b13fa0414df3"
        
        # Test queries (these are the actual queries from the hooks)
        test_queries = [
            "toolstac project",
            "editing test_context.py",
            "edit file",
            "python development",
            "test-memory-bank",
            "bash command",
            "tool result",
            "project context"
        ]
        
        print(f"📝 Searching with:")
        print(f"   app_name: '{app_name}'")
        print(f"   user_id: '{user_id}'")
        print(f"   agent_engine_id: {memory_service._agent_engine_id}")
        print()
        
        total_memories_found = 0
        
        for query in test_queries:
            print(f"🔍 Query: '{query}'")
            
            try:
                result = await memory_service.search_memory(
                    app_name=app_name,
                    user_id=user_id,
                    query=query
                )
                
                print(f"   📊 Results: {len(result.memories)} memories found")
                
                if result.memories:
                    total_memories_found += len(result.memories)
                    for i, memory in enumerate(result.memories[:2]):  # Show first 2
                        print(f"   💭 Memory {i+1}: {memory.content[:100]}...")
                        print(f"      Score: {memory.score}")
                else:
                    print("   💭 No memories found")
                    
            except Exception as e:
                print(f"   ❌ Search failed: {e}")
            
            print()
        
        print(f"📊 TOTAL MEMORIES FOUND: {total_memories_found}")
        print()
        
        # Check if there are any memories at all
        print("🔍 Checking for ANY memories in Memory Bank...")
        try:
            # Try a very broad search
            result = await memory_service.search_memory(
                app_name=app_name,
                user_id=user_id,
                query="*"
            )
            print(f"   Broad search (*): {len(result.memories)} memories")
            
            result = await memory_service.search_memory(
                app_name=app_name,
                user_id=user_id,
                query=""
            )
            print(f"   Empty search: {len(result.memories)} memories")
            
        except Exception as e:
            print(f"   ❌ Broad search failed: {e}")
        
        print()
        print("="*80)
        print("🧐 POSSIBLE REASONS FOR NO RESULTS:")
        print("="*80)
        print("1. ⏳ Memory processing delay - Sessions need time to become searchable")
        print("2. 🔍 Query mismatch - Search terms don't match stored content")
        print("3. 🗂️ App name mismatch - Stored with different app_name")
        print("4. 👤 User ID mismatch - Stored with different user_id")
        print("5. 🏗️ Agent engine mismatch - Wrong agent_engine_id")
        print("6. 📝 Content format - Agent responses might not be indexed properly")
        print("7. 🔄 Processing state - Sessions saved but not yet processed into memories")
        print()
        
        # Let's check what we're actually storing
        print("🔍 CHECKING WHAT WE'RE STORING...")
        print("The hooks are storing sessions with:")
        print(f"   app_name: 'claude-code'")
        print(f"   user_id: '{user_id}'")
        print(f"   agent_engine_id: {memory_service._agent_engine_id}")
        print()
        print("Each session contains:")
        print("   User: 'Context: Project: test-memory-bank | Tool: Edit | ...'")
        print("   Agent: 'I understand you're working on...'")
        print()
        
        print("="*80)
        print("🔬 NEXT STEPS TO DEBUG:")
        print("="*80)
        print("1. Wait 5-10 minutes for Memory Bank to process sessions")
        print("2. Try different search queries")
        print("3. Check if sessions are being created in the right agent engine")
        print("4. Verify the search is using the same parameters as storage")
        print("="*80)
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_memory_search())