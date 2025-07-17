#!/usr/bin/env python3
"""
Working ADK Memory Bank Test - demonstrates the concept
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_adk_memory_concept():
    """Test the core ADK Memory Bank concept"""
    print("🧠 ADK Memory Bank Concept Test")
    print("=" * 40)
    
    try:
        from google.adk.memory import InMemoryMemoryService
        from google.adk.sessions import InMemorySessionService
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.tools import load_memory
        from google.genai.types import Content, Part
        
        print("✅ ADK imports successful")
        
        # Setup services
        memory_service = InMemoryMemoryService()
        session_service = InMemorySessionService()
        
        # Create agent
        agent = LlmAgent(
            name="memory_agent",
            model="gemini-2.5-flash",
            tools=[load_memory]
        )
        
        # Setup runner
        runner = Runner(
            agent=agent,
            memory_service=memory_service,
            session_service=session_service,
            app_name="memory_test"
        )
        
        print("🚀 Testing memory workflow...")
        
        # Session 1: Store information
        print("\n💾 Session 1: Storing user info...")
        session1 = await session_service.create_session(
            app_name="memory_test",
            user_id="user123",
            session_id="session1"
        )
        
        user_message = Content(
            parts=[Part(text="Hi! I'm Alice and I love pizza. I also prefer window seats on flights.")],
            role="user"
        )
        
        print("👤 User: Hi! I'm Alice and I love pizza. I also prefer window seats on flights.")
        
        # Process message
        final_response = ""
        async for event in runner.run_async(
            user_id="user123",
            session_id="session1",
            new_message=user_message
        ):
            if hasattr(event, 'content'):
                if isinstance(event.content, str):
                    final_response += event.content
                else:
                    final_response += str(event.content)
        
        print(f"🤖 Agent: {final_response}")
        
        # Add to memory
        await memory_service.add_session_to_memory(session1)
        print("💾 Session stored in memory")
        
        # Session 2: Retrieve memories
        print("\n🔍 Session 2: Using memory...")
        session2 = await session_service.create_session(
            app_name="memory_test",
            user_id="user123",
            session_id="session2"
        )
        
        query_message = Content(
            parts=[Part(text="What do you remember about my food preferences?")],
            role="user"
        )
        
        print("👤 User: What do you remember about my food preferences?")
        
        # Process with memory
        final_response2 = ""
        async for event in runner.run_async(
            user_id="user123",
            session_id="session2",
            new_message=query_message
        ):
            if hasattr(event, 'content'):
                if isinstance(event.content, str):
                    final_response2 += event.content
                else:
                    final_response2 += str(event.content)
        
        print(f"🤖 Agent: {final_response2}")
        
        # Test memory search
        print("\n🔍 Direct memory search...")
        search_result = await memory_service.search_memory(
            app_name="memory_test",
            user_id="user123",
            query="food preferences"
        )
        
        print(f"📝 Found {len(search_result.memories)} memories:")
        for i, result in enumerate(search_result.memories):
            print(f"  {i+1}. {result.content}")
        
        print("\n✅ ADK Memory Bank concept test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test"""
    success = asyncio.run(test_adk_memory_concept())
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 ADK Memory Bank is working!")
        print("\n💡 Next steps:")
        print("1. Set up Google Cloud project (see GOOGLE_CLOUD_SETUP.md)")
        print("2. Use real Vertex AI Memory Bank service")
        print("3. Create MCP server wrapper for your system")
    else:
        print("❌ ADK Memory Bank test failed")
        print("Check the error messages above for troubleshooting")

if __name__ == "__main__":
    main()