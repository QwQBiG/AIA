/**
 * Anthropic LLM Service
 * Anthropic Claude LLM 服务实现
 */

import {
  LLMProvider,
  CognitionInput,
  CognitionOutput,
} from '@digital-human/shared';
import { ILLMService, AnthropicMessage, AnthropicMessageResponse } from './types';
import { AnthropicLLMConfig } from '../types';
import { buildAnthropicMessages, parseAIResponse } from './prompt-builder';

/**
 * Anthropic LLM 服务类
 */
export class AnthropicLLMService implements ILLMService {
  private config: Required<AnthropicLLMConfig>;
  private provider: LLMProvider;

  constructor(config: AnthropicLLMConfig) {
    this.config = {
      apiKey: config.apiKey,
      model: config.model || 'claude-3-haiku-20240307',
      baseUrl: config.baseUrl || 'https://api.anthropic.com/v1',
      maxTokens: config.maxTokens || 1024,
      temperature: config.temperature || 0.7,
    };

    this.provider = {
      type: 'cloud',
      name: 'anthropic',
      model: this.config.model,
      endpoint: this.config.baseUrl,
    };
  }

  /**
   * 生成响应
   */
  async generateResponse(input: CognitionInput): Promise<CognitionOutput> {
    const { systemPrompt, messages } = buildAnthropicMessages(input);
    
    const response = await fetch(`${this.config.baseUrl}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this.config.apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: this.config.model,
        max_tokens: this.config.maxTokens,
        temperature: this.config.temperature,
        system: systemPrompt,
        messages: messages,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Anthropic API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as AnthropicMessageResponse;
    const content = data.content[0]?.text || '';

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
      // Anthropic 没有简单的健康检查端点，尝试发送一个最小请求
      const response = await fetch(`${this.config.baseUrl}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.config.apiKey,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: this.config.model,
          max_tokens: 1,
          messages: [{ role: 'user', content: 'hi' }],
        }),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
