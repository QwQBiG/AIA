import { app, dialog, BrowserWindow, shell } from 'electron';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

/**
 * Error types for categorization
 */
export enum ErrorType {
  DISK_SPACE = 'DISK_SPACE',
  PERMISSION = 'PERMISSION',
  NETWORK = 'NETWORK',
  PORT_IN_USE = 'PORT_IN_USE',
  DATABASE = 'DATABASE',
  LLM_CONNECTION = 'LLM_CONNECTION',
  CONFIG_CORRUPT = 'CONFIG_CORRUPT',
  FILE_LOCKED = 'FILE_LOCKED',
  UNKNOWN = 'UNKNOWN',
}

/**
 * Error severity levels
 */
export enum ErrorSeverity {
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical',
}

/**
 * Structured error information
 */
export interface AppError {
  type: ErrorType;
  severity: ErrorSeverity;
  message: string;
  details?: string;
  suggestion?: string;
  recoverable: boolean;
  timestamp: Date;
  context?: Record<string, any>;
}

/**
 * Error handler result
 */
export interface ErrorHandlerResult {
  handled: boolean;
  action?: 'retry' | 'ignore' | 'abort' | 'rollback';
  userChoice?: string;
}

/**
 * Logger for error tracking
 */
export class ErrorLogger {
  private logPath: string;
  private maxLogSize: number = 5 * 1024 * 1024; // 5MB

  constructor(userDataPath: string) {
    this.logPath = path.join(userDataPath, 'logs', 'error.log');
    this.ensureLogDirectory();
  }

  private ensureLogDirectory(): void {
    const dir = path.dirname(this.logPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  /**
   * Log an error to file
   */
  log(error: AppError): void {
    try {
      this.rotateLogIfNeeded();
      
      const logEntry = {
        ...error,
        timestamp: error.timestamp.toISOString(),
        system: {
          platform: process.platform,
          arch: process.arch,
          nodeVersion: process.version,
          appVersion: app.getVersion(),
          freeMemory: os.freemem(),
          totalMemory: os.totalmem(),
        },
      };

      const line = JSON.stringify(logEntry) + '\n';
      fs.appendFileSync(this.logPath, line, 'utf-8');
    } catch (e) {
      console.error('Failed to write error log:', e);
    }
  }

  /**
   * Rotate log file if it exceeds max size
   */
  private rotateLogIfNeeded(): void {
    try {
      if (fs.existsSync(this.logPath)) {
        const stats = fs.statSync(this.logPath);
        if (stats.size > this.maxLogSize) {
          const backupPath = this.logPath + '.old';
          if (fs.existsSync(backupPath)) {
            fs.unlinkSync(backupPath);
          }
          fs.renameSync(this.logPath, backupPath);
        }
      }
    } catch (e) {
      console.error('Failed to rotate log:', e);
    }
  }

  /**
   * Get log file path
   */
  getLogPath(): string {
    return this.logPath;
  }

  /**
   * Open log file in system viewer
   */
  async openLogFile(): Promise<void> {
    if (fs.existsSync(this.logPath)) {
      await shell.openPath(this.logPath);
    }
  }
}


/**
 * Centralized error handler for the application
 */
export class ErrorHandler {
  private logger: ErrorLogger;
  private mainWindow: BrowserWindow | null = null;

  constructor(userDataPath: string) {
    this.logger = new ErrorLogger(userDataPath);
  }

  /**
   * Set the main window for dialog display
   */
  setMainWindow(window: BrowserWindow | null): void {
    this.mainWindow = window;
  }

  /**
   * Create an AppError from various error types
   */
  createError(
    type: ErrorType,
    message: string,
    options?: {
      severity?: ErrorSeverity;
      details?: string;
      suggestion?: string;
      recoverable?: boolean;
      context?: Record<string, any>;
    }
  ): AppError {
    return {
      type,
      severity: options?.severity ?? ErrorSeverity.ERROR,
      message,
      details: options?.details,
      suggestion: options?.suggestion,
      recoverable: options?.recoverable ?? false,
      timestamp: new Date(),
      context: options?.context,
    };
  }

  /**
   * Handle disk space errors
   */
  async handleDiskSpaceError(
    requiredBytes: number,
    availableBytes: number,
    targetPath: string
  ): Promise<ErrorHandlerResult> {
    const requiredMB = Math.ceil(requiredBytes / (1024 * 1024));
    const availableMB = Math.floor(availableBytes / (1024 * 1024));

    const error = this.createError(
      ErrorType.DISK_SPACE,
      '磁盘空间不足',
      {
        severity: ErrorSeverity.ERROR,
        details: `需要 ${requiredMB} MB，可用 ${availableMB} MB`,
        suggestion: '请清理磁盘空间或选择其他安装路径',
        recoverable: true,
        context: { requiredBytes, availableBytes, targetPath },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'error',
      title: '磁盘空间不足',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['选择其他路径', '取消安装'],
      defaultId: 0,
      cancelId: 1,
    });

    return {
      handled: true,
      action: result.response === 0 ? 'retry' : 'abort',
      userChoice: result.response === 0 ? 'change_path' : 'cancel',
    };
  }

  /**
   * Handle permission errors
   */
  async handlePermissionError(
    operation: string,
    targetPath: string
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.PERMISSION,
      '权限不足',
      {
        severity: ErrorSeverity.ERROR,
        details: `无法执行操作: ${operation}\n路径: ${targetPath}`,
        suggestion: '请以管理员身份运行安装程序',
        recoverable: true,
        context: { operation, targetPath },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'error',
      title: '权限不足',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['以管理员身份重试', '取消'],
      defaultId: 0,
      cancelId: 1,
    });

    return {
      handled: true,
      action: result.response === 0 ? 'retry' : 'abort',
      userChoice: result.response === 0 ? 'run_as_admin' : 'cancel',
    };
  }

  /**
   * Handle network errors
   */
  async handleNetworkError(
    operation: string,
    url?: string
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.NETWORK,
      '网络连接失败',
      {
        severity: ErrorSeverity.WARNING,
        details: `操作: ${operation}${url ? `\nURL: ${url}` : ''}`,
        suggestion: '请检查网络连接后重试，或跳过此步骤',
        recoverable: true,
        context: { operation, url },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'warning',
      title: '网络错误',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['重试', '跳过', '取消'],
      defaultId: 0,
      cancelId: 2,
    });

    const actions: ('retry' | 'ignore' | 'abort')[] = ['retry', 'ignore', 'abort'];
    return {
      handled: true,
      action: actions[result.response],
      userChoice: ['retry', 'skip', 'cancel'][result.response],
    };
  }

  /**
   * Handle port in use errors
   */
  async handlePortInUseError(
    port: number,
    processName?: string
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.PORT_IN_USE,
      `端口 ${port} 被占用`,
      {
        severity: ErrorSeverity.WARNING,
        details: processName ? `占用进程: ${processName}` : '无法确定占用进程',
        suggestion: '可以自动选择其他可用端口，或手动关闭占用进程',
        recoverable: true,
        context: { port, processName },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'warning',
      title: '端口被占用',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['自动选择其他端口', '手动处理', '取消'],
      defaultId: 0,
      cancelId: 2,
    });

    return {
      handled: true,
      action: result.response === 0 ? 'retry' : result.response === 1 ? 'ignore' : 'abort',
      userChoice: ['auto_port', 'manual', 'cancel'][result.response],
    };
  }

  /**
   * Handle database errors
   */
  async handleDatabaseError(
    operation: string,
    originalError?: Error
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.DATABASE,
      '数据库错误',
      {
        severity: ErrorSeverity.ERROR,
        details: `操作: ${operation}\n${originalError?.message ?? '未知错误'}`,
        suggestion: '可以尝试重新初始化数据库，或查看日志获取详细信息',
        recoverable: true,
        context: { operation, originalError: originalError?.message },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'error',
      title: '数据库错误',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['重新初始化', '查看日志', '取消'],
      defaultId: 0,
      cancelId: 2,
    });

    if (result.response === 1) {
      await this.logger.openLogFile();
    }

    return {
      handled: true,
      action: result.response === 0 ? 'retry' : 'abort',
      userChoice: ['reinit', 'view_log', 'cancel'][result.response],
    };
  }

  /**
   * Handle LLM connection errors
   */
  async handleLLMConnectionError(
    provider: string,
    endpoint?: string
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.LLM_CONNECTION,
      `无法连接到 ${provider}`,
      {
        severity: ErrorSeverity.WARNING,
        details: endpoint ? `端点: ${endpoint}` : '',
        suggestion: provider === 'ollama' || provider === 'koboldcpp'
          ? '请确保服务已启动，或切换到云端 LLM 提供者'
          : '请检查 API Key 和网络连接',
        recoverable: true,
        context: { provider, endpoint },
      }
    );

    this.logger.log(error);

    const buttons = provider === 'ollama' || provider === 'koboldcpp'
      ? ['启动服务', '切换提供者', '忽略']
      : ['重试', '切换提供者', '忽略'];

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'warning',
      title: 'LLM 连接失败',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons,
      defaultId: 0,
    });

    return {
      handled: true,
      action: result.response === 0 ? 'retry' : 'ignore',
      userChoice: ['start_service', 'switch_provider', 'ignore'][result.response],
    };
  }

  /**
   * Handle config corruption errors
   */
  async handleConfigCorruptError(
    configPath: string
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.CONFIG_CORRUPT,
      '配置文件损坏',
      {
        severity: ErrorSeverity.WARNING,
        details: `配置文件路径: ${configPath}`,
        suggestion: '将备份当前配置并重置为默认设置',
        recoverable: true,
        context: { configPath },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'warning',
      title: '配置文件损坏',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['备份并重置', '尝试修复', '取消'],
      defaultId: 0,
      cancelId: 2,
    });

    return {
      handled: true,
      action: result.response === 0 ? 'rollback' : result.response === 1 ? 'retry' : 'abort',
      userChoice: ['reset', 'repair', 'cancel'][result.response],
    };
  }

  /**
   * Handle file locked errors
   */
  async handleFileLockError(
    filePath: string,
    processName?: string
  ): Promise<ErrorHandlerResult> {
    const error = this.createError(
      ErrorType.FILE_LOCKED,
      '文件被占用',
      {
        severity: ErrorSeverity.WARNING,
        details: `文件: ${filePath}${processName ? `\n占用进程: ${processName}` : ''}`,
        suggestion: '请关闭占用该文件的程序后重试',
        recoverable: true,
        context: { filePath, processName },
      }
    );

    this.logger.log(error);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'warning',
      title: '文件被占用',
      message: error.message,
      detail: `${error.details}\n\n${error.suggestion}`,
      buttons: ['重试', '取消'],
      defaultId: 0,
      cancelId: 1,
    });

    return {
      handled: true,
      action: result.response === 0 ? 'retry' : 'abort',
      userChoice: result.response === 0 ? 'retry' : 'cancel',
    };
  }

  /**
   * Handle generic/unknown errors
   */
  async handleUnknownError(
    error: Error,
    context?: string
  ): Promise<ErrorHandlerResult> {
    const appError = this.createError(
      ErrorType.UNKNOWN,
      '发生未知错误',
      {
        severity: ErrorSeverity.ERROR,
        details: `${context ? `上下文: ${context}\n` : ''}错误: ${error.message}`,
        suggestion: '请查看日志获取详细信息，或联系技术支持',
        recoverable: false,
        context: { originalError: error.message, stack: error.stack },
      }
    );

    this.logger.log(appError);

    const result = await dialog.showMessageBox(this.mainWindow!, {
      type: 'error',
      title: '错误',
      message: appError.message,
      detail: `${appError.details}\n\n${appError.suggestion}`,
      buttons: ['查看日志', '继续', '退出'],
      defaultId: 0,
    });

    if (result.response === 0) {
      await this.logger.openLogFile();
    }

    return {
      handled: true,
      action: result.response === 2 ? 'abort' : 'ignore',
      userChoice: ['view_log', 'continue', 'exit'][result.response],
    };
  }

  /**
   * Get the error logger instance
   */
  getLogger(): ErrorLogger {
    return this.logger;
  }

  /**
   * Log an error without showing dialog
   */
  logError(error: AppError): void {
    this.logger.log(error);
  }

  /**
   * Send error to renderer process
   */
  sendErrorToRenderer(error: AppError): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('error:occurred', error);
    }
  }
}

// Factory function
let errorHandlerInstance: ErrorHandler | null = null;

export function createErrorHandler(userDataPath: string): ErrorHandler {
  if (!errorHandlerInstance) {
    errorHandlerInstance = new ErrorHandler(userDataPath);
  }
  return errorHandlerInstance;
}

export function getErrorHandler(): ErrorHandler | null {
  return errorHandlerInstance;
}
