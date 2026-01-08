/**
 * LLM Service Factory
 * LLM 服务工厂
 */

import { LLMProvider } from '@digital-human/shared';
import { ILLMService } from './types';
import { LLMFactoryConfig } from '../types';
import { OpenAILLMService } from './openai-llm';
import { AnthropicLLMService } from './anthropic-llm';
import { OllamaLLMService } from './ollama-llm';
import { KoboldCPPLLMService } from './koboldcpp-llm';

/**
 * 创建 LLM 服务
 */
export function createLLMService(
  provider: LLMProvider,
  config: LLMFactoryConfig
): ILLMService {
  switch (provider.name) {
    case 'openai':
      if (!config.openaiApiKey) {
        throw new Error('OpenAI API key is required for OpenAI LLM service');
      }
      return new OpenAILLMService({
        apiKey: config.openaiApiKey,
        model: provider.model,
        baseUrl: config.openaiBaseUrl || provider.endpoint,
      });

    case 'anthropic':
      if (!config.anthropicApiKey) {
        throw new Error('Anthropic API key is required for Anthropic LLM service');
      }
      return new AnthropicLLMService({
        apiKey: config.anthropicApiKey,
        model: provider.model,
        baseUrl: config.anthropicBaseUrl || provider.endpoint,
      });

    case 'ollama':
      return new OllamaLLMService({
        endpoint: config.ollamaEndpoint || provider.endpoint || 'http://localhost:11434',
        model: provider.model,
      });

    case 'koboldcpp':
      if (!config.koboldEndpoint && !provider.endpoint) {
        throw new Error('KoboldCPP endpoint is required');
      }
      return new KoboldCPPLLMService({
        endpoint: config.koboldEndpoint || provider.endpoint!,
      });

    default:
      throw new Error(`Unknown LLM provider: ${provider.name}`);
  }
}

/**
 * 获取默认 LLM 提供者配置
 */
export function getDefaultLLMProvider(): LLMProvider {
  // 优先使用本地 Ollama
  if (process.env.OLLAMA_ENDPOINT || process.env.USE_LOCAL_LLM === 'true') {
    return {
      type: 'local',
      name: 'ollama',
      model: process.env.OLLAMA_MODEL || 'llama3.2',
      endpoint: process.env.OLLAMA_ENDPOINT || 'http://localhost:11434',
    };
  }

  // 如果有 KoboldCPP 端点
  if (process.env.KOBOLDCPP_ENDPOINT) {
    return {
      type: 'local',
      name: 'koboldcpp',
      model: 'local',
      endpoint: process.env.KOBOLDCPP_ENDPOINT,
    };
  }

  // 如果有 Anthropic API Key
  if (process.env.ANTHROPIC_API_KEY) {
    return {
      type: 'cloud',
      name: 'anthropic',
      model: process.env.ANTHROPIC_MODEL || 'claude-3-haiku-20240307',
    };
  }

  // 如果有 OpenAI API Key
  if (process.env.OPENAI_API_KEY) {
    return {
      type: 'cloud',
      name: 'openai',
      model: process.env.OPENAI_MODEL || 'gpt-4o-mini',
    };
  }

  // 默认使用本地 Ollama
  return {
    type: 'local',
    name: 'ollama',
    model: 'llama3.2',
    endpoint: 'http://localhost:11434',
  };
}

/**
 * 获取所有可用的 LLM 提供者
 */
export function getAvailableLLMProviders(config: LLMFactoryConfig): LLMProvider[] {
  const providers: LLMProvider[] = [];

  // OpenAI
  if (config.openaiApiKey) {
    providers.push({
      type: 'cloud',
      name: 'openai',
      model: process.env.OPENAI_MODEL || 'gpt-4o-mini',
    });
  }

  // Anthropic
  if (config.anthropicApiKey) {
    providers.push({
      type: 'cloud',
      name: 'anthropic',
      model: process.env.ANTHROPIC_MODEL || 'claude-3-haiku-20240307',
    });
  }

  // Ollama (本地，总是可用)
  providers.push({
    type: 'local',
    name: 'ollama',
    model: process.env.OLLAMA_MODEL || 'llama3.2',
    endpoint: config.ollamaEndpoint || 'http://localhost:11434',
  });

  // KoboldCPP
  if (config.koboldEndpoint) {
    providers.push({
      type: 'local',
      name: 'koboldcpp',
      model: 'local',
      endpoint: config.koboldEndpoint,
    });
  }

  return providers;
}
