#!/usr/bin/env python3
"""
Small isolated test of Memory Bank storage and search
"""

import asyncio
import os

async def isolated_test():
    """Test Memory Bank storage and search in isolation"""
    try:
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.sessions import VertexAiSessionService
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.tools import load_memory
        from google.genai.types import Content, Part
        import vertexai
        
        project = 'gen-lang-client-0220754900'
        location = 'us-central1'
        
        print("🧪 ISOLATED MEMORY BANK TEST")
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
        
        # Create agent and runner
        agent = LlmAgent(
            name="test_agent",
            model="gemini-2.5-flash",
            tools=[load_memory],
            vertexai=True,
            project=project,
            location=location
        )
        
        runner = Runner(
            agent=agent,
            memory_service=memory_service,
            session_service=session_service,
            app_name="test-isolated"
        )
        
        # Test parameters
        APP_NAME = "test-isolated"
        USER_ID = "test-user-123"
        
        print(f"📝 Using app_name: '{APP_NAME}'")
        print(f"👤 Using user_id: '{USER_ID}'")
        print()
        
        # Step 1: Create a session with actual content
        print("1️⃣ Creating session with content...")
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID
        )
        
        print(f"   Session created: {session.id}")
        
        # Step 2: Add a simple message
        user_input = Content(
            parts=[Part(text="I am working on a Python project called toolstac. I prefer using TypeScript and Redis.")],
            role="user"
        )
        
        print("2️⃣ Processing message through agent...")
        agent_response = None
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session.id,
            new_message=user_input
        ):
            if hasattr(event, 'content'):
                agent_response = str(event.content)
                print(f"   Agent response: {agent_response[:100]}...")
                break
        
        # Step 3: Save session to memory
        print("3️⃣ Saving session to Memory Bank...")
        await memory_service.add_session_to_memory(session)
        print("   ✅ Session saved to Memory Bank")
        print()
        
        # Step 4: IMMEDIATELY search for the content
        print("4️⃣ IMMEDIATELY searching for content...")
        
        search_queries = [
            "toolstac",
            "Python project",
            "TypeScript",
            "Redis",
            "working on"
        ]
        
        for query in search_queries:
            print(f"   🔍 Searching for: '{query}'")
            
            try:
                result = await memory_service.search_memory(
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    query=query
                )
                
                print(f"      📊 Found {len(result.memories)} memories")
                
                if result.memories:
                    for i, memory in enumerate(result.memories):
                        print(f"      💭 Memory {i+1}: {memory.content[:100]}...")
                        print(f"         Score: {memory.score}")
                else:
                    print("      💭 No memories found")
                    
            except Exception as e:
                print(f"      ❌ Search failed: {e}")
            print()
        
        # Step 5: Test with different parameters
        print("5️⃣ Testing with different search parameters...")
        
        # Try searching with different app_name
        print("   🔍 Searching with different app_name...")
        try:
            result = await memory_service.search_memory(
                app_name="claude-code",  # Different app name
                user_id=USER_ID,
                query="toolstac"
            )
            print(f"      📊 Different app_name: {len(result.memories)} memories")
        except Exception as e:
            print(f"      ❌ Different app_name failed: {e}")
        
        # Try searching with different user_id
        print("   🔍 Searching with different user_id...")
        try:
            result = await memory_service.search_memory(
                app_name=APP_NAME,
                user_id="different-user",  # Different user ID
                query="toolstac"
            )
            print(f"      📊 Different user_id: {len(result.memories)} memories")
        except Exception as e:
            print(f"      ❌ Different user_id failed: {e}")
        
        print()
        print("="*50)
        print("🎯 RESULTS:")
        print("="*50)
        print("If memories are found immediately → Storage/search is working")
        print("If no memories found → There's an issue with the process")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(isolated_test())