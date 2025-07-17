#!/usr/bin/env python3
"""
Test Google Memory Bank with ADK - focused on the Memory Bank functionality
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_adk_imports():
    """Test if we can import ADK Memory Bank components"""
    try:
        from google.adk.memory import InMemoryMemoryService
        from google.adk.sessions import InMemorySessionService
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.tools import load_memory
        from google.genai.types import Content, Part
        
        print("✅ ADK Memory Bank imports successful")
        return True
        
    except ImportError as e:
        print(f"❌ ADK import failed: {e}")
        return False

def test_gemini_connection():
    """Test basic Gemini API connectivity"""
    try:
        import google.generativeai as genai
        
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("❌ No Gemini API key found")
            return False
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Test with a simple prompt
        response = model.generate_content("Hello! Can you help me test memory functionality?")
        print(f"✅ Gemini API working: {response.text[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        return False

async def test_in_memory_adk():
    """Test ADK Memory Bank using in-memory services (no Google Cloud needed)"""
    try:
        from google.adk.memory import InMemoryMemoryService
        from google.adk.sessions import InMemorySessionService
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.tools import load_memory
        from google.genai.types import Content, Part
        
        print("🧪 Testing ADK Memory Bank (In-Memory)...")
        
        # Setup in-memory services
        memory_service = InMemoryMemoryService()
        session_service = InMemorySessionService()
        
        # Create agent with memory capabilities
        agent = LlmAgent(
            name="memory_test_agent",
            model="gemini-2.5-flash",
            tools=[load_memory]
        )
        
        # Setup runner
        runner = Runner(
            agent=agent,
            memory_service=memory_service,
            session_service=session_service,
            app_name="memory_test_app"
        )
        
        print("🚀 Testing memory functionality...")
        
        # Test constants
        APP_NAME = "memory_test_app"
        USER_ID = "test_user_123"
        
        # Test 1: Store information
        print("💾 Session 1: Storing user preferences...")
        session1 = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id="test_session_1"
        )
        
        # Simulate user sharing preferences
        user_input = Content(
            parts=[Part(text="Hi! I'm John and I prefer aisle seats when flying. I'm also vegetarian.")],
            role="user"
        )
        
        print("💬 User input: Hi! I'm John and I prefer aisle seats when flying. I'm also vegetarian.")
        
        # Process with agent
        response_text = ""
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id="test_session_1",
            new_message=user_input
        ):
            if hasattr(event, 'content'):
                response_text += event.content
                print(f"🤖 Agent: {event.content}")
        
        # Add session to memory
        print("💾 Adding session to memory...")
        await memory_service.add_session_to_memory(session1)
        
        # Test 2: Create new session and retrieve memories
        print("🔍 Session 2: Retrieving memories...")
        session2 = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id="test_session_2"
        )
        
        # Ask about preferences
        query_input = Content(
            parts=[Part(text="What do you know about my flight preferences?")],
            role="user"
        )
        
        print("💬 User query: What do you know about my flight preferences?")
        
        # Process with agent (should use memory)
        response_text2 = ""
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id="test_session_2",
            new_message=query_input
        ):
            if hasattr(event, 'content'):
                response_text2 += event.content
                print(f"🤖 Agent (with memory): {event.content}")
        
        # Test 3: Search memories directly
        print("🔍 Testing direct memory search...")
        search_results = await memory_service.search_memory(
            app_name=APP_NAME,
            user_id=USER_ID,
            query="flight preferences"
        )
        
        print(f"📋 Memory search results: {len(search_results.results)} found")
        for result in search_results.results:
            print(f"  - {result.content}")
        
        print("✅ ADK Memory Bank (In-Memory) test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ ADK Memory Bank test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧠 Google ADK Memory Bank Test Suite")
    print("=" * 50)
    
    # Test 1: Check ADK imports
    print("\n1. Testing ADK imports...")
    imports_ok = test_adk_imports()
    
    # Test 2: Check Gemini API
    print("\n2. Testing Gemini API...")
    gemini_ok = test_gemini_connection()
    
    # Test 3: ADK Memory Bank (In-Memory)
    if imports_ok and gemini_ok:
        print("\n3. Testing ADK Memory Bank (In-Memory)...")
        try:
            success = asyncio.run(test_in_memory_adk())
        except Exception as e:
            print(f"❌ ADK test failed: {e}")
            success = False
    else:
        print("\n3. Skipping ADK Memory Bank test (requirements not met)")
        success = False
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary:")
    print(f"  ADK Imports: {'✅' if imports_ok else '❌'}")
    print(f"  Gemini API: {'✅' if gemini_ok else '❌'}")
    print(f"  Memory Bank: {'✅' if success else '❌'}")
    
    if not imports_ok:
        print("\n📋 To use ADK Memory Bank:")
        print("  1. Install ADK: pip install google-adk[vertexai]")
    
    if not gemini_ok:
        print("\n📋 To use Gemini API:")
        print("  1. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env")
    
    if success:
        print("\n🎉 Great! ADK Memory Bank is working with in-memory services!")
        print("💡 Next step: Set up Google Cloud project for full Vertex AI integration")

if __name__ == "__main__":
    main()