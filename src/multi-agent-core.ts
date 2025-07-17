/**
 * UI-Agnostic Multi-Agent Core Classes
 * 
 * Extracted from claude-multi-chat.ts to separate business logic from UI.
 * These classes can be used with any UI framework (blessed, ink, etc.).
 */

import { ChildProcess, spawn } from 'child_process';
import { ClaudeSessionManager } from './claude-session-manager';
import { EventEmitter } from 'events';

// Types
export interface ActiveAgent {
  name: string;
  sessionId: string;
  process?: ChildProcess;
  isProcessing?: boolean;
  lastActivity: Date;
  isCreating?: boolean;
  queuedMessages?: string[];
}

export interface MultiAgentConfig {
  sessionsFile?: string;
  defaultOutputFormat?: 'json' | 'text' | 'stream-json';
  verbose?: boolean;
  streamingMode?: boolean;
  queueMode?: boolean;
  suppressConsoleOutput?: boolean;
}

export interface AgentEvent {
  type: 'agent_created' | 'agent_switched' | 'agent_processing' | 'agent_completed' | 'agent_error' | 'message_queued' | 'queue_processed';
  agentName: string;
  data?: Record<string, unknown>;
}

export interface ProcessEvent {
  type: 'process_started' | 'process_output' | 'process_completed' | 'process_error' | 'process_terminated';
  agentName: string;
  data?: Record<string, unknown>;
}

export interface QueueEvent {
  type: 'message_queued' | 'queue_processed' | 'queue_empty';
  agentName: string;
  queueLength: number;
  message?: string;
}

/**
 * Core Agent Management - handles agent lifecycle and state
 */
export class AgentManager extends EventEmitter {
  private agents: Map<string, ActiveAgent> = new Map();
  private currentAgent: string | null = null;
  private sessionManager: ClaudeSessionManager;

  private logDebug(_message: string): void {
    // Debug logging disabled for TUI compatibility
    // const timestamp = new Date().toISOString();
    // const logMessage = `[${timestamp}] AGENT_MANAGER: ${message}\n`;
    // console.log(logMessage);
  }

  public getSessionManager(): ClaudeSessionManager {
    return this.sessionManager;
  }

  constructor(private config: MultiAgentConfig = {}) {
    super();
    this.logDebug(`AgentManager constructor called with config: ${JSON.stringify(config)}`);
    this.sessionManager = new ClaudeSessionManager({
      sessionsFile: config.sessionsFile || '.claude-multi-chat-sessions.json',
      defaultOutputFormat: config.defaultOutputFormat || 'stream-json',
      verbose: config.verbose !== undefined ? config.verbose : true, // Respect explicit verbose setting
      suppressConsoleOutput: config.suppressConsoleOutput || false
    });
    this.logDebug('AgentManager constructor complete');
  }

  async initialize(): Promise<void> {
    this.logDebug('AgentManager initialize() called');
    await this.sessionManager.initialize();
    await this.loadExistingAgents();
    this.logDebug('AgentManager initialize() complete');
  }

  private async loadExistingAgents(): Promise<void> {
    const agents = this.sessionManager.listAgents();
    agents.forEach(agent => {
      this.agents.set(agent.name.toLowerCase(), {
        name: agent.name,
        sessionId: agent.sessionId,
        lastActivity: agent.lastUsed
      });
    });

    if (agents.length > 0) {
      const mostRecent = this.getMostRecentAgent();
      if (mostRecent) {
        this.currentAgent = mostRecent.name;
        this.emit('agent_switched', { type: 'agent_switched', agentName: mostRecent.name });
      }
    }
  }

  async createAgent(name: string, role: string, eventHandler?: (event: any) => void): Promise<ActiveAgent> {
    this.logDebug(`createAgent called: name="${name}", role="${role}"`);
    if (this.agents.has(name.toLowerCase())) {
      throw new Error(`Agent "${name}" already exists`);
    }

    // Create placeholder
    const agent: ActiveAgent = {
      name: name,
      sessionId: '',
      lastActivity: new Date(),
      isCreating: true,
      queuedMessages: []
    };

    this.agents.set(name.toLowerCase(), agent);
    this.emit('agent_created', { type: 'agent_created', agentName: name, data: { creating: true } });

    try {
      // Create combined event handler that both emits and calls provided callback
      const combinedEventHandler = (event: any) => {
        // Debug logging
        const fs = require('fs');
        const debugMsg = `[${new Date().toISOString()}] MULTI-AGENT-CORE: Received event from session manager: ${JSON.stringify(event)}\n`;
        fs.appendFileSync('/tmp/agent-creation-debug.log', debugMsg);
        
        // Emit the event for regular listeners
        this.emit('process_output', event);
        
        const emitMsg = `[${new Date().toISOString()}] MULTI-AGENT-CORE: Emitted process_output event: ${JSON.stringify(event)}\n`;
        fs.appendFileSync('/tmp/agent-creation-debug.log', emitMsg);
        
        // Call the provided event handler directly (bypass EventEmitter)
        if (eventHandler) {
          const callbackMsg = `[${new Date().toISOString()}] MULTI-AGENT-CORE: Calling provided eventHandler directly\n`;
          fs.appendFileSync('/tmp/agent-creation-debug.log', callbackMsg);
          eventHandler(event);
        }
        
        const listenerMsg = `[${new Date().toISOString()}] MULTI-AGENT-CORE: Event listeners count: ${this.listenerCount('process_output')}\n`;
        fs.appendFileSync('/tmp/agent-creation-debug.log', listenerMsg);
      };
      
      const session = await this.sessionManager.designateAgent(name, role, combinedEventHandler);
      agent.sessionId = session.sessionId;
      agent.isCreating = false;
      agent.lastActivity = new Date();

      this.currentAgent = name;
      this.emit('agent_created', { type: 'agent_created', agentName: name, data: { session, completed: true } });
      this.emit('agent_switched', { type: 'agent_switched', agentName: name });

      return agent;
    } catch (error) {
      this.agents.delete(name.toLowerCase());
      throw error;
    }
  }

  switchToAgent(agentName: string): ActiveAgent | null {
    // Try exact match first
    let agent = this.agents.get(agentName.toLowerCase());
    
    if (!agent) {
      // Try partial match
      const matches = Array.from(this.agents.entries()).filter(([key, a]) => 
        key.includes(agentName.toLowerCase()) || a.name.toLowerCase().includes(agentName.toLowerCase())
      );
      
      if (matches.length === 1) {
        agent = matches[0][1];
      } else if (matches.length > 1) {
        throw new Error(`Multiple agents match "${agentName}": ${matches.map(([_, a]) => a.name).join(', ')}`);
      }
    }
    
    if (!agent) {
      throw new Error(`Agent "${agentName}" not found`);
    }

    this.currentAgent = agent.name;
    this.emit('agent_switched', { type: 'agent_switched', agentName: agent.name });
    return agent;
  }

  getCurrentAgent(): ActiveAgent | null {
    if (!this.currentAgent) return null;
    return this.agents.get(this.currentAgent.toLowerCase()) || null;
  }

  getAgent(name: string): ActiveAgent | null {
    return this.agents.get(name.toLowerCase()) || null;
  }

  getAllAgents(): ActiveAgent[] {
    return Array.from(this.agents.values());
  }

  getMostRecentAgent(): ActiveAgent | null {
    const agents = Array.from(this.agents.values());
    if (agents.length === 0) return null;
    
    return agents.reduce((latest, agent) => 
      agent.lastActivity > latest.lastActivity ? agent : latest
    );
  }

  async removeAgent(agentName: string): Promise<boolean> {
    const agent = this.agents.get(agentName.toLowerCase());
    if (!agent) return false;

    // If this is the current agent, clear it
    if (this.currentAgent === agent.name) {
      this.currentAgent = null;
    }

    const deleted = this.agents.delete(agentName.toLowerCase());
    if (deleted) {
      await this.sessionManager.removeAgent(agentName);
    }
    return deleted;
  }

  async clearAllAgents(): Promise<void> {
    this.agents.clear();
    this.currentAgent = null;
    await this.sessionManager.clearAllSessions();
  }
}

/**
 * Process Management - handles Claude process lifecycle per agent
 */
export class ProcessManager extends EventEmitter {
  private config: MultiAgentConfig;
  private sessionManager: ClaudeSessionManager;

  private logDebug(_message: string): void {
    // Debug logging disabled for TUI compatibility
    // const timestamp = new Date().toISOString();
    // const logMessage = `[${timestamp}] PROCESS_MANAGER: ${message}\n`;
    // console.log(logMessage);
  }

  constructor(config: MultiAgentConfig, sessionManager: ClaudeSessionManager) {
    super();
    this.config = config;
    this.sessionManager = sessionManager;
    this.logDebug(`ProcessManager constructor: streamingMode=${config.streamingMode}, verbose=${config.verbose}`);
  }

  async startAgentProcess(agent: ActiveAgent, message: string): Promise<void> {
    this.logDebug(`startAgentProcess called: agent="${agent.name}", sessionId="${agent.sessionId}", message="${message.substring(0, 50)}..."`);
    
    if (agent.process) {
      await this.terminateAgentProcess(agent);
    }

    agent.isProcessing = true;
    this.emit('process_started', { type: 'process_started', agentName: agent.name });

    if (this.config.streamingMode) {
      this.logDebug(`Using streaming mode for agent ${agent.name}`);
      await this.startStreamingProcess(agent, message);
    } else {
      this.logDebug(`Using regular mode for agent ${agent.name}`);
      await this.startRegularProcess(agent, message);
    }
  }

  private async startStreamingProcess(agent: ActiveAgent, message: string): Promise<void> {
    this.logDebug(`startStreamingProcess called for agent ${agent.name}`);
    
    // **MEMORY BANK INTEGRATION**: Retrieve memories before streaming
    try {
      this.logDebug(`About to retrieve memories for ${agent.sessionId}`);
      
      // Build richer context from recent USER messages only (no assistant responses)
      const agentContext = this.sessionManager.getAgentContext(agent.name) || [];
      // Extract only user prompts (odd indices in context array)
      const userPrompts = agentContext.filter((_, index) => index % 2 === 0); // User prompts are at even indices
      const recentUserContext = userPrompts.slice(-3); // Last 3 user prompts
      const contextHint = [...recentUserContext, message].join(' '); // NO substring - keep full context
      
      this.logDebug(`Using expanded context hint (${contextHint.length} chars): ${contextHint.substring(0, 100)}...`);
      await this.sessionManager.retrieveMemories(agent.sessionId, contextHint);
      this.logDebug(`Memory retrieval completed for ${agent.sessionId}`);
      
      // Store the user prompt
      this.logDebug(`About to store user prompt for ${agent.sessionId}`);
      await this.sessionManager.storeConversationInMemoryBank(agent.sessionId, 'user_prompt', { text: message });
      this.logDebug(`User prompt storage completed for ${agent.sessionId}`);
    } catch (error) {
      this.logDebug(`Memory Bank operation failed: ${error}`);
      console.error('Memory Bank operation failed in streaming mode:', error);
    }

    const args = ['-r', agent.sessionId, '-p', message, '--output-format', 'stream-json', '--dangerously-skip-permissions'];
    
    if (this.config.verbose) {
      args.push('--verbose');
    }
    
    // Add home directory as additional working directory
    const homeDir = require('os').homedir();
    args.push('--add-dir', homeDir);

    agent.process = spawn('claude', args, {
      cwd: this.sessionManager['config'].workingDirectory,
      stdio: ['inherit', 'pipe', 'pipe'] // Back to inherit stdin for Claude to work
    });

    let _accumulatedResponse = '';
    let accumulatedCost = 0;
    let totalDuration = 0;

    agent.process.stdout?.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line.trim());
      
      lines.forEach((line: string) => {
        try {
          const jsonData = JSON.parse(line);
          
          switch (jsonData.type) {
            case 'system':
              this.emit('process_output', { 
                type: 'process_output', 
                agentName: agent.name, 
                data: { type: 'system', sessionId: jsonData.session_id } 
              });
              break;
              
            case 'assistant':
              const message = jsonData.message;
              if (message?.content) {
                this.emit('process_output', { 
                  type: 'process_output', 
                  agentName: agent.name, 
                  data: { type: 'assistant', content: message.content } 
                });
                // Store assistant response in Memory Bank
                try {
                  this.sessionManager.storeConversationInMemoryBank(agent.sessionId, 'assistant', message);
                } catch (error) {
                  console.error('Failed to store assistant message:', error);
                }
              }
              break;
              
            case 'activity':
              this.emit('process_output', { 
                type: 'process_output', 
                agentName: agent.name, 
                data: { type: 'activity', activity: jsonData.activity } 
              });
              break;
              
            case 'progress':
              this.emit('process_output', { 
                type: 'process_output', 
                agentName: agent.name, 
                data: { type: 'progress', message: jsonData.message } 
              });
              break;
              
            case 'content':
              this.emit('process_output', { 
                type: 'process_output', 
                agentName: agent.name, 
                data: { type: 'content', content: jsonData.content } 
              });
              _accumulatedResponse += jsonData.content;
              break;
              
            case 'result':
              _accumulatedResponse = jsonData.result;
              accumulatedCost = jsonData.total_cost_usd || 0;
              totalDuration = jsonData.duration_ms || 0;
              break;
          }
        } catch (_error) {
          // Non-JSON line
          this.emit('process_output', { 
            type: 'process_output', 
            agentName: agent.name, 
            data: { type: 'raw', content: line } 
          });
        }
      });
    });

    agent.process.stderr?.on('data', (data) => {
      this.emit('process_output', { 
        type: 'process_output', 
        agentName: agent.name, 
        data: { type: 'error', content: data.toString() } 
      });
    });

    agent.process.on('close', (code) => {
      agent.process = undefined;
      agent.isProcessing = false;
      agent.lastActivity = new Date();

      this.emit('process_completed', { 
        type: 'process_completed', 
        agentName: agent.name, 
        data: { code, cost: accumulatedCost, duration: totalDuration } 
      });
    });

    agent.process.on('error', (error) => {
      agent.process = undefined;
      agent.isProcessing = false;
      
      this.emit('process_error', { 
        type: 'process_error', 
        agentName: agent.name, 
        data: { error: error.message } 
      });
    });
  }

  private async startRegularProcess(agent: ActiveAgent, message: string): Promise<void> {
    // Debug logging disabled to avoid require-style imports
    // TODO: Implement proper logging system
    // fs.appendFileSync('/tmp/multi-agent-debug.log', 
    //   `[${new Date().toISOString()}] REGULAR PROCESS START:\n` +
    //   `Agent: ${agent.name}\n` +
    //   `Session: ${agent.sessionId}\n` +
    //   `Message Length: ${message.length}\n` +
    //   `Has Newlines: ${message.includes('\n')}\n` +
    //   `Message: ${JSON.stringify(message)}\n` +
    //   `---\n`
    // );

    try {
      const response = await this.sessionManager.resumeAgent(agent.name, message);
      agent.lastActivity = new Date();
      agent.isProcessing = false;

      // fs.appendFileSync('/tmp/multi-agent-debug.log', 
      //   `[${new Date().toISOString()}] REGULAR PROCESS SUCCESS:\n` +
      //   `Agent: ${agent.name}\n` +
      //   `Response Length: ${response.result.length}\n` +
      //   `Response Preview: ${JSON.stringify(response.result.substring(0, 200))}...\n` +
      //   `---\n`
      // );

      this.emit('process_completed', { 
        type: 'process_completed', 
        agentName: agent.name, 
        data: { response } 
      });
    } catch (error) {
      agent.isProcessing = false;
      
      // fs.appendFileSync('/tmp/multi-agent-debug.log', 
      //   `[${new Date().toISOString()}] REGULAR PROCESS ERROR:\n` +
      //   `Agent: ${agent.name}\n` +
      //   `Error: ${error instanceof Error ? error.message : error}\n` +
      //   `Stack: ${error instanceof Error ? error.stack : 'No stack'}\n` +
      //   `---\n`
      // );

      this.emit('process_error', { 
        type: 'process_error', 
        agentName: agent.name, 
        data: { error: error instanceof Error ? error.message : error } 
      });
    }
  }

  async terminateAgentProcess(agent: ActiveAgent): Promise<void> {
    if (!agent.process) {
      return;
    }

    return new Promise((resolve) => {
      if (!agent.process) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        if (agent.process && !agent.process.killed) {
          agent.process.kill('SIGKILL');
        }
        agent.process = undefined;
        agent.isProcessing = false;
        resolve();
      }, 2000);

      agent.process.once('close', () => {
        clearTimeout(timeout);
        agent.process = undefined;
        agent.isProcessing = false;
        this.emit('process_terminated', { type: 'process_terminated', agentName: agent.name });
        resolve();
      });

      agent.process.kill('SIGTERM');
    });
  }
}

/**
 * Queue Management - handles per-agent message queuing
 */
export class QueueManager extends EventEmitter {
  private queueMode: boolean = false;

  constructor() {
    super();
  }

  toggleQueueMode(): boolean {
    this.queueMode = !this.queueMode;
    return this.queueMode;
  }

  isQueueMode(): boolean {
    return this.queueMode;
  }

  queueMessage(agent: ActiveAgent, message: string): void {
    if (!agent.queuedMessages) {
      agent.queuedMessages = [];
    }
    agent.queuedMessages.push(message);
    
    this.emit('message_queued', { 
      type: 'message_queued', 
      agentName: agent.name, 
      queueLength: agent.queuedMessages.length,
      message 
    });
  }

  processNextMessage(agent: ActiveAgent): string | null {
    if (!agent.queuedMessages || agent.queuedMessages.length === 0) {
      return null;
    }

    const nextMessage = agent.queuedMessages.shift()!;
    
    this.emit('queue_processed', { 
      type: 'queue_processed', 
      agentName: agent.name, 
      queueLength: agent.queuedMessages.length,
      message: nextMessage 
    });

    if (agent.queuedMessages.length === 0) {
      this.emit('queue_empty', { 
        type: 'queue_empty', 
        agentName: agent.name, 
        queueLength: 0 
      });
    }

    return nextMessage;
  }

  getQueueLength(agent: ActiveAgent): number {
    return agent.queuedMessages?.length || 0;
  }

  getAgentsWithQueues(agents: ActiveAgent[]): ActiveAgent[] {
    return agents.filter(agent => agent.queuedMessages && agent.queuedMessages.length > 0);
  }
}

/**
 * Main Multi-Agent Controller - orchestrates all managers
 */
export class MultiAgentController extends EventEmitter {
  private agentManager: AgentManager;
  private processManager: ProcessManager;
  private queueManager: QueueManager;
  private config: MultiAgentConfig;

  constructor(config: MultiAgentConfig = {}) {
    super();
    this.config = config;
    this.agentManager = new AgentManager(config);
    this.processManager = new ProcessManager(config, this.agentManager.getSessionManager());
    this.queueManager = new QueueManager();

    this.setupEventForwarding();
  }

  private setupEventForwarding(): void {
    // Forward all events from managers
    this.agentManager.on('agent_created', (event) => this.emit('agent_created', event));
    this.agentManager.on('agent_switched', (event) => this.emit('agent_switched', event));
    
    this.processManager.on('process_started', (event) => this.emit('process_started', event));
    this.processManager.on('process_output', (event) => this.emit('process_output', event));
    this.processManager.on('process_completed', (event) => {
      this.emit('process_completed', event);
      // Auto-process queue when agent completes
      const agent = this.agentManager.getAgent(event.agentName);
      if (agent) {
        this.processAgentQueue(agent);
      }
    });
    this.processManager.on('process_error', (event) => this.emit('process_error', event));
    this.processManager.on('process_terminated', (event) => this.emit('process_terminated', event));
    
    this.queueManager.on('message_queued', (event) => this.emit('message_queued', event));
    this.queueManager.on('queue_processed', (event) => this.emit('queue_processed', event));
    this.queueManager.on('queue_empty', (event) => this.emit('queue_empty', event));
  }

  async initialize(): Promise<void> {
    await this.agentManager.initialize();
  }

  // Agent Management
  async createAgent(name: string, role: string, eventHandler?: (event: any) => void): Promise<ActiveAgent> {
    return this.agentManager.createAgent(name, role, eventHandler);
  }

  switchToAgent(agentName: string): ActiveAgent | null {
    return this.agentManager.switchToAgent(agentName);
  }

  async removeAgent(agentName: string): Promise<boolean> {
    return this.agentManager.removeAgent(agentName);
  }

  getCurrentAgent(): ActiveAgent | null {
    return this.agentManager.getCurrentAgent();
  }

  getAllAgents(): ActiveAgent[] {
    return this.agentManager.getAllAgents();
  }

  // Message Handling
  async sendMessage(message: string): Promise<void> {
    const currentAgent = this.agentManager.getCurrentAgent();
    if (!currentAgent) {
      throw new Error('No current agent selected');
    }

    await this.sendMessageToAgent(currentAgent, message);
  }

  async sendMessageToAgent(agent: ActiveAgent, message: string): Promise<void> {
    // If agent is creating, queue the message
    if (agent.isCreating) {
      this.queueManager.queueMessage(agent, message);
      return;
    }

    // If agent is processing and queue mode is on, queue the message
    if (agent.isProcessing && this.queueManager.isQueueMode()) {
      this.queueManager.queueMessage(agent, message);
      return;
    }

    // If agent is processing and queue mode is off, terminate and send new message
    if (agent.isProcessing && !this.queueManager.isQueueMode()) {
      await this.processManager.terminateAgentProcess(agent);
    }

    // Send the message
    await this.processManager.startAgentProcess(agent, message);
  }

  private async processAgentQueue(agent: ActiveAgent): Promise<void> {
    if (!this.queueManager.isQueueMode() || agent.isProcessing) {
      return;
    }

    // Get all queued messages and send them as one batch
    const queuedMessages: string[] = [];
    let message = this.queueManager.processNextMessage(agent);
    while (message) {
      queuedMessages.push(message);
      message = this.queueManager.processNextMessage(agent);
    }

    if (queuedMessages.length > 0) {
      const batchedMessage = queuedMessages.join('\n');
      await this.processManager.startAgentProcess(agent, batchedMessage);
    }
  }

  // Configuration
  toggleStreamingMode(): boolean {
    this.config.streamingMode = !this.config.streamingMode;
    return this.config.streamingMode;
  }

  toggleVerboseMode(): boolean {
    this.config.verbose = !this.config.verbose;
    return this.config.verbose;
  }

  toggleQueueMode(): boolean {
    return this.queueManager.toggleQueueMode();
  }

  getConfig(): MultiAgentConfig {
    return { ...this.config };
  }

  // Utility
  getQueueStatus(): { agent: ActiveAgent; queueLength: number }[] {
    const agents = this.agentManager.getAllAgents();
    return this.queueManager.getAgentsWithQueues(agents).map(agent => ({
      agent,
      queueLength: this.queueManager.getQueueLength(agent)
    }));
  }
}