/**
 * LLM Provider Types
 * LLM 提供者类型定义
 */

import { LLMProvider, CognitionInput, CognitionOutput } from '@digital-human/shared';

/**
 * LLM 服务接口
 */
export interface ILLMService {
  /** 生成响应 */
  generateResponse(input: CognitionInput): Promise<CognitionOutput>;
  /** 获取当前提供者 */
  getProvider(): LLMProvider;
  /** 检查服务是否可用 */
  isAvailable(): Promise<boolean>;
}

/**
 * OpenAI 聊天消息格式
 */
export interface OpenAIChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

/**
 * OpenAI 聊天完成响应
 */
export interface OpenAIChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: {
      role: string;
      content: string;
    };
    finish_reason: string;
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

/**
 * Anthropic 消息格式
 */
export interface AnthropicMessage {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * Anthropic 消息响应
 */
export interface AnthropicMessageResponse {
  id: string;
  type: string;
  role: string;
  content: Array<{
    type: string;
    text: string;
  }>;
  model: string;
  stop_reason: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

/**
 * Ollama 生成响应
 */
export interface OllamaGenerateResponse {
  model: string;
  created_at: string;
  response: string;
  done: boolean;
  context?: number[];
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  eval_count?: number;
}

/**
 * KoboldCPP 生成响应
 */
export interface KoboldCPPGenerateResponse {
  results: Array<{
    text: string;
  }>;
}
