import { contextBridge, ipcRenderer } from 'electron';

/**
 * Preload script that exposes safe IPC communication to the renderer process
 * This script runs in a privileged context and bridges the main and renderer processes
 */

// Result type for operations that can fail
export interface OperationResult {
  success: boolean;
  error?: string;
  action?: string;
}

// Define the API that will be exposed to the renderer
export interface ElectronAPI {
  // Configuration management
  config: {
    get: (key: string) => Promise<any>;
    set: (key: string, value: any) => Promise<void>;
    getAll: () => Promise<any>;
    save: (config: any) => Promise<OperationResult>;
  };
  
  // Server management
  server: {
    start: () => Promise<OperationResult & { port?: number }>;
    stop: () => Promise<OperationResult>;
    getStatus: () => Promise<{ running: boolean; port?: number; pid?: number }>;
  };
  
  // Database management
  database: {
    initialize: () => Promise<OperationResult>;
    runMigrations: () => Promise<OperationResult>;
    getStatus: () => Promise<{ initialized: boolean; version: string; path: string }>;
  };
  
  // LLM management
  llm: {
    // Ollama
    checkOllama: () => Promise<{ installed: boolean; running: boolean; version?: string }>;
    startOllama: () => Promise<OperationResult>;
    stopOllama: () => Promise<OperationResult>;
    pullModel: (model: string) => Promise<OperationResult>;
    listModels: () => Promise<string[]>;
    // KoboldCPP
    checkKoboldCPP: () => Promise<{ installed: boolean; running: boolean; version?: string }>;
    startKoboldCPP: (modelPath?: string) => Promise<OperationResult>;
    stopKoboldCPP: () => Promise<OperationResult>;
    installKoboldCPP: () => Promise<OperationResult>;
  };
  
  // System utilities
  system: {
    getAppVersion: () => Promise<string>;
    getAppPath: () => Promise<string>;
    openExternal: (url: string) => Promise<void>;
    openLogFile: () => Promise<void>;
    getLogPath: () => Promise<string>;
  };

  // Error handling
  error: {
    log: (error: {
      type?: string;
      message: string;
      severity?: string;
      details?: string;
      context?: Record<string, any>;
      recoverable?: boolean;
    }) => Promise<void>;
    onError: (callback: (error: any) => void) => void;
    removeErrorListener: () => void;
  };

  // Wizard management
  wizard: {
    getState: () => Promise<any>;
    next: () => Promise<any>;
    previous: () => Promise<any>;
    setStepData: (stepId: string, data: any) => Promise<any>;
    finish: () => Promise<any>;
    skip: () => Promise<any>;
  };
}

// Error listener reference for cleanup
let errorListener: ((event: any, error: any) => void) | null = null;

// Expose the API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Configuration management
  config: {
    get: (key: string) => ipcRenderer.invoke('config:get', key),
    set: (key: string, value: any) => ipcRenderer.invoke('config:set', key, value),
    getAll: () => ipcRenderer.invoke('config:getAll'),
    save: (config: any) => ipcRenderer.invoke('config:save', config),
  },
  
  // Server management
  server: {
    start: () => ipcRenderer.invoke('server:start'),
    stop: () => ipcRenderer.invoke('server:stop'),
    getStatus: () => ipcRenderer.invoke('server:getStatus'),
  },
  
  // Database management
  database: {
    initialize: () => ipcRenderer.invoke('database:initialize'),
    runMigrations: () => ipcRenderer.invoke('database:runMigrations'),
    getStatus: () => ipcRenderer.invoke('database:getStatus'),
  },
  
  // LLM management
  llm: {
    // Ollama
    checkOllama: () => ipcRenderer.invoke('llm:checkOllama'),
    startOllama: () => ipcRenderer.invoke('llm:startOllama'),
    stopOllama: () => ipcRenderer.invoke('llm:stopOllama'),
    pullModel: (model: string) => ipcRenderer.invoke('llm:pullModel', model),
    listModels: () => ipcRenderer.invoke('llm:listModels'),
    // KoboldCPP
    checkKoboldCPP: () => ipcRenderer.invoke('llm:checkKoboldCPP'),
    startKoboldCPP: (modelPath?: string) => ipcRenderer.invoke('llm:startKoboldCPP', modelPath),
    stopKoboldCPP: () => ipcRenderer.invoke('llm:stopKoboldCPP'),
    installKoboldCPP: () => ipcRenderer.invoke('llm:installKoboldCPP'),
  },
  
  // System utilities
  system: {
    getAppVersion: () => ipcRenderer.invoke('system:getAppVersion'),
    getAppPath: () => ipcRenderer.invoke('system:getAppPath'),
    openExternal: (url: string) => ipcRenderer.invoke('system:openExternal', url),
    openLogFile: () => ipcRenderer.invoke('system:openLogFile'),
    getLogPath: () => ipcRenderer.invoke('system:getLogPath'),
  },

  // Error handling
  error: {
    log: (error) => ipcRenderer.invoke('error:log', error),
    onError: (callback: (error: any) => void) => {
      errorListener = (_event, error) => callback(error);
      ipcRenderer.on('error:occurred', errorListener);
    },
    removeErrorListener: () => {
      if (errorListener) {
        ipcRenderer.removeListener('error:occurred', errorListener);
        errorListener = null;
      }
    },
  },

  // Wizard management
  wizard: {
    getState: () => ipcRenderer.invoke('wizard:getState'),
    next: () => ipcRenderer.invoke('wizard:next'),
    previous: () => ipcRenderer.invoke('wizard:previous'),
    setStepData: (stepId: string, data: any) => ipcRenderer.invoke('wizard:setStepData', stepId, data),
    finish: () => ipcRenderer.invoke('wizard:finish'),
    skip: () => ipcRenderer.invoke('wizard:skip'),
  },
} as ElectronAPI);

// Type declaration for TypeScript support in renderer
declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
