/**
 * Memory System
 * 记忆系统核心实现
 */

import { v4 as uuidv4 } from 'uuid';
import { Memory, MemoryInput, EmbeddingProvider } from '@digital-human/shared';
import { DatabaseConfig, IMemorySystem, IMemoryStore } from './types';
import { PostgresMemoryStore } from './postgres-memory-store';
import { ShortTermMemoryStore } from './short-term-memory-store';
import { IEmbeddingService } from './embedding/types';
import { createEmbeddingService, getDefaultEmbeddingProvider, EmbeddingFactoryConfig } from './embedding/embedding-factory';

/**
 * 记忆系统配置
 */
export interface MemorySystemConfig {
  database: DatabaseConfig;
  embedding: EmbeddingFactoryConfig;
  shortTermMaxSize?: number;
  useDatabaseFallback?: boolean;
}

/**
 * 记忆系统类
 * 整合长期记忆（PostgreSQL）和短期记忆（内存）
 */
export class MemorySystem implements IMemorySystem {
  private longTermStore: IMemoryStore;
  private shortTermStore: ShortTermMemoryStore;
  private embeddingService: IEmbeddingService;
  private config: MemorySystemConfig;
  private initialized = false;
  private databaseAvailable = true;

  constructor(config: MemorySystemConfig) {
    this.config = config;
    this.longTermStore = new PostgresMemoryStore(config.database);
    this.shortTermStore = new ShortTermMemoryStore(config.shortTermMaxSize || 100);
    
    // 初始化嵌入服务
    const provider = getDefaultEmbeddingProvider();
    this.embeddingService = createEmbeddingService(provider, config.embedding);
  }

  /**
   * 初始化记忆系统
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    try {
      await this.longTermStore.initialize();
      this.databaseAvailable = true;
    } catch (error) {
      console.warn('Failed to initialize database, falling back to in-memory only:', error);
      this.databaseAvailable = false;
      
      if (!this.config.useDatabaseFallback) {
        throw error;
      }
    }

    this.initialized = true;
  }

  /**
   * 关闭记忆系统
   */
  async close(): Promise<void> {
    if (this.databaseAvailable) {
      await this.longTermStore.close();
    }
    this.shortTermStore.clear();
    this.initialized = false;
  }

  /**
   * 存储记忆
   */
  async storeMemory(memory: MemoryInput): Promise<string> {
    if (!this.initialized) {
      throw new Error('MemorySystem not initialized. Call initialize() first.');
    }

    // 生成嵌入向量
    const embedding = await this.embeddingService.generateEmbedding(memory.content);

    // 创建记忆对象
    const memoryObj: Memory = {
      id: uuidv4(),
      content: memory.content,
      type: memory.type,
      timestamp: new Date(),
      embedding,
    };

    // 存储到短期记忆
    this.shortTermStore.add(memoryObj);

    // 尝试存储到长期记忆
    if (this.databaseAvailable) {
      try {
        const id = await this.longTermStore.storeMemory(memory, embedding);
        memoryObj.id = id;
      } catch (error) {
        console.warn('Failed to store memory in database:', error);
        this.databaseAvailable = false;
      }
    }

    return memoryObj.id;
  }

  /**
   * 语义搜索记忆
   */
  async searchMemories(query: string, limit: number): Promise<Memory[]> {
    if (!this.initialized) {
      throw new Error('MemorySystem not initialized. Call initialize() first.');
    }

    const effectiveLimit = Math.min(limit, 10);

    // 如果数据库可用，使用向量搜索
    if (this.databaseAvailable) {
      try {
        const queryEmbedding = await this.embeddingService.generateEmbedding(query);
        const memories = await this.longTermStore.searchMemories(queryEmbedding, effectiveLimit);
        
        // 按相关性分数降序排列
        return memories.sort((a, b) => (b.relevanceScore || 0) - (a.relevanceScore || 0));
      } catch (error) {
        console.warn('Database search failed, falling back to short-term memory:', error);
        this.databaseAvailable = false;
      }
    }

    // 降级到短期记忆的简单搜索
    return this.shortTermStore.search(query, effectiveLimit);
  }

  /**
   * 获取最近记忆
   */
  async getRecentMemories(count: number): Promise<Memory[]> {
    if (!this.initialized) {
      throw new Error('MemorySystem not initialized. Call initialize() first.');
    }

    const effectiveCount = Math.min(count, 50);

    // 如果数据库可用，从数据库获取
    if (this.databaseAvailable) {
      try {
        return await this.longTermStore.getRecentMemories(effectiveCount);
      } catch (error) {
        console.warn('Database query failed, falling back to short-term memory:', error);
        this.databaseAvailable = false;
      }
    }

    // 降级到短期记忆
    return this.shortTermStore.getRecent(effectiveCount);
  }

  /**
   * 设置嵌入提供者
   */
  setEmbeddingProvider(provider: EmbeddingProvider): void {
    this.embeddingService = createEmbeddingService(provider, this.config.embedding);
  }

  /**
   * 获取当前嵌入提供者
   */
  getEmbeddingProvider(): EmbeddingProvider {
    return this.embeddingService.getProvider();
  }

  /**
   * 检查数据库是否可用
   */
  isDatabaseAvailable(): boolean {
    return this.databaseAvailable;
  }

  /**
   * 获取短期记忆数量
   */
  getShortTermMemoryCount(): number {
    return this.shortTermStore.size();
  }
}
