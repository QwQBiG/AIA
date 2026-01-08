/**
 * Embedding Service Factory
 * 嵌入服务工厂
 */

import { EmbeddingProvider } from '@digital-human/shared';
import { IEmbeddingService } from './types';
import { OpenAIEmbeddingService } from './openai-embedding';
import { LocalEmbeddingService, OllamaEmbeddingService } from './local-embedding';

/**
 * 嵌入服务工厂配置
 */
export interface EmbeddingFactoryConfig {
  openaiApiKey?: string;
  openaiBaseUrl?: string;
  localEndpoint?: string;
  ollamaEndpoint?: string;
}

/**
 * 创建嵌入服务
 */
export function createEmbeddingService(
  provider: EmbeddingProvider,
  config: EmbeddingFactoryConfig
): IEmbeddingService {
  switch (provider.name) {
    case 'openai':
      if (!config.openaiApiKey) {
        throw new Error('OpenAI API key is required for OpenAI embedding service');
      }
      return new OpenAIEmbeddingService({
        apiKey: config.openaiApiKey,
        model: provider.model,
        baseUrl: config.openaiBaseUrl,
      });

    case 'sentence-transformers':
    case 'bge':
      if (!config.localEndpoint) {
        throw new Error('Local endpoint is required for local embedding service');
      }
      return new LocalEmbeddingService(
        {
          endpoint: config.localEndpoint,
          model: provider.model,
        },
        provider.dimensions
      );

    case 'ollama':
      return new OllamaEmbeddingService(
        config.ollamaEndpoint || 'http://localhost:11434',
        provider.model,
        provider.dimensions
      );

    default:
      throw new Error(`Unknown embedding provider: ${provider.name}`);
  }
}

/**
 * 获取默认嵌入提供者配置
 */
export function getDefaultEmbeddingProvider(): EmbeddingProvider {
  // 优先使用本地 Ollama
  if (process.env.OLLAMA_ENDPOINT || process.env.USE_LOCAL_EMBEDDING === 'true') {
    return {
      type: 'local',
      name: 'ollama',
      model: process.env.OLLAMA_EMBEDDING_MODEL || 'nomic-embed-text',
      dimensions: 768,
    };
  }

  // 如果有 OpenAI API Key，使用 OpenAI
  if (process.env.OPENAI_API_KEY) {
    return {
      type: 'cloud',
      name: 'openai',
      model: process.env.OPENAI_EMBEDDING_MODEL || 'text-embedding-3-small',
      dimensions: 1536,
    };
  }

  // 默认使用本地 sentence-transformers
  return {
    type: 'local',
    name: 'sentence-transformers',
    model: 'all-MiniLM-L6-v2',
    dimensions: 384,
  };
}
