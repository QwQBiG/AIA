/**
 * Local Embedding Service
 * 本地嵌入服务实现（支持 sentence-transformers 等）
 */

import { EmbeddingProvider } from '@digital-human/shared';
import { IEmbeddingService, LocalEmbeddingConfig } from './types';

/**
 * 本地嵌入服务类
 * 支持通过 HTTP API 调用本地嵌入模型（如 sentence-transformers）
 */
export class LocalEmbeddingService implements IEmbeddingService {
  private config: LocalEmbeddingConfig;
  private provider: EmbeddingProvider;
  private dimensions: number;

  constructor(config: LocalEmbeddingConfig, dimensions: number = 384) {
    this.config = {
      ...config,
      model: config.model || 'all-MiniLM-L6-v2',
    };
    this.dimensions = dimensions;
    
    this.provider = {
      type: 'local',
      name: 'sentence-transformers',
      model: this.config.model!,
      dimensions: this.dimensions,
    };
  }

  /**
   * 生成单个文本的嵌入
   */
  async generateEmbedding(text: string): Promise<number[]> {
    const embeddings = await this.generateEmbeddings([text]);
    return embeddings[0];
  }

  /**
   * 批量生成嵌入
   */
  async generateEmbeddings(texts: string[]): Promise<number[][]> {
    const response = await fetch(`${this.config.endpoint}/embed`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: this.config.model,
        texts: texts,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Local embedding API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as {
      embeddings: number[][];
    };

    return data.embeddings;
  }

  /**
   * 获取当前提供者
   */
  getProvider(): EmbeddingProvider {
    return this.provider;
  }

  /**
   * 获取嵌入维度
   */
  getDimensions(): number {
    return this.dimensions;
  }
}

/**
 * Ollama 嵌入服务类
 * 支持通过 Ollama API 调用本地嵌入模型
 */
export class OllamaEmbeddingService implements IEmbeddingService {
  private endpoint: string;
  private model: string;
  private provider: EmbeddingProvider;
  private dimensions: number;

  constructor(endpoint: string = 'http://localhost:11434', model: string = 'nomic-embed-text', dimensions: number = 768) {
    this.endpoint = endpoint;
    this.model = model;
    this.dimensions = dimensions;
    
    this.provider = {
      type: 'local',
      name: 'ollama',
      model: this.model,
      dimensions: this.dimensions,
    };
  }

  /**
   * 生成单个文本的嵌入
   */
  async generateEmbedding(text: string): Promise<number[]> {
    const response = await fetch(`${this.endpoint}/api/embeddings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: this.model,
        prompt: text,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Ollama API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as {
      embedding: number[];
    };

    return data.embedding;
  }

  /**
   * 批量生成嵌入
   */
  async generateEmbeddings(texts: string[]): Promise<number[][]> {
    // Ollama 不支持批量嵌入，需要逐个处理
    const embeddings: number[][] = [];
    for (const text of texts) {
      const embedding = await this.generateEmbedding(text);
      embeddings.push(embedding);
    }
    return embeddings;
  }

  /**
   * 获取当前提供者
   */
  getProvider(): EmbeddingProvider {
    return this.provider;
  }

  /**
   * 获取嵌入维度
   */
  getDimensions(): number {
    return this.dimensions;
  }
}
