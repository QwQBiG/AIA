import { app, BrowserWindow, Tray, Menu, ipcMain, shell } from 'electron';
import * as path from 'path';
import { serverManager } from './server-manager';
import { ConfigManager, createConfigManager } from './config-manager';
import { DatabaseInitializer, createDatabaseInitializer } from './db-initializer';
import { ollamaManager } from './ollama-manager';
import { createKoboldCPPManager, KoboldCPPManager } from './koboldcpp-manager';
import { 
  ErrorHandler, 
  createErrorHandler, 
  ErrorType, 
  ErrorSeverity 
} from './error-handler';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let configManager: ConfigManager | null = null;
let dbInitializer: DatabaseInitializer | null = null;
let errorHandler: ErrorHandler | null = null;
let koboldcppManager: KoboldCPPManager | null = null;

/**
 * Create the main application window
 */
function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, '../assets/icon.ico'),
  });

  // Load the control panel UI
  // In production, this would load from the bundled client files
  const resourcesPath = (process as any).resourcesPath || __dirname;
  const clientPath = path.join(resourcesPath, 'client', 'index.html');
  window.loadFile(clientPath).catch(() => {
    // Fallback for development
    window.loadURL('http://localhost:5173');
  });

  window.on('close', (event: Electron.Event) => {
    // Minimize to tray instead of closing
    if (!(app as any).isQuitting) {
      event.preventDefault();
      window.hide();
    }
  });

  return window;
}

/**
 * Create system tray icon
 */
function createTrayIcon(): Tray {
  const trayIcon = new Tray(path.join(__dirname, '../assets/tray.ico'));
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Window',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      },
    },
    {
      label: 'Quit',
      click: () => {
        (app as any).isQuitting = true;
        app.quit();
      },
    },
  ]);

  trayIcon.setToolTip('AI VTuber Digital Human');
  trayIcon.setContextMenu(contextMenu);

  trayIcon.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });

  return trayIcon;
}

/**
 * Register IPC handlers for renderer process communication
 */
function registerIpcHandlers(): void {
  // Configuration management
  ipcMain.handle('config:get', (_event: Electron.IpcMainInvokeEvent, key: string) => {
    return configManager?.get(key);
  });

  ipcMain.handle('config:set', (_event: Electron.IpcMainInvokeEvent, key: string, value: any) => {
    configManager?.set(key, value);
  });

  ipcMain.handle('config:getAll', () => {
    return configManager?.getAll();
  });

  ipcMain.handle('config:save', (_event: Electron.IpcMainInvokeEvent, config: any) => {
    try {
      configManager?.save(config);
      return { success: true };
    } catch (error) {
      errorHandler?.logError(errorHandler.createError(
        ErrorType.CONFIG_CORRUPT,
        '保存配置失败',
        { details: (error as Error).message, recoverable: true }
      ));
      return { success: false, error: (error as Error).message };
    }
  });

  // Database management
  ipcMain.handle('database:initialize', async () => {
    try {
      await dbInitializer?.initialize();
      return { success: true };
    } catch (error) {
      const result = await errorHandler?.handleDatabaseError(
        'initialize',
        error as Error
      );
      return { success: false, error: (error as Error).message, action: result?.action };
    }
  });

  ipcMain.handle('database:runMigrations', async () => {
    try {
      await dbInitializer?.runMigrations();
      return { success: true };
    } catch (error) {
      const result = await errorHandler?.handleDatabaseError(
        'runMigrations',
        error as Error
      );
      return { success: false, error: (error as Error).message, action: result?.action };
    }
  });

  ipcMain.handle('database:getStatus', () => {
    return dbInitializer?.getStatus();
  });

  // Server management
  ipcMain.handle('server:start', async () => {
    try {
      await serverManager.start();
      return { success: true, port: serverManager.getStatus().port };
    } catch (error) {
      const status = serverManager.getStatus();
      if ((error as Error).message.includes('EADDRINUSE') || 
          (error as Error).message.includes('port')) {
        const result = await errorHandler?.handlePortInUseError(status.port || 3000);
        return { success: false, error: (error as Error).message, action: result?.action };
      }
      await errorHandler?.handleUnknownError(error as Error, 'server:start');
      return { success: false, error: (error as Error).message };
    }
  });

  ipcMain.handle('server:stop', async () => {
    await serverManager.stop();
    return { success: true };
  });

  ipcMain.handle('server:getStatus', () => {
    return serverManager.getStatus();
  });

  // LLM management - Ollama
  ipcMain.handle('llm:checkOllama', async () => {
    return ollamaManager.getStatus();
  });

  ipcMain.handle('llm:startOllama', async () => {
    try {
      await ollamaManager.start();
      return { success: true };
    } catch (error) {
      const result = await errorHandler?.handleLLMConnectionError(
        'ollama',
        ollamaManager.getEndpoint()
      );
      return { success: false, error: (error as Error).message, action: result?.userChoice };
    }
  });

  ipcMain.handle('llm:stopOllama', async () => {
    await ollamaManager.stop();
    return { success: true };
  });

  ipcMain.handle('llm:pullModel', async (_event: Electron.IpcMainInvokeEvent, model: string) => {
    try {
      await ollamaManager.pullModel(model);
      return { success: true };
    } catch (error) {
      const result = await errorHandler?.handleNetworkError(
        `下载模型 ${model}`,
        ollamaManager.getEndpoint()
      );
      return { success: false, error: (error as Error).message, action: result?.action };
    }
  });

  ipcMain.handle('llm:listModels', async () => {
    return ollamaManager.listModels();
  });

  // LLM management - KoboldCPP
  ipcMain.handle('llm:checkKoboldCPP', async () => {
    return koboldcppManager?.getStatus();
  });

  ipcMain.handle('llm:startKoboldCPP', async (_event: Electron.IpcMainInvokeEvent, modelPath?: string) => {
    try {
      await koboldcppManager?.start(modelPath);
      return { success: true };
    } catch (error) {
      const result = await errorHandler?.handleLLMConnectionError(
        'koboldcpp',
        koboldcppManager?.getEndpoint()
      );
      return { success: false, error: (error as Error).message, action: result?.userChoice };
    }
  });

  ipcMain.handle('llm:stopKoboldCPP', async () => {
    await koboldcppManager?.stop();
    return { success: true };
  });

  ipcMain.handle('llm:installKoboldCPP', async () => {
    try {
      await koboldcppManager?.install();
      return { success: true };
    } catch (error) {
      const result = await errorHandler?.handleNetworkError(
        '下载 KoboldCPP',
        'https://github.com/LostRuins/koboldcpp'
      );
      return { success: false, error: (error as Error).message, action: result?.action };
    }
  });

  // System utilities
  ipcMain.handle('system:getAppVersion', () => {
    return app.getVersion();
  });

  ipcMain.handle('system:getAppPath', () => {
    return app.getPath('userData');
  });

  ipcMain.handle('system:openExternal', async (_event: Electron.IpcMainInvokeEvent, url: string) => {
    await shell.openExternal(url);
  });

  ipcMain.handle('system:openLogFile', async () => {
    await errorHandler?.getLogger().openLogFile();
  });

  ipcMain.handle('system:getLogPath', () => {
    return errorHandler?.getLogger().getLogPath();
  });

  // Error handling
  ipcMain.handle('error:log', (_event: Electron.IpcMainInvokeEvent, error: any) => {
    errorHandler?.logError(errorHandler.createError(
      error.type || ErrorType.UNKNOWN,
      error.message,
      {
        severity: error.severity || ErrorSeverity.ERROR,
        details: error.details,
        context: error.context,
        recoverable: error.recoverable ?? false,
      }
    ));
  });
}

// App lifecycle handlers
app.on('ready', async () => {
  try {
    const userDataPath = app.getPath('userData');
    
    // Initialize error handler first
    errorHandler = createErrorHandler(userDataPath);
    
    // Initialize config manager
    configManager = createConfigManager(userDataPath);
    
    // Initialize KoboldCPP manager
    koboldcppManager = createKoboldCPPManager(userDataPath);
    
    // Initialize database
    dbInitializer = createDatabaseInitializer(userDataPath);
    
    try {
      await dbInitializer.initialize();
      await dbInitializer.runMigrations();
    } catch (dbError) {
      const result = await errorHandler.handleDatabaseError(
        'initialization',
        dbError as Error
      );
      if (result.action === 'abort') {
        app.quit();
        return;
      }
    }
    
    // Register IPC handlers
    registerIpcHandlers();
    
    // Start the server
    try {
      await serverManager.start();
    } catch (serverError) {
      const status = serverManager.getStatus();
      const result = await errorHandler.handlePortInUseError(status.port || 3000);
      if (result.action === 'abort') {
        app.quit();
        return;
      }
      // If user chose auto port, server manager already handles this
    }
    
    // Create main window
    mainWindow = createMainWindow();
    errorHandler.setMainWindow(mainWindow);
    
    // Create tray icon
    tray = createTrayIcon();
    
    // Check if first run and show setup wizard
    if (configManager.get<boolean>('firstRun')) {
      // Setup wizard will be shown by the renderer
    }
  } catch (error) {
    console.error('Failed to initialize application:', error);
    if (errorHandler) {
      await errorHandler.handleUnknownError(error as Error, 'app initialization');
    }
    app.quit();
  }
});

app.on('window-all-closed', () => {
  // On macOS, keep app running in tray
  if (process.platform !== 'darwin') {
    // On Windows, keep running in tray
    // Don't quit unless explicitly requested
  }
});

app.on('activate', () => {
  // On macOS, re-create window when dock icon is clicked
  if (BrowserWindow.getAllWindows().length === 0) {
    mainWindow = createMainWindow();
  }
});

app.on('before-quit', async () => {
  (app as any).isQuitting = true;
  dbInitializer?.close();
  await serverManager.stop();
});
