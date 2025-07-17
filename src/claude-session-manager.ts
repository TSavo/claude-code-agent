/**
 * Claude Code Session Management Framework
 * 
 * Provides TypeScript framework for managing Claude Code sessions with:
 * - Agent designation and persistence
 * - Session ID tracking and resumption
 * - JSON output parsing and validation
 * - Context management and retrieval
 */

import { spawn } from 'child_process';
import { promises as fs } from 'fs';
import * as fsSync from 'fs';
import * as path from 'path';
import chalk from 'chalk';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Conversation content types
 */
type ConversationContent = 
  | { text: string }
  | { content: Array<{ type: string; text?: string; name?: string }> | string }
  | Record<string, unknown>;

/**
 * Conversation buffer entry
 */
interface ConversationBufferEntry {
  sessionId: string;
  type: string;
  content: ConversationContent;
  timestamp: Date;
}

// Memory Bank imports  
import * as os from 'os';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Types for Claude Code JSON responses
export interface ClaudeResponse {
  type: 'result' | 'error';
  subtype?: 'success' | 'failure';
  is_error: boolean;
  duration_ms: number;
  duration_api_ms: number;
  num_turns: number;
  result: string;
  session_id: string;
  total_cost_usd: number;
  usage: {
    input_tokens: number;
    cache_creation_input_tokens: number;
    cache_read_input_tokens: number;
    output_tokens: number;
    server_tool_use: {
      web_search_requests: number;
    };
    service_tier: string;
  };
  error?: string;
}

export interface AgentSession {
  agentName: string;
  sessionId: string;
  lastPrompt: string;
  lastResponse: string;
  createdAt: Date;
  lastUsedAt: Date;
  totalCost: number;
  totalTurns: number;
  context: string[];
}

export interface SessionManagerConfig {
  sessionsFile?: string;
  claudeCommand?: string;
  workingDirectory?: string;
  defaultOutputFormat?: 'json' | 'text' | 'stream-json';
  verbose?: boolean;
  suppressConsoleOutput?: boolean;
}

export class ClaudeSessionManager {
  private sessions: Map<string, AgentSession> = new Map();
  private config: Required<SessionManagerConfig>;
  
  // Memory Bank services
  private memoryBankEnabled: boolean = false;
  private memoryBankSessionMapping: Map<string, string> = new Map(); // claude_session_id -> memory_bank_session_id
  private conversationBuffer: ConversationBufferEntry[] = [];
  private memoryBankScriptPath: string;

  constructor(config: SessionManagerConfig = {}) {
    this.config = {
      sessionsFile: config.sessionsFile || '.claude-sessions.json',
      claudeCommand: config.claudeCommand || 'claude',
      workingDirectory: config.workingDirectory || process.cwd(),
      defaultOutputFormat: config.defaultOutputFormat || 'json',
      verbose: config.verbose || false,
      suppressConsoleOutput: config.suppressConsoleOutput || false
    };
    
    // Set up Memory Bank script path
    this.memoryBankScriptPath = path.join(__dirname, '../test-memory-bank/memory-bank-integration.py');
  }

  /**
   * Debug logging to file
   */
  private logDebug(message: string): void {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] ${message}\n`;
    
    try {
      const logPath = path.join(os.homedir(), '.claude', 'memory_bank_debug.log');
      fsSync.appendFileSync(logPath, logMessage);
    } catch (error) {
      // Silent fail - don't break the main flow
      console.error('Debug logging failed:', error);
    }
  }

  /**
   * Initialize session manager and load existing sessions
   */
  async initialize(): Promise<void> {
    this.logDebug('SessionManager initializing...');
    await this.loadSessions();
    await this.initializeMemoryBank();
    this.logDebug('SessionManager initialization complete');
  }

  /**
   * Initialize Memory Bank services
   */
  private async initializeMemoryBank(): Promise<void> {
    try {
      // Check if Memory Bank script exists
      this.logDebug(`Checking Memory Bank script at: ${this.memoryBankScriptPath}`);
      if (await fs.access(this.memoryBankScriptPath).then(() => true).catch(() => false)) {
        this.memoryBankEnabled = true;
        this.logDebug('Memory Bank integration enabled');
        if (!this.config.suppressConsoleOutput) {
          console.log(chalk.green('🧠 Memory Bank integration enabled'));
        }
      } else {
        this.logDebug('Memory Bank script not found - Memory Bank disabled');
        if (!this.config.suppressConsoleOutput) {
          console.log(chalk.yellow('⚠️ Memory Bank script not found - Memory Bank disabled'));
        }
      }
    } catch (error) {
      this.logDebug(`Memory Bank initialization failed: ${error instanceof Error ? error.message : error}`);
      if (!this.config.suppressConsoleOutput) {
        console.log(chalk.yellow(`⚠️ Memory Bank initialization failed: ${error instanceof Error ? error.message : error}`));
      }
    }
  }

  /**
   * Store conversation data in Memory Bank using Python script
   */
  public async storeConversationInMemoryBank(claudeSessionId: string, type: string, content: ConversationContent): Promise<void> {
    if (!this.memoryBankEnabled) {
      this.logDebug('Memory Bank not enabled, skipping storage');
      return;
    }
    
    try {
      // Format content with proper conversational context for Memory Bank
      let textContent = '';
      if (type === 'assistant' && 'content' in content && content.content) {
        if (Array.isArray(content.content)) {
          const assistantText = content.content
            .map((item) => item.type === 'text' ? item.text : `[${item.type}: ${item.name || 'tool'}]`)
            .join(' ');
          textContent = `Claude responded: ${assistantText}`;
        } else if (typeof content.content === 'string') {
          textContent = `Claude responded: ${content.content}`;
        }
      } else if (type === 'user_prompt' && 'text' in content && content.text) {
        textContent = `User said: ${content.text}`;
      } else if (type === 'user') {
        textContent = `Tool returned: ${JSON.stringify(content)}`;
      } else if (type === 'result') {
        textContent = `Final result: ${JSON.stringify(content)}`;
      } else {
        textContent = `${type}: ${JSON.stringify(content)}`;
      }
      
      this.logDebug(`Storing ${type} for session ${claudeSessionId}: ${textContent.substring(0, 100)}...`);
      
      // Add to buffer
      this.conversationBuffer.push({
        sessionId: claudeSessionId,
        type,
        content: { text: textContent },
        timestamp: new Date()
      });
      
      // Store immediately in Memory Bank using Python script
      const result = await execAsync(`python3 "${this.memoryBankScriptPath}" store "${claudeSessionId}" "${type}" "${textContent.replace(/"/g, '\\"')}"`);
      this.logDebug(`Storage result: ${result.stdout}`);
      if (result.stderr) {
        this.logDebug(`Storage stderr: ${result.stderr}`);
      }
      
      // Periodically generate memories
      if (this.conversationBuffer.length >= 5) {
        this.logDebug(`Buffer reached 5 items, generating memories for ${claudeSessionId}`);
        await this.generateMemories(claudeSessionId);
        this.conversationBuffer = []; // Clear buffer after generating memories
      }
      
    } catch (error) {
      this.logDebug(`Memory Bank storage failed: ${error instanceof Error ? error.message : error}`);
      // Silently fail - don't break the main conversation flow
      if (this.config.verbose && !this.config.suppressConsoleOutput) {
        console.log(chalk.yellow(`⚠️ Memory Bank storage failed: ${error instanceof Error ? error.message : error}`));
      }
    }
  }

  /**
   * Generate memories from accumulated conversation data
   */
  private async generateMemories(claudeSessionId: string): Promise<void> {
    if (!this.memoryBankEnabled) {
      this.logDebug('Memory Bank not enabled, skipping memory generation');
      return;
    }
    
    try {
      this.logDebug(`Generating memories for session ${claudeSessionId}`);
      const result = await execAsync(`python3 "${this.memoryBankScriptPath}" generate "${claudeSessionId}"`);
      this.logDebug(`Memory generation result: ${result.stdout}`);
      if (result.stderr) {
        this.logDebug(`Memory generation stderr: ${result.stderr}`);
      }
    } catch (error) {
      this.logDebug(`Memory generation failed: ${error instanceof Error ? error.message : error}`);
      if (this.config.verbose && !this.config.suppressConsoleOutput) {
        console.log(chalk.yellow(`⚠️ Memory generation failed: ${error instanceof Error ? error.message : error}`));
      }
    }
  }

  /**
   * Retrieve relevant memories and write to context file
   */
  public async retrieveMemories(claudeSessionId: string, contextHint: string = ""): Promise<void> {
    if (!this.memoryBankEnabled) {
      this.logDebug('Memory Bank not enabled, skipping retrieval');
      return;
    }
    
    try {
      this.logDebug(`Retrieving memories for session ${claudeSessionId} with hint: "${contextHint}"`);
      const result = await execAsync(`python3 "${this.memoryBankScriptPath}" retrieve "${claudeSessionId}" "${contextHint}"`);
      this.logDebug(`Memory retrieval result: ${result.stdout}`);
      if (result.stderr) {
        this.logDebug(`Memory retrieval stderr: ${result.stderr}`);
      }
    } catch (error) {
      this.logDebug(`Memory retrieval failed: ${error instanceof Error ? error.message : error}`);
      if (this.config.verbose && !this.config.suppressConsoleOutput) {
        console.log(chalk.yellow(`⚠️ Memory retrieval failed: ${error instanceof Error ? error.message : error}`));
      }
    }
  }

  /**
   * Flush conversation buffer to ensure all data is stored
   */
  private async flushConversationBuffer(): Promise<void> {
    // Generate memories for any remaining buffered conversations
    const sessions = new Set(this.conversationBuffer.map(item => item.sessionId));
    const sessionArray = Array.from(sessions);
    for (const sessionId of sessionArray) {
      await this.generateMemories(sessionId);
    }
    this.conversationBuffer = [];
  }

  /**
   * Designate an agent with an initial prompt and create session
   */
  async designateAgent(agentName: string, initialPrompt: string, eventHandler?: (event: any) => void): Promise<AgentSession> {
    this.logDebug(`Creating agent: ${agentName} with prompt: ${initialPrompt.substring(0, 100)}...`);
    if (!this.config.suppressConsoleOutput) {
      console.log(chalk.blue(`🔄 Starting agent creation for ${agentName}...`));
    }
    
    // Create a more explicit agent setup prompt
    const setupPrompt = `${initialPrompt}

For this conversation, you will roleplay as this character. When I ask "What is your name?" or similar questions, respond as this character would. Acknowledge that you understand your role.`;
    
    const response = await this.executeClaudeCommandStreaming(setupPrompt, undefined, agentName, eventHandler);
    
    const session: AgentSession = {
      agentName,
      sessionId: response.session_id,
      lastPrompt: initialPrompt,
      lastResponse: response.result,
      createdAt: new Date(),
      lastUsedAt: new Date(),
      totalCost: response.total_cost_usd,
      totalTurns: response.num_turns,
      context: [initialPrompt, response.result]
    };

    this.sessions.set(agentName, session);
    await this.saveSessions();
    
    return session;
  }

  /**
   * Get existing session for an agent
   */
  getAgentSession(agentName: string): AgentSession | undefined {
    return this.sessions.get(agentName);
  }

  /**
   * Resume session with an agent by name
   */
  async resumeAgent(agentName: string, prompt: string, eventHandler?: (event: any) => void): Promise<ClaudeResponse> {
    this.logDebug(`Resuming agent: ${agentName} with prompt: ${prompt.substring(0, 100)}...`);
    const session = this.sessions.get(agentName);
    if (!session) {
      throw new Error(`No session found for agent: ${agentName}`);
    }

    const response = await this.executeClaudeCommandStreaming(prompt, session.sessionId, agentName, eventHandler);
    
    // Update session data
    session.lastPrompt = prompt;
    session.lastResponse = response.result;
    session.lastUsedAt = new Date();
    session.totalCost += response.total_cost_usd;
    session.totalTurns += response.num_turns;
    session.context.push(prompt, response.result);
    
    // Keep context manageable (last 20 interactions)
    if (session.context.length > 40) {
      session.context = session.context.slice(-40);
    }

    await this.saveSessions();
    return response;
  }

  /**
   * Get the last thing said to/by an agent
   */
  async getLastInteraction(agentName: string): Promise<{ prompt: string; response: string } | null> {
    const session = this.sessions.get(agentName);
    if (!session) {
      return null;
    }

    return {
      prompt: session.lastPrompt,
      response: session.lastResponse
    };
  }

  /**
   * Get full context history for an agent
   */
  getAgentContext(agentName: string): string[] | null {
    const session = this.sessions.get(agentName);
    return session ? [...session.context] : null;
  }

  /**
   * Ask agent what was the last thing you said
   */
  async askLastThing(agentName: string): Promise<ClaudeResponse> {
    return this.resumeAgent(agentName, "What's the last thing I said?");
  }

  /**
   * List all active agent sessions
   */
  listAgents(): Array<{ name: string; sessionId: string; lastUsed: Date; totalCost: number }> {
    return Array.from(this.sessions.entries()).map(([name, session]) => ({
      name,
      sessionId: session.sessionId,
      lastUsed: session.lastUsedAt,
      totalCost: session.totalCost
    }));
  }

  /**
   * Remove an agent session
   */
  async removeAgent(agentName: string): Promise<boolean> {
    const deleted = this.sessions.delete(agentName);
    if (deleted) {
      await this.saveSessions();
    }
    return deleted;
  }

  /**
   * Clear all sessions
   */
  async clearAllSessions(): Promise<void> {
    this.sessions.clear();
    await this.saveSessions();
  }

  /**
   * Execute Claude command with streaming output for agent creation
   */
  private async executeClaudeCommandStreaming(prompt: string, sessionId?: string, agentName?: string, eventHandler?: (event: any) => void): Promise<ClaudeResponse> {
    // Retrieve relevant memories before processing (MUST be awaited)
    if (sessionId && agentName) {
      // Build richer context from recent USER messages only (no assistant responses)
      const agentContext = this.getAgentContext(agentName) || [];
      // Extract only user prompts (even indices in context array)
      const userPrompts = agentContext.filter((_, index) => index % 2 === 0);
      const recentUserContext = userPrompts.slice(-3); // Last 3 user prompts
      const contextHint = [...recentUserContext, prompt].join(' '); // NO substring - keep full context
      
      this.logDebug(`About to retrieve memories for streaming command, session: ${sessionId}, expanded hint: "${contextHint.substring(0, 100)}..."`);
      await this.retrieveMemories(sessionId, contextHint);
    }

    return new Promise((resolve, reject) => {
      const args: string[] = [];
      
      if (sessionId) {
        args.push('-r', sessionId);
      }
      
      args.push('-p', prompt, '--output-format', 'stream-json', '--verbose', '--dangerously-skip-permissions');
      
      // Add home directory as additional working directory
      const homeDir = os.homedir();
      args.push('--add-dir', homeDir);

      if (!this.config.suppressConsoleOutput) {
        console.log(chalk.gray(`🔧 Command: ${this.config.claudeCommand} ${args.join(' ')}`));
      }

      // Store the user's prompt in Memory Bank  
      if (sessionId) {
        this.storeConversationInMemoryBank(sessionId, 'user_prompt', { text: prompt });
      }

      const claudeProcess = spawn(this.config.claudeCommand, args, {
        cwd: this.config.workingDirectory,
        stdio: ['inherit', 'pipe', 'pipe']
      });

      let finalResponse: ClaudeResponse | null = null;

      claudeProcess.stdout.on('data', (data) => {
        const lines = data.toString().split('\n').filter((line: string) => line.trim());
        
        lines.forEach((line: string) => {
          try {
            const jsonData = JSON.parse(line);
            
            switch (jsonData.type) {
              case 'system':
                if (!this.config.suppressConsoleOutput) {
                  console.log(chalk.blue(`🔧 ${agentName || 'Claude'} system: Session ${jsonData.session_id?.substring(0, 8)}... initialized`));
                }
                // Store system initialization
                if (sessionId) {
                  this.storeConversationInMemoryBank(sessionId, 'system', { session_id: jsonData.session_id });
                }
                break;
                
              case 'assistant':
                const message = jsonData.message;
                if (message?.content) {
                  const content = message.content;
                  if (Array.isArray(content)) {
                    content.forEach((item: { type: string; text?: string; name?: string; input?: { description?: string } }) => {
                      if (item.type === 'text') {
                        if (!this.config.suppressConsoleOutput) {
                          console.log(chalk.green(`💬 ${agentName || 'Claude'}: ${item.text}`));
                        }
                        // Emit event for TUI to capture
                        if (eventHandler) {
                          const event = {
                            type: 'process_output',
                            agentName: agentName || 'Claude',
                            data: { type: 'assistant', content: [{ type: 'text', text: item.text }] }
                          };
                          
                          // Debug logging
                          const fs = require('fs');
                          const debugMsg = `[${new Date().toISOString()}] SESSION-MANAGER: Calling eventHandler with: ${JSON.stringify(event)}\n`;
                          fs.appendFileSync('/tmp/agent-creation-debug.log', debugMsg);
                          
                          eventHandler(event);
                        }
                      } else if (item.type === 'tool_use') {
                        if (!this.config.suppressConsoleOutput) {
                          console.log(chalk.magenta(`🔧 ${agentName || 'Claude'} using ${item.name}: ${item.input?.description || 'Executing tool'}`));
                        }
                        // Emit tool use event
                        if (eventHandler) {
                          const event = {
                            type: 'tool_use',
                            agentName: agentName || 'Claude',
                            data: { 
                              type: 'tool_use', 
                              name: item.name,
                              input: item.input,
                              description: item.input?.description || 'Executing tool'
                            }
                          };
                          eventHandler(event);
                        }
                      }
                    });
                  } else if (typeof content === 'string') {
                    if (!this.config.suppressConsoleOutput) {
                      console.log(chalk.green(`💬 ${agentName || 'Claude'}: ${content}`));
                    }
                    // Emit event for TUI to capture
                    if (eventHandler) {
                      const event = {
                        type: 'process_output',
                        agentName: agentName || 'Claude',
                        data: { type: 'assistant', content: [{ type: 'text', text: content }] }
                      };
                      
                      // Debug logging
                      const fs = require('fs');
                      const debugMsg = `[${new Date().toISOString()}] SESSION-MANAGER: Calling eventHandler with string content: ${JSON.stringify(event)}\n`;
                      fs.appendFileSync('/tmp/agent-creation-debug.log', debugMsg);
                      
                      eventHandler(event);
                    }
                  }
                  
                  // Store assistant message in Memory Bank
                  if (sessionId) {
                    this.storeConversationInMemoryBank(sessionId, 'assistant', message);
                  }
                }
                break;
                
              case 'user':
                if (!this.config.suppressConsoleOutput) {
                  console.log(chalk.cyan(`📋 ${agentName || 'Claude'} tool results received`));
                }
                
                // Debug logging to file
                const fs = require('fs');
                const debugMsg = `[${new Date().toISOString()}] USER EVENT: ${JSON.stringify(jsonData, null, 2)}\n`;
                fs.appendFileSync('/tmp/tool-result-debug.log', debugMsg);
                
                // Emit tool result event - check for tool result content
                if (eventHandler && jsonData.message && jsonData.message.content) {
                  const content = jsonData.message.content;
                  if (Array.isArray(content) && content.length > 0 && content[0].type === 'tool_result') {
                    const event = {
                      type: 'tool_result',
                      agentName: agentName || 'Claude',
                      data: {
                        content: content[0].content,
                        tool_use_id: content[0].tool_use_id
                      }
                    };
                    const eventMsg = `[${new Date().toISOString()}] EMITTING tool_result: ${JSON.stringify(event, null, 2)}\n`;
                    fs.appendFileSync('/tmp/tool-result-debug.log', eventMsg);
                    eventHandler(event);
                  }
                }
                // Store user message/tool results
                if (sessionId) {
                  this.storeConversationInMemoryBank(sessionId, 'user', jsonData);
                }
                break;
                
              case 'result':
                finalResponse = jsonData;
                // Store final result and flush buffer
                if (sessionId) {
                  this.storeConversationInMemoryBank(sessionId, 'result', jsonData);
                  this.flushConversationBuffer(); // Ensure all data is stored
                }
                break;
                
              default:
                if (!this.config.suppressConsoleOutput) {
                  console.log(chalk.gray(`📄 ${agentName || 'Claude'} (${jsonData.type}): Processing...`));
                }
                // Store other message types
                if (sessionId) {
                  this.storeConversationInMemoryBank(sessionId, jsonData.type, jsonData);
                }
                break;
            }
          } catch (_error) {
            // Skip malformed JSON lines
          }
        });
      });

      claudeProcess.stderr.on('data', (data) => {
        if (!this.config.suppressConsoleOutput) {
          console.error(chalk.red(`⚠️  ${agentName || 'Claude'} stderr: ${data.toString()}`));
        }
      });

      claudeProcess.on('close', (code) => {
        if (code !== 0) {
          if (!this.config.suppressConsoleOutput) {
            console.error(chalk.red(`🐛 ${agentName || 'Claude'} command failed with code ${code}`));
          }
          reject(new Error(`Claude command failed with code ${code}`));
          return;
        }

        if (finalResponse) {
          resolve(finalResponse);
        } else {
          reject(new Error('No final response received from streaming Claude command'));
        }
      });

      claudeProcess.on('error', (error) => {
        reject(new Error(`Failed to execute Claude command: ${error.message}`));
      });
    });
  }

  /**
   * Execute Claude command with optional session resumption (non-streaming)
   */
  private async executeClaudeCommand(prompt: string, sessionId?: string): Promise<ClaudeResponse> {
    // Retrieve relevant memories before processing (MUST be awaited)
    if (sessionId) {
      this.logDebug(`About to retrieve memories for regular command, session: ${sessionId}, hint: "${prompt.substring(0, 100)}..."`);
      await this.retrieveMemories(sessionId, prompt); // Use full prompt as context hint
    }

    return new Promise((resolve, reject) => {
      const args: string[] = [];
      
      if (sessionId) {
        args.push('-r', sessionId);
      }
      
      args.push('-p', prompt, '--output-format', this.config.defaultOutputFormat);
      
      // stream-json requires --verbose when using --print
      if (this.config.defaultOutputFormat === 'stream-json' || this.config.verbose) {
        args.push('--verbose');
      }
      
      args.push('--dangerously-skip-permissions');
      
      // Add home directory as additional working directory
      const homeDir = os.homedir();
      args.push('--add-dir', homeDir);

      const claudeProcess = spawn(this.config.claudeCommand, args, {
        cwd: this.config.workingDirectory,
        stdio: ['inherit', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      claudeProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      claudeProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      claudeProcess.on('close', (code) => {
        if (code !== 0) {
          console.error(chalk.red('🐛 Claude command failed:'));
          console.error(chalk.red(`   Exit code: ${code}`));
          console.error(chalk.red(`   Command: ${this.config.claudeCommand} ${args.join(' ')}`));
          console.error(chalk.red(`   STDERR: ${stderr}`));
          reject(new Error(`Claude command failed with code ${code}: ${stderr}`));
          return;
        }

        try {
          // Handle stream-json format - parse the last complete JSON object
          let response: ClaudeResponse | undefined = undefined;
          
          if (this.config.defaultOutputFormat === 'stream-json') {
            // Split by lines and find the last valid JSON with type: "result" 
            const lines = stdout.trim().split('\n').filter(line => line.trim());
            let resultFound = false;
            
            for (let i = lines.length - 1; i >= 0; i--) {
              try {
                const jsonData = JSON.parse(lines[i]);
                if (jsonData.type === 'result' || jsonData.result) {
                  response = jsonData;
                  resultFound = true;
                  break;
                }
              } catch (_e) {
                // Skip malformed lines
                continue;
              }
            }
            
            if (!resultFound || !response) {
              console.error(chalk.red('🐛 Debug - No result found in stream-json output:'));
              console.error(chalk.gray(stdout.substring(0, 500) + '...'));
              reject(new Error('No valid result found in stream-json output'));
              return;
            }
          } else {
            response = JSON.parse(stdout.trim());
          }
          
          if (response) {
            resolve(response);
          } else {
            reject(new Error('No response parsed from Claude output'));
          }
        } catch (_error) {
          console.error(chalk.red('🐛 Debug - JSON Parse Error:'));
          console.error(chalk.red(`   Error: ${_error}`));
          console.error(chalk.red(`   Command: ${this.config.claudeCommand} ${args.join(' ')}`));
          console.error(chalk.gray('🐛 Raw stdout (first 500 chars):'));
          console.error(chalk.gray(stdout.substring(0, 500) + '...'));
          console.error(chalk.gray('🐛 Raw stdout (last 500 chars):'));
          console.error(chalk.gray('...' + stdout.substring(Math.max(0, stdout.length - 500))));
          reject(new Error(`Failed to parse Claude JSON response: ${_error}`));
        }
      });

      claudeProcess.on('error', (error) => {
        reject(new Error(`Failed to execute Claude command: ${error.message}`));
      });
    });
  }

  /**
   * Load sessions from file
   */
  private async loadSessions(): Promise<void> {
    try {
      const sessionsPath = path.resolve(this.config.workingDirectory, this.config.sessionsFile);
      const data = await fs.readFile(sessionsPath, 'utf-8');
      const sessionsData = JSON.parse(data);
      
      this.sessions.clear();
      for (const [agentName, sessionData] of Object.entries(sessionsData)) {
        const session = sessionData as AgentSession & { createdAt: string; lastUsedAt: string };
        this.sessions.set(agentName, {
          ...session,
          createdAt: new Date(session.createdAt),
          lastUsedAt: new Date(session.lastUsedAt)
        });
      }
    } catch (_error) {
      // File doesn't exist or is invalid, start with empty sessions
      this.sessions.clear();
    }
  }

  /**
   * Save sessions to file
   */
  private async saveSessions(): Promise<void> {
    const sessionsPath = path.resolve(this.config.workingDirectory, this.config.sessionsFile);
    const sessionsData = Object.fromEntries(this.sessions.entries());
    await fs.writeFile(sessionsPath, JSON.stringify(sessionsData, null, 2), 'utf-8');
  }
}

// Utility functions for common patterns
export class ClaudeAgentUtils {
  /**
   * Create a quick agent manager instance
   */
  static async createManager(config?: SessionManagerConfig): Promise<ClaudeSessionManager> {
    const manager = new ClaudeSessionManager(config);
    await manager.initialize();
    return manager;
  }

  /**
   * Quick agent designation helper
   */
  static async designate(agentName: string, role: string, context?: string): Promise<AgentSession> {
    const manager = await ClaudeAgentUtils.createManager();
    const prompt = context 
      ? `Your name is ${agentName}. Your role: ${role}. Context: ${context}`
      : `Your name is ${agentName}. Your role: ${role}`;
    return manager.designateAgent(agentName, prompt);
  }

  /**
   * Quick resume helper
   */
  static async resume(agentName: string, prompt: string): Promise<ClaudeResponse> {
    const manager = await ClaudeAgentUtils.createManager();
    return manager.resumeAgent(agentName, prompt);
  }

  /**
   * Quick "what did I last say" helper
   */
  static async lastThing(agentName: string): Promise<ClaudeResponse> {
    const manager = await ClaudeAgentUtils.createManager();
    return manager.askLastThing(agentName);
  }
}

export default ClaudeSessionManager;