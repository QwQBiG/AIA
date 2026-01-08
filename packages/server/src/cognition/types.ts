/**
 * Cognition Engine Types
 * 认知引擎类型定义
 */

import {
  LLMProvider,
  CognitionInput,
  CognitionOutput,
  PersonalityConfig,
} from '@digital-human/shared';

/**
 * 认知引擎接口
 */
export interface ICognitionEngine {
  /** 生成响应 */
  generateResponse(input: CognitionInput): Promise<CognitionOutput>;
  /** 设置 LLM 提供者 */
  setProvider(provider: LLMProvider): void;
  /** 获取可用的提供者列表 */
  getAvailableProviders(): LLMProvider[];
  /** 设置人格配置 */
  setPersonality(personality: PersonalityConfig): void;
  /** 获取当前人格配置 */
  getPersonality(): PersonalityConfig | null;
}

/**
 * OpenAI LLM 配置
 */
export interface OpenAILLMConfig {
  apiKey: string;
  model?: string;
  baseUrl?: string;
  maxTokens?: number;
  temperature?: number;
}

/**
 * Anthropic LLM 配置
 */
export interface AnthropicLLMConfig {
  apiKey: string;
  model?: string;
  baseUrl?: string;
  maxTokens?: number;
  temperature?: number;
}

/**
 * Ollama LLM 配置
 */
export interface OllamaLLMConfig {
  endpoint?: string;
  model?: string;
  maxTokens?: number;
  temperature?: number;
}

/**
 * KoboldCPP LLM 配置
 */
export interface KoboldCPPConfig {
  endpoint: string;
  maxTokens?: number;
  temperature?: number;
}

/**
 * LLM 工厂配置
 */
export interface LLMFactoryConfig {
  openaiApiKey?: string;
  openaiBaseUrl?: string;
  anthropicApiKey?: string;
  anthropicBaseUrl?: string;
  ollamaEndpoint?: string;
  koboldEndpoint?: string;
}

/**
 * LLM 响应格式（内部使用）
 */
export interface LLMRawResponse {
  text: string;
  finishReason?: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}
