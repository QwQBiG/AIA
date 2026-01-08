/**
 * Memory Storage Property Tests
 * 记忆存储属性测试
 * 
 * **Feature: ai-vtuber-digital-human, Property 4: 记忆存储完整性**
 * **Validates: Requirements 7.1**
 */

import * as fc from 'fast-check';
import { Memory, MemoryInput } from '@digital-human/shared';
import { ShortTermMemoryStore } from './short-term-memory-store';

/**
 * 生成有效的 MemoryInput
 */
const memoryInputArbitrary = fc.record({
  content: fc.string({ minLength: 1, maxLength: 1000 }),
  type: fc.constantFrom('conversation', 'game_event', 'system') as fc.Arbitrary<'conversation' | 'game_event' | 'system'>,
  participants: fc.option(fc.array(fc.string({ minLength: 1, maxLength: 50 }), { minLength: 0, maxLength: 10 }), { nil: undefined }),
  metadata: fc.option(fc.dictionary(fc.string(), fc.jsonValue()), { nil: undefined }),
});

/**
 * 生成有效的 Memory 对象
 */
const memoryArbitrary = fc.record({
  id: fc.uuid(),
  content: fc.string({ minLength: 1, maxLength: 1000 }),
  type: fc.constantFrom('conversation', 'game_event', 'system'),
  timestamp: fc.date(),
  embedding: fc.option(fc.array(fc.float(), { minLength: 384, maxLength: 384 }), { nil: undefined }),
  relevanceScore: fc.option(fc.float({ min: 0, max: 1 }), { nil: undefined }),
});

describe('Property 4: 记忆存储完整性', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 4: 记忆存储完整性**
   * *For any* 存储的记忆对象，检索时应该包含原始的 content、timestamp 和 participant metadata。
   * **Validates: Requirements 7.1**
   */
  it('should preserve content, timestamp, and type when storing and retrieving memories', () => {
    fc.assert(
      fc.property(memoryArbitrary, (memory) => {
        const store = new ShortTermMemoryStore(100);
        
        // 存储记忆
        store.add(memory);
        
        // 检索记忆
        const retrieved = store.getAll();
        
        // 验证记忆被正确存储
        expect(retrieved.length).toBe(1);
        const retrievedMemory = retrieved[0];
        
        // 验证核心字段完整性
        expect(retrievedMemory.id).toBe(memory.id);
        expect(retrievedMemory.content).toBe(memory.content);
        expect(retrievedMemory.type).toBe(memory.type);
        expect(retrievedMemory.timestamp).toEqual(memory.timestamp);
        
        return true;
      }),
      { numRuns: 100 }
    );
  });

  it('should maintain memory integrity across multiple stores and retrieves', () => {
    fc.assert(
      fc.property(
        fc.array(memoryArbitrary, { minLength: 1, maxLength: 20 }),
        (memories) => {
          const store = new ShortTermMemoryStore(100);
          
          // 存储所有记忆
          for (const memory of memories) {
            store.add(memory);
          }
          
          // 检索所有记忆
          const retrieved = store.getAll();
          
          // 验证数量一致
          expect(retrieved.length).toBe(memories.length);
          
          // 验证每个记忆的完整性
          for (let i = 0; i < memories.length; i++) {
            expect(retrieved[i].content).toBe(memories[i].content);
            expect(retrieved[i].type).toBe(memories[i].type);
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should preserve memory content exactly without modification', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 5000 }),
        (content) => {
          const store = new ShortTermMemoryStore(100);
          const memory: Memory = {
            id: 'test-id',
            content,
            type: 'conversation',
            timestamp: new Date(),
          };
          
          store.add(memory);
          const retrieved = store.getAll()[0];
          
          // 内容应该完全相同，包括特殊字符
          expect(retrieved.content).toBe(content);
          expect(retrieved.content.length).toBe(content.length);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('Memory Store Size Limits', () => {
  it('should respect max size limit', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 50 }),
        fc.array(memoryArbitrary, { minLength: 1, maxLength: 100 }),
        (maxSize, memories) => {
          const store = new ShortTermMemoryStore(maxSize);
          
          for (const memory of memories) {
            store.add(memory);
          }
          
          // 存储大小不应超过最大限制
          expect(store.size()).toBeLessThanOrEqual(maxSize);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});
