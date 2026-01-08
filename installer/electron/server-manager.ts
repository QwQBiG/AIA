import { ChildProcess, spawn } from 'child_process';
import * as path from 'path';
import * as net from 'net';

export interface ServerStatus {
  running: boolean;
  port?: number;
  pid?: number;
  error?: string;
}

export interface ServerError {
  type: 'PORT_IN_USE' | 'STARTUP_FAILED' | 'PROCESS_ERROR' | 'UNKNOWN';
  message: string;
  port?: number;
  details?: string;
}

// Extend NodeJS.Process for Electron-specific properties
declare global {
  namespace NodeJS {
    interface Process {
      defaultApp?: boolean;
      resourcesPath?: string;
    }
  }
}

/**
 * Manages the Node.js server process lifecycle
 */
export class ServerManager {
  private serverProcess: ChildProcess | null = null;
  private port: number = 3000;
  private isProduction: boolean;
  private lastError: ServerError | null = null;

  constructor() {
    this.isProduction = process.env.NODE_ENV === 'production' || 
                        !(process as any).defaultApp;
  }

  /**
   * Check if a port is in use
   */
  private async isPortInUse(port: number): Promise<boolean> {
    return new Promise((resolve) => {
      const server = net.createServer();
      server.once('error', () => resolve(true));
      server.once('listening', () => {
        server.close();
        resolve(false);
      });
      server.listen(port);
    });
  }

  /**
   * Find an available port starting from the default
   */
  private async findAvailablePort(startPort: number, maxAttempts: number = 10): Promise<number> {
    for (let i = 0; i < maxAttempts; i++) {
      const port = startPort + i;
      if (!await this.isPortInUse(port)) {
        return port;
      }
    }
    throw new Error(`No available port found in range ${startPort}-${startPort + maxAttempts - 1}`);
  }

  /**
   * Get the path to the server entry point
   */
  private getServerPath(): string {
    if (this.isProduction) {
      return path.join((process as any).resourcesPath || '', 'server', 'main.js');
    }
    // Development mode - use the packages/server/dist
    return path.join(__dirname, '../../packages/server/dist/main.js');
  }

  /**
   * Start the Node.js server
   */
  async start(): Promise<void> {
    if (this.serverProcess && !this.serverProcess.killed) {
      console.log('Server is already running');
      return;
    }

    this.lastError = null;

    // Check if default port is in use
    const defaultPortInUse = await this.isPortInUse(3000);
    if (defaultPortInUse) {
      console.log('Default port 3000 is in use, finding available port...');
    }

    // Find available port
    try {
      this.port = await this.findAvailablePort(3000);
    } catch (error) {
      this.lastError = {
        type: 'PORT_IN_USE',
        message: '无法找到可用端口',
        port: 3000,
        details: (error as Error).message,
      };
      throw error;
    }

    const serverPath = this.getServerPath();

    return new Promise((resolve, reject) => {
      console.log(`Starting server at ${serverPath} on port ${this.port}`);

      try {
        this.serverProcess = spawn('node', [serverPath], {
          env: {
            ...process.env,
            NODE_ENV: this.isProduction ? 'production' : 'development',
            PORT: String(this.port),
          },
          stdio: 'pipe',
          windowsHide: true,
        });
      } catch (spawnError) {
        this.lastError = {
          type: 'STARTUP_FAILED',
          message: '无法启动服务器进程',
          details: (spawnError as Error).message,
        };
        reject(spawnError);
        return;
      }

      let startupError = '';
      let resolved = false;

      this.serverProcess.stdout?.on('data', (data) => {
        const message = data.toString();
        console.log(`[Server] ${message}`);
        
        // Check for successful startup message
        if (!resolved && (message.includes('listening') || message.includes('started'))) {
          resolved = true;
          resolve();
        }
      });

      this.serverProcess.stderr?.on('data', (data) => {
        const message = data.toString();
        console.error(`[Server Error] ${message}`);
        startupError += message;

        // Check for common error patterns
        if (message.includes('EADDRINUSE')) {
          this.lastError = {
            type: 'PORT_IN_USE',
            message: `端口 ${this.port} 被占用`,
            port: this.port,
            details: message,
          };
        } else if (message.includes('EACCES')) {
          this.lastError = {
            type: 'PROCESS_ERROR',
            message: '权限不足',
            details: message,
          };
        }
      });

      this.serverProcess.on('error', (error) => {
        console.error('Failed to start server:', error);
        this.lastError = {
          type: 'PROCESS_ERROR',
          message: '服务器进程错误',
          details: error.message,
        };
        if (!resolved) {
          resolved = true;
          reject(error);
        }
      });

      this.serverProcess.on('exit', (code, signal) => {
        console.log(`Server process exited with code ${code}, signal ${signal}`);
        if (!resolved && code !== 0) {
          this.lastError = {
            type: 'STARTUP_FAILED',
            message: `服务器启动失败，退出码: ${code}`,
            details: startupError,
          };
          resolved = true;
          reject(new Error(`Server failed to start: ${startupError}`));
        }
        this.serverProcess = null;
      });

      // Timeout for startup
      setTimeout(() => {
        if (!resolved) {
          if (this.serverProcess && !this.serverProcess.killed) {
            resolved = true;
            resolve();
          } else {
            this.lastError = {
              type: 'STARTUP_FAILED',
              message: '服务器启动超时',
              details: startupError,
            };
            resolved = true;
            reject(new Error(`Server failed to start: ${startupError}`));
          }
        }
      }, 5000);
    });
  }

  /**
   * Stop the Node.js server
   */
  async stop(): Promise<void> {
    if (!this.serverProcess || this.serverProcess.killed) {
      console.log('Server is not running');
      return;
    }

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        // Force kill if graceful shutdown fails
        if (this.serverProcess && !this.serverProcess.killed) {
          console.log('Force killing server process');
          this.serverProcess.kill('SIGKILL');
        }
        this.serverProcess = null;
        resolve();
      }, 5000);

      this.serverProcess!.on('exit', () => {
        clearTimeout(timeout);
        this.serverProcess = null;
        resolve();
      });

      // Send graceful shutdown signal
      this.serverProcess!.kill('SIGTERM');
    });
  }

  /**
   * Get the current server status
   */
  getStatus(): ServerStatus {
    return {
      running: this.serverProcess !== null && !this.serverProcess.killed,
      port: this.port,
      pid: this.serverProcess?.pid,
      error: this.lastError?.message,
    };
  }

  /**
   * Get the last error
   */
  getLastError(): ServerError | null {
    return this.lastError;
  }

  /**
   * Restart the server
   */
  async restart(): Promise<void> {
    await this.stop();
    await this.start();
  }
}

// Singleton instance
export const serverManager = new ServerManager();
