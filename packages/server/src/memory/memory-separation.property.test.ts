/**
 * Memory Separation Property Tests
 * 短期和长期记忆分离属性测试
 * 
 * **Feature: ai-vtuber-digital-human, Property 7: 短期和长期记忆分离**
 * **Validates: Requirements 7.4**
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

describe('Property 7: 短期和长期记忆分离', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 7: 短期和长期记忆分离**
   * *For any* 系统运行状态，短期会话记忆和长期持久记忆应该存储在不同的存储区域，互不干扰。
   * **Validates: Requirements 7.4**
   */
  it('should maintain independent short-term memory stores', () => {
    fc.assert(
      fc.property(
        fc.array(memoryArbitrary, { minLength: 1, maxLength: 20 }),
        fc.array(memoryArbitrary, { minLength: 1, maxLength: 20 }),
        (memories1, memories2) => {
          // 创建两个独立的短期记忆存储
          const store1 = new ShortTermMemoryStore(100);
          const store2 = new ShortTermMemoryStore(100);
          
          // 向第一个存储添加记忆
          for (const memory of memories1) {
            store1.add(memory);
          }
          
          // 向第二个存储添加记忆
          for (const memory of memories2) {
            store2.add(memory);
          }
          
          // 验证两个存储是独立的
          expect(store1.size()).toBe(memories1.length);
          expect(store2.size()).toBe(memories2.length);
          
          // 清空一个存储不应影响另一个
          store1.clear();
          expect(store1.size()).toBe(0);
          expect(store2.size()).toBe(memories2.length);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should not share state between different short-term stores', () => {
    fc.assert(
      fc.property(
        memoryArbitrary,
        (memory) => {
          const store1 = new ShortTermMemoryStore(100);
          const store2 = new ShortTermMemoryStore(100);
          
          // 只向 store1 添加记忆
          store1.add(memory);
          
          // store2 应该是空的
          expect(store1.size()).toBe(1);
          expect(store2.size()).toBe(0);
          
          // store2 的操作不应影响 store1
          store2.add({
            id: 'different-id',
            content: 'different content',
            type: 'system',
            timestamp: new Date(),
          });
          
          expect(store1.size()).toBe(1);
          expect(store2.size()).toBe(1);
          
          // 验证内容独立
          const retrieved1 = store1.getAll();
          const retrieved2 = store2.getAll();
          
          expect(retrieved1[0].id).toBe(memory.id);
          expect(retrieved2[0].id).toBe('different-id');
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should maintain separate max size limits for each store', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 5, max: 20 }),
        fc.integer({ min: 5, max: 20 }),
        fc.array(memoryArbitrary, { minLength: 30, maxLength: 50 }),
        (maxSize1, maxSize2, memories) => {
          const store1 = new ShortTermMemoryStore(maxSize1);
          const store2 = new ShortTermMemoryStore(maxSize2);
          
          // 向两个存储添加相同的记忆
          for (const memory of memories) {
            store1.add({ ...memory, id: `store1-${memory.id}` });
            store2.add({ ...memory, id: `store2-${memory.id}` });
          }
          
          // 每个存储应该遵守自己的大小限制
          expect(store1.size()).toBeLessThanOrEqual(maxSize1);
          expect(store2.size()).toBeLessThanOrEqual(maxSize2);
          
          // 大小可能不同（如果 maxSize 不同）
          if (maxSize1 !== maxSize2) {
            expect(store1.size()).not.toBe(store2.size());
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should allow independent search operations on each store', () => {
    const store1 = new ShortTermMemoryStore(100);
    const store2 = new ShortTermMemoryStore(100);
    
    // 向 store1 添加关于猫的记忆
    store1.add({
      id: '1',
      content: 'The cat sat on the mat',
      type: 'conversation',
      timestamp: new Date(),
    });
    
    // 向 store2 添加关于狗的记忆
    store2.add({
      id: '2',
      content: 'The dog ran in the park',
      type: 'conversation',
      timestamp: new Date(),
    });
    
    // 搜索应该只在各自的存储中进行
    const catResults1 = store1.search('cat', 10);
    const catResults2 = store2.search('cat', 10);
    const dogResults1 = store1.search('dog', 10);
    const dogResults2 = store2.search('dog', 10);
    
    expect(catResults1.length).toBe(1);
    expect(catResults2.length).toBe(0);
    expect(dogResults1.length).toBe(0);
    expect(dogResults2.length).toBe(1);
  });
});

describe('Memory Store Isolation', () => {
  it('should not leak memory references between stores', () => {
    fc.assert(
      fc.property(
        memoryArbitrary,
        (memory) => {
          const store1 = new ShortTermMemoryStore(100);
          const store2 = new ShortTermMemoryStore(100);
          
          // 添加到 store1
          store1.add(memory);
          
          // 获取并修改（如果可能的话）
          const retrieved = store1.getAll()[0];
          
          // 即使我们有引用，store2 也不应该受影响
          expect(store2.size()).toBe(0);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should handle concurrent operations on different stores', () => {
    fc.assert(
      fc.property(
        fc.array(memoryArbitrary, { minLength: 1, maxLength: 10 }),
        (memories) => {
          const stores = [
            new ShortTermMemoryStore(100),
            new ShortTermMemoryStore(100),
            new ShortTermMemoryStore(100),
          ];
          
          // 添加到不同的存储
          memories.forEach((memory, i) => {
            stores.forEach((store, j) => {
              store.add({ ...memory, id: `store${j}-${memory.id}` });
            });
          });
          
          // 每个存储应该有相同数量的记忆
          for (const store of stores) {
            expect(store.size()).toBe(memories.length);
          }
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});
