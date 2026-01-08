/**
 * Embedding Service Types
 * 嵌入服务类型定义
 */

import { EmbeddingProvider } from '@digital-human/shared';

/**
 * 嵌入服务接口
 */
export interface IEmbeddingService {
  /** 生成文本嵌入 */
  generateEmbedding(text: string): Promise<number[]>;
  /** 批量生成嵌入 */
  generateEmbeddings(texts: string[]): Promise<number[][]>;
  /** 获取当前提供者 */
  getProvider(): EmbeddingProvider;
  /** 获取嵌入维度 */
  getDimensions(): number;
}

/**
 * OpenAI 嵌入配置
 */
export interface OpenAIEmbeddingConfig {
  apiKey: string;
  model?: string;
  baseUrl?: string;
}

/**
 * 本地嵌入配置
 */
export interface LocalEmbeddingConfig {
  endpoint: string;
  model?: string;
}
