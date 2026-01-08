import * as fs from 'fs';
import * as path from 'path';
import { AppConfig, DEFAULT_CONFIG } from './types';

export interface ConfigError {
  type: 'PARSE_ERROR' | 'READ_ERROR' | 'WRITE_ERROR' | 'VALIDATION_ERROR';
  message: string;
  details?: string;
  recoverable: boolean;
}

/**
 * Manages application configuration persistence
 * Handles reading, writing, and validating configuration files
 */
export class ConfigManager {
  private configPath: string;
  private backupPath: string;
  private config: AppConfig;
  private lastError: ConfigError | null = null;

  constructor(userDataPath: string) {
    this.configPath = path.join(userDataPath, 'config.json');
    this.backupPath = path.join(userDataPath, 'config.backup.json');
    this.config = this.load();
  }

  /**
   * Get the configuration file path
   */
  getConfigPath(): string {
    return this.configPath;
  }

  /**
   * Get the last error
   */
  getLastError(): ConfigError | null {
    return this.lastError;
  }

  /**
   * Load configuration from disk
   * Returns default config if file doesn't exist or is invalid
   */
  load(): AppConfig {
    this.lastError = null;
    
    try {
      if (fs.existsSync(this.configPath)) {
        const data = fs.readFileSync(this.configPath, 'utf-8');
        
        try {
          const parsed = JSON.parse(data) as Partial<AppConfig>;
          // Merge with defaults to ensure all fields exist
          this.config = this.mergeWithDefaults(parsed);
          return this.config;
        } catch (parseError) {
          // JSON parse error - config is corrupted
          this.lastError = {
            type: 'PARSE_ERROR',
            message: '配置文件格式错误',
            details: (parseError as Error).message,
            recoverable: true,
          };
          console.error('Config file is corrupted, attempting recovery...');
          
          // Try to load from backup
          if (this.loadFromBackup()) {
            return this.config;
          }
          
          // Backup the corrupted file and use defaults
          this.backupCorruptedConfig();
        }
      }
    } catch (error) {
      this.lastError = {
        type: 'READ_ERROR',
        message: '无法读取配置文件',
        details: (error as Error).message,
        recoverable: true,
      };
      console.error('Failed to load config:', error);
    }
    
    this.config = { ...DEFAULT_CONFIG };
    return this.config;
  }

  /**
   * Try to load configuration from backup
   */
  private loadFromBackup(): boolean {
    try {
      if (fs.existsSync(this.backupPath)) {
        const data = fs.readFileSync(this.backupPath, 'utf-8');
        const parsed = JSON.parse(data) as Partial<AppConfig>;
        this.config = this.mergeWithDefaults(parsed);
        console.log('Loaded configuration from backup');
        return true;
      }
    } catch (error) {
      console.error('Failed to load backup config:', error);
    }
    return false;
  }

  /**
   * Backup corrupted config file
   */
  private backupCorruptedConfig(): void {
    try {
      if (fs.existsSync(this.configPath)) {
        const corruptedPath = this.configPath + '.corrupted.' + Date.now();
        fs.copyFileSync(this.configPath, corruptedPath);
        console.log(`Corrupted config backed up to: ${corruptedPath}`);
      }
    } catch (error) {
      console.error('Failed to backup corrupted config:', error);
    }
  }

  /**
   * Save configuration to disk
   */
  save(config: AppConfig): void {
    this.lastError = null;
    
    try {
      // Ensure directory exists
      const dir = path.dirname(this.configPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      
      // Create backup of current config before saving
      if (fs.existsSync(this.configPath)) {
        try {
          fs.copyFileSync(this.configPath, this.backupPath);
        } catch (backupError) {
          console.warn('Failed to create config backup:', backupError);
        }
      }
      
      // Validate before saving
      const validation = this.validate(config);
      if (!validation.valid) {
        this.lastError = {
          type: 'VALIDATION_ERROR',
          message: '配置验证失败',
          details: validation.errors.join('; '),
          recoverable: true,
        };
        // Still save but log warning
        console.warn('Saving config with validation errors:', validation.errors);
      }
      
      fs.writeFileSync(
        this.configPath,
        JSON.stringify(config, null, 2),
        'utf-8'
      );
      this.config = config;
    } catch (error) {
      this.lastError = {
        type: 'WRITE_ERROR',
        message: '无法保存配置文件',
        details: (error as Error).message,
        recoverable: false,
      };
      console.error('Failed to save config:', error);
      throw error;
    }
  }

  /**
   * Get a specific configuration value by key path
   * Supports dot notation: 'llm.provider'
   */
  get<T>(key: string): T | undefined {
    const keys = key.split('.');
    let value: any = this.config;
    
    for (const k of keys) {
      if (value === undefined || value === null) {
        return undefined;
      }
      value = value[k];
    }
    
    return value as T;
  }

  /**
   * Set a specific configuration value by key path
   * Supports dot notation: 'llm.provider'
   */
  set<T>(key: string, value: T): void {
    const keys = key.split('.');
    let obj: any = this.config;
    
    for (let i = 0; i < keys.length - 1; i++) {
      const k = keys[i];
      if (obj[k] === undefined) {
        obj[k] = {};
      }
      obj = obj[k];
    }
    
    obj[keys[keys.length - 1]] = value;
    this.save(this.config);
  }

  /**
   * Get the entire configuration object
   */
  getAll(): AppConfig {
    return { ...this.config };
  }

  /**
   * Reset configuration to defaults
   */
  reset(): void {
    this.config = { ...DEFAULT_CONFIG };
    this.save(this.config);
  }

  /**
   * Merge partial config with defaults
   */
  private mergeWithDefaults(partial: Partial<AppConfig>): AppConfig {
    return {
      database: {
        ...DEFAULT_CONFIG.database,
        ...partial.database,
      },
      llm: {
        ...DEFAULT_CONFIG.llm,
        ...partial.llm,
      },
      tts: {
        ...DEFAULT_CONFIG.tts,
        ...partial.tts,
      },
      streaming: {
        ...DEFAULT_CONFIG.streaming,
        ...partial.streaming,
      },
      server: {
        port: partial.server?.port ?? DEFAULT_CONFIG.server?.port ?? 3000,
      },
      firstRun: partial.firstRun ?? DEFAULT_CONFIG.firstRun,
    };
  }

  /**
   * Validate configuration structure
   */
  validate(config: AppConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Validate LLM config
    if (!config.llm?.provider) {
      errors.push('LLM provider is required');
    }

    // Validate provider-specific requirements
    if (config.llm?.provider === 'openai' && !config.llm.openaiApiKey) {
      errors.push('OpenAI API key is required when using OpenAI provider');
    }

    if (config.llm?.provider === 'anthropic' && !config.llm.anthropicApiKey) {
      errors.push('Anthropic API key is required when using Anthropic provider');
    }

    // Validate TTS config
    if (!config.tts?.provider) {
      errors.push('TTS provider is required');
    }

    if (config.tts?.provider === 'elevenlabs' && !config.tts.apiKey) {
      errors.push('ElevenLabs API key is required when using ElevenLabs provider');
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}

// Factory function for creating ConfigManager with app userData path
export function createConfigManager(userDataPath: string): ConfigManager {
  return new ConfigManager(userDataPath);
}
