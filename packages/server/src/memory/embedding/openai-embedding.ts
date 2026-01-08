/**
 * OpenAI Embedding Service
 * OpenAI 嵌入服务实现
 */

import { EmbeddingProvider } from '@digital-human/shared';
import { IEmbeddingService, OpenAIEmbeddingConfig } from './types';

/**
 * OpenAI 嵌入服务类
 */
export class OpenAIEmbeddingService implements IEmbeddingService {
  private config: OpenAIEmbeddingConfig;
  private provider: EmbeddingProvider;

  constructor(config: OpenAIEmbeddingConfig) {
    this.config = {
      ...config,
      model: config.model || 'text-embedding-3-small',
      baseUrl: config.baseUrl || 'https://api.openai.com/v1',
    };
    
    this.provider = {
      type: 'cloud',
      name: 'openai',
      model: this.config.model!,
      dimensions: this.getModelDimensions(this.config.model!),
    };
  }

  /**
   * 获取模型的嵌入维度
   */
  private getModelDimensions(model: string): number {
    const dimensionMap: Record<string, number> = {
      'text-embedding-3-small': 1536,
      'text-embedding-3-large': 3072,
      'text-embedding-ada-002': 1536,
    };
    return dimensionMap[model] || 1536;
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
    const response = await fetch(`${this.config.baseUrl}/embeddings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.config.apiKey}`,
      },
      body: JSON.stringify({
        model: this.config.model,
        input: texts,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as {
      data: Array<{ embedding: number[]; index: number }>;
    };

    // 按索引排序确保顺序正确
    return data.data
      .sort((a, b) => a.index - b.index)
      .map((item) => item.embedding);
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
    return this.provider.dimensions;
  }
}
