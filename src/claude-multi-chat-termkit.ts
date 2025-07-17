#!/usr/bin/env tsx

/**
 * Claude Multi-Agent Terminal-Kit TUI
 * 
 * Terminal-kit based TUI for managing multiple Claude agents with:
 * - Agent list panel with status indicators
 * - Real-time output area with proper scrolling
 * - Input area with command completion
 * - Status bar showing modes and queue info
 * - No scrolling corruption issues!
 */

import * as termkit from 'terminal-kit';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { MultiAgentController, ActiveAgent } from './multi-agent-core';

const term = termkit.terminal;

interface TUIState {
  agents: ActiveAgent[];
  currentAgent: ActiveAgent | null;
  outputLines: string[];
  inputText: string;
  inputLines: string[]; // Support multi-line input
  currentInputLine: number; // Track current line being edited
  outputScrollOffset: number; // Track scroll position in output
  streamingMode: boolean;
  verbose: boolean;
  queueMode: boolean;
  showHelp: boolean;
  running: boolean;
}

interface TUIPreferences {
  queueMode: boolean;
  streamingMode: boolean;
  verbose: boolean;
  lastAgentName?: string;
  agentColors?: Record<string, string>; // Persist agent color assignments
}

class ClaudeMultiAgentTermKitTUI {
  private controller: MultiAgentController;
  private state: TUIState;
  private outputHeight: number = 100; // Much larger output area
  private agentListWidth: number = 25;
  private prefsFile: string;
  private agentColors: Map<string, string> = new Map(); // Agent name -> color code
  private availableColors: string[] = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'red', 'white']; // Terminal-kit color names
  private colorIndex: number = 0;

  constructor() {
    this.prefsFile = path.join(os.homedir(), '.claude', 'termkit-prefs.json');
    
    // Load saved preferences
    const prefs = this.loadPreferences();
    
    this.controller = new MultiAgentController({
      streamingMode: prefs.streamingMode,
      verbose: true, // Keep verbose for Claude command functionality
      queueMode: prefs.queueMode,
      suppressConsoleOutput: true // New flag to suppress console output in TUI
    });

    this.state = {
      agents: [],
      currentAgent: null,
      outputLines: [
        '🚀 Claude Multi-Agent TUI (Terminal-Kit)',
        'Type /help for commands',
        'Press Shift+Enter for new line, Enter to send',
        ''
      ],
      inputText: '',
      inputLines: [''],
      currentInputLine: 0,
      outputScrollOffset: 0, // 0 = showing most recent, positive = scrolled up
      streamingMode: prefs.streamingMode,
      verbose: prefs.verbose,
      queueMode: prefs.queueMode,
      showHelp: false,
      running: true
    };
    
    // Load saved agent colors
    if (prefs.agentColors) {
      for (const [agentName, color] of Object.entries(prefs.agentColors)) {
        this.agentColors.set(agentName, color);
      }
      this.colorIndex = Object.keys(prefs.agentColors).length;
    }
  }

  async initialize(): Promise<void> {
    // Setup terminal
    term.fullscreen(true);
    term.hideCursor();
    term.clear();

    // Set up event listeners BEFORE initializing controller
    this.setupControllerEvents();

    // Initialize controller
    await this.controller.initialize();

    // Setup input handling
    this.setupInput();

    // Initial render
    this.render();

    // Update agent list
    this.updateAgentList();
    
    // Restore last used agent if available
    const prefs = this.loadPreferences();
    if (prefs.lastAgentName && this.state.agents.length > 0) {
      const lastAgent = this.state.agents.find(a => a.name === prefs.lastAgentName);
      if (lastAgent) {
        this.controller.switchToAgent(lastAgent.name);
        this.updateAgentList();
        this.addOutput(`Restored last used agent: ${lastAgent.name}`);
      }
    }
  }

  private loadPreferences(): TUIPreferences {
    const defaultPrefs: TUIPreferences = {
      queueMode: false,
      streamingMode: true,
      verbose: true
    };
    
    try {
      if (fs.existsSync(this.prefsFile)) {
        const data = fs.readFileSync(this.prefsFile, 'utf8');
        return { ...defaultPrefs, ...JSON.parse(data) };
      }
    } catch (error) {
      console.error('Failed to load preferences:', error);
    }
    
    return defaultPrefs;
  }

  private savePreferences(): void {
    try {
      const prefsDir = path.dirname(this.prefsFile);
      if (!fs.existsSync(prefsDir)) {
        fs.mkdirSync(prefsDir, { recursive: true });
      }
      
      const prefs: TUIPreferences = {
        queueMode: this.state.queueMode,
        streamingMode: this.state.streamingMode,
        verbose: this.state.verbose,
        lastAgentName: this.state.currentAgent?.name,
        agentColors: Object.fromEntries(this.agentColors)
      };
      
      fs.writeFileSync(this.prefsFile, JSON.stringify(prefs, null, 2));
    } catch (error) {
      console.error('Failed to save preferences:', error);
    }
  }

  private getAgentColor(agentName: string): string {
    if (!this.agentColors.has(agentName)) {
      // Assign a new color to this agent
      const color = this.availableColors[this.colorIndex % this.availableColors.length];
      this.agentColors.set(agentName, color);
      this.colorIndex++;
    }
    return this.agentColors.get(agentName)!;
  }

  private setupControllerEvents(): void {
    this.controller.on('agent_created', (event) => {
      const agentColor = this.getAgentColor(event.agentName);
      this.state.outputLines.push(`^${agentColor[0]}✅ Agent "${event.agentName}" created^:`);
      this.renderOutput();
      this.updateAgentList();
      this.savePreferences(); // Save when agent is created and becomes current
    });

    this.controller.on('agent_switched', (event) => {
      const agentColor = this.getAgentColor(event.agentName);
      this.state.outputLines.push(`^${agentColor[0]}🔄 Switched to agent "${event.agentName}"^:`);
      this.renderOutput();
      this.updateAgentList();
      this.savePreferences(); // Save when agent is switched
    });

    this.controller.on('process_output', (event) => {
      this.handleProcessOutput(event);
    });

    this.controller.on('process_started', (event) => {
      // Skip started messages for cleaner output
      this.updateAgentList();
    });

    this.controller.on('process_completed', (event) => {
      // Add subtle completion indicator
      this.addOutput(`  ✓ ${event.agentName} finished`);
      this.updateAgentList();
    });

    this.controller.on('process_error', (event) => {
      this.addOutput(`❌ ${event.agentName} error: ${event.data.error}`);
      this.updateAgentList();
    });

    this.controller.on('message_queued', (event) => {
      this.addOutput(`📥 Queued message for ${event.agentName} (${event.queueLength} in queue)`);
    });
  }

  private setupInput(): void {
    // Use grabInput with mouse support for better control including wheel
    term.grabInput({ mouse: 'button' });
    
    // Handle mouse events
    term.on('mouse', (name: string, data: any) => {
      if (name === 'MOUSE_LEFT_BUTTON_PRESSED') {
        this.handleMouseClick(data.x, data.y, 'left');
      } else if (name === 'MOUSE_RIGHT_BUTTON_PRESSED') {
        this.handleMouseClick(data.x, data.y, 'right');
      } else if (name === 'MOUSE_WHEEL_UP') {
        this.scrollOutput(3); // Scroll up 3 lines
      } else if (name === 'MOUSE_WHEEL_DOWN') {
        this.scrollOutput(-3); // Scroll down 3 lines
      }
    });
    
    term.on('key', async (name: string, matches: any, data: any) => {
      if (name === 'CTRL_C') {
        this.cleanup();
        process.exit(0);
      }

      if (name === 'ENTER') {
        // Check if shift is held for new line
        if (data && data.shift) {
          // Shift+Enter: add new line
          this.state.inputLines.push('');
          this.state.currentInputLine++;
          this.renderInputArea();
        } else {
          // Regular Enter: send message
          const fullInput = this.state.inputLines.join('\n').trim();
          if (fullInput) {
            await this.handleInput();
          }
        }
        return;
      }

      if (name === 'BACKSPACE') {
        const currentLine = this.state.inputLines[this.state.currentInputLine];
        if (currentLine.length > 0) {
          // Remove character from current line
          this.state.inputLines[this.state.currentInputLine] = currentLine.slice(0, -1);
          this.renderInputArea();
        } else if (this.state.currentInputLine > 0) {
          // Remove current empty line and move up
          this.state.inputLines.splice(this.state.currentInputLine, 1);
          this.state.currentInputLine--;
          this.renderInputArea();
        }
        return;
      }

      if (name === 'UP') {
        if (this.state.currentInputLine > 0) {
          this.state.currentInputLine--;
          this.renderInputArea();
        }
        return;
      }

      if (name === 'DOWN') {
        if (this.state.currentInputLine < this.state.inputLines.length - 1) {
          this.state.currentInputLine++;
          this.renderInputArea();
        }
        return;
      }

      // Regular character input
      if (data && data.isCharacter && data.codepoint) {
        const char = String.fromCharCode(data.codepoint);
        if (char && char.length === 1 && char.charCodeAt(0) >= 32) { // Printable characters only
          this.state.inputLines[this.state.currentInputLine] += char;
          this.renderInputArea();
        }
      }
    });
  }

  private scrollOutput(lines: number): void {
    const outputHeight = this.calculateAvailableOutputHeight();
    const maxScrollOffset = Math.max(0, this.state.outputLines.length - outputHeight);
    
    this.state.outputScrollOffset = Math.max(0, Math.min(maxScrollOffset, this.state.outputScrollOffset + lines));
    this.renderOutput();
  }

  private calculateAvailableOutputHeight(): number {
    const height = term.height;
    const headerRows = 3; // Title + separator
    const maxInputLines = 5; // Reserved for input area
    const statusRows = 2; // Status bar + separator
    const helpRows = this.state.showHelp ? 10 : 0;
    return height - headerRows - statusRows - helpRows - maxInputLines - 1; // -1 for safety margin
  }

  private addOutput(text: string): void {
    this.state.outputLines.push(text);
    
    // Limit output lines
    if (this.state.outputLines.length > 1000) {
      this.state.outputLines = this.state.outputLines.slice(-1000);
    }
    
    // Reset scroll to bottom when new content arrives
    this.state.outputScrollOffset = 0;
    this.renderOutput();
  }

  private addColoredOutput(speaker: string, message: string, type: 'user' | 'assistant'): void {
    // Extract agent name from speaker (format might be "❯ AgentName" for user messages)
    const agentName = speaker.replace('❯ ', '').trim();
    const agentColor = this.getAgentColor(agentName);
    
    // Store with color codes for terminal-kit
    const coloredLine = type === 'user' 
      ? `^${agentColor[0]}${speaker}: ${message}^:` // Agent color for both speaker and message
      : `^${agentColor[0]}${speaker}: ${message}^:`; // Agent color for both speaker and message
    
    this.state.outputLines.push(coloredLine);
    
    // Limit output lines
    if (this.state.outputLines.length > 1000) {
      this.state.outputLines = this.state.outputLines.slice(-1000);
    }
    
    // Reset scroll to bottom when new content arrives
    this.state.outputScrollOffset = 0;
    this.renderOutput();
  }

  private addMultiLineOutput(speaker: string, message: string): void {
    const outputStartCol = this.agentListWidth + 2;
    const outputWidth = term.width - outputStartCol - 2; // Same calculation as render
    const agentColor = this.getAgentColor(speaker);
    const speakerPrefix = `${speaker}: `;
    
    // First split on \n (actual newlines)
    const paragraphs = message.split('\n');
    const lines: string[] = [];
    
    paragraphs.forEach((paragraph, paragraphIndex) => {
      if (paragraph.trim() === '') {
        // Empty line
        lines.push('');
        return;
      }
      
      // Now wrap each paragraph to fit width
      let remaining = paragraph;
      let isFirstInParagraph = true;
      
      while (remaining.length > 0) {
        const isVeryFirstLine = paragraphIndex === 0 && isFirstInParagraph;
        const availableWidth = isVeryFirstLine ? outputWidth - speakerPrefix.length : outputWidth - 2; // 2 for indent
        
        if (remaining.length <= availableWidth) {
          // Last chunk of this paragraph
          const line = isVeryFirstLine 
            ? `^${agentColor[0]}${speakerPrefix}${remaining}^:` // Color both speaker and message
            : `^${agentColor[0]}  ${remaining}^:`; // Color continuation lines too
          lines.push(line);
          break;
        } else {
          // Find break point
          let breakPoint = availableWidth;
          for (let i = availableWidth - 1; i >= Math.max(0, availableWidth - 20); i--) {
            if (remaining[i] === ' ' || remaining[i] === '.' || remaining[i] === ',') {
              breakPoint = i;
              break;
            }
          }
          
          const chunk = remaining.substring(0, breakPoint).trim();
          const line = isVeryFirstLine 
            ? `^${agentColor[0]}${speakerPrefix}${chunk}^:` // Color both speaker and message
            : `^${agentColor[0]}  ${chunk}^:`; // Color continuation lines too
          lines.push(line);
          
          remaining = remaining.substring(breakPoint).trim();
          isFirstInParagraph = false;
        }
      }
    });
    
    // Add all lines at once
    lines.forEach(line => {
      this.state.outputLines.push(line);
    });
    
    // Limit output lines
    if (this.state.outputLines.length > 1000) {
      this.state.outputLines = this.state.outputLines.slice(-1000);
    }
    
    // Reset scroll to bottom when new content arrives
    this.state.outputScrollOffset = 0;
    
    // Single render call
    this.renderOutput();
  }

  private updateAgentList(): void {
    this.state.agents = this.controller.getAllAgents();
    this.state.currentAgent = this.controller.getCurrentAgent();
    this.render();
  }

  private async handleInput(): Promise<void> {
    const input = this.state.inputLines.join('\n').trim();
    if (!input) return;

    // Reset input state
    this.state.inputLines = [''];
    this.state.currentInputLine = 0;
    this.state.inputText = ''; // Keep for compatibility
    this.renderInputArea();

    try {
      if (input.startsWith('/')) {
        // Commands don't get shown as messages to agents
        await this.handleCommand(input);
      } else {
        // Only show actual messages to agents
        if (!this.state.currentAgent) {
          this.addOutput('❌ No current agent selected. Use /create or /switch first.');
          return;
        }
        
        // Show the message being sent to the agent
        const targetAgent = this.state.currentAgent.name;
        this.addColoredOutput(`❯ ${targetAgent}`, input, 'user');
        
        await this.controller.sendMessage(input);
      }
    } catch (error) {
      this.addOutput(`❌ Error: ${error instanceof Error ? error.message : error}`);
    }
  }

  private async handleCommand(command: string): Promise<void> {
    const parts = command.slice(1).split(' ');
    const cmd = parts[0].toLowerCase();

    try {
      switch (cmd) {
        case 'help':
          this.addOutput('📋 Available Commands:');
          this.addOutput('/create <name> <role> - Create new agent');
          this.addOutput('/switch <name> - Switch to agent');
          this.addOutput('/delete <name> - Delete agent');
          this.addOutput('/list - List all agents');
          this.addOutput('/clear - Clear output');
          this.addOutput('/streaming - Toggle streaming mode');
          this.addOutput('/queue - Toggle queue mode');
          this.addOutput('/verbose - Toggle verbose mode');
          this.addOutput('/help - Show this help');
          this.addOutput('/exit - Quit application');
          break;

        case 'create':
        case 'agent':
          if (parts.length < 3) {
            this.addOutput('❌ Usage: /create <name> <role>');
            return;
          }
          
          // Handle quoted names and multi-word names
          const commandArgs = parts.slice(1).join(' ');
          let name: string;
          let role: string;
          
          // Check if name is quoted
          if (commandArgs.startsWith('"')) {
            const endQuoteIndex = commandArgs.indexOf('"', 1);
            if (endQuoteIndex === -1) {
              this.addOutput('❌ Unclosed quote in agent name');
              return;
            }
            name = commandArgs.substring(1, endQuoteIndex);
            role = commandArgs.substring(endQuoteIndex + 1).trim();
          } else {
            // For unquoted names, take first word as name
            const spaceIndex = commandArgs.indexOf(' ');
            if (spaceIndex === -1) {
              this.addOutput('❌ Usage: /create <name> <role>');
              return;
            }
            name = commandArgs.substring(0, spaceIndex);
            role = commandArgs.substring(spaceIndex + 1).trim();
          }
          
          if (!role) {
            this.addOutput('❌ Role cannot be empty');
            return;
          }
          
          try {
            // Pass event handler directly to createAgent
            await this.controller.createAgent(name, role, (event: any) => {
              const fs = require('fs');
              const debugMsg = `[${new Date().toISOString()}] TUI: Direct callback received event: ${JSON.stringify(event)}\n`;
              fs.appendFileSync('/tmp/agent-creation-debug.log', debugMsg);
              
              // Call the existing process_output handler directly
              this.handleProcessOutput(event);
            });
          } catch (error) {
            this.addOutput(`❌ Failed to create agent "${name}": ${error instanceof Error ? error.message : error}`);
          }
          break;

        case 'switch':
        case 'sw':
          if (parts.length < 2) {
            this.addOutput('❌ Usage: /switch <agent-name>');
            return;
          }
          const agentName = parts.slice(1).join(' '); // Join all parts for names with spaces
          this.controller.switchToAgent(agentName);
          this.updateAgentList();
          this.savePreferences(); // Save last used agent
          break;

        case 'delete':
        case 'del':
          if (parts.length < 2) {
            this.addOutput('❌ Usage: /delete <agent-name>');
            return;
          }
          const delName = parts.slice(1).join(' '); // Join all parts for names with spaces
          const success = await this.controller.removeAgent(delName);
          if (success) {
            this.addOutput(`🗑️ Agent "${delName}" deleted`);
            this.updateAgentList();
          } else {
            this.addOutput(`❌ Agent "${delName}" not found`);
          }
          break;

        case 'list':
        case 'ls':
          this.addOutput('📋 Active Agents:');
          this.state.agents.forEach(agent => {
            const status = agent.isProcessing ? '🔄' : agent.isCreating ? '⏳' : '✅';
            const current = agent.name === this.state.currentAgent?.name ? '👉 ' : '   ';
            this.addOutput(`${current}${status} ${agent.name} (${agent.sessionId.substring(0, 8)})`);
          });
          break;

        case 'clear':
          this.state.outputLines = [];
          break;

        case 'streaming':
          this.state.streamingMode = this.controller.toggleStreamingMode();
          this.addOutput(`🔄 Streaming mode: ${this.state.streamingMode ? 'ON' : 'OFF'}`);
          this.renderStatusBar();
          this.savePreferences();
          break;

        case 'queue':
          this.state.queueMode = this.controller.toggleQueueMode();
          this.addOutput(`📥 Queue mode: ${this.state.queueMode ? 'ON' : 'OFF'}`);
          this.renderStatusBar();
          this.savePreferences();
          break;

        case 'verbose':
          this.state.verbose = this.controller.toggleVerboseMode();
          this.addOutput(`🔍 Verbose mode: ${this.state.verbose ? 'ON' : 'OFF'}`);
          this.renderStatusBar();
          this.savePreferences();
          break;

        case 'exit':
        case 'quit':
          this.cleanup();
          process.exit(0);
          break;

        default:
          this.addOutput(`❌ Unknown command: ${cmd}. Type /help for available commands.`);
          break;
      }
    } catch (error) {
      this.addOutput(`❌ Error: ${error instanceof Error ? error.message : error}`);
    }

    // Don't do full render here, addOutput will handle it
  }

  private renderInputArea(): void {
    const height = term.height;
    const maxInputLines = 5; // Maximum lines to show for input
    const visibleLines = Math.min(this.state.inputLines.length, maxInputLines);
    
    // Calculate the fixed input area positions from the bottom
    const inputAreaStart = height - maxInputLines + 1;
    
    // Clear the entire reserved input area first
    for (let i = 0; i < maxInputLines; i++) {
      term.moveTo(1, inputAreaStart + i);
      term.eraseLineAfter();
    }
    
    // Render input lines in the fixed area
    const startLine = Math.max(0, this.state.inputLines.length - visibleLines);
    for (let i = 0; i < visibleLines; i++) {
      const lineIndex = startLine + i;
      const line = this.state.inputLines[lineIndex] || '';
      const isCurrent = lineIndex === this.state.currentInputLine;
      
      // Position relative to the start of the input area
      term.moveTo(1, inputAreaStart + (maxInputLines - visibleLines) + i);
      
      if (i === 0 || (visibleLines === 1)) {
        // First visible line gets the prompt (or only line)
        term.cyan(`❯ ${line}`);
        if (isCurrent) {
          term.bold.white('█'); // Cursor on current line
        }
      } else {
        // Continuation lines get indentation
        term.cyan(`  ${line}`);
        if (isCurrent) {
          term.bold.white('█'); // Cursor on current line
        }
      }
    }
    
    // Compatibility method
    this.state.inputText = this.state.inputLines[this.state.currentInputLine] || '';
  }

  private renderInputLine(): void {
    // Fallback to new method for compatibility
    this.renderInputArea();
  }

  private renderOutput(): void {
    const width = term.width;
    const height = term.height;
    const outputStartCol = this.agentListWidth + 2;
    const outputWidth = width - outputStartCol - 2; // Leave margin
    
    // Use the shared calculation
    const availableOutputHeight = this.calculateAvailableOutputHeight();
    
    // Clear output area
    for (let i = 4; i < 4 + availableOutputHeight; i++) {
      term.moveTo(outputStartCol, i);
      term.eraseLineAfter();
    }
    
    // NO TRUNCATION - show all text with proper wrapping
    const wrappedLines: string[] = [];
    this.state.outputLines.forEach(line => {
      // Remove any color codes for length calculation
      const plainLine = line.replace(/\^[a-zA-Z]/g, '');
      
      if (plainLine.length <= outputWidth) {
        wrappedLines.push(line);
      } else {
        // Split long lines - ensure we never lose text
        let remaining = line;
        let isFirst = true;
        
        while (remaining.length > 0) {
          let chunkSize = outputWidth;
          if (!isFirst) chunkSize -= 2; // Account for indent
          
          if (remaining.length <= chunkSize) {
            // Last chunk - ALWAYS add it
            wrappedLines.push(isFirst ? remaining : `  ${remaining}`);
            break;
          } else {
            // Find good break point (space or punctuation)
            let breakPoint = chunkSize;
            for (let i = chunkSize - 1; i >= Math.max(0, chunkSize - 20); i--) {
              if (remaining[i] === ' ' || remaining[i] === '.' || remaining[i] === ',' || remaining[i] === ';') {
                breakPoint = i + 1;
                break;
              }
            }
            
            // Ensure we always make progress
            if (breakPoint === 0) breakPoint = chunkSize;
            
            const chunk = remaining.substring(0, breakPoint).trim();
            if (chunk.length > 0) { // Only add non-empty chunks
              wrappedLines.push(isFirst ? chunk : `  ${chunk}`);
            }
            remaining = remaining.substring(breakPoint).trim();
            isFirst = false;
            
            // Safety check to prevent infinite loops
            if (remaining === chunk) break;
          }
        }
      }
    });
    
    // Wrapped lines calculated
    
    // Show lines based on scroll offset
    const totalLines = wrappedLines.length;
    const visibleLines = Math.min(availableOutputHeight, totalLines);
    
    // Calculate start index based on scroll offset
    // scrollOffset = 0 means show most recent (bottom)
    // scrollOffset > 0 means scrolled up from bottom
    const startIndex = Math.max(0, totalLines - visibleLines - this.state.outputScrollOffset);
    
    for (let i = 0; i < visibleLines; i++) {
      const lineIndex = startIndex + i;
      const line = wrappedLines[lineIndex];
      if (line) {
        term.moveTo(outputStartCol, 4 + i);
        
        // Render with color support - terminal-kit will process the ^ color codes
        term(line);
      }
    }
    
    // Re-render status bar and input area to keep them visible
    this.renderStatusBar();
    this.renderInputArea();
  }

  private renderStatusBar(): void {
    const width = term.width;
    const maxInputLines = 5; // Same as in renderInputArea
    const statusRow = term.height - maxInputLines - 1; // Position above input area
    
    // Clear status line and separator
    term.moveTo(1, statusRow - 1);
    term.eraseLineAfter();
    term.gray('─'.repeat(width));
    
    term.moveTo(1, statusRow);
    term.eraseLineAfter();
    
    // Render updated status
    term.yellow(`Agent: ${this.state.currentAgent?.name || 'None'} | `);
    term.yellow(`Streaming: ${this.state.streamingMode ? 'ON' : 'OFF'} | `);
    term.yellow(`Queue: ${this.state.queueMode ? 'ON' : 'OFF'} | `);
    term.yellow(`Verbose: ${this.state.verbose ? 'ON' : 'OFF'}`);
  }

  private render(): void {
    // Clear screen and move to top
    term.moveTo(1, 1);
    term.eraseDisplayBelow();

    const width = term.width;
    const height = term.height;

    // Header
    term.bold.blue('🚀 Claude Multi-Agent TUI (Terminal-Kit)\n');
    term.gray('─'.repeat(width) + '\n');

    // Agent list (left panel)
    term.moveTo(1, 3);
    term.bold.cyan('Agents:\n');
    
    this.state.agents.forEach((agent, index) => {
      const status = agent.isProcessing ? '🔄' : agent.isCreating ? '⏳' : '✅';
      const current = agent.name === this.state.currentAgent?.name;
      const agentColor = this.getAgentColor(agent.name);
      
      term.moveTo(1, 4 + index);
      if (current) {
        (term.bold as any)[agentColor](`👉 ${status} ${agent.name}\n`);
      } else {
        (term as any)[agentColor](`   ${status} ${agent.name}\n`);
      }
    });

    // Output area (right panel)
    const outputStartCol = this.agentListWidth + 2;
    const outputWidth = width - outputStartCol;
    
    term.moveTo(outputStartCol, 3);
    term.bold.yellow('Output:\n');
    
    // Show recent output lines
    const visibleLines = Math.min(this.outputHeight, this.state.outputLines.length);
    const startIndex = Math.max(0, this.state.outputLines.length - visibleLines);
    
    for (let i = 0; i < visibleLines; i++) {
      const lineIndex = startIndex + i;
      const line = this.state.outputLines[lineIndex];
      if (line) {
        term.moveTo(outputStartCol, 4 + i);
        // Truncate line if too long
        const truncated = line.length > outputWidth - 2 ? line.substring(0, outputWidth - 5) + '...' : line;
        term.white(truncated + '\n');
      }
    }

    // Help section
    if (this.state.showHelp) {
      const helpStartRow = Math.max(12, 4 + this.state.agents.length + 2);
      term.moveTo(1, helpStartRow);
      term.bold.magenta('Commands:\n');
      const helpCommands = [
        '/create <name> <role> - Create new agent',
        '/switch <name> - Switch to agent',
        '/delete <name> - Delete agent',
        '/list - List all agents',
        '/clear - Clear output',
        '/streaming - Toggle streaming mode',
        '/queue - Toggle queue mode',
        '/verbose - Toggle verbose mode',
        '/help - Toggle this help',
        '/exit - Quit application'
      ];
      
      helpCommands.forEach((cmd, index) => {
        term.moveTo(1, helpStartRow + 1 + index);
        term.gray(cmd + '\n');
      });
    }

    // Status bar
    const statusRow = height - 2;
    term.moveTo(1, statusRow);
    term.gray('─'.repeat(width) + '\n');
    term.moveTo(1, statusRow + 1);
    term.yellow(`Agent: ${this.state.currentAgent?.name || 'None'} | `);
    term.yellow(`Streaming: ${this.state.streamingMode ? 'ON' : 'OFF'} | `);
    term.yellow(`Queue: ${this.state.queueMode ? 'ON' : 'OFF'} | `);
    term.yellow(`Verbose: ${this.state.verbose ? 'ON' : 'OFF'}\n`);

    // Input area (handled by renderInputArea)
    this.renderInputArea();
  }

  private handleProcessOutput(event: any): void {
    // Debug logging
    const fs = require('fs');
    const debugMsg = `[${new Date().toISOString()}] TUI: handleProcessOutput called with: ${JSON.stringify(event)}\n`;
    fs.appendFileSync('/tmp/agent-creation-debug.log', debugMsg);
    
    const { agentName, data } = event;
    
    switch (data.type) {
      case 'assistant':
        if (Array.isArray(data.content)) {
          data.content.forEach((item: any) => {
            if (item.type === 'text') {
              this.addMultiLineOutput(agentName, item.text);
            } else if (item.type === 'tool_use') {
              // Format tool use messages nicely
              const toolName = item.name || 'Unknown Tool';
              const prettyInput = this.prettyPrintToolInput(item.input || {});
              const formattedToolUse = `🔧 Using ${toolName}: ${prettyInput}`;
              this.addMultiLineOutput(agentName, formattedToolUse);
            }
          });
        } else if (typeof data.content === 'string') {
          this.addMultiLineOutput(agentName, data.content);
        }
        break;

      case 'content':
        // For streaming content, append to last line
        if (this.state.outputLines.length > 0) {
          this.state.outputLines[this.state.outputLines.length - 1] += data.content;
        } else {
          this.addOutput(`${agentName}: ${data.content}`);
        }
        this.render();
        break;

      case 'error':
        this.addOutput(`❌ ${agentName}: ${data.content}`);
        break;

      default:
        // Skip all other message types for clean conversation view
        break;
    }
  }

  private handleMouseClick(x: number, y: number, button: 'left' | 'right'): void {
    // Check if click is in the agent list area
    // Agent list starts at row 4 and goes for this.state.agents.length rows
    // Agent list is in column 1 to this.agentListWidth
    
    if (x >= 1 && x <= this.agentListWidth && y >= 4) {
      const agentIndex = y - 4; // Row 4 is first agent
      
      if (agentIndex >= 0 && agentIndex < this.state.agents.length) {
        const clickedAgent = this.state.agents[agentIndex];
        
        if (button === 'left') {
          // Left click: switch to agent
          try {
            this.controller.switchToAgent(clickedAgent.name);
            this.updateAgentList();
            this.savePreferences(); // Save last used agent
            this.addOutput(`🖱️ Switched to ${clickedAgent.name} (mouse click)`);
          } catch (error) {
            this.addOutput(`❌ Error switching to ${clickedAgent.name}: ${error instanceof Error ? error.message : error}`);
          }
        } else if (button === 'right') {
          // Right click: delete agent (with confirmation)
          this.handleAgentDeletion(clickedAgent.name);
        }
      }
    }
  }

  private async handleAgentDeletion(agentName: string): Promise<void> {
    // Show confirmation prompt
    const agentColor = this.getAgentColor(agentName);
    this.state.outputLines.push(`^${agentColor[0]}❓ Delete agent "${agentName}"? Type 'yes' to confirm or any other input to cancel.^:`);
    this.renderOutput();
    
    // Clear input area for confirmation
    this.state.inputLines = [''];
    this.state.currentInputLine = 0;
    this.renderInputArea();
    
    // Wait for user confirmation with a simpler approach
    const confirmationPromise = new Promise<boolean>((resolve) => {
      let confirmationInput = '';
      
      const handleConfirmation = (name: string, matches: any, data: any) => {
        if (name === 'CTRL_C') {
          // Allow exit
          term.removeListener('key', handleConfirmation);
          this.cleanup();
          process.exit(0);
        } else if (name === 'ENTER') {
          // Check the input
          term.removeListener('key', handleConfirmation);
          resolve(confirmationInput.trim().toLowerCase() === 'yes');
        } else if (name === 'BACKSPACE') {
          if (confirmationInput.length > 0) {
            confirmationInput = confirmationInput.slice(0, -1);
            this.renderConfirmationInput(confirmationInput);
          }
        } else if (data && data.isCharacter && data.codepoint) {
          const char = String.fromCharCode(data.codepoint);
          if (char && char.length === 1 && char.charCodeAt(0) >= 32) {
            confirmationInput += char;
            this.renderConfirmationInput(confirmationInput);
          }
        }
      };
      
      // Remove existing key listeners temporarily
      term.removeAllListeners('key');
      term.on('key', handleConfirmation);
    });
    
    const confirmed = await confirmationPromise;
    
    // Restore normal key handling (only once)
    this.restoreNormalInput();
    
    if (confirmed) {
      try {
        const wasCurrentAgent = this.state.currentAgent?.name === agentName;
        const success = await this.controller.removeAgent(agentName);
        if (success) {
          this.state.outputLines.push(`^${agentColor[0]}🗑️ Agent "${agentName}" deleted^:`);
          this.updateAgentList();
          
          // If we deleted the current agent, switch to the first available agent
          if (wasCurrentAgent && this.state.agents.length > 0) {
            const firstAgent = this.state.agents[0];
            try {
              this.controller.switchToAgent(firstAgent.name);
              const newAgentColor = this.getAgentColor(firstAgent.name);
              this.state.outputLines.push(`^${newAgentColor[0]}🔄 Switched to "${firstAgent.name}" (auto-selected after deletion)^:`);
              this.updateAgentList();
            } catch (switchError) {
              this.addOutput(`❌ Error switching to ${firstAgent.name}: ${switchError instanceof Error ? switchError.message : switchError}`);
            }
          }
          
          this.savePreferences(); // Save preferences after deletion and potential switch
        } else {
          this.addOutput(`❌ Failed to delete agent "${agentName}"`);
        }
      } catch (error) {
        this.addOutput(`❌ Error deleting agent "${agentName}": ${error instanceof Error ? error.message : error}`);
      }
    } else {
      this.addOutput(`↩️ Agent deletion cancelled`);
    }
    
    // Clear the input area after confirmation
    this.state.inputLines = [''];
    this.state.currentInputLine = 0;
    this.renderInputArea();
    this.renderOutput();
  }

  private renderConfirmationInput(input: string): void {
    const height = term.height;
    term.moveTo(1, height);
    term.eraseLineAfter();
    term.cyan(`❯ ${input}`);
    term.bold.white('█'); // Cursor
  }

  private prettyPrintToolInput(input: any): string {
    if (!input || Object.keys(input).length === 0) {
      return '{}';
    }
    
    // For simple single values, show inline
    const keys = Object.keys(input);
    if (keys.length === 1) {
      const key = keys[0];
      const value = input[key];
      if (typeof value === 'string' && value.length < 50) {
        return `${key}: "${value}"`;
      }
      if (typeof value === 'number' || typeof value === 'boolean') {
        return `${key}: ${value}`;
      }
    }
    
    // For multiple values or complex objects, format nicely
    const parts: string[] = [];
    for (const [key, value] of Object.entries(input)) {
      if (typeof value === 'string') {
        if (value.length > 60) {
          parts.push(`${key}: "${value.substring(0, 57)}..."`);
        } else {
          parts.push(`${key}: "${value}"`);
        }
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        parts.push(`${key}: ${value}`);
      } else if (Array.isArray(value)) {
        if (value.length <= 3 && value.every(v => typeof v === 'string' && v.length < 20)) {
          parts.push(`${key}: [${value.map(v => `"${v}"`).join(', ')}]`);
        } else {
          parts.push(`${key}: [${value.length} items]`);
        }
      } else {
        parts.push(`${key}: {...}`);
      }
    }
    
    // If it all fits on one line (under 80 chars), show inline
    const inline = `{ ${parts.join(', ')} }`;
    if (inline.length <= 80) {
      return inline;
    }
    
    // Otherwise, format with newlines
    return `{\n  ${parts.join(',\n  ')}\n}`;
  }

  private restoreNormalInput(): void {
    // Remove all listeners first to avoid duplicates
    term.removeAllListeners('key');
    term.removeAllListeners('mouse');
    
    // Re-add only the normal input handling
    this.setupInput();
  }

  public cleanup(): void {
    term.fullscreen(false);
    term.hideCursor(false); // Show cursor (hideCursor(false) = show)
    term.clear();
    term.grabInput(false); // Disable input grabbing on cleanup
  }
}

// Main execution
async function main() {
  const tui = new ClaudeMultiAgentTermKitTUI();
  
  try {
    await tui.initialize();
    
    // Keep the process running
    process.on('SIGINT', () => {
      tui.cleanup();
      process.exit(0);
    });
    
    // Keep the process alive with an interval
    const keepAlive = setInterval(() => {
      // Do nothing, just keep the process running
    }, 1000);
    
    // Clean up interval on exit
    process.on('exit', () => {
      clearInterval(keepAlive);
    });
    
    // Wait indefinitely
    await new Promise((resolve) => {
      // This promise never resolves, keeping the process alive
    });
    
  } catch (error) {
    console.error('Failed to initialize TUI:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(console.error);
}