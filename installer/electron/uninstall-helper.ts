/**
 * Uninstall Helper Module
 * Provides utilities for uninstallation process
 * 
 * Requirements: 5.2, 5.3, 5.5
 */

import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

// Electron app module - imported dynamically to avoid issues in non-Electron context
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let electronApp: any = null;
try {
  // Dynamic require to avoid bundling issues
  electronApp = require('electron').app;
} catch {
  // Not running in Electron context
}

export interface UserDataPaths {
  config: string;
  database: string;
  logs: string;
  models: string;
  appData: string;
}

/**
 * Get all user data paths
 */
export function getUserDataPaths(basePath?: string): UserDataPaths {
  const appDataPath = basePath || (electronApp?.getPath('userData') ?? path.join(process.env.APPDATA || '', 'ai-vtuber-digital-human'));
  
  return {
    config: path.join(appDataPath, 'config'),
    database: path.join(appDataPath, 'data'),
    logs: path.join(appDataPath, 'logs'),
    models: path.join(appDataPath, 'models'),
    appData: appDataPath
  };
}

/**
 * Check if the application is running
 * Requirements: 5.5
 */
export function isApplicationRunning(): boolean {
  try {
    const processName = 'AI VTuber Digital Human.exe';
    const result = execSync(`tasklist /FI "IMAGENAME eq ${processName}" /NH`, {
      encoding: 'utf-8',
      windowsHide: true
    });
    
    // If the process is not found, tasklist returns "INFO: No tasks..."
    return !result.includes('INFO:');
  } catch {
    return false;
  }
}

/**
 * Get the size of user data in bytes
 */
export function getUserDataSize(): number {
  const paths = getUserDataPaths();
  let totalSize = 0;
  
  const calculateDirSize = (dirPath: string): number => {
    if (!fs.existsSync(dirPath)) return 0;
    
    let size = 0;
    const items = fs.readdirSync(dirPath, { withFileTypes: true });
    
    for (const item of items) {
      const itemPath = path.join(dirPath, item.name);
      if (item.isDirectory()) {
        size += calculateDirSize(itemPath);
      } else {
        try {
          size += fs.statSync(itemPath).size;
        } catch {
          // Ignore files we can't access
        }
      }
    }
    
    return size;
  };
  
  totalSize += calculateDirSize(paths.config);
  totalSize += calculateDirSize(paths.database);
  totalSize += calculateDirSize(paths.logs);
  totalSize += calculateDirSize(paths.models);
  
  return totalSize;
}

/**
 * Format bytes to human readable string
 */
export function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  
  return `${size.toFixed(2)} ${units[unitIndex]}`;
}

/**
 * Backup user data before uninstall
 * Requirements: 5.3
 */
export function backupUserData(backupPath: string): boolean {
  try {
    const paths = getUserDataPaths();
    
    if (!fs.existsSync(backupPath)) {
      fs.mkdirSync(backupPath, { recursive: true });
    }
    
    // Copy config
    if (fs.existsSync(paths.config)) {
      copyDirectory(paths.config, path.join(backupPath, 'config'));
    }
    
    // Copy database
    if (fs.existsSync(paths.database)) {
      copyDirectory(paths.database, path.join(backupPath, 'data'));
    }
    
    return true;
  } catch (error) {
    console.error('Failed to backup user data:', error);
    return false;
  }
}

/**
 * Copy directory recursively
 */
function copyDirectory(src: string, dest: string): void {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  
  const items = fs.readdirSync(src, { withFileTypes: true });
  
  for (const item of items) {
    const srcPath = path.join(src, item.name);
    const destPath = path.join(dest, item.name);
    
    if (item.isDirectory()) {
      copyDirectory(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * Clean up user data
 * Requirements: 5.2
 */
export function cleanupUserData(keepData: boolean): void {
  if (keepData) {
    console.log('User data will be preserved');
    return;
  }
  
  const paths = getUserDataPaths();
  
  const removeDirectory = (dirPath: string): void => {
    if (fs.existsSync(dirPath)) {
      fs.rmSync(dirPath, { recursive: true, force: true });
    }
  };
  
  removeDirectory(paths.config);
  removeDirectory(paths.database);
  removeDirectory(paths.logs);
  removeDirectory(paths.models);
  
  // Try to remove the main app data folder if empty
  try {
    const items = fs.readdirSync(paths.appData);
    if (items.length === 0) {
      fs.rmdirSync(paths.appData);
    }
  } catch {
    // Ignore errors when removing app data folder
  }
}

/**
 * Register uninstall info in registry (for Windows)
 * This is typically handled by electron-builder, but we can add extra info
 */
export function getUninstallInfo(installPath?: string): {
  displayName: string;
  displayVersion: string;
  publisher: string;
  installLocation: string;
  uninstallString: string;
  displayIcon: string;
  estimatedSize: number;
} {
  const appPath = installPath || (electronApp ? path.dirname(electronApp.getPath('exe')) : process.cwd());
  const version = electronApp?.getVersion() || '1.0.0';
  
  return {
    displayName: 'AI VTuber Digital Human',
    displayVersion: version,
    publisher: 'AI VTuber Team',
    installLocation: appPath,
    uninstallString: path.join(appPath, 'Uninstall AI VTuber Digital Human.exe'),
    displayIcon: path.join(appPath, 'AI VTuber Digital Human.exe'),
    estimatedSize: Math.round(getUserDataSize() / 1024) // Size in KB
  };
}
