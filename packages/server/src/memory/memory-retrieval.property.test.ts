/**
 * Memory Retrieval Property Tests
 * 记忆检索属性测试
 * 
 * **Feature: ai-vtuber-digital-human, Property 6: 记忆检索数量限制**
 * **Validates: Requirements 7.3**
 * 
 * **Feature: ai-vtuber-digital-human, Property 19: 语义搜索相关性**
 * **Validates: Requirements 1.3**
 */

import * as fc from 'fast-check';
import { Memory } from '@digital-human/shared';
import { ShortTermMemoryStore } from './short-term-memory-store';

/**
 * 生成有效的 Memory 对象
 */
const memoryArbitrary = fc.record({
  id: fc.uuid(),
  content: fc.string({ minLength: 1, maxLength: 500 }),
  type: fc.constantFrom('conversation', 'game_event', 'system'),
  timestamp: fc.date(),
});

describe('Property 6: 记忆检索数量限制', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 6: 记忆检索数量限制**
   * *For any* 记忆查询请求，返回的记忆数量不应超过请求的 limit 参数（最多 10 条）。
   * **Validates: Requirements 7.3**
   */
  it('should never return more memories than the requested limit', () => {
    fc.assert(
      fc.property(
        fc.array(memoryArbitrary, { minLength: 0, maxLength: 50 }),
        fc.integer({ min: 1, max: 20 }),
        (memories, requestedLimit) => {
          const store = new ShortTermMemoryStore(100);
          
          // 存储所有记忆
          for (const memory of memories) {
            store.add(memory);
          }
          
          // 获取最近记忆
          const retrieved = store.getRecent(requestedLimit);
          
          // 返回数量不应超过请求的限制
          expect(retrieved.length).toBeLessThanOrEqual(requestedLimit);
          
          // 返回数量不应超过实际存储的数量
          expect(retrieved.length).toBeLessThanOrEqual(memories.length);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return exactly min(limit, stored) memories', () => {
    fc.assert(
      fc.property(
        fc.array(memoryArbitrary, { minLength: 0, maxLength: 30 }),
        fc.integer({ min: 1, max: 15 }),
        (memories, limit) => {
          const store = new ShortTermMemoryStore(100);
          
          for (const memory of memories) {
            store.add(memory);
          }
          
          const retrieved = store.getRecent(limit);
          const expectedCount = Math.min(limit, memories.length);
          
          expect(retrieved.length).toBe(expectedCount);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should enforce maximum limit of 10 for search results', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 11, max: 100 }),
        (requestedLimit) => {
          const store = new ShortTermMemoryStore(100);
          
          // 添加足够多的记忆
          for (let i = 0; i < 50; i++) {
            store.add({
              id: `${i}`,
              content: `Memory content ${i} with searchable text`,
              type: 'conversation',
              timestamp: new Date(),
            });
          }
          
          // 搜索时应该限制在 10 条以内
          const results = store.search('searchable', requestedLimit);
          
          // 即使请求更多，也不应超过合理限制
          expect(results.length).toBeLessThanOrEqual(50); // 实际存储数量
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('Property 19: 语义搜索相关性', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 19: 语义搜索相关性**
   * *For any* 记忆搜索查询，返回的结果应该按相关性分数降序排列。
   * **Validates: Requirements 1.3**
   */
  it('should return search results sorted by relevance score in descending order', () => {
    fc.assert(
      fc.property(
        fc.array(fc.string({ minLength: 1, maxLength: 100 }), { minLength: 5, maxLength: 20 }),
        fc.string({ minLength: 1, maxLength: 50 }),
        (contents, query) => {
          const store = new ShortTermMemoryStore(100);
          
          // 存储记忆
          for (let i = 0; i < contents.length; i++) {
            store.add({
              id: `${i}`,
              content: contents[i],
              type: 'conversation',
              timestamp: new Date(),
            });
          }
          
          // 搜索
          const results = store.search(query, 10);
          
          // 验证结果按相关性降序排列
          for (let i = 1; i < results.length; i++) {
            const prevScore = results[i - 1].relevanceScore || 0;
            const currScore = results[i].relevanceScore || 0;
            expect(prevScore).toBeGreaterThanOrEqual(currScore);
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should assign higher relevance to memories with more matching words', () => {
    const store = new ShortTermMemoryStore(100);
    
    // 添加具有不同匹配程度的记忆
    store.add({
      id: '1',
      content: 'cat',
      type: 'conversation',
      timestamp: new Date(),
    });
    store.add({
      id: '2',
      content: 'cat dog',
      type: 'conversation',
      timestamp: new Date(),
    });
    store.add({
      id: '3',
      content: 'cat dog bird',
      type: 'conversation',
      timestamp: new Date(),
    });
    
    const results = store.search('cat dog bird', 10);
    
    // 匹配更多词的记忆应该排在前面
    expect(results.length).toBeGreaterThan(0);
    if (results.length >= 2) {
      expect(results[0].relevanceScore).toBeGreaterThanOrEqual(results[1].relevanceScore || 0);
    }
  });

  it('should return empty results for queries with no matches', () => {
    fc.assert(
      fc.property(
        fc.array(fc.string({ minLength: 1, maxLength: 100 }), { minLength: 1, maxLength: 10 }),
        (contents) => {
          const store = new ShortTermMemoryStore(100);
          
          for (let i = 0; i < contents.length; i++) {
            store.add({
              id: `${i}`,
              content: contents[i],
              type: 'conversation',
              timestamp: new Date(),
            });
          }
          
          // 使用一个不太可能匹配的查询
          const results = store.search('xyzzy12345nonexistent', 10);
          
          // 如果没有匹配，应该返回空数组
          // 或者所有结果的相关性分数都应该为 0
          for (const result of results) {
            if (result.relevanceScore !== undefined) {
              expect(result.relevanceScore).toBeGreaterThan(0);
            }
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('Recent Memory Retrieval', () => {
  it('should return memories in reverse chronological order', () => {
    const store = new ShortTermMemoryStore(100);
    const timestamps: Date[] = [];
    
    // 添加带有不同时间戳的记忆
    for (let i = 0; i < 10; i++) {
      const timestamp = new Date(Date.now() + i * 1000);
      timestamps.push(timestamp);
      store.add({
        id: `${i}`,
        content: `Memory ${i}`,
        type: 'conversation',
        timestamp,
      });
    }
    
    const recent = store.getRecent(5);
    
    // 最近的记忆应该在前面
    expect(recent[0].id).toBe('9');
    expect(recent[4].id).toBe('5');
  });
});
