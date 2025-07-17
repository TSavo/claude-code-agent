#!/usr/bin/env python3
"""
Combined Save and Load Context Hook
Loads relevant context before tool execution AND saves current context
"""

import json
import sys
import os
import asyncio
import time
from datetime import datetime
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

async def get_memory_and_session_services():
    """Get or create Memory Bank and Session services"""
    try:
        from google.adk.memory import VertexAiMemoryBankService
        from google.adk.sessions import VertexAiSessionService
        import vertexai
        
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        # Get or create agent engine
        agent_engines = list(client.agent_engines.list())
        if agent_engines:
            agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
        else:
            agent_engine = client.agent_engines.create()
            agent_engine_id = agent_engine.api_resource.name.split("/")[-1]
        
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
        
        return memory_service, session_service
        
    except Exception as e:
        print(f"🔧 Memory service setup failed: {e}", file=sys.stderr)
        return None, None

async def load_relevant_context(memory_service, tool_name, tool_input, session_id):
    """Load relevant context from Memory Bank"""
    if not memory_service:
        return []
    
    try:
        # Generate context queries
        queries = []
        project_name = os.path.basename(os.getcwd())
        
        if tool_name == "Edit":
            file_path = tool_input.get('file_path', '')
            if file_path:
                queries.extend([
                    f"editing {os.path.basename(file_path)}",
                    f"file {file_path}",
                    f"modifying {os.path.splitext(os.path.basename(file_path))[0]}"
                ])
        
        elif tool_name == "Write":
            file_path = tool_input.get('file_path', '')
            if file_path:
                queries.extend([
                    f"creating {os.path.basename(file_path)}",
                    f"new file {file_path}"
                ])
        
        elif tool_name == "Bash":
            command = tool_input.get('command', '')
            if command:
                cmd_parts = command.split()
                if cmd_parts:
                    queries.extend([
                        f"running {cmd_parts[0]}",
                        f"command {command}"
                    ])
        
        # Always add project context
        queries.extend([
            f"project {project_name}",
            "recent development",
            "current work"
        ])
        
        # Retrieve ALL memories for this user (we know this works!)
        all_memories = []
        try:
            import vertexai
            project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            vertexai.init(project=project, location=location)
            client = vertexai.Client(project=project, location=location)
            agent_engines = list(client.agent_engines.list())
            agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
            
            # Retrieve all memories for this user
            retrieved_memories = list(
                client.agent_engines.retrieve_memories(
                    name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                    scope={"user_id": session_id}
                )
            )
            
            print(f"🔍 Retrieved {len(retrieved_memories)} total memories for user", file=sys.stderr)
            
            # Convert to our format and filter by relevance to current queries
            for memory_item in retrieved_memories:
                fact = memory_item.memory.fact
                # Simple relevance check - if any query terms appear in the fact
                relevance_score = 0
                matched_queries = []
                
                for query in queries:
                    if any(word.lower() in fact.lower() for word in query.split() if len(word) > 2):
                        relevance_score += 1
                        matched_queries.append(query)
                
                # Always include memories, but give higher scores to more relevant ones
                all_memories.append({
                    "content": fact,
                    "score": relevance_score + 0.5,  # Base score so all memories have some value
                    "query": ", ".join(matched_queries) if matched_queries else "general context"
                })
                
        except Exception as e:
            print(f"🔍 Memory retrieval failed: {e}", file=sys.stderr)
        
        # Deduplicate and sort
        unique_memories = {}
        for mem in all_memories:
            content = mem['content']
            if content not in unique_memories or mem['score'] > unique_memories[content]['score']:
                unique_memories[content] = mem
        
        return sorted(unique_memories.values(), key=lambda x: x['score'], reverse=True)
        
    except Exception as e:
        print(f"🔍 Context loading failed: {e}", file=sys.stderr)
        return []

def load_session_mapping():
    """Load Claude session to Memory Bank session mapping"""
    mapping_file = Path.home() / ".claude" / "memory_bank_sessions.json"
    try:
        if mapping_file.exists():
            with open(mapping_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"📝 Failed to load session mapping: {e}", file=sys.stderr)
        return {}

def save_session_mapping(mapping):
    """Save Claude session to Memory Bank session mapping"""
    mapping_file = Path.home() / ".claude" / "memory_bank_sessions.json"
    try:
        mapping_file.parent.mkdir(exist_ok=True)
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f, indent=2)
        print(f"📝 Session mapping saved to {mapping_file}", file=sys.stderr)
    except Exception as e:
        print(f"📝 Failed to save session mapping: {e}", file=sys.stderr)

async def save_current_context(memory_service, session_service, claude_session_id, tool_name, tool_input, transcript_path=None):
    """Save current context to Memory Bank"""
    if not memory_service or not session_service:
        return
    
    try:
        # Get agent engine ID for REST API calls
        import vertexai
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        agent_engines = list(client.agent_engines.list())
        agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
        # Load session mapping
        session_mapping = load_session_mapping()
        print(f"🗂️ Loaded session mapping: {session_mapping}", file=sys.stderr)
        
        # Get or create Memory Bank session for this Claude session
        if claude_session_id not in session_mapping:
            print(f"🆕 Claude session {claude_session_id} not found in mapping, creating new...", file=sys.stderr)
            # Create new Memory Bank session
            memory_session = await session_service.create_session(
                app_name="claude-code",
                user_id=claude_session_id
            )
            session_mapping[claude_session_id] = memory_session.id
            save_session_mapping(session_mapping)
            print(f"🆕 Created new Memory Bank session: {memory_session.id}", file=sys.stderr)
        else:
            print(f"♻️ Reusing existing Memory Bank session for Claude session {claude_session_id}", file=sys.stderr)
        
        memory_session_id = session_mapping[claude_session_id]
        print(f"🔗 Using Memory Bank session: {memory_session_id}", file=sys.stderr)
        
        # Create context summary
        project_name = os.path.basename(os.getcwd())
        timestamp = datetime.now().isoformat()
        
        context_parts = [
            f"Project: {project_name}",
            f"Tool: {tool_name}",
            f"Time: {timestamp}"
        ]
        
        # Add tool-specific context
        if tool_name == "Edit":
            file_path = tool_input.get('file_path', '')
            old_string = tool_input.get('old_string', '')
            new_string = tool_input.get('new_string', '')
            
            if file_path:
                context_parts.append(f"Edited file: {file_path}")
            if old_string and new_string:
                context_parts.append(f"Changed: {old_string[:100]}... → {new_string[:100]}...")
        
        elif tool_name == "Write":
            file_path = tool_input.get('file_path', '')
            content = tool_input.get('content', '')
            
            if file_path:
                context_parts.append(f"Created file: {file_path}")
            if content:
                context_parts.append(f"Content preview: {content[:200]}...")
        
        elif tool_name == "Bash":
            command = tool_input.get('command', '')
            if command:
                context_parts.append(f"Executed: {command}")
        
        # Add conversation context if available
        if transcript_path and os.path.exists(transcript_path):
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                    # Extract recent conversation context (last 500 chars)
                    recent_context = transcript[-500:] if len(transcript) > 500 else transcript
                    context_parts.append(f"Recent conversation: {recent_context}")
            except Exception as e:
                print(f"📝 Failed to read transcript: {e}", file=sys.stderr)
        
        # Save context
        context_summary = " | ".join(context_parts)
        
        # Use the existing mapped session instead of creating new one
        try:
            # Get the existing mapped session
            print(f"🔍 DEBUG: Getting session with app_name='claude-code', user_id='{claude_session_id}', session_id='{memory_session_id}'", file=sys.stderr)
            session = await session_service.get_session(
                app_name="claude-code",
                user_id=claude_session_id,
                session_id=memory_session_id
            )
            print(f"🔍 DEBUG: Retrieved session {session.id}, type: {type(session)}", file=sys.stderr)
            
            # Use the existing session (don't create new one!)
            content_session = session
            
            # Add event to session using proper API format
            from google.cloud import aiplatform_v1beta1
            
            print(f"🔍 DEBUG: Adding event to session {memory_session_id}", file=sys.stderr)
            print(f"🔍 DEBUG: Context summary: {context_summary[:200]}...", file=sys.stderr)
            
            # Create proper session client
            project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            
            sessions_client = aiplatform_v1beta1.SessionServiceClient(
                client_options={
                    "api_endpoint": f"https://{location}-aiplatform.googleapis.com"
                },
                transport="rest"
            )
            
            # Create session name format
            session_name = f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}/sessions/{memory_session_id}"
            
            # Create event in proper format
            event = aiplatform_v1beta1.SessionEvent(
                author="user",
                invocation_id=str(int(time.time())),
                timestamp=datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                content=aiplatform_v1beta1.Content(
                    role="user",
                    parts=[aiplatform_v1beta1.Part(text=f"Context: {context_summary}")]
                )
            )
            
            # Append event to session
            sessions_client.append_event(name=session_name, event=event)
            print(f"🔍 DEBUG: Added event to session via REST API", file=sys.stderr)
            
            # Generate memories from the session
            print(f"🔍 DEBUG: About to generate memories for session {memory_session_id}", file=sys.stderr)
            
            # Generate memories using client approach
            client.agent_engines.generate_memories(
                name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                vertex_session_source={
                    "session": session_name
                },
                scope={"user_id": claude_session_id}
            )
            print(f"💾 Generated memories for session {memory_session_id} in Memory Bank", file=sys.stderr)
            
        except Exception as e:
            print(f"💾 Memory Bank save failed: {e}", file=sys.stderr)
            print(f"💾 Context was: {context_summary[:200]}...", file=sys.stderr)
        
    except Exception as e:
        print(f"💾 Context saving failed: {e}", file=sys.stderr)

def display_context_to_claude(memories, tool_name):
    """Display context in a way Claude will see and understand"""
    if not memories:
        return
    
    print("\n" + "="*60)
    print("🧠 MEMORY BANK CONTEXT LOADED")
    print("="*60)
    print(f"Found {len(memories)} relevant memories for {tool_name}:")
    print()
    
    for i, memory in enumerate(memories[:3]):  # Show top 3
        score = memory.get('score', 0)
        content = memory.get('content', '')
        query = memory.get('query', 'general')
        
        print(f"💭 Memory {i+1} (relevance: {score:.2f}, query: '{query}'):")
        print(f"   {content}")
        print()
    
    if len(memories) > 3:
        print(f"   ... and {len(memories) - 3} more memories")
    
    print("="*60)
    print("You can reference this context in your response.")
    print("="*60 + "\n")

async def main():
    """Main hook function - loads context before tool execution"""
    try:
        # Read hook input
        hook_data = json.load(sys.stdin)
        
        # Debug: Print all available hook data
        print(f"🔍 Hook data keys: {list(hook_data.keys())}", file=sys.stderr)
        
        tool_name = hook_data.get('tool_name', 'unknown')
        tool_input = hook_data.get('tool_input', {})
        session_id = hook_data.get('session_id', 'default')
        transcript_path = hook_data.get('transcript_path')
        
        # Look for other session-related data
        if transcript_path:
            print(f"📝 Transcript path: {transcript_path}", file=sys.stderr)
        
        # Skip for simple tools
        if tool_name in ['LS', 'Glob', 'Grep']:
            sys.exit(0)
        
        print(f"🔄 Processing {tool_name} with Memory Bank integration...")
        
        # Get memory and session services
        memory_service, session_service = await get_memory_and_session_services()
        
        # Load relevant context
        memories = await load_relevant_context(memory_service, tool_name, tool_input, session_id)
        
        # Display context to Claude
        if memories:
            display_context_to_claude(memories, tool_name)
        else:
            print("💭 No relevant context found in Memory Bank")
        
        # Save current context for future use
        await save_current_context(memory_service, session_service, session_id, tool_name, tool_input, transcript_path)
        
        # Always succeed - don't block tool execution
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Hook failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        # Don't block tool execution
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())