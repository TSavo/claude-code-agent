# Claude Code Agent

A standalone multi-agent terminal interface for Claude Code with Memory Bank integration.

## Features

- **Multi-Agent Management**: Create, switch between, and manage multiple Claude agents
- **Terminal UI**: Interactive terminal interface with mouse support
- **Memory Bank Integration**: Persistent memory across conversations using Google Cloud AI Platform
- **Session Persistence**: Agents and conversations persist between runs
- **Real-time Interaction**: Streaming responses with proper text wrapping

## Installation

```bash
cd claude-code-agent
npm install
```

## Usage

Start the TUI:
```bash
npm run tui
# or
npm run dev
# or
npm start
```

### Commands

- `/create "Agent Name" Role description` - Create a new agent
- `/switch "Agent Name"` - Switch to an agent (or click on agent name)
- `/delete "Agent Name"` - Delete an agent
- `/list` - List all agents
- `/clear` - Clear output
- `/streaming` - Toggle streaming mode
- `/queue` - Toggle queue mode
- `/verbose` - Toggle verbose mode
- `/help` - Show help
- `/exit` - Quit application

### Mouse Support

- **Click on any agent name** in the left panel to switch to that agent

## Memory Bank Setup

The Memory Bank integration requires Google Cloud AI Platform setup. See `test-memory-bank/GOOGLE_CLOUD_SETUP.md` for detailed instructions.

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Google Cloud configuration for Memory Bank
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Optional: Claude Code configuration
CLAUDE_API_KEY=your-api-key
```

## File Structure

- `src/claude-multi-chat-termkit.ts` - Main TUI application
- `src/multi-agent-core.ts` - Core agent management logic
- `src/claude-session-manager.ts` - Session management and Memory Bank integration
- `test-memory-bank/` - Memory Bank integration scripts and utilities

## Development

```bash
# Type checking
npm run typecheck

# Build
npm run build
```