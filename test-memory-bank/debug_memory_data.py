#!/usr/bin/env python3
"""
Debug script to show exactly what data is being passed to Memory Bank
"""

import json
import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

async def debug_memory_data():
    """Show exactly what data is being passed to Memory Bank"""
    try:
        from hooks.save_and_load_context import get_memory_and_session_services
        
        # Get services
        memory_service, session_service = await get_memory_and_session_services()
        
        if not memory_service or not session_service:
            print("❌ Failed to get services")
            return
        
        # Simulate the data that would be sent to Memory Bank
        claude_session_id = "a649ac00-90d0-412b-a1d1-b13fa0414df3"
        project_name = "test-memory-bank"
        timestamp = datetime.now().isoformat()
        
        # Example 1: PreToolUse context data
        print("="*60)
        print("🔍 PRETOOLUSE DATA BEING SENT TO MEMORY BANK:")
        print("="*60)
        
        tool_name = "Edit"
        tool_input = {
            "file_path": "/path/to/file.py",
            "old_string": "print('old')",
            "new_string": "print('new')"
        }
        
        # Simulate conversation transcript
        transcript_content = """
**Human:** Can you help me fix this Python file?

**Assistant:** I'll help you fix the Python file. Let me take a look at it first.

**Human:** Change the print statement to say 'new' instead of 'old'

**Assistant:** I'll edit the file to change the print statement.
        """
        
        context_parts = [
            f"Project: {project_name}",
            f"Tool: {tool_name}",
            f"Time: {timestamp}",
            f"Edited file: {tool_input['file_path']}",
            f"Changed: {tool_input['old_string']} → {tool_input['new_string']}",
            f"Recent conversation: {transcript_content[-300:]}"
        ]
        
        context_summary = " | ".join(context_parts)
        
        print(f"📝 Context Summary Length: {len(context_summary)} characters")
        print(f"📝 Context Summary Preview:")
        print(f"   {context_summary[:200]}...")
        print()
        
        # This is the exact message sent to the agent
        user_message = f"Context: {context_summary}"
        print(f"💬 Exact User Message to Agent:")
        print(f"   Role: user")
        print(f"   Content: {user_message}")
        print()
        
        # Example 2: PostToolUse result data
        print("="*60)
        print("📤 POSTTOOLUSE DATA BEING SENT TO MEMORY BANK:")
        print("="*60)
        
        tool_output = "File edited successfully"
        success = True
        
        result_parts = [
            f"Project: {project_name}",
            f"Tool: {tool_name}",
            f"Success: {success}",
            f"Time: {timestamp}",
            f"Edited file: {tool_input['file_path']}",
            f"Edit completed successfully",
            f"Recent conversation: {transcript_content[-300:]}"
        ]
        
        result_summary = " | ".join(result_parts)
        
        print(f"📝 Result Summary Length: {len(result_summary)} characters")
        print(f"📝 Result Summary Preview:")
        print(f"   {result_summary[:200]}...")
        print()
        
        # This is the exact message sent to the agent
        user_message = f"Tool Result: {result_summary}"
        print(f"💬 Exact User Message to Agent:")
        print(f"   Role: user")
        print(f"   Content: {user_message}")
        print()
        
        # Example 3: Stop session data
        print("="*60)
        print("🛑 STOP SESSION DATA BEING SENT TO MEMORY BANK:")
        print("="*60)
        
        full_transcript = transcript_content + """
**Assistant:** I've successfully edited the file to change the print statement from 'old' to 'new'. The change has been applied.

**Human:** Great! Thanks for the help.

**Assistant:** You're welcome! The file has been updated successfully.
        """
        
        lines = full_transcript.split('\n')
        user_messages = [l for l in lines if l.startswith('**Human:**')]
        assistant_messages = [l for l in lines if l.startswith('**Assistant:**')]
        
        session_parts = [
            f"Project: {project_name}",
            f"Session completed: {timestamp}",
            f"Session type: Complete conversation summary",
            f"User messages: {len(user_messages)}",
            f"Assistant messages: {len(assistant_messages)}",
            f"Total conversation length: {len(full_transcript)} chars",
            f"Full session: {full_transcript}"
        ]
        
        session_summary = " | ".join(session_parts)
        
        print(f"📝 Session Summary Length: {len(session_summary)} characters")
        print(f"📝 Session Summary Preview:")
        print(f"   {session_summary[:200]}...")
        print()
        
        # This is the exact message sent to the agent
        user_message = f"Session Summary: {session_summary}"
        print(f"💬 Exact User Message to Agent:")
        print(f"   Role: user")
        print(f"   Content: {user_message}")
        print()
        
        # Example 4: Notification data
        print("="*60)
        print("🔔 NOTIFICATION DATA BEING SENT TO MEMORY BANK:")
        print("="*60)
        
        notification_type = "system_event"
        message = "File system change detected"
        
        notification_parts = [
            f"Project: {project_name}",
            f"Notification: {notification_type}",
            f"Message: {message}",
            f"Time: {timestamp}"
        ]
        
        notification_summary = " | ".join(notification_parts)
        
        print(f"📝 Notification Summary Length: {len(notification_summary)} characters")
        print(f"📝 Notification Summary:")
        print(f"   {notification_summary}")
        print()
        
        # This is the exact message sent to the agent
        user_message = f"Notification: {notification_summary}"
        print(f"💬 Exact User Message to Agent:")
        print(f"   Role: user")
        print(f"   Content: {user_message}")
        print()
        
        print("="*60)
        print("🎯 SUMMARY OF MEMORY BANK DATA FLOW:")
        print("="*60)
        print("1. Each hook creates a structured summary of context/results")
        print("2. Summary is passed as 'user' message to Vertex AI agent")
        print("3. Agent processes the message and generates a response")
        print("4. The complete user/agent conversation is stored in a new session")
        print("5. Session is saved to Memory Bank via add_session_to_memory()")
        print("6. Memory Bank processes the session into searchable memories")
        print("7. Future searches can find these memories for context injection")
        print("="*60)
        
        # Show the agent processing flow
        print("\n🤖 AGENT PROCESSING FLOW:")
        print("   User Message: 'Context: Project: test-memory-bank | Tool: Edit | ...'")
        print("   ↓")
        print("   Agent Response: 'I understand you're working on editing a file...'")
        print("   ↓")
        print("   Complete Session: [User Message] + [Agent Response]")
        print("   ↓")
        print("   Memory Bank Storage: Session with searchable content")
        print("   ↓")
        print("   Future Searches: 'editing file' → Returns relevant memories")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_memory_data())