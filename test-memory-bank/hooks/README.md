# Pre-loaded Context via Hooks Implementation

This demonstrates **Method 2** from the Memory Bank integration approaches - automatically injecting relevant memories into Claude's environment before tool execution.

## How It Works

1. **PreToolUse Hook** triggers before every tool execution
2. **Context Search** queries Memory Bank for relevant past conversations
3. **Context Injection** displays relevant memories directly to Claude
4. **Tool Execution** proceeds with Claude having access to past context
5. **Context Saving** stores current context for future use

## Key Features

### Smart Context Queries
- **File-based**: When editing `config.py`, searches for "editing config.py", "file config.py"
- **Command-based**: When running `npm install`, searches for "running npm", "command npm install"  
- **Project-based**: Always includes current project context
- **Language-aware**: Adds Python/JavaScript specific context for relevant files

### Context Display
Claude sees output like:
```
============================================================
🧠 MEMORY BANK CONTEXT LOADED
============================================================
Found 3 relevant memories for Edit:

💭 Memory 1 (relevance: 0.95, query: 'editing config.py'):
   Previously configured database settings in config.py with PostgreSQL connection

💭 Memory 2 (relevance: 0.87, query: 'project toolstac'):
   Working on toolstac.com Next.js project with Redis and job management

💭 Memory 3 (relevance: 0.82, query: 'python development'):
   User prefers using environment variables for configuration
============================================================
You can reference this context in your response.
============================================================
```

### Multiple Injection Methods
1. **Direct Output**: Prints context to stdout (Claude sees it immediately)
2. **Context Files**: Creates `.claude/context/current_context.md` 
3. **Environment Variables**: Sets `CLAUDE_CONTEXT_AVAILABLE=true`

## Setup Instructions

### 1. Install Dependencies
```bash
pip install google-adk[vertexai] google-cloud-aiplatform
```

### 2. Configure Environment
```bash
# In .env
GOOGLE_CLOUD_PROJECT=gen-lang-client-0220754900
GOOGLE_API_KEY=your-api-key
GOOGLE_CLOUD_LOCATION=us-central1
```

### 3. Authenticate with Google Cloud
```bash
gcloud auth application-default login
```

### 4. Configure Hooks
Copy to `.claude/settings.local.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /absolute/path/to/hooks/save_and_load_context.py"
          }
        ]
      }
    ]
  }
}
```

### 5. Test the Integration
```bash
# Start Claude Code
claude

# Try editing a file - you should see context loaded
/edit some_file.py
```

## Example Workflow

1. **Session 1**: User asks Claude to set up a Python project
   - Claude creates files, configures settings
   - Hook saves: "Created Python project with FastAPI and PostgreSQL"

2. **Session 2** (days later): User asks Claude to add a new endpoint
   - Hook loads context: "Previously set up FastAPI project with PostgreSQL"
   - Claude knows the existing architecture without re-explaining

3. **Session 3**: User asks Claude to debug a database issue
   - Hook loads context: "Database configured with PostgreSQL, connection in config.py"
   - Claude immediately knows the database setup

## Advanced Features

### Context Scoring
- Memories are ranked by relevance (0.0 to 1.0)
- Only top 3 most relevant memories are shown
- Deduplication prevents identical memories

### Tool-Specific Context
- **Edit**: Searches for file-specific and modification history
- **Write**: Searches for file creation and similar files
- **Bash**: Searches for command history and similar operations
- **Read**: Searches for file content and previous reads

### Error Handling
- Never blocks tool execution (always exits with code 0 or 1)
- Gracefully handles Memory Bank service failures
- Provides informative error messages without disrupting Claude

## Files

- `load_context.py` - Simple context loading hook
- `save_and_load_context.py` - Combined save/load functionality
- `setup_hooks.json` - Hook configuration template
- `README.md` - This documentation

## Benefits

✅ **Automatic**: No explicit memory function calls needed
✅ **Contextual**: Relevant memories based on current task
✅ **Seamless**: Claude sees context as natural part of conversation
✅ **Persistent**: Context survives across sessions and restarts
✅ **Smart**: Context relevance improves over time

This creates the experience of Claude having "memory" of past conversations without requiring any changes to Claude's behavior or responses.