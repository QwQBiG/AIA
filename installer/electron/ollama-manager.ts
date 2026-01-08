import { spawn, ChildProcess, execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as https from 'https';

export interface OllamaStatus {
  installed: boolean;
  running: boolean;
  version?: string;
}

/**
 * Manages Ollama installation and lifecycle
 */
export class OllamaManager {
  private process: ChildProcess | null = null;
  private endpoint: string = 'http://localhost:11434';

  /**
   * Check if Ollama is installed
   */
  async isInstalled(): Promise<boolean> {
    try {
      if (process.platform === 'win32') {
        execSync('where ollama', { stdio: 'ignore' });
      } else {
        execSync('which ollama', { stdio: 'ignore' });
      }
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get Ollama version
   */
  async getVersion(): Promise<string | null> {
    try {
      const output = execSync('ollama --version', { encoding: 'utf-8' });
      const match = output.match(/ollama version (\S+)/);
      return match ? match[1] : output.trim();
    } catch {
      return null;
    }
  }

  /**
   * Check if Ollama is running
   */
  async isRunning(): Promise<boolean> {
    try {
      const response = await fetch(`${this.endpoint}/api/tags`);
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Download Ollama installer
   */
  async download(destPath: string): Promise<string> {
    const url = 'https://ollama.com/download/OllamaSetup.exe';
    const filePath = path.join(destPath, 'OllamaSetup.exe');

    return new Promise((resolve, reject) => {
      const file = fs.createWriteStream(filePath);
      
      https.get(url, (response) => {
        if (response.statusCode === 302 || response.statusCode === 301) {
          // Follow redirect
          https.get(response.headers.location!, (redirectResponse) => {
            redirectResponse.pipe(file);
            file.on('finish', () => {
              file.close();
              resolve(filePath);
            });
          }).on('error', reject);
        } else {
          response.pipe(file);
          file.on('finish', () => {
            file.close();
            resolve(filePath);
          });
        }
      }).on('error', (err) => {
        fs.unlink(filePath, () => {});
        reject(err);
      });
    });
  }

  /**
   * Install Ollama (runs the installer)
   */
  async install(installerPath: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const installer = spawn(installerPath, ['/S'], {
        detached: true,
        stdio: 'ignore',
      });

      installer.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Installer exited with code ${code}`));
        }
      });

      installer.on('error', reject);
    });
  }

  /**
   * Start Ollama service
   */
  async start(): Promise<void> {
    if (await this.isRunning()) {
      console.log('Ollama is already running');
      return;
    }

    return new Promise((resolve, reject) => {
      this.process = spawn('ollama', ['serve'], {
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
      });

      this.process.unref();

      // Wait for service to be ready
      const checkReady = async (attempts: number) => {
        if (attempts <= 0) {
          reject(new Error('Ollama failed to start'));
          return;
        }

        if (await this.isRunning()) {
          resolve();
        } else {
          setTimeout(() => checkReady(attempts - 1), 1000);
        }
      };

      setTimeout(() => checkReady(10), 1000);
    });
  }

  /**
   * Stop Ollama service
   */
  async stop(): Promise<void> {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }

    // Also try to kill any running ollama process
    try {
      if (process.platform === 'win32') {
        execSync('taskkill /F /IM ollama.exe', { stdio: 'ignore' });
      } else {
        execSync('pkill ollama', { stdio: 'ignore' });
      }
    } catch {
      // Process might not exist
    }
  }

  /**
   * Pull a model
   */
  async pullModel(model: string, onProgress?: (progress: string) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      const pull = spawn('ollama', ['pull', model]);

      pull.stdout?.on('data', (data) => {
        const message = data.toString();
        onProgress?.(message);
      });

      pull.stderr?.on('data', (data) => {
        const message = data.toString();
        onProgress?.(message);
      });

      pull.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Failed to pull model ${model}`));
        }
      });

      pull.on('error', reject);
    });
  }

  /**
   * List available models
   */
  async listModels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.endpoint}/api/tags`);
      if (!response.ok) {
        return [];
      }
      const data = await response.json() as { models: { name: string }[] };
      return data.models?.map(m => m.name) ?? [];
    } catch {
      return [];
    }
  }

  /**
   * Get full status
   */
  async getStatus(): Promise<OllamaStatus> {
    const [installed, running, version] = await Promise.all([
      this.isInstalled(),
      this.isRunning(),
      this.getVersion(),
    ]);

    return { installed, running, version: version ?? undefined };
  }

  /**
   * Set custom endpoint
   */
  setEndpoint(endpoint: string): void {
    this.endpoint = endpoint;
  }

  /**
   * Get current endpoint
   */
  getEndpoint(): string {
    return this.endpoint;
  }
}

export const ollamaManager = new OllamaManager();
