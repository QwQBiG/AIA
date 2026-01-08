/**
 * Memory System Unit Tests
 * 记忆系统单元测试
 */

import { Memory, MemoryInput } from '@digital-human/shared';
import { ShortTermMemoryStore } from './short-term-memory-store';

describe('ShortTermMemoryStore', () => {
  let store: ShortTermMemoryStore;

  beforeEach(() => {
    store = new ShortTermMemoryStore(10);
  });

  describe('add', () => {
    it('should add a memory to the store', () => {
      const memory: Memory = {
        id: '1',
        content: 'Test memory',
        type: 'conversation',
        timestamp: new Date(),
      };

      store.add(memory);
      expect(store.size()).toBe(1);
    });

    it('should remove oldest memory when exceeding max size', () => {
      const maxSize = 5;
      store = new ShortTermMemoryStore(maxSize);

      for (let i = 0; i < maxSize + 2; i++) {
        store.add({
          id: `${i}`,
          content: `Memory ${i}`,
          type: 'conversation',
          timestamp: new Date(),
        });
      }

      expect(store.size()).toBe(maxSize);
      const all = store.getAll();
      expect(all[0].id).toBe('2'); // First two should be removed
    });
  });

  describe('getRecent', () => {
    it('should return most recent memories in reverse order', () => {
      for (let i = 0; i < 5; i++) {
        store.add({
          id: `${i}`,
          content: `Memory ${i}`,
          type: 'conversation',
          timestamp: new Date(),
        });
      }

      const recent = store.getRecent(3);
      expect(recent.length).toBe(3);
      expect(recent[0].id).toBe('4'); // Most recent first
      expect(recent[1].id).toBe('3');
      expect(recent[2].id).toBe('2');
    });

    it('should return all memories if count exceeds size', () => {
      store.add({
        id: '1',
        content: 'Memory 1',
        type: 'conversation',
        timestamp: new Date(),
      });

      const recent = store.getRecent(10);
      expect(recent.length).toBe(1);
    });
  });

  describe('search', () => {
    beforeEach(() => {
      store.add({
        id: '1',
        content: 'The cat sat on the mat',
        type: 'conversation',
        timestamp: new Date(),
      });
      store.add({
        id: '2',
        content: 'The dog ran in the park',
        type: 'conversation',
        timestamp: new Date(),
      });
      store.add({
        id: '3',
        content: 'A cat and a dog played together',
        type: 'conversation',
        timestamp: new Date(),
      });
    });

    it('should find memories containing query words', () => {
      const results = store.search('cat', 10);
      expect(results.length).toBe(2);
    });

    it('should rank results by relevance', () => {
      const results = store.search('cat dog', 10);
      expect(results.length).toBe(3);
      // Memory 3 should be first as it contains both words
      expect(results[0].id).toBe('3');
    });

    it('should respect limit parameter', () => {
      const results = store.search('the', 2);
      expect(results.length).toBe(2);
    });

    it('should return empty array for no matches', () => {
      const results = store.search('elephant', 10);
      expect(results.length).toBe(0);
    });
  });

  describe('clear', () => {
    it('should remove all memories', () => {
      store.add({
        id: '1',
        content: 'Memory 1',
        type: 'conversation',
        timestamp: new Date(),
      });
      store.add({
        id: '2',
        content: 'Memory 2',
        type: 'conversation',
        timestamp: new Date(),
      });

      store.clear();
      expect(store.size()).toBe(0);
    });
  });
});

describe('Memory Input Validation', () => {
  it('should accept valid memory input', () => {
    const input: MemoryInput = {
      content: 'Test content',
      type: 'conversation',
      participants: ['user1', 'user2'],
      metadata: { key: 'value' },
    };

    expect(input.content).toBe('Test content');
    expect(input.type).toBe('conversation');
    expect(input.participants).toEqual(['user1', 'user2']);
  });

  it('should accept memory input without optional fields', () => {
    const input: MemoryInput = {
      content: 'Test content',
      type: 'game_event',
    };

    expect(input.content).toBe('Test content');
    expect(input.type).toBe('game_event');
    expect(input.participants).toBeUndefined();
    expect(input.metadata).toBeUndefined();
  });
});
