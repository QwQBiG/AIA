/**
 * Spam Filter Property Tests
 * 垃圾消息过滤属性测试
 * 
 * **Feature: ai-vtuber-digital-human, Property 12: 垃圾消息过滤**
 * **Validates: Requirements 4.4**
 */

import * as fc from 'fast-check';
import { SpamFilter } from './spam-filter.js';
import type { ChatMessage } from '@digital-human/shared';

/**
 * 创建测试用的 ChatMessage
 */
function createTestMessage(
  content: string,
  senderId: string = 'user-123'
): ChatMessage {
  return {
    id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    platform: 'twitch',
    sender: {
      id: senderId,
      username: 'testuser',
      displayName: 'Test User',
      isModerator: false,
      isSubscriber: false,
    },
    content,
    timestamp: new Date(),
  };
}

/**
 * 生成有效的屏蔽词（只包含字母数字）
 */
const blockedWordArbitrary = fc.stringOf(
  fc.constantFrom(...'abcdefghijklmnopqrstuvwxyz'.split('')),
  { minLength: 2, maxLength: 10 }
);

/**
 * 生成包含屏蔽词的消息内容
 */
function messageContainingWord(word: string): fc.Arbitrary<string> {
  return fc.tuple(
    fc.string({ minLength: 0, maxLength: 50 }),
    fc.string({ minLength: 0, maxLength: 50 })
  ).map(([prefix, suffix]) => `${prefix} ${word} ${suffix}`);
}

/**
 * 生成不包含任何屏蔽词的消息内容
 */
function messageNotContainingWords(blockedWords: string[]): fc.Arbitrary<string> {
  return fc.string({ minLength: 1, maxLength: 100 })
    .filter(content => {
      const lowerContent = content.toLowerCase();
      return !blockedWords.some(word => lowerContent.includes(word.toLowerCase()));
    });
}

describe('Spam Filter Property Tests', () => {
  /**
   * Property 12: 垃圾消息过滤
   * *For any* 配置了垃圾过滤的聊天接口，包含屏蔽词的消息应该被过滤，不转发到 Cognition_Engine
   */
  describe('Property 12: Spam Message Filtering', () => {
    it('should block all messages containing any blocked word', () => {
      fc.assert(
        fc.property(
          fc.array(blockedWordArbitrary, { minLength: 1, maxLength: 5 }),
          fc.nat({ max: 4 }), // 选择哪个屏蔽词
          (blockedWords, wordIndex) => {
            const filter = new SpamFilter({ blockedWords });
            const selectedWord = blockedWords[wordIndex % blockedWords.length];
            
            // 生成包含选定屏蔽词的消息
            const content = `Hello ${selectedWord} world`;
            const message = createTestMessage(content);
            
            const result = filter.filter(message);
            
            // 消息应该被阻止
            expect(result.passed).toBe(false);
            expect(result.reason).toBe('blocked_word');
            
            filter.stop();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should pass messages not containing any blocked word', () => {
      fc.assert(
        fc.property(
          fc.array(blockedWordArbitrary, { minLength: 1, maxLength: 5 }),
          (blockedWords) => {
            const filter = new SpamFilter({ blockedWords });
            
            // 生成不包含任何屏蔽词的消息
            // 使用简单的安全内容
            const safeContent = 'Hello world this is a safe message';
            
            // 确保安全内容不包含任何屏蔽词
            const containsBlockedWord = blockedWords.some(word => 
              safeContent.toLowerCase().includes(word.toLowerCase())
            );
            
            if (!containsBlockedWord) {
              const message = createTestMessage(safeContent);
              const result = filter.filter(message);
              
              // 消息应该通过
              expect(result.passed).toBe(true);
            }
            
            filter.stop();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should be case insensitive when filtering blocked words', () => {
      fc.assert(
        fc.property(
          blockedWordArbitrary,
          fc.constantFrom('lower', 'upper', 'mixed'),
          (word, caseType) => {
            const filter = new SpamFilter({ blockedWords: [word.toLowerCase()] });
            
            // 根据 caseType 转换单词大小写
            let transformedWord: string;
            switch (caseType) {
              case 'upper':
                transformedWord = word.toUpperCase();
                break;
              case 'mixed':
                transformedWord = word.split('').map((c, i) => 
                  i % 2 === 0 ? c.toUpperCase() : c.toLowerCase()
                ).join('');
                break;
              default:
                transformedWord = word.toLowerCase();
            }
            
            const message = createTestMessage(`Test ${transformedWord} message`);
            const result = filter.filter(message);
            
            // 无论大小写，消息都应该被阻止
            expect(result.passed).toBe(false);
            
            filter.stop();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should enforce rate limits per user', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 10 }),
          fc.string({ minLength: 5, maxLength: 20 }),
          (maxMessages, userId) => {
            const filter = new SpamFilter({ maxMessagesPerMinute: maxMessages });
            
            // 发送 maxMessages 条消息（应该全部通过）
            for (let i = 0; i < maxMessages; i++) {
              const message = createTestMessage(`Message ${i}`, userId);
              const result = filter.filter(message);
              expect(result.passed).toBe(true);
            }
            
            // 下一条消息应该被阻止
            const extraMessage = createTestMessage('Extra message', userId);
            const result = filter.filter(extraMessage);
            
            expect(result.passed).toBe(false);
            expect(result.reason).toBe('rate_limit');
            
            filter.stop();
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should track rate limits independently per user', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 2, max: 5 }),
          fc.array(fc.string({ minLength: 5, maxLength: 20 }), { minLength: 2, maxLength: 5 }),
          (maxMessages, userIds) => {
            // 确保用户 ID 唯一
            const uniqueUserIds = [...new Set(userIds)];
            if (uniqueUserIds.length < 2) return; // 需要至少 2 个不同的用户
            
            const filter = new SpamFilter({ maxMessagesPerMinute: maxMessages });
            
            // 第一个用户发送到达限制
            const user1 = uniqueUserIds[0];
            for (let i = 0; i < maxMessages; i++) {
              filter.filter(createTestMessage(`Message ${i}`, user1));
            }
            
            // 第一个用户应该被限制
            const user1Result = filter.filter(createTestMessage('Extra', user1));
            expect(user1Result.passed).toBe(false);
            
            // 第二个用户应该仍然可以发送
            const user2 = uniqueUserIds[1];
            const user2Result = filter.filter(createTestMessage('Hello', user2));
            expect(user2Result.passed).toBe(true);
            
            filter.stop();
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should pass all messages when filter is disabled', () => {
      fc.assert(
        fc.property(
          fc.array(blockedWordArbitrary, { minLength: 1, maxLength: 5 }),
          fc.string({ minLength: 1, maxLength: 100 }),
          (blockedWords, content) => {
            const filter = new SpamFilter({ 
              enabled: false, 
              blockedWords,
              maxMessagesPerMinute: 1, // 非常严格的限制
            });
            
            // 即使内容包含屏蔽词，也应该通过
            const message = createTestMessage(content);
            const result = filter.filter(message);
            
            expect(result.passed).toBe(true);
            
            filter.stop();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should correctly report matched blocked word', () => {
      fc.assert(
        fc.property(
          fc.array(blockedWordArbitrary, { minLength: 1, maxLength: 5 }),
          fc.nat({ max: 4 }),
          (blockedWords, wordIndex) => {
            const filter = new SpamFilter({ blockedWords });
            const selectedWord = blockedWords[wordIndex % blockedWords.length];
            
            const message = createTestMessage(`Contains ${selectedWord} here`);
            const result = filter.filter(message);
            
            if (!result.passed && result.reason === 'blocked_word') {
              // 匹配的词应该是屏蔽词列表中的一个
              expect(blockedWords.map(w => w.toLowerCase())).toContain(result.matchedWord);
            }
            
            filter.stop();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should clear user history and allow new messages', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 5 }),
          fc.string({ minLength: 5, maxLength: 20 }),
          (maxMessages, userId) => {
            const filter = new SpamFilter({ maxMessagesPerMinute: maxMessages });
            
            // 发送到达限制
            for (let i = 0; i < maxMessages; i++) {
              filter.filter(createTestMessage(`Message ${i}`, userId));
            }
            
            // 应该被限制
            expect(filter.filter(createTestMessage('Blocked', userId)).passed).toBe(false);
            
            // 清除历史
            filter.clearUserHistory(userId);
            
            // 应该可以再次发送
            expect(filter.filter(createTestMessage('Allowed', userId)).passed).toBe(true);
            
            filter.stop();
          }
        ),
        { numRuns: 50 }
      );
    });
  });
});
