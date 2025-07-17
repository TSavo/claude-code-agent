#!/usr/bin/env python3
"""
Simple isolated test of Memory Bank storage and search - no agent runner
"""

import asyncio
import os

async def simple_test():
    """Test Memory Bank directly without agent runner"""
    try:
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.sessions import VertexAiSessionService
        import vertexai
        
        project = 'gen-lang-client-0220754900'
        location = 'us-central1'
        
        print("🧪 SIMPLE MEMORY BANK TEST")
        print("="*50)
        
        # Initialize
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        # Get agent engine
        agent_engines = list(client.agent_engines.list())
        agent_engine_id = agent_engines[0].api_resource.name.split('/')[-1]
        
        print(f"🏗️ Agent Engine ID: {agent_engine_id}")
        
        # Create services
        memory_service = VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        session_service = VertexAiSessionService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Test parameters - these are the EXACT parameters from the hooks
        APP_NAME = "claude-code"
        USER_ID = "9524689c-c3eb-43be-965c-c06f87702219"
        
        # The session ID that we just added data to!
        EXISTING_SESSION_ID = "8328530650298580992"
        
        print(f"📝 Using app_name: '{APP_NAME}'")
        print(f"👤 Using user_id: '{USER_ID}'")
        print(f"🏗️ Using agent_engine_id: {agent_engine_id}")
        print(f"🔗 Looking for existing session: {EXISTING_SESSION_ID}")
        print()
        
        # Step 1: Get the existing session that hooks have been using
        print("1️⃣ Getting the EXISTING session that hooks have been using...")
        try:
            session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=EXISTING_SESSION_ID
            )
            print(f"   ✅ Got existing session: {session.id}")
            print(f"   Session type: {type(session)}")
        except Exception as e:
            print(f"   ❌ Failed to get existing session: {e}")
            print("   Creating new session instead...")
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID
            )
            print(f"   Session created: {session.id}")
        print()
        
        # Step 3: IMMEDIATELY search for anything
        print("3️⃣ IMMEDIATELY searching for ANY content...")
        
        search_queries = [
            "session",
            "test",
            "claude",
            "code",
            "project"
        ]
        
        total_found = 0
        for query in search_queries:
            print(f"   🔍 Searching for: '{query}'")
            
            try:
                result = await memory_service.search_memory(
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    query=query
                )
                
                print(f"      📊 Found {len(result.memories)} memories")
                total_found += len(result.memories)
                
                if result.memories:
                    for i, memory in enumerate(result.memories):
                        print(f"      💭 Memory {i+1}: {memory.content[:100]}...")
                        print(f"         Score: {memory.score}")
                else:
                    print("      💭 No memories found")
                    
            except Exception as e:
                print(f"      ❌ Search failed: {e}")
            print()
        
        print(f"📊 TOTAL MEMORIES FOUND: {total_found}")
        print()
        
        # Step 3.5: Retrieve ALL memories for this user
        print("3️⃣.5️⃣ Retrieving ALL memories for user...")
        try:
            retrieved_memories = list(
                client.agent_engines.retrieve_memories(
                    name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                    scope={"user_id": USER_ID}
                )
            )
            print(f"📊 Found {len(retrieved_memories)} total memories for user {USER_ID}")
            for i, mem in enumerate(retrieved_memories):
                print(f"💭 Memory {i+1}: {mem.memory.fact}")
        except Exception as e:
            print(f"❌ Retrieve memories failed: {e}")
        print()
        
        # Step 4: Test different search parameters
        print("4️⃣ Testing different search parameters...")
        
        # Search with the exact same parameters the hooks are using
        hook_queries = [
            "toolstac project",
            "editing test_context.py", 
            "test-memory-bank",
            "edit file"
        ]
        
        for query in hook_queries:
            print(f"   🔍 Hook-style search: '{query}'")
            try:
                result = await memory_service.search_memory(
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    query=query
                )
                print(f"      📊 Found {len(result.memories)} memories")
                if result.memories:
                    for memory in result.memories:
                        print(f"      💭 {memory.content[:100]}...")
            except Exception as e:
                print(f"      ❌ Search failed: {e}")
            print()
        
        print("="*50)
        print("🎯 DIAGNOSIS:")
        print("="*50)
        
        if total_found > 0:
            print("✅ Memory Bank is working - sessions are being stored and found")
            print("❌ Hook issue - the hooks might not be storing sessions correctly")
        else:
            print("❌ Memory Bank issue - empty sessions aren't searchable")
            print("💡 Sessions need actual content to be searchable")
        
        print("="*50)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simple_test())