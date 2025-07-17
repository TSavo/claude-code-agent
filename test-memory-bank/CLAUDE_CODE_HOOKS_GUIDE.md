# Claude Code Hooks Guide for Memory Bank Integration

## How Claude Code Hooks Work

Claude Code hooks are **user-defined shell commands** that execute automatically at specific points in Claude's lifecycle. They provide control over Claude's behavior and can intercept, modify, or enhance tool usage.

## Hook Types

### 1. **PreToolUse** 
- **When**: Before Claude uses any tool
- **Purpose**: Validation, blocking, preprocessing
- **Can**: Block tool execution, provide feedback
- **Use case**: Save conversation context before tool use

### 2. **PostToolUse**
- **When**: After tool completes successfully  
- **Purpose**: Validation, cleanup, post-processing
- **Can**: Block completion, provide feedback
- **Use case**: Store tool results in memory

### 3. **Stop**
- **When**: When Claude finishes responding
- **Purpose**: Completion actions, cleanup
- **Can**: Force Claude to continue
- **Use case**: Save entire conversation to Memory Bank

### 4. **Notification**
- **When**: Claude sends notifications
- **Purpose**: Custom alerts, integrations
- **Use case**: Trigger memory operations

### 5. **SubagentStop**
- **When**: Subagent tasks complete
- **Purpose**: Subagent coordination
- **Use case**: Coordinate multi-agent memory

## Hook Configuration

### Location
Hooks are configured in JSON files:
- **Global**: `~/.claude/settings.json`
- **Project**: `.claude/settings.json`
- **Local**: `.claude/settings.local.json`

### Structure
```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here"
          }
        ]
      }
    ]
  }
}
```

### Matchers
- **`""`** - Match all tools
- **`"Bash"`** - Match only Bash tool
- **`"Edit|Write"`** - Match Edit or Write tools
- **`"*"`** - Match all (legacy, use `""` instead)

## Hook Input Data

Hooks receive JSON data via **stdin** with information about the event:

### PreToolUse Input
```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "old_string": "...",
    "new_string": "..."
  },
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../session.jsonl"
}
```

### PostToolUse Input
```json
{
  "tool_name": "Edit",
  "tool_input": {...},
  "tool_output": "Tool result",
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../session.jsonl"
}
```

### Stop Input
```json
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../session.jsonl",
  "stop_hook_active": false
}
```

## Hook Output & Control

### Exit Codes
- **0**: Success, continue
- **1**: Error, continue with warning
- **2**: Block action, show error

### JSON Decision Control
```json
{
  "decision": "approve|block",
  "reason": "Explanation for user"
}
```

### Environment Variables
- **`$CLAUDE_EVENT_TYPE`**: Event type (PreToolUse, etc.)
- **`$CLAUDE_TOOL_NAME`**: Tool name
- **`$CLAUDE_TOOL_INPUT`**: Raw JSON input
- **`$CLAUDE_FILE_PATHS`**: Space-separated file paths

## Memory Bank Integration Examples

### 1. Pre-Tool Hook: Save Context Before Tool Use
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/save_context.py"
          }
        ]
      }
    ]
  }
}
```

### 2. Post-Tool Hook: Store Tool Results
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/store_tool_result.py"
          }
        ]
      }
    ]
  }
}
```

### 3. Stop Hook: Save Full Conversation
```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/save_conversation.py"
          }
        ]
      }
    ]
  }
}
```

## Security Considerations

⚠️ **USE AT YOUR OWN RISK**: Hooks execute arbitrary shell commands

### Best Practices:
1. **Review all commands** before adding to configuration
2. **Use proper escaping** for shell commands
3. **Avoid sensitive operations** in hooks
4. **Test thoroughly** in safe environments
5. **Handle errors gracefully**
6. **Check `stop_hook_active`** flag to avoid infinite loops

## Setting Up Hooks

### Method 1: Interactive Setup
```bash
claude
/hooks
```
Follow prompts to create hooks visually.

### Method 2: Manual Configuration
Edit `~/.claude/settings.json` directly:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'About to run: $CLAUDE_TOOL_INPUT' >> ~/.claude/bash.log"
          }
        ]
      }
    ]
  }
}
```

### Method 3: Project-Specific
Create `.claude/settings.local.json` in your project:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/format_and_save.py"
          }
        ]
      }
    ]
  }
}
```

## Hook Script Examples

### Basic Hook Script
```python
#!/usr/bin/env python3
import json
import sys
import os

def main():
    # Read hook input from stdin
    hook_data = json.load(sys.stdin)
    
    # Process the data
    tool_name = hook_data.get('tool_name', 'unknown')
    session_id = hook_data.get('session_id', 'no-session')
    
    # Your logic here
    print(f"Processing {tool_name} for session {session_id}")
    
    # Return success
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Memory Bank Hook Script
```python
#!/usr/bin/env python3
import json
import sys
import asyncio
from memory_bank_integration import store_in_memory_bank

def main():
    try:
        hook_data = json.load(sys.stdin)
        
        # Extract conversation context
        session_id = hook_data.get('session_id')
        transcript_path = hook_data.get('transcript_path')
        
        # Store in Memory Bank
        asyncio.run(store_in_memory_bank(session_id, transcript_path))
        
        # Success
        sys.exit(0)
        
    except Exception as e:
        # Error - show to user but continue
        print(f"Memory Bank error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Common Use Cases

### 1. **Auto-formatting**
```json
{
  "command": "if echo '$(.tool_input.file_path)' | grep -q '\\.py$'; then black '$(.tool_input.file_path)'; fi"
}
```

### 2. **Running Tests**
```json
{
  "command": "python3 -m pytest tests/ --tb=short"
}
```

### 3. **Git Operations**
```json
{
  "command": "git add . && git commit -m 'Auto-commit from Claude Code'"
}
```

### 4. **Notifications**
```json
{
  "command": "osascript -e 'display notification \"Claude Code task completed\" with title \"Development\"'"
}
```

## Debugging Hooks

### Enable Verbose Logging
```bash
claude --verbose
```

### Check Hook Execution
```bash
tail -f ~/.claude/logs/hooks.log
```

### Test Hook Manually
```bash
echo '{"tool_name": "test"}' | python3 ~/.claude/hooks/your_hook.py
```

## Integration with Memory Bank

The key insight is that hooks give you **automatic access** to:
- **Session IDs** - For tracking conversations
- **Transcript paths** - For reading conversation history
- **Tool context** - For understanding what Claude is doing
- **Timing control** - For saving at the right moments

This makes hooks perfect for **automatic memory management** without requiring Claude to explicitly call memory functions.