/**
 * Memory System Types
 * 记忆系统类型定义
 */

import { Memory, MemoryInput, EmbeddingProvider } from '@digital-human/shared';

/**
 * 数据库配置接口
 */
export interface DatabaseConfig {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  ssl?: boolean;
}

/**
 * 记忆存储接口
 */
export interface IMemoryStore {
  /** 存储记忆 */
  storeMemory(memory: MemoryInput, embedding: number[]): Promise<string>;
  /** 语义搜索记忆 */
  searchMemories(queryEmbedding: number[], limit: number): Promise<Memory[]>;
  /** 获取最近记忆 */
  getRecentMemories(count: number): Promise<Memory[]>;
  /** 初始化存储 */
  initialize(): Promise<void>;
  /** 关闭连接 */
  close(): Promise<void>;
}

/**
 * 记忆系统接口
 */
export interface IMemorySystem {
  /** 存储记忆 */
  storeMemory(memory: MemoryInput): Promise<string>;
  /** 语义搜索记忆 */
  searchMemories(query: string, limit: number): Promise<Memory[]>;
  /** 获取最近记忆 */
  getRecentMemories(count: number): Promise<Memory[]>;
  /** 设置嵌入提供者 */
  setEmbeddingProvider(provider: EmbeddingProvider): void;
  /** 初始化系统 */
  initialize(): Promise<void>;
  /** 关闭系统 */
  close(): Promise<void>;
}

/**
 * 短期记忆存储接口（内存）
 */
export interface IShortTermMemoryStore {
  /** 添加记忆 */
  add(memory: Memory): void;
  /** 获取所有记忆 */
  getAll(): Memory[];
  /** 获取最近 N 条记忆 */
  getRecent(count: number): Memory[];
  /** 清空记忆 */
  clear(): void;
  /** 获取记忆数量 */
  size(): number;
}

/**
 * 数据库记忆行接口
 */
export interface MemoryRow {
  id: string;
  content: string;
  type: string;
  timestamp: Date;
  embedding: string | null;
  participants: string[] | null;
  metadata: Record<string, unknown> | null;
}
