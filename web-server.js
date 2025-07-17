#!/usr/bin/env node

const express = require('express');
const path = require('path');
const fs = require('fs');
const { ClaudeSessionManager } = require('./dist/claude-session-manager');

const app = express();
const port = 4000;

// Middleware
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json({ limit: '50mb' })); // Increase payload limit
app.use((req, res, next) => {
    console.log(`${new Date().toISOString()} ${req.method} ${req.path}`, req.body ? `Body: ${JSON.stringify(req.body).substring(0, 200)}...` : '');
    next();
});

// Persistence files
const AGENTS_FILE = '.web-agents.json';
const CHAT_HISTORY_FILE = '.web-chat-history.json';
const PREFERENCES_FILE = '.web-preferences.json';

// In-memory store for web sessions  
const sessionManager = new ClaudeSessionManager({
  sessionsFile: '.web-claude-sessions.json',
  suppressConsoleOutput: true
});

console.log('Session manager created with sessions file: .web-claude-sessions.json');

let agents = new Map(); // agentName -> { session, color, lastActivity }
let chatHistory = []; // Array of all messages
let preferences = {
  colorIndex: 0,
  lastSelectedAgent: null
};
const colors = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4'];

// Load persisted data
function loadPersistedData() {
  // Load agents
  if (fs.existsSync(AGENTS_FILE)) {
    try {
      const agentsData = JSON.parse(fs.readFileSync(AGENTS_FILE, 'utf8'));
      console.log('Loading persisted agents:', agentsData.length);
      
      // Restore agents with their session IDs and roles
      agentsData.forEach(agentData => {
        agents.set(agentData.name, {
          color: agentData.color,
          lastActivity: new Date(agentData.lastActivity),
          sessionId: agentData.sessionId,
          role: agentData.role,
          session: null // Will be restored when needed
        });
      });
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  }

  // Load chat history
  if (fs.existsSync(CHAT_HISTORY_FILE)) {
    try {
      chatHistory = JSON.parse(fs.readFileSync(CHAT_HISTORY_FILE, 'utf8'));
      console.log('Loaded chat history:', chatHistory.length, 'messages');
    } catch (error) {
      console.error('Error loading chat history:', error);
    }
  }

  // Load preferences
  if (fs.existsSync(PREFERENCES_FILE)) {
    try {
      const savedPrefs = JSON.parse(fs.readFileSync(PREFERENCES_FILE, 'utf8'));
      preferences = { ...preferences, ...savedPrefs };
      console.log('Loaded preferences:', preferences);
    } catch (error) {
      console.error('Error loading preferences:', error);
    }
  }
}

// Save data to disk
function saveAgents() {
  const agentsData = Array.from(agents.entries()).map(([name, data]) => ({
    name,
    color: data.color,
    lastActivity: data.lastActivity,
    sessionId: data.sessionId || (data.session ? data.session.sessionId : null),
    role: data.role || null
  }));
  
  fs.writeFileSync(AGENTS_FILE, JSON.stringify(agentsData, null, 2));
}

function saveChatHistory() {
  fs.writeFileSync(CHAT_HISTORY_FILE, JSON.stringify(chatHistory, null, 2));
}

function savePreferences() {
  fs.writeFileSync(PREFERENCES_FILE, JSON.stringify(preferences, null, 2));
}

function addToChatHistory(message) {
  chatHistory.push({
    ...message,
    timestamp: new Date().toISOString()
  });
  
  // Keep only last 1000 messages to prevent file from growing too large
  if (chatHistory.length > 1000) {
    chatHistory = chatHistory.slice(-1000);
  }
  
  saveChatHistory();
}

// Lazily restore agent session when needed
async function ensureAgentSession(agentName) {
  const agent = agents.get(agentName);
  if (!agent) {
    throw new Error('Agent not found');
  }
  
  if (!agent.session) {
    if (agent.sessionId) {
      // Agent has a saved session ID, create a session object that will use -r
      console.log('Restoring session for:', agentName, 'sessionId:', agent.sessionId.substring(0, 8));
      agent.session = {
        agentName: agentName,
        sessionId: agent.sessionId,
        lastPrompt: '',
        lastResponse: '',
        createdAt: new Date(),
        lastUsedAt: new Date(),
        totalCost: 0,
        totalTurns: 0,
        context: []
      };
    } else {
      // No session ID saved, create new session (will not use -r flag)
      console.log('Creating new session for agent:', agentName);
      agent.session = await sessionManager.designateAgent(agentName, agent.role || 'Assistant', null);
      agent.sessionId = agent.session.sessionId;
      saveAgents(); // Save the new sessionId
    }
  }
  
  return agent.session;
}

// Initialize session manager and load data
sessionManager.initialize();
loadPersistedData();

// Session manager initialized
console.log('Session manager initialized.');

// API Routes
app.get('/api/agents', (req, res) => {
  const agentList = Array.from(agents.entries()).map(([name, data]) => ({
    name,
    color: data.color,
    lastActivity: data.lastActivity,
    sessionId: data.sessionId ? data.sessionId.substring(0, 8) : (data.session ? data.session.sessionId.substring(0, 8) : 'new')
  }));
  res.json(agentList);
});

app.post('/api/agents', async (req, res) => {
  const { name, role } = req.body;
  
  if (agents.has(name)) {
    return res.status(400).json({ error: 'Agent already exists' });
  }

  try {
    const color = colors[preferences.colorIndex % colors.length];
    preferences.colorIndex++;
    savePreferences();
    
    // Create agent data
    const agentData = {
      color,
      lastActivity: new Date(),
      role: role
    };
    agents.set(name, agentData);
    
    // Event handler to capture all streaming events
    const eventHandler = (event) => {
      
      if (event.type === 'process_output' && event.data && event.data.content) {
        const response = event.data.content
          .filter(item => item.type === 'text')
          .map(item => item.text)
          .join('');
        
        if (response.trim()) {
          // Add to chat history
          addToChatHistory({
            type: 'assistant',
            agent: name,
            content: response,
            color: agentData.color
          });
          
          // Broadcast to all clients
          broadcastToAllClients({
            type: 'message',
            agent: name,
            content: response,
            color: agentData.color
          });
        }
      } else if (event.type === 'tool_use') {
        // Broadcast tool use events
        broadcastToAllClients({
          type: 'tool_use',
          agent: name,
          tool_name: event.data.name,
          description: event.data.description,
          input: event.data.input,
          color: agentData.color
        });
      } else if (event.type === 'tool_result') {
        console.log('DEBUG: Received tool_result event (agent creation):', JSON.stringify(event, null, 2));
        // Broadcast tool result events
        broadcastToAllClients({
          type: 'tool_result',
          agent: name,
          content: event.data.content,
          color: agentData.color
        });
      }
    };
    
    const session = await sessionManager.designateAgent(name, role, eventHandler);
    agentData.session = session;
    agentData.sessionId = session.sessionId;
    
    // Save agents to disk
    saveAgents();
    
    res.json({ name, color, sessionId: session.sessionId.substring(0, 8) });
  } catch (error) {
    console.error('Error creating agent:', error);
    agents.delete(name); // Clean up if creation failed
    res.status(500).json({ error: error.message });
  }
});

// Update agent color
app.put('/api/agents/:name/color', async (req, res) => {
  const { name } = req.params;
  const { color } = req.body;
  
  if (!agents.has(name)) {
    return res.status(404).json({ error: 'Agent not found' });
  }

  try {
    const agent = agents.get(name);
    agent.color = color;
    
    // Update chat history with new color
    chatHistory.forEach(msg => {
      if (msg.agent === name && msg.type === 'assistant') {
        msg.color = color;
      }
    });
    
    // Save changes
    saveAgents();
    saveChatHistory();
    
    res.json({ success: true, color });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.delete('/api/agents/:name', async (req, res) => {
  const { name } = req.params;
  
  if (!agents.has(name)) {
    return res.status(404).json({ error: 'Agent not found' });
  }

  try {
    await sessionManager.removeAgent(name);
    agents.delete(name);
    
    // Save agents to disk
    saveAgents();
    
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Global stream for all agent messages
const globalStreams = new Set();

app.get('/api/stream', (req, res) => {
  // Set up SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
  });

  // Send initial connection message
  res.write(`data: ${JSON.stringify({ type: 'connected' })}\n\n`);

  // Store the response object globally
  globalStreams.add(res);
  
  // Clean up on disconnect
  req.on('close', () => {
    globalStreams.delete(res);
  });
});

// Helper function to broadcast to all connected clients
function broadcastToAllClients(data) {
  globalStreams.forEach(stream => {
    try {
      stream.write(`data: ${JSON.stringify(data)}\n\n`);
    } catch (e) {
      // Stream closed, remove it
      globalStreams.delete(stream);
    }
  });
}

app.post('/api/message/:agentName', async (req, res) => {
  const { agentName } = req.params;
  const { message } = req.body;
  const agent = agents.get(agentName);
  
  if (!agent) {
    return res.status(404).json({ error: 'Agent not found' });
  }

  try {
    // Ensure agent has a session
    await ensureAgentSession(agentName);
    
    // Add user message to chat history
    addToChatHistory({
      type: 'user',
      content: message,
      agent: agentName
    });
    
    // Broadcast user message to all connected clients
    broadcastToAllClients({
      type: 'user_message',
      agent: agentName,
      content: message,
      color: agent.color
    });
    
    // Event handler for streaming events during conversation
    const eventHandler = (event) => {
      
      if (event.type === 'process_output' && event.data && event.data.content) {
        const response = event.data.content
          .filter(item => item.type === 'text')
          .map(item => item.text)
          .join('');
        
        if (response.trim()) {
          // Broadcast incremental responses
          broadcastToAllClients({
            type: 'message',
            agent: agentName,
            content: response,
            color: agent.color
          });
        }
      } else if (event.type === 'tool_use') {
        // Broadcast tool use events
        broadcastToAllClients({
          type: 'tool_use',
          agent: agentName,
          tool_name: event.data.name,
          description: event.data.description,
          input: event.data.input,
          color: agent.color
        });
      } else if (event.type === 'tool_result') {
        console.log('DEBUG: Received tool_result event:', JSON.stringify(event, null, 2));
        // Broadcast tool result events
        broadcastToAllClients({
          type: 'tool_result',
          agent: agentName,
          content: event.data.content,
          color: agent.color
        });
      }
    };
    
    // Send the message and get response with streaming
    const response = await sessionManager.resumeAgent(agentName, message, eventHandler);
    
    // Add assistant response to chat history (if not already added by streaming)
    if (response.result && response.result.trim()) {
      addToChatHistory({
        type: 'assistant',
        agent: agentName,
        content: response.result,
        color: agent.color
      });
    }
    
    agent.lastActivity = new Date();
    
    // Update last selected agent preference
    preferences.lastSelectedAgent = agentName;
    savePreferences();
    
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get chat history
app.get('/api/chat-history', (req, res) => {
  res.json(chatHistory);
});

// Get preferences
app.get('/api/preferences', (req, res) => {
  res.json(preferences);
});

// Update preferences
app.post('/api/preferences', (req, res) => {
  preferences = { ...preferences, ...req.body };
  savePreferences();
  res.json({ success: true });
});

// Clear chat history
app.delete('/api/chat-history', (req, res) => {
  chatHistory = [];
  saveChatHistory();
  res.json({ success: true });
});

// Start server
app.listen(port, () => {
  console.log(`🚀 Claude Multi-Agent Web running at http://localhost:${port}`);
});