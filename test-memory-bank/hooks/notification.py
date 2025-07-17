#!/usr/bin/env python3
"""
Notification Hook for Memory Bank Integration
Captures system events and notifications
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

async def save_notification_context(memory_service, session_service, claude_session_id, notification_type, message, transcript_path=None):
    """Save notification context to Memory Bank"""
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
        
        # Create notification context
        project_name = os.path.basename(os.getcwd())
        timestamp = datetime.now().isoformat()
        
        context_parts = [
            f"Project: {project_name}",
            f"Notification: {notification_type}",
            f"Message: {message}",
            f"Time: {timestamp}"
        ]
        
        # Create notification summary
        notification_summary = " | ".join(context_parts)
        
        # Add notification using working REST API approach
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
                author="system",  # System notification
                invocation_id=str(int(time.time())),
                timestamp=datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                content=aiplatform_v1beta1.Content(
                    role="user",
                    parts=[aiplatform_v1beta1.Part(text=f"Notification: {notification_summary}")]
                )
            )
            
            # Append event to session
            sessions_client.append_event(name=session_name, event=event)
            print(f"🔍 DEBUG: Added notification event to session", file=sys.stderr)
            
            # Generate memories from the session
            client.agent_engines.generate_memories(
                name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                vertex_session_source={
                    "session": session_name
                },
                scope={"user_id": claude_session_id}
            )
            print(f"💾 Saved notification to Memory Bank: {notification_type}", file=sys.stderr)
            
        except Exception as e:
            print(f"💾 Memory Bank notification save failed: {e}", file=sys.stderr)
        
    except Exception as e:
        print(f"💾 Notification context saving failed: {e}", file=sys.stderr)

async def main():
    """Main Notification hook function"""
    try:
        # Read hook input
        hook_data = json.load(sys.stdin)
        
        session_id = hook_data.get('session_id', 'default')
        transcript_path = hook_data.get('transcript_path')
        notification_type = hook_data.get('type', 'unknown')
        message = hook_data.get('message', '')
        
        print(f"🔔 Notification: {notification_type} - {message}", file=sys.stderr)
        
        # Get services
        memory_service, session_service = await get_memory_and_session_services()
        
        # Save notification context
        await save_notification_context(
            memory_service, session_service, session_id, 
            notification_type, message, transcript_path
        )
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Notification hook failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())