#!/usr/bin/env python3
"""
Pre-loaded Context Hook for Claude Code + Memory Bank Integration
Automatically injects relevant memories before tool execution
"""

import json
import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

async def search_memory_bank(query, user_id="default", project_path=None):
    """Search Memory Bank for relevant context"""
    try:
        from google.adk.memory import VertexAiMemoryBankService
        import vertexai
        
        # Initialize
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'gen-lang-client-0220754900')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        # Get or create agent engine (you'd cache this in practice)
        agent_engines = client.agent_engines.list()
        if agent_engines:
            agent_engine_id = agent_engines[0].api_resource.name.split("/")[-1]
        else:
            agent_engine = client.agent_engines.create()
            agent_engine_id = agent_engine.api_resource.name.split("/")[-1]
        
        # Search memory
        memory_service = VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        # Enhanced query with project context
        if project_path:
            enhanced_query = f"{query} project:{os.path.basename(project_path)}"
        else:
            enhanced_query = query
        
        results = await memory_service.search_memory(
            app_name="claude-code",
            user_id=user_id,
            query=enhanced_query
        )
        
        return [{"content": mem.content, "score": mem.score} for mem in results.memories]
        
    except Exception as e:
        print(f"🔍 Memory search failed: {e}", file=sys.stderr)
        return []

def get_context_from_tool(tool_name, tool_input):
    """Generate context queries based on tool being used"""
    contexts = []
    
    if tool_name == "Edit":
        file_path = tool_input.get('file_path', '')
        if file_path:
            contexts.append(f"editing {os.path.basename(file_path)}")
            contexts.append(f"file {file_path}")
            
            # Add language-specific context
            if file_path.endswith('.py'):
                contexts.append("python development")
            elif file_path.endswith('.js') or file_path.endswith('.ts'):
                contexts.append("javascript typescript development")
            elif file_path.endswith('.md'):
                contexts.append("documentation writing")
    
    elif tool_name == "Write":
        file_path = tool_input.get('file_path', '')
        if file_path:
            contexts.append(f"creating {os.path.basename(file_path)}")
            contexts.append(f"new file {file_path}")
    
    elif tool_name == "Bash":
        command = tool_input.get('command', '')
        if command:
            contexts.append(f"running {command.split()[0]}")
            contexts.append(f"command {command}")
    
    elif tool_name == "Read":
        file_path = tool_input.get('file_path', '')
        if file_path:
            contexts.append(f"reading {os.path.basename(file_path)}")
            contexts.append(f"file content {file_path}")
    
    # Always add general project context
    project_name = os.path.basename(os.getcwd())
    contexts.append(f"project {project_name}")
    contexts.append("recent work")
    
    return contexts

def inject_context_as_output(memories, tool_name):
    """Inject context in a way Claude will see it"""
    if not memories:
        return
    
    # Create context summary
    context_lines = []
    context_lines.append("💭 RELEVANT CONTEXT FROM PREVIOUS SESSIONS:")
    context_lines.append("=" * 50)
    
    for i, memory in enumerate(memories[:3]):  # Top 3 most relevant
        score = memory.get('score', 0)
        content = memory.get('content', '')
        context_lines.append(f"{i+1}. [{score:.2f}] {content}")
    
    context_lines.append("=" * 50)
    
    # Print to stdout so Claude sees it
    for line in context_lines:
        print(line)

def create_context_file(memories, tool_name, tool_input):
    """Create a context file that Claude can read"""
    if not memories:
        return
    
    context_dir = Path(".claude/context")
    context_dir.mkdir(parents=True, exist_ok=True)
    
    context_file = context_dir / "current_context.md"
    
    with open(context_file, 'w') as f:
        f.write("# Current Session Context\n\n")
        f.write(f"**Tool about to execute:** {tool_name}\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        
        f.write("## Relevant Previous Context\n\n")
        for i, memory in enumerate(memories[:5]):
            score = memory.get('score', 0)
            content = memory.get('content', '')
            f.write(f"### Memory {i+1} (Relevance: {score:.2f})\n")
            f.write(f"{content}\n\n")
        
        f.write("---\n")
        f.write("*This context was automatically loaded from Memory Bank*\n")
    
    print(f"📝 Context saved to {context_file}")

async def main():
    """Main hook function"""
    try:
        # Read hook input
        hook_data = json.load(sys.stdin)
        
        tool_name = hook_data.get('tool_name', 'unknown')
        tool_input = hook_data.get('tool_input', {})
        session_id = hook_data.get('session_id', 'default')
        project_path = os.getcwd()
        
        # Skip if no meaningful context can be derived
        if tool_name in ['LS', 'Glob']:
            sys.exit(0)
        
        print(f"🔍 Loading context for {tool_name}...")
        
        # Generate context queries
        context_queries = get_context_from_tool(tool_name, tool_input)
        
        # Search for relevant memories
        all_memories = []
        for query in context_queries:
            memories = await search_memory_bank(query, session_id, project_path)
            all_memories.extend(memories)
        
        # Deduplicate and sort by relevance
        unique_memories = {}
        for mem in all_memories:
            content = mem['content']
            if content not in unique_memories or mem['score'] > unique_memories[content]['score']:
                unique_memories[content] = mem
        
        sorted_memories = sorted(unique_memories.values(), key=lambda x: x['score'], reverse=True)
        
        if sorted_memories:
            print(f"💭 Found {len(sorted_memories)} relevant memories")
            
            # Method 1: Inject as immediate output
            inject_context_as_output(sorted_memories, tool_name)
            
            # Method 2: Create context file
            create_context_file(sorted_memories, tool_name, tool_input)
            
            # Method 3: Update environment
            os.environ['CLAUDE_CONTEXT_AVAILABLE'] = 'true'
            os.environ['CLAUDE_CONTEXT_COUNT'] = str(len(sorted_memories))
        else:
            print("💭 No relevant context found")
        
        # Always succeed - don't block tool execution
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Context loading failed: {e}", file=sys.stderr)
        # Don't block tool execution on errors
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())