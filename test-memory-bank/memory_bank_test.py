#!/usr/bin/env python3
"""
Test Google Memory Bank with ADK (if available) or fallback to simulation
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_adk_availability():
    """Check if Google ADK is available and properly configured"""
    try:
        import google.adk
        print("✅ Google ADK is available")
        
        # Check for required environment variables
        project = os.getenv('GOOGLE_CLOUD_PROJECT')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        if not project:
            print("❌ GOOGLE_CLOUD_PROJECT not set in environment")
            return False
        
        print(f"📍 Project: {project}")
        print(f"📍 Location: {location}")
        
        return True
        
    except ImportError:
        print("❌ Google ADK not available. Install with: pip install google-adk[vertexai]")
        return False

def test_gemini_api():
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
        
    except ImportError:
        print("❌ google-generativeai not installed. Run: pip install google-generativeai")
        return False
    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        return False

async def test_adk_memory_bank():
    """Test full ADK Memory Bank integration"""
    try:
        from google.adk.agents import LlmAgent
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.sessions import VertexAiSessionService
        from google.adk.runners import Runner
        from google.adk.tools import load_memory
        import vertexai
        
        print("🧪 Testing ADK Memory Bank...")
        
        # Setup Google Cloud client
        project = os.getenv('GOOGLE_CLOUD_PROJECT')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Initialize Vertex AI
        vertexai.init(project=project, location=location)
        
        # Create Agent Engine instance
        client = vertexai.Client(project=project, location=location)
        
        print("🔧 Creating Agent Engine...")
        agent_engine = client.agent_engines.create()
        agent_engine_id = agent_engine.api_resource.name.split("/")[-1]
        
        print(f"✅ Agent Engine created: {agent_engine_id}")
        
        # Setup Memory Bank service
        memory_service = VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Setup Session service
        session_service = VertexAiSessionService(
            project_id=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Create agent with memory capabilities
        agent = LlmAgent(
            name="memory_test_agent",
            model="gemini-2.0-flash",
            tools=[load_memory]
        )
        
        # Setup runner
        runner = Runner(
            agent=agent,
            memory_service=memory_service,
            session_service=session_service
        )
        
        print("🚀 Testing memory functionality...")
        
        # Test 1: Store information
        APP_NAME = "memory_test_app"
        USER_ID = "test_user_123"
        
        session1 = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id="test_session_1"
        )
        
        # Simulate user sharing preferences
        from google.genai.types import Content, Part
        user_input = Content(
            parts=[Part(text="Hi! I'm John and I prefer aisle seats when flying. I'm also vegetarian.")],
            role="user"
        )
        
        print("💬 User input: Hi! I'm John and I prefer aisle seats when flying. I'm also vegetarian.")
        
        # Process with agent
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id="test_session_1",
            new_message=user_input
        ):
            if hasattr(event, 'content'):
                print(f"🤖 Agent: {event.content}")
        
        # Add session to memory
        print("💾 Adding session to memory...")
        await memory_service.add_session_to_memory(session1)
        
        # Test 2: Create new session and retrieve memories
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
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id="test_session_2",
            new_message=query_input
        ):
            if hasattr(event, 'content'):
                print(f"🤖 Agent (with memory): {event.content}")
        
        print("✅ ADK Memory Bank test completed!")
        return True
        
    except Exception as e:
        print(f"❌ ADK Memory Bank test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧠 Google Memory Bank Test Suite")
    print("=" * 50)
    
    # Test 1: Check ADK availability
    print("\n1. Testing ADK availability...")
    adk_available = test_adk_availability()
    
    # Test 2: Check Gemini API
    print("\n2. Testing Gemini API...")
    gemini_available = test_gemini_api()
    
    # Test 3: ADK Memory Bank (if available)
    if adk_available and gemini_available:
        print("\n3. Testing ADK Memory Bank...")
        try:
            asyncio.run(test_adk_memory_bank())
        except Exception as e:
            print(f"❌ ADK test failed: {e}")
            print("💡 Try running simple_memory_test.py instead")
    else:
        print("\n3. Skipping ADK Memory Bank test (requirements not met)")
        print("💡 Try running simple_memory_test.py for a basic simulation")
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary:")
    print(f"  ADK Available: {'✅' if adk_available else '❌'}")
    print(f"  Gemini API: {'✅' if gemini_available else '❌'}")
    
    if not adk_available:
        print("\n📋 To use full Memory Bank:")
        print("  1. Install ADK: pip install google-adk[vertexai]")
        print("  2. Set GOOGLE_CLOUD_PROJECT in .env")
        print("  3. Configure Google Cloud authentication")
    
    if not gemini_available:
        print("\n📋 To use Gemini API:")
        print("  1. Install client: pip install google-generativeai")
        print("  2. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env")

if __name__ == "__main__":
    main()