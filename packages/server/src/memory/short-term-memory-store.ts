/**
 * Short-Term Memory Store
 * 短期记忆存储（内存实现）
 */

import { Memory } from '@digital-human/shared';
import { IShortTermMemoryStore } from './types';

/**
 * 短期记忆存储类
 * 用于会话级别的记忆存储，数据保存在内存中
 */
export class ShortTermMemoryStore implements IShortTermMemoryStore {
  private memories: Memory[] = [];
  private maxSize: number;

  constructor(maxSize: number = 100) {
    this.maxSize = maxSize;
  }

  /**
   * 添加记忆
   */
  add(memory: Memory): void {
    this.memories.push(memory);
    
    // 如果超过最大容量，移除最旧的记忆
    if (this.memories.length > this.maxSize) {
      this.memories.shift();
    }
  }

  /**
   * 获取所有记忆
   */
  getAll(): Memory[] {
    return [...this.memories];
  }

  /**
   * 获取最近 N 条记忆
   */
  getRecent(count: number): Memory[] {
    const effectiveCount = Math.min(count, this.memories.length);
    return this.memories.slice(-effectiveCount).reverse();
  }

  /**
   * 清空记忆
   */
  clear(): void {
    this.memories = [];
  }

  /**
   * 获取记忆数量
   */
  size(): number {
    return this.memories.length;
  }

  /**
   * 按相关性搜索（简单的关键词匹配）
   * 用于降级模式下的基本搜索
   */
  search(query: string, limit: number): Memory[] {
    const queryLower = query.toLowerCase();
    const scored = this.memories.map((memory) => {
      const contentLower = memory.content.toLowerCase();
      let score = 0;
      
      // 简单的关键词匹配评分
      const queryWords = queryLower.split(/\s+/);
      for (const word of queryWords) {
        if (contentLower.includes(word)) {
          score += 1;
        }
      }
      
      return { memory, score };
    });

    return scored
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map((item) => ({
        ...item.memory,
        relevanceScore: item.score / query.split(/\s+/).length,
      }));
  }
}
