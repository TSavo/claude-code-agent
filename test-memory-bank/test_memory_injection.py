#!/usr/bin/env python3
"""
Test memory injection by creating a proper session with content
"""

import asyncio
import os
from datetime import datetime

async def create_test_memory():
    """Create a test memory that the hooks can find"""
    try:
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.session import VertexAiSessionService
        from google.adk.agents import AgentRunner
        from vertexai.generative_models import Content, Part
        import vertexai
        
        project = 'gen-lang-client-0220754900'
        location = 'us-central1'
        
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        # Get agent engine
        agent_engines = list(client.agent_engines.list())
        agent_engine_id = agent_engines[0].api_resource.name.split('/')[-1]
        
        # Create services
        memory_service = VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        session_service = VertexAiSessionService(
            project_id=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Create agent runner
        runner = AgentRunner(
            memory_service=memory_service,
            session_service=session_service,
            app_name="claude-code-test"
        )
        
        print("🧪 Creating test memory with actual content...")
        
        # Create session
        session = await session_service.create_session(
            app_name="claude-code-test",
            user_id="a649ac00-90d0-412b-a1d1-b13fa0414df3"
        )
        
        # Create user input about toolstac project
        user_input = Content(
            parts=[Part(text="I'm working on toolstac.com project with Next.js, Redis, and AI agents. I prefer TypeScript strict mode and environment variables for configuration.")],
            role="user"
        )
        
        print("💬 Processing user message through agent...")
        
        # Process through agent to build session
        responses = []
        async for event in runner.run_async(
            user_id="a649ac00-90d0-412b-a1d1-b13fa0414df3",
            session_id=session.id,
            new_message=user_input
        ):
            if hasattr(event, 'content'):
                content = str(event.content)
                responses.append(content)
                print(f"🤖 Agent: {content}")
        
        # Save session to memory
        print("💾 Saving session to Memory Bank...")
        await memory_service.add_session_to_memory(session)
        print("✅ Test memory created!")
        
        # Search for it
        print("🔍 Searching for the test memory...")
        result = await memory_service.search_memory(
            app_name="claude-code-test",
            user_id="a649ac00-90d0-412b-a1d1-b13fa0414df3",
            query="toolstac project"
        )
        
        print(f"Found {len(result.memories)} memories:")
        for i, memory in enumerate(result.memories):
            print(f"  {i+1}. {memory.content[:200]}...")
        
        return len(result.memories) > 0
        
    except Exception as e:
        print(f"❌ Test memory creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(create_test_memory())
    print(f"🎯 Memory injection test: {'✅ PASSED' if success else '❌ FAILED'}")