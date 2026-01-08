import { BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';

export interface WizardStep {
  id: string;
  title: string;
  description: string;
  optional?: boolean;
}

export interface WizardState {
  currentStep: number;
  totalSteps: number;
  steps: WizardStep[];
  completed: boolean;
  data: Record<string, any>;
}

/**
 * Setup wizard for first-time configuration
 */
export class SetupWizard {
  private window: BrowserWindow | null = null;
  private state: WizardState;
  private onComplete?: (data: Record<string, any>) => void;

  constructor() {
    this.state = {
      currentStep: 0,
      totalSteps: 4,
      steps: [
        {
          id: 'welcome',
          title: '欢迎',
          description: '欢迎使用 AI VTuber Digital Human',
        },
        {
          id: 'llm',
          title: 'LLM 配置',
          description: '选择并配置大语言模型提供者',
        },
        {
          id: 'tts',
          title: 'TTS 配置',
          description: '选择并配置语音合成服务',
        },
        {
          id: 'streaming',
          title: '直播平台',
          description: '配置直播平台连接',
        },
      ],
      completed: false,
      data: {},
    };

    this.registerIpcHandlers();
  }

  /**
   * Register IPC handlers for wizard communication
   */
  private registerIpcHandlers(): void {
    ipcMain.handle('wizard:getState', () => {
      return this.state;
    });

    ipcMain.handle('wizard:next', () => {
      return this.next();
    });

    ipcMain.handle('wizard:previous', () => {
      return this.previous();
    });

    ipcMain.handle('wizard:setStepData', (_event: Electron.IpcMainInvokeEvent, stepId: string, data: any) => {
      this.state.data[stepId] = data;
      return this.state;
    });

    ipcMain.handle('wizard:finish', async () => {
      return this.finish();
    });

    ipcMain.handle('wizard:skip', () => {
      return this.skip();
    });
  }

  /**
   * Show the wizard window
   */
  show(onComplete?: (data: Record<string, any>) => void): void {
    this.onComplete = onComplete;

    if (this.window) {
      this.window.focus();
      return;
    }

    this.window = new BrowserWindow({
      width: 800,
      height: 600,
      resizable: false,
      minimizable: false,
      maximizable: false,
      modal: true,
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: false,
        contextIsolation: true,
      },
    });

    // Load wizard UI
    const wizardPath = path.join(__dirname, '../wizard/index.html');
    this.window.loadFile(wizardPath).catch(() => {
      // Fallback for development
      this.window?.loadURL('http://localhost:5173/wizard');
    });

    this.window.on('closed', () => {
      this.window = null;
    });
  }

  /**
   * Close the wizard window
   */
  close(): void {
    if (this.window) {
      this.window.close();
      this.window = null;
    }
  }

  /**
   * Move to next step
   */
  next(): WizardState {
    if (this.state.currentStep < this.state.totalSteps - 1) {
      this.state.currentStep++;
    }
    return this.state;
  }

  /**
   * Move to previous step
   */
  previous(): WizardState {
    if (this.state.currentStep > 0) {
      this.state.currentStep--;
    }
    return this.state;
  }

  /**
   * Skip current step (if optional)
   */
  skip(): WizardState {
    const currentStep = this.state.steps[this.state.currentStep];
    if (currentStep?.optional) {
      return this.next();
    }
    return this.state;
  }

  /**
   * Finish the wizard
   */
  async finish(): Promise<Record<string, any>> {
    this.state.completed = true;
    
    if (this.onComplete) {
      this.onComplete(this.state.data);
    }

    this.close();
    return this.state.data;
  }

  /**
   * Validate current step
   */
  validateStep(stepId: string): { valid: boolean; errors: string[] } {
    const data = this.state.data[stepId];
    const errors: string[] = [];

    switch (stepId) {
      case 'llm':
        if (!data?.provider) {
          errors.push('请选择 LLM 提供者');
        }
        if (data?.provider === 'openai' && !data?.apiKey) {
          errors.push('请输入 OpenAI API Key');
        }
        if (data?.provider === 'anthropic' && !data?.apiKey) {
          errors.push('请输入 Anthropic API Key');
        }
        break;

      case 'tts':
        if (!data?.provider) {
          errors.push('请选择 TTS 提供者');
        }
        if (data?.provider === 'elevenlabs' && !data?.apiKey) {
          errors.push('请输入 ElevenLabs API Key');
        }
        break;

      case 'streaming':
        // Streaming is optional, no validation required
        break;
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Get current state
   */
  getState(): WizardState {
    return this.state;
  }

  /**
   * Reset wizard state
   */
  reset(): void {
    this.state = {
      currentStep: 0,
      totalSteps: 4,
      steps: this.state.steps,
      completed: false,
      data: {},
    };
  }
}

export const setupWizard = new SetupWizard();
