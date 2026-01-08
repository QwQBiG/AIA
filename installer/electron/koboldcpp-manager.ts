import { spawn, ChildProcess, execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as https from 'https';

export interface KoboldCPPStatus {
  installed: boolean;
  running: boolean;
  version?: string;
}

/**
 * Manages KoboldCPP installation and lifecycle
 */
export class KoboldCPPManager {
  private process: ChildProcess | null = null;
  private endpoint: string = 'http://localhost:5001';
  private installPath: string;

  constructor(userDataPath: string) {
    this.installPath = path.join(userDataPath, 'koboldcpp');
  }

  /**
   * Get the executable path
   */
  private getExecutablePath(): string {
    return path.join(this.installPath, 'koboldcpp.exe');
  }

  /**
   * Check if KoboldCPP is installed
   */
  async isInstalled(): Promise<boolean> {
    return fs.existsSync(this.getExecutablePath());
  }

  /**
   * Get KoboldCPP version
   */
  async getVersion(): Promise<string | null> {
    if (!await this.isInstalled()) {
      return null;
    }

    try {
      const output = execSync(`"${this.getExecutablePath()}" --version`, { 
        encoding: 'utf-8',
        timeout: 5000,
      });
      return output.trim();
    } catch {
      return 'unknown';
    }
  }

  /**
   * Check if KoboldCPP is running
   */
  async isRunning(): Promise<boolean> {
    try {
      const response = await fetch(`${this.endpoint}/api/v1/model`);
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Download KoboldCPP
   */
  async download(onProgress?: (progress: number) => void): Promise<string> {
    const url = 'https://github.com/LostRuins/koboldcpp/releases/latest/download/koboldcpp.exe';
    
    // Ensure install directory exists
    if (!fs.existsSync(this.installPath)) {
      fs.mkdirSync(this.installPath, { recursive: true });
    }

    const filePath = this.getExecutablePath();

    return new Promise((resolve, reject) => {
      const file = fs.createWriteStream(filePath);
      
      const download = (downloadUrl: string) => {
        https.get(downloadUrl, (response) => {
          if (response.statusCode === 302 || response.statusCode === 301) {
            // Follow redirect
            download(response.headers.location!);
            return;
          }

          const totalSize = parseInt(response.headers['content-length'] || '0', 10);
          let downloadedSize = 0;

          response.on('data', (chunk) => {
            downloadedSize += chunk.length;
            if (totalSize > 0 && onProgress) {
              onProgress(Math.round((downloadedSize / totalSize) * 100));
            }
          });

          response.pipe(file);
          
          file.on('finish', () => {
            file.close();
            resolve(filePath);
          });
        }).on('error', (err) => {
          fs.unlink(filePath, () => {});
          reject(err);
        });
      };

      download(url);
    });
  }

  /**
   * Install KoboldCPP (download if needed)
   */
  async install(onProgress?: (progress: number) => void): Promise<void> {
    if (await this.isInstalled()) {
      console.log('KoboldCPP is already installed');
      return;
    }

    await this.download(onProgress);
  }

  /**
   * Start KoboldCPP with optional model
   */
  async start(modelPath?: string): Promise<void> {
    if (await this.isRunning()) {
      console.log('KoboldCPP is already running');
      return;
    }

    if (!await this.isInstalled()) {
      throw new Error('KoboldCPP is not installed');
    }

    const args = ['--port', '5001'];
    if (modelPath) {
      args.push('--model', modelPath);
    }

    return new Promise((resolve, reject) => {
      this.process = spawn(this.getExecutablePath(), args, {
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
      });

      this.process.unref();

      // Wait for service to be ready
      const checkReady = async (attempts: number) => {
        if (attempts <= 0) {
          reject(new Error('KoboldCPP failed to start'));
          return;
        }

        if (await this.isRunning()) {
          resolve();
        } else {
          setTimeout(() => checkReady(attempts - 1), 2000);
        }
      };

      // KoboldCPP takes longer to start
      setTimeout(() => checkReady(30), 2000);
    });
  }

  /**
   * Stop KoboldCPP service
   */
  async stop(): Promise<void> {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }

    // Also try to kill any running koboldcpp process
    try {
      if (process.platform === 'win32') {
        execSync('taskkill /F /IM koboldcpp.exe', { stdio: 'ignore' });
      } else {
        execSync('pkill koboldcpp', { stdio: 'ignore' });
      }
    } catch {
      // Process might not exist
    }
  }

  /**
   * Test connection to KoboldCPP
   */
  async testConnection(): Promise<boolean> {
    try {
      const response = await fetch(`${this.endpoint}/api/v1/model`);
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Get full status
   */
  async getStatus(): Promise<KoboldCPPStatus> {
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

export function createKoboldCPPManager(userDataPath: string): KoboldCPPManager {
  return new KoboldCPPManager(userDataPath);
}
