/**
 * KoboldCPP LLM Service
 * KoboldCPP 本地 LLM 服务实现
 */

import {
  LLMProvider,
  CognitionInput,
  CognitionOutput,
} from '@digital-human/shared';
import { ILLMService, KoboldCPPGenerateResponse } from './types';
import { KoboldCPPConfig } from '../types';
import { buildOllamaPrompt, parseAIResponse } from './prompt-builder';

/**
 * KoboldCPP LLM 服务类
 */
export class KoboldCPPLLMService implements ILLMService {
  private config: Required<KoboldCPPConfig>;
  private provider: LLMProvider;

  constructor(config: KoboldCPPConfig) {
    this.config = {
      endpoint: config.endpoint,
      maxTokens: config.maxTokens || 1024,
      temperature: config.temperature || 0.7,
    };

    this.provider = {
      type: 'local',
      name: 'koboldcpp',
      model: 'local',
      endpoint: this.config.endpoint,
    };
  }

  /**
   * 生成响应
   */
  async generateResponse(input: CognitionInput): Promise<CognitionOutput> {
    const prompt = buildOllamaPrompt(input);
    
    const response = await fetch(`${this.config.endpoint}/api/v1/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: prompt,
        max_length: this.config.maxTokens,
        temperature: this.config.temperature,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`KoboldCPP API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as KoboldCPPGenerateResponse;
    const content = data.results[0]?.text || '';

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
      const response = await fetch(`${this.config.endpoint}/api/v1/model`, {
        method: 'GET',
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
