#!/usr/bin/env python3
"""
PostToolUse Hook for Memory Bank Integration
Captures tool results and outcomes after execution
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

async def save_tool_result_context(memory_service, session_service, claude_session_id, tool_name, tool_input, tool_output, success, transcript_path=None):
    """Save tool execution results to Memory Bank"""
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
        
        # Create result context
        project_name = os.path.basename(os.getcwd())
        timestamp = datetime.now().isoformat()
        
        context_parts = [
            f"Project: {project_name}",
            f"Tool: {tool_name}",
            f"Success: {success}",
            f"Time: {timestamp}"
        ]
        
        # Add tool-specific result context
        if tool_name == "Edit":
            file_path = tool_input.get('file_path', '')
            if file_path:
                context_parts.append(f"Edited file: {file_path}")
            if success:
                context_parts.append("Edit completed successfully")
            else:
                context_parts.append("Edit failed")
        
        elif tool_name == "Write":
            file_path = tool_input.get('file_path', '')
            if file_path:
                context_parts.append(f"Created file: {file_path}")
            if success:
                context_parts.append("File creation successful")
            else:
                context_parts.append("File creation failed")
        
        elif tool_name == "Bash":
            command = tool_input.get('command', '')
            if command:
                context_parts.append(f"Executed: {command}")
            if success:
                context_parts.append("Command executed successfully")
                # Add output preview if available
                if tool_output and len(str(tool_output)) > 0:
                    output_preview = str(tool_output)[:200].replace('\n', ' ')
                    context_parts.append(f"Output: {output_preview}")
            else:
                context_parts.append("Command failed")
        
        elif tool_name == "Read":
            file_path = tool_input.get('file_path', '')
            if file_path:
                context_parts.append(f"Read file: {file_path}")
            if success:
                context_parts.append("File read successfully")
            else:
                context_parts.append("File read failed")
        
        # Add conversation context if available
        if transcript_path and os.path.exists(transcript_path):
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                    # Extract recent conversation context (last 300 chars)
                    recent_context = transcript[-300:] if len(transcript) > 300 else transcript
                    context_parts.append(f"Recent conversation: {recent_context}")
            except Exception as e:
                print(f"📝 Failed to read transcript: {e}", file=sys.stderr)
        
        # Create result summary
        result_summary = " | ".join(context_parts)
        
        # Add tool result to session using working REST API approach
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
                    parts=[aiplatform_v1beta1.Part(text=f"Tool Result: {result_summary}")]
                )
            )
            
            # Append event to session
            sessions_client.append_event(name=session_name, event=event)
            print(f"🔍 DEBUG: Added tool result event to session", file=sys.stderr)
            
            # Generate memories from the session
            client.agent_engines.generate_memories(
                name=f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}",
                vertex_session_source={
                    "session": session_name
                },
                scope={"user_id": claude_session_id}
            )
            print(f"💾 Saved tool result to Memory Bank: {tool_name} {'✅' if success else '❌'}", file=sys.stderr)
            
        except Exception as e:
            print(f"💾 Memory Bank result save failed: {e}", file=sys.stderr)
        
    except Exception as e:
        print(f"💾 Tool result context saving failed: {e}", file=sys.stderr)

async def main():
    """Main PostToolUse hook function"""
    try:
        # Read hook input
        hook_data = json.load(sys.stdin)
        
        tool_name = hook_data.get('tool_name', 'unknown')
        tool_input = hook_data.get('tool_input', {})
        tool_output = hook_data.get('tool_output', '')
        session_id = hook_data.get('session_id', 'default')
        transcript_path = hook_data.get('transcript_path')
        success = hook_data.get('success', True)
        
        print(f"📤 PostToolUse: {tool_name} {'✅' if success else '❌'}", file=sys.stderr)
        
        # Get services
        memory_service, session_service = await get_memory_and_session_services()
        
        # Save tool result context
        await save_tool_result_context(
            memory_service, session_service, session_id, 
            tool_name, tool_input, tool_output, success, transcript_path
        )
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ PostToolUse hook failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())