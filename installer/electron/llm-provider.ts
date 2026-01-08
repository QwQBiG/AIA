import { LLMProvider, LLMConfig } from './types';
import { ollamaManager, OllamaManager } from './ollama-manager';
import { KoboldCPPManager, createKoboldCPPManager } from './koboldcpp-manager';

export interface LLMProviderStatus {
  provider: LLMProvider;
  available: boolean;
  endpoint?: string;
  model?: string;
  error?: string;
}

/**
 * Manages LLM provider selection and switching
 */
export class LLMProviderManager {
  private currentProvider: LLMProvider = 'ollama';
  private ollamaManager: OllamaManager;
  private koboldcppManager: KoboldCPPManager;
  private config: LLMConfig;

  constructor(userDataPath: string, config: LLMConfig) {
    this.ollamaManager = ollamaManager;
    this.koboldcppManager = createKoboldCPPManager(userDataPath);
    this.config = config;
    this.currentProvider = config.provider;
  }

  /**
   * Get current provider
   */
  getCurrentProvider(): LLMProvider {
    return this.currentProvider;
  }

  /**
   * Switch to a different provider
   */
  async switchProvider(provider: LLMProvider): Promise<void> {
    this.currentProvider = provider;
    this.config.provider = provider;
  }

  /**
   * Test if a provider is available
   */
  async testProvider(provider: LLMProvider): Promise<LLMProviderStatus> {
    switch (provider) {
      case 'ollama':
        return this.testOllama();
      case 'koboldcpp':
        return this.testKoboldCPP();
      case 'openai':
        return this.testOpenAI();
      case 'anthropic':
        return this.testAnthropic();
      default:
        return {
          provider,
          available: false,
          error: `Unknown provider: ${provider}`,
        };
    }
  }

  /**
   * Test Ollama availability
   */
  private async testOllama(): Promise<LLMProviderStatus> {
    try {
      const status = await this.ollamaManager.getStatus();
      
      if (!status.installed) {
        return {
          provider: 'ollama',
          available: false,
          error: 'Ollama is not installed',
        };
      }

      if (!status.running) {
        return {
          provider: 'ollama',
          available: false,
          error: 'Ollama is not running',
        };
      }

      return {
        provider: 'ollama',
        available: true,
        endpoint: this.config.ollamaEndpoint || 'http://localhost:11434',
        model: this.config.ollamaModel,
      };
    } catch (error) {
      return {
        provider: 'ollama',
        available: false,
        error: String(error),
      };
    }
  }

  /**
   * Test KoboldCPP availability
   */
  private async testKoboldCPP(): Promise<LLMProviderStatus> {
    try {
      const status = await this.koboldcppManager.getStatus();
      
      if (!status.installed) {
        return {
          provider: 'koboldcpp',
          available: false,
          error: 'KoboldCPP is not installed',
        };
      }

      if (!status.running) {
        return {
          provider: 'koboldcpp',
          available: false,
          error: 'KoboldCPP is not running',
        };
      }

      return {
        provider: 'koboldcpp',
        available: true,
        endpoint: this.config.koboldcppEndpoint || 'http://localhost:5001',
      };
    } catch (error) {
      return {
        provider: 'koboldcpp',
        available: false,
        error: String(error),
      };
    }
  }

  /**
   * Test OpenAI availability
   */
  private async testOpenAI(): Promise<LLMProviderStatus> {
    if (!this.config.openaiApiKey) {
      return {
        provider: 'openai',
        available: false,
        error: 'OpenAI API key is not configured',
      };
    }

    try {
      const response = await fetch('https://api.openai.com/v1/models', {
        headers: {
          'Authorization': `Bearer ${this.config.openaiApiKey}`,
        },
      });

      if (!response.ok) {
        return {
          provider: 'openai',
          available: false,
          error: `OpenAI API error: ${response.status}`,
        };
      }

      return {
        provider: 'openai',
        available: true,
        model: this.config.openaiModel || 'gpt-4',
      };
    } catch (error) {
      return {
        provider: 'openai',
        available: false,
        error: String(error),
      };
    }
  }

  /**
   * Test Anthropic availability
   */
  private async testAnthropic(): Promise<LLMProviderStatus> {
    if (!this.config.anthropicApiKey) {
      return {
        provider: 'anthropic',
        available: false,
        error: 'Anthropic API key is not configured',
      };
    }

    // Anthropic doesn't have a simple health check endpoint
    // We just verify the key is present
    return {
      provider: 'anthropic',
      available: true,
      model: this.config.anthropicModel || 'claude-3-sonnet-20240229',
    };
  }

  /**
   * Get status of all providers
   */
  async getAllProviderStatus(): Promise<LLMProviderStatus[]> {
    const providers: LLMProvider[] = ['ollama', 'koboldcpp', 'openai', 'anthropic'];
    return Promise.all(providers.map(p => this.testProvider(p)));
  }

  /**
   * Get the endpoint for the current provider
   */
  getEndpoint(): string {
    switch (this.currentProvider) {
      case 'ollama':
        return this.config.ollamaEndpoint || 'http://localhost:11434';
      case 'koboldcpp':
        return this.config.koboldcppEndpoint || 'http://localhost:5001';
      case 'openai':
        return 'https://api.openai.com/v1';
      case 'anthropic':
        return 'https://api.anthropic.com/v1';
      default:
        return '';
    }
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<LLMConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.provider) {
      this.currentProvider = config.provider;
    }
  }
}

export function createLLMProviderManager(
  userDataPath: string, 
  config: LLMConfig
): LLMProviderManager {
  return new LLMProviderManager(userDataPath, config);
}
