/**
 * Ollama LLM Service
 * Ollama 本地 LLM 服务实现
 */

import {
  LLMProvider,
  CognitionInput,
  CognitionOutput,
} from '@digital-human/shared';
import { ILLMService, OllamaGenerateResponse } from './types';
import { OllamaLLMConfig } from '../types';
import { buildOllamaPrompt, parseAIResponse } from './prompt-builder';

/**
 * Ollama LLM 服务类
 */
export class OllamaLLMService implements ILLMService {
  private config: Required<OllamaLLMConfig>;
  private provider: LLMProvider;

  constructor(config: OllamaLLMConfig = {}) {
    this.config = {
      endpoint: config.endpoint || 'http://localhost:11434',
      model: config.model || 'llama3.2',
      maxTokens: config.maxTokens || 1024,
      temperature: config.temperature || 0.7,
    };

    this.provider = {
      type: 'local',
      name: 'ollama',
      model: this.config.model,
      endpoint: this.config.endpoint,
    };
  }

  /**
   * 生成响应
   */
  async generateResponse(input: CognitionInput): Promise<CognitionOutput> {
    const prompt = buildOllamaPrompt(input);
    
    const response = await fetch(`${this.config.endpoint}/api/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: this.config.model,
        prompt: prompt,
        stream: false,
        options: {
          num_predict: this.config.maxTokens,
          temperature: this.config.temperature,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Ollama API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as OllamaGenerateResponse;
    const content = data.response || '';

    return parseAIResponse(content);
  }

  /**
   * 获取当前提供者
   */
  getProvider(): LLMProvider {
    return this.provider;
  }

  /**
   * 检查服务是否可用
   */
  async isAvailable(): Promise<boolean> {
    try {
      const response = await fetch(`${this.config.endpoint}/api/tags`, {
        method: 'GET',
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
