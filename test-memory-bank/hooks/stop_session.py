#!/usr/bin/env python3
"""
Stop Hook for Memory Bank Integration
Captures complete session summaries when conversation ends
"""

import json
import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from save_and_load_context import (
    get_memory_and_session_services,
    load_session_mapping,
    save_session_mapping
)

async def save_session_summary(memory_service, session_service, claude_session_id, transcript_path=None):
    """Save complete session summary to Memory Bank"""
    if not memory_service or not session_service:
        return
    
    try:
        # Load session mapping
        session_mapping = load_session_mapping()
        
        # Get or create Memory Bank session
        if claude_session_id not in session_mapping:
            memory_session = await session_service.create_session(
                app_name="claude-code",
                user_id=claude_session_id
            )
            session_mapping[claude_session_id] = memory_session.id
            save_session_mapping(session_mapping)
            print(f"🆕 Created new Memory Bank session: {memory_session.id}", file=sys.stderr)
        
        memory_session_id = session_mapping[claude_session_id]
        
        # Create session summary
        project_name = os.path.basename(os.getcwd())
        timestamp = datetime.now().isoformat()
        
        context_parts = [
            f"Project: {project_name}",
            f"Session completed: {timestamp}",
            f"Session type: Complete conversation summary"
        ]
        
        # Add full conversation context if available
        if transcript_path and os.path.exists(transcript_path):
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                    
                    # Extract session statistics
                    lines = transcript.split('\n')
                    user_messages = [l for l in lines if l.startswith('**Human:**')]
                    assistant_messages = [l for l in lines if l.startswith('**Assistant:**')]
                    
                    context_parts.extend([
                        f"User messages: {len(user_messages)}",
                        f"Assistant messages: {len(assistant_messages)}",
                        f"Total conversation length: {len(transcript)} chars"
                    ])
                    
                    # Add conversation summary (last 1000 chars)
                    if len(transcript) > 1000:
                        summary_context = transcript[-1000:]
                        context_parts.append(f"Session summary: {summary_context}")
                    else:
                        context_parts.append(f"Full session: {transcript}")
                        
            except Exception as e:
                print(f"📝 Failed to read transcript: {e}", file=sys.stderr)
        
        # Create complete summary
        session_summary = " | ".join(context_parts)
        
        # Add session summary using working REST API approach
        try:
            # Get agent engine ID for REST API calls
            import vertexai
            import time
            from google.cloud import aiplatform_v1beta1
            
            project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            vertexai.init(project=project, location=location)
            client = vertexai.Client(project=project, location=location)
            agent_engines = list(client.agent_engines.list())
            agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
            
            # Get existing session
            session = await session_service.get_session(
                app_name="claude-code",
                user_id=claude_session_id,
                session_id=memory_session_id
            )
            
            # Create proper session client
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
                    parts=[aiplatform_v1beta1.Part(text=f"Session Summary: {session_summary}")]
                )
            )
            
            # Append event to session
            sessions_client.append_event(name=session_name, event=event)
            print(f"🔍 DEBUG: Added session summary event to session", file=sys.stderr)
            
            # Generate memories from the session
            client.agent_engines.generate_memories(
                name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                vertex_session_source={
                    "session": session_name
                },
                scope={"user_id": claude_session_id}
            )
            print(f"💾 Saved complete session summary to Memory Bank", file=sys.stderr)
            
        except Exception as e:
            print(f"💾 Memory Bank session summary save failed: {e}", file=sys.stderr)
        
    except Exception as e:
        print(f"💾 Session summary saving failed: {e}", file=sys.stderr)

async def main():
    """Main Stop hook function"""
    try:
        # Read hook input
        hook_data = json.load(sys.stdin)
        
        session_id = hook_data.get('session_id', 'default')
        transcript_path = hook_data.get('transcript_path')
        
        print(f"🛑 Session ending: {session_id}", file=sys.stderr)
        
        # Get services
        memory_service, session_service = await get_memory_and_session_services()
        
        # Save session summary
        await save_session_summary(
            memory_service, session_service, session_id, transcript_path
        )
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Stop hook failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())