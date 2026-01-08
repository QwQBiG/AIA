/**
 * OpenAI LLM Service
 * OpenAI LLM 服务实现
 */

import {
  LLMProvider,
  CognitionInput,
  CognitionOutput,
  EmotionType,
} from '@digital-human/shared';
import { ILLMService, OpenAIChatMessage, OpenAIChatCompletionResponse } from './types';
import { OpenAILLMConfig } from '../types';
import { buildPromptMessages, parseAIResponse } from './prompt-builder';

/**
 * OpenAI LLM 服务类
 */
export class OpenAILLMService implements ILLMService {
  private config: Required<OpenAILLMConfig>;
  private provider: LLMProvider;

  constructor(config: OpenAILLMConfig) {
    this.config = {
      apiKey: config.apiKey,
      model: config.model || 'gpt-4o-mini',
      baseUrl: config.baseUrl || 'https://api.openai.com/v1',
      maxTokens: config.maxTokens || 1024,
      temperature: config.temperature || 0.7,
    };

    this.provider = {
      type: 'cloud',
      name: 'openai',
      model: this.config.model,
      endpoint: this.config.baseUrl,
    };
  }

  /**
   * 生成响应
   */
  async generateResponse(input: CognitionInput): Promise<CognitionOutput> {
    const messages = buildPromptMessages(input);
    
    const response = await fetch(`${this.config.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.config.apiKey}`,
      },
      body: JSON.stringify({
        model: this.config.model,
        messages: messages,
        max_tokens: this.config.maxTokens,
        temperature: this.config.temperature,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as OpenAIChatCompletionResponse;
    const content = data.choices[0]?.message?.content || '';

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
      const response = await fetch(`${this.config.baseUrl}/models`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
