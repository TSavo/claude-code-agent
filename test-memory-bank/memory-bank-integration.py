#!/usr/bin/env python3
"""
Memory Bank Integration Script for Multi-Agent System
Called from Node.js to store conversation data
"""

import json
import sys
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

async def store_conversation_data(claude_session_id: str, message_type: str, content: str):
    """Store conversation data in Memory Bank"""
    try:
        # Updated imports for new Memory Bank API
        import vertexai
        from google.cloud import aiplatform_v1beta1
        
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Initialize Vertex AI Client (new API)
        client = vertexai.Client(project=project, location=location)
        
        # Get agent engine
        agent_engines = list(client.agent_engines.list())
        if not agent_engines:
            print(f"⚠️ No agent engines found", file=sys.stderr)
            return
            
        agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
        
        # Load or create session mapping
        mapping_file = os.path.expanduser('~/.claude/memory_bank_sessions.json')
        session_mapping = {}
        
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                session_mapping = json.load(f)
        
        # Get or create Memory Bank session
        if claude_session_id not in session_mapping:
            from google.adk.sessions import VertexAiSessionService
            
            session_service = VertexAiSessionService(
                project=project,
                location=location,
                agent_engine_id=agent_engine_id
            )
            
            memory_session = await session_service.create_session(
                app_name="claude-code-multi-agent",
                user_id=claude_session_id
            )
            
            session_mapping[claude_session_id] = memory_session.id
            
            # Save mapping
            os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
            with open(mapping_file, 'w') as f:
                json.dump(session_mapping, f)
                
            print(f"🧠 Created Memory Bank session {memory_session.id}", file=sys.stderr)
        
        memory_session_id = session_mapping[claude_session_id]
        
        # Create proper session client
        sessions_client = aiplatform_v1beta1.SessionServiceClient(
            client_options={
                "api_endpoint": f"https://{location}-aiplatform.googleapis.com"
            },
            transport="rest"
        )
        
        # Create session name format
        session_name = f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}/sessions/{memory_session_id}"
        
        # Format content with proper conversational context
        if message_type == 'user_prompt':
            formatted_content = f"User said: {content}"
        elif message_type == 'assistant':
            formatted_content = f"Claude responded: {content}"
        elif message_type == 'user':
            formatted_content = f"Tool returned: {content}"
        elif message_type == 'result':
            formatted_content = f"Final result: {content}"
        else:
            formatted_content = f"{message_type}: {content}"
        
        # Create event in proper format with contextual content
        event = aiplatform_v1beta1.SessionEvent(
            author="user" if message_type in ['user', 'user_prompt'] else "assistant",
            invocation_id=str(int(time.time())),
            timestamp=datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            content=aiplatform_v1beta1.Content(
                role="user" if message_type in ['user', 'user_prompt'] else "assistant",
                parts=[aiplatform_v1beta1.Part(text=formatted_content)]
            )
        )
        
        # Append event to session
        sessions_client.append_event(name=session_name, event=event)
        
        print(f"💾 Stored {message_type} in Memory Bank session {memory_session_id}", file=sys.stderr)
        
        return True
        
    except Exception as e:
        print(f"❌ Memory Bank storage failed: {e}", file=sys.stderr)
        return False

async def generate_memories(claude_session_id: str):
    """Generate memories from accumulated conversation data"""
    try:
        import vertexai
        
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        agent_engines = list(client.agent_engines.list())
        agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
        
        # Load session mapping
        mapping_file = os.path.expanduser('~/.claude/memory_bank_sessions.json')
        if not os.path.exists(mapping_file):
            return False
            
        with open(mapping_file, 'r') as f:
            session_mapping = json.load(f)
            
        if claude_session_id not in session_mapping:
            return False
            
        memory_session_id = session_mapping[claude_session_id]
        session_name = f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}/sessions/{memory_session_id}"
        
        # Generate memories
        client.agent_engines.generate_memories(
            name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
            vertex_session_source={"session": session_name},
            scope={"user_id": claude_session_id}
        )
        
        print(f"🧠 Generated memories for session {memory_session_id}", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ Memory generation failed: {e}", file=sys.stderr)
        return False

async def retrieve_relevant_memories(claude_session_id: str, context_hint: str = ""):
    """Retrieve relevant memories and write to context file"""
    try:
        import vertexai
        
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        agent_engines = list(client.agent_engines.list())
        agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
        
        # Retrieve all memories for this user (our approach that works!)
        retrieved_memories = list(
            client.agent_engines.retrieve_memories(
                name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                scope={"user_id": claude_session_id}
            )
        )
        
        if not retrieved_memories:
            print(f"💭 No memories found for user {claude_session_id}", file=sys.stderr)
            return False
        
        print(f"🔍 Retrieved {len(retrieved_memories)} memories", file=sys.stderr)
        
        # Generate context queries based on hint
        queries = []
        if context_hint:
            # Extract potential query terms from context hint
            words = context_hint.lower().split()
            queries = [word for word in words if len(word) > 3]
        
        # Add default broad queries
        queries.extend(['edit', 'file', 'project', 'tool', 'command', 'recent', 'work'])
        
        # Score memories for relevance
        scored_memories = []
        for memory_item in retrieved_memories:
            fact = memory_item.memory.fact
            relevance_score = 0
            matched_queries = []
            
            for query in queries:
                if query.lower() in fact.lower():
                    relevance_score += 1
                    matched_queries.append(query)
            
            # Always include memories, but give higher scores to more relevant ones
            scored_memories.append({
                "fact": fact,
                "score": relevance_score + 0.5,  # Base score so all memories have some value
                "matched_queries": matched_queries
            })
        
        # Sort by relevance score (descending) and take top 10
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        top_memories = scored_memories[:10]
        
        # Write to session-specific context injection file
        context_dir = os.path.expanduser('~/.claude/memory_contexts')
        os.makedirs(context_dir, exist_ok=True)
        context_file = os.path.join(context_dir, f'{claude_session_id}.txt')
        
        with open(context_file, 'w') as f:
            f.write("============================================================\n")
            f.write("🧠 MEMORY BANK CONTEXT LOADED\n")
            f.write("============================================================\n")
            f.write(f"Found {len(top_memories)} relevant memories:\n\n")
            
            for i, memory in enumerate(top_memories, 1):
                f.write(f"💭 Memory {i} (relevance: {memory['score']:.2f}):\n")
                f.write(f"   {memory['fact']}\n\n")
            
            f.write("============================================================\n")
            f.write("You can reference this context in your response.\n")
            f.write("============================================================\n")
        
        print(f"📝 Wrote {len(top_memories)} memories to context file", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ Memory retrieval failed: {e}", file=sys.stderr)
        return False

async def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("Usage: python memory-bank-integration.py <action> <claude_session_id> [args...]")
        sys.exit(1)
    
    action = sys.argv[1]
    claude_session_id = sys.argv[2]
    
    if action == "store":
        if len(sys.argv) < 5:
            print("Usage: python memory-bank-integration.py store <claude_session_id> <message_type> <content>")
            sys.exit(1)
        message_type = sys.argv[3]
        content = sys.argv[4]
        
        success = await store_conversation_data(claude_session_id, message_type, content)
        sys.exit(0 if success else 1)
        
    elif action == "generate":
        success = await generate_memories(claude_session_id)
        sys.exit(0 if success else 1)
        
    elif action == "retrieve":
        context_hint = sys.argv[3] if len(sys.argv) > 3 else ""
        success = await retrieve_relevant_memories(claude_session_id, context_hint)
        sys.exit(0 if success else 1)
        
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())