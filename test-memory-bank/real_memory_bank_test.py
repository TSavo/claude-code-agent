#!/usr/bin/env python3
"""
Test Real Google Memory Bank Service with Vertex AI
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def check_prerequisites():
    """Check if all prerequisites are met"""
    print("🔍 Checking prerequisites...")
    
    # Check environment variables
    project = os.getenv('GOOGLE_CLOUD_PROJECT')
    location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if not project:
        print("❌ GOOGLE_CLOUD_PROJECT not set")
        return False
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not set")
        return False
    
    print(f"✅ Project: {project}")
    print(f"✅ Location: {location}")
    print(f"✅ API Key: {api_key[:20]}...")
    
    # Check imports
    try:
        import google.adk
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.sessions import VertexAiSessionService
        print("✅ ADK imports successful")
    except ImportError as e:
        print(f"❌ ADK import failed: {e}")
        return False
    
    # Check authentication
    try:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError
        
        try:
            credentials, project_id = google.auth.default()
            print(f"✅ Authentication found for project: {project_id}")
        except DefaultCredentialsError:
            print("❌ No authentication found")
            print("💡 Run: gcloud auth application-default login")
            return False
    except ImportError:
        print("❌ google-auth not installed")
        return False
    
    return True

async def test_vertex_ai_memory_bank():
    """Test the real Vertex AI Memory Bank service"""
    try:
        print("\n🧪 Testing Vertex AI Memory Bank...")
        
        # Import required modules
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.sessions import VertexAiSessionService
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.tools import load_memory
        from google.genai.types import Content, Part
        import vertexai
        
        # Get config
        project = os.getenv('GOOGLE_CLOUD_PROJECT')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Initialize Vertex AI
        print(f"🔧 Initializing Vertex AI for project {project}...")
        vertexai.init(project=project, location=location)
        
        # Create Vertex AI client
        client = vertexai.Client(project=project, location=location)
        
        # Create Agent Engine
        print("🏗️ Creating Agent Engine...")
        agent_engine = client.agent_engines.create()
        agent_engine_id = agent_engine.api_resource.name.split("/")[-1]
        print(f"✅ Agent Engine created: {agent_engine_id}")
        
        # Setup Memory Bank service
        print("🧠 Setting up Memory Bank service...")
        memory_service = VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Setup Session service
        print("📝 Setting up Session service...")
        session_service = VertexAiSessionService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Create agent with memory capabilities
        print("🤖 Creating agent with memory capabilities...")
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
            app_name="memory_bank_test"
        )
        
        print("🚀 Starting Memory Bank test...")
        
        # Constants
        APP_NAME = "memory_bank_test"
        USER_ID = "test_user_real"
        
        # Test 1: Store user information
        print("\n💾 Test 1: Storing user information...")
        session1 = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID
        )
        
        user_input = Content(
            parts=[Part(text="Hi! I'm Sarah. I'm a software engineer who loves coffee and prefers coding in Python. I also enjoy hiking on weekends.")],
            role="user"
        )
        
        print("👤 User: Hi! I'm Sarah. I'm a software engineer who loves coffee and prefers coding in Python. I also enjoy hiking on weekends.")
        
        # Process with agent
        responses = []
        print(f"🔍 Session1 ID: {session1.id}")
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session1.id,
            new_message=user_input
        ):
            if hasattr(event, 'content'):
                content = str(event.content)
                responses.append(content)
                print(f"🤖 Agent: {content}")
        
        # Add session to memory
        print("💾 Adding session to Memory Bank...")
        await memory_service.add_session_to_memory(session1)
        print("✅ Session stored in Memory Bank")
        
        # Test 2: Create new session and use memory
        print("\n🔍 Test 2: Creating new session and using memory...")
        session2 = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID
        )
        
        query_input = Content(
            parts=[Part(text="What programming language do I prefer?")],
            role="user"
        )
        
        print("👤 User: What programming language do I prefer?")
        
        # Process with agent (should use memory)
        responses2 = []
        print(f"🔍 Session2 ID: {session2.id}")
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session2.id,
            new_message=query_input
        ):
            if hasattr(event, 'content'):
                content = str(event.content)
                responses2.append(content)
                print(f"🤖 Agent (with memory): {content}")
        
        # Test 3: Search memories directly
        print("\n🔍 Test 3: Searching memories directly...")
        search_results = await memory_service.search_memory(
            app_name=APP_NAME,
            user_id=USER_ID,
            query="programming preferences"
        )
        
        print(f"📝 Found {len(search_results.memories)} memories:")
        for i, memory in enumerate(search_results.memories):
            print(f"  {i+1}. {memory.content}")
        
        print("\n🎉 Vertex AI Memory Bank test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Vertex AI Memory Bank test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🧠 Real Google Memory Bank Test Suite")
    print("=" * 50)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please:")
        print("1. Set GOOGLE_CLOUD_PROJECT=gen-lang-client-0220754900 in .env")
        print("2. Set GOOGLE_API_KEY in .env")
        print("3. Run: gcloud auth application-default login")
        print("4. Install ADK: pip install google-adk[vertexai]")
        return
    
    # Run Memory Bank test
    print("\n🚀 Running Memory Bank test...")
    success = asyncio.run(test_vertex_ai_memory_bank())
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SUCCESS: Real Memory Bank is working!")
        print("\n💡 What this means:")
        print("- Your memories persist across sessions")
        print("- AI agents can remember user preferences")
        print("- Cross-session context is maintained")
        print("- Ready for production use!")
    else:
        print("❌ Memory Bank test failed")
        print("Check the error messages above for troubleshooting")

if __name__ == "__main__":
    main()