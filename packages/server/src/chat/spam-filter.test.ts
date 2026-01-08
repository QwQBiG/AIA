/**
 * Spam Filter Unit Tests
 * 测试垃圾过滤器的核心功能
 */

import { SpamFilter, createSpamFilterWithPresets, DEFAULT_SPAM_FILTER_CONFIG } from './spam-filter.js';
import type { ChatMessage } from '@digital-human/shared';

/**
 * 创建测试用的 ChatMessage
 */
function createTestMessage(
  content: string,
  senderId: string = 'user-123'
): ChatMessage {
  return {
    id: `msg-${Date.now()}`,
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

describe('SpamFilter', () => {
  let filter: SpamFilter;

  beforeEach(() => {
    filter = new SpamFilter();
  });

  afterEach(() => {
    filter.stop();
  });

  describe('constructor', () => {
    it('should create filter with default config', () => {
      const config = filter.getConfig();
      expect(config.enabled).toBe(true);
      expect(config.maxMessagesPerMinute).toBe(20);
      expect(config.blockedWords).toEqual([]);
    });

    it('should create filter with custom config', () => {
      const customFilter = new SpamFilter({
        enabled: false,
        maxMessagesPerMinute: 10,
        blockedWords: ['spam'],
      });
      
      const config = customFilter.getConfig();
      expect(config.enabled).toBe(false);
      expect(config.maxMessagesPerMinute).toBe(10);
      expect(config.blockedWords).toEqual(['spam']);
      
      customFilter.stop();
    });
  });

  describe('filter - disabled', () => {
    it('should pass all messages when disabled', () => {
      filter.setConfig({ enabled: false });
      
      const message = createTestMessage('This contains spam word');
      filter.addBlockedWord('spam');
      
      const result = filter.filter(message);
      expect(result.passed).toBe(true);
    });
  });

  describe('filter - blocked words', () => {
    beforeEach(() => {
      filter.addBlockedWord('spam');
      filter.addBlockedWord('bad');
      filter.addBlockedWord('inappropriate');
    });

    it('should block messages containing blocked words', () => {
      const message = createTestMessage('This is spam content');
      const result = filter.filter(message);
      
      expect(result.passed).toBe(false);
      expect(result.reason).toBe('blocked_word');
      expect(result.matchedWord).toBe('spam');
    });

    it('should be case insensitive', () => {
      const message = createTestMessage('This is SPAM content');
      const result = filter.filter(message);
      
      expect(result.passed).toBe(false);
      expect(result.matchedWord).toBe('spam');
    });

    it('should pass messages without blocked words', () => {
      const message = createTestMessage('This is a normal message');
      const result = filter.filter(message);
      
      expect(result.passed).toBe(true);
    });

    it('should detect blocked words anywhere in message', () => {
      const message = createTestMessage('Hello bad world');
      const result = filter.filter(message);
      
      expect(result.passed).toBe(false);
      expect(result.matchedWord).toBe('bad');
    });

    it('should detect blocked words as substrings', () => {
      const message = createTestMessage('This is spammy');
      const result = filter.filter(message);
      
      expect(result.passed).toBe(false);
      expect(result.matchedWord).toBe('spam');
    });
  });

  describe('filter - rate limiting', () => {
    beforeEach(() => {
      filter.setConfig({ maxMessagesPerMinute: 3 });
    });

    it('should allow messages within rate limit', () => {
      const userId = 'rate-test-user';
      
      for (let i = 0; i < 3; i++) {
        const message = createTestMessage(`Message ${i}`, userId);
        const result = filter.filter(message);
        expect(result.passed).toBe(true);
      }
    });

    it('should block messages exceeding rate limit', () => {
      const userId = 'rate-test-user-2';
      
      // 发送 3 条消息（达到限制）
      for (let i = 0; i < 3; i++) {
        const message = createTestMessage(`Message ${i}`, userId);
        filter.filter(message);
      }
      
      // 第 4 条消息应该被阻止
      const message = createTestMessage('Message 4', userId);
      const result = filter.filter(message);
      
      expect(result.passed).toBe(false);
      expect(result.reason).toBe('rate_limit');
    });

    it('should track rate limits per user', () => {
      const user1 = 'user-1';
      const user2 = 'user-2';
      
      // 用户 1 发送 3 条消息
      for (let i = 0; i < 3; i++) {
        filter.filter(createTestMessage(`Message ${i}`, user1));
      }
      
      // 用户 2 应该仍然可以发送
      const result = filter.filter(createTestMessage('Hello', user2));
      expect(result.passed).toBe(true);
    });
  });

  describe('blocked word management', () => {
    it('should add blocked words', () => {
      filter.addBlockedWord('test');
      const config = filter.getConfig();
      expect(config.blockedWords).toContain('test');
    });

    it('should normalize blocked words to lowercase', () => {
      filter.addBlockedWord('TEST');
      const config = filter.getConfig();
      expect(config.blockedWords).toContain('test');
    });

    it('should not add duplicate blocked words', () => {
      filter.addBlockedWord('test');
      filter.addBlockedWord('test');
      filter.addBlockedWord('TEST');
      
      const config = filter.getConfig();
      expect(config.blockedWords.filter(w => w === 'test').length).toBe(1);
    });

    it('should remove blocked words', () => {
      filter.addBlockedWord('test');
      filter.removeBlockedWord('test');
      
      const config = filter.getConfig();
      expect(config.blockedWords).not.toContain('test');
    });

    it('should handle removing non-existent words', () => {
      filter.removeBlockedWord('nonexistent');
      // 不应该抛出错误
    });
  });

  describe('user history management', () => {
    it('should clear user history', () => {
      const userId = 'clear-test-user';
      filter.setConfig({ maxMessagesPerMinute: 2 });
      
      // 发送 2 条消息
      filter.filter(createTestMessage('Message 1', userId));
      filter.filter(createTestMessage('Message 2', userId));
      
      // 清除历史
      filter.clearUserHistory(userId);
      
      // 应该可以再次发送
      const result = filter.filter(createTestMessage('Message 3', userId));
      expect(result.passed).toBe(true);
    });

    it('should clear all history', () => {
      filter.setConfig({ maxMessagesPerMinute: 2 });
      
      // 多个用户发送消息
      filter.filter(createTestMessage('Message', 'user-a'));
      filter.filter(createTestMessage('Message', 'user-a'));
      filter.filter(createTestMessage('Message', 'user-b'));
      filter.filter(createTestMessage('Message', 'user-b'));
      
      // 清除所有历史
      filter.clearAllHistory();
      
      // 所有用户应该可以再次发送
      expect(filter.filter(createTestMessage('Message', 'user-a')).passed).toBe(true);
      expect(filter.filter(createTestMessage('Message', 'user-b')).passed).toBe(true);
    });

    it('should get user message rate', () => {
      const userId = 'rate-check-user';
      
      filter.filter(createTestMessage('Message 1', userId));
      filter.filter(createTestMessage('Message 2', userId));
      
      expect(filter.getUserMessageRate(userId)).toBe(2);
    });

    it('should return 0 for unknown user', () => {
      expect(filter.getUserMessageRate('unknown-user')).toBe(0);
    });
  });

  describe('config management', () => {
    it('should update config', () => {
      filter.setConfig({
        maxMessagesPerMinute: 50,
        enabled: false,
      });
      
      const config = filter.getConfig();
      expect(config.maxMessagesPerMinute).toBe(50);
      expect(config.enabled).toBe(false);
    });

    it('should preserve unmodified config values', () => {
      filter.addBlockedWord('test');
      filter.setConfig({ maxMessagesPerMinute: 100 });
      
      const config = filter.getConfig();
      expect(config.blockedWords).toContain('test');
    });
  });
});

describe('createSpamFilterWithPresets', () => {
  let filter: SpamFilter;

  afterEach(() => {
    if (filter) {
      filter.stop();
    }
  });

  it('should create filter with preset blocked words', () => {
    filter = createSpamFilterWithPresets(
      { maxMessagesPerMinute: 10 },
      ['spam', 'bad', 'inappropriate']
    );
    
    const config = filter.getConfig();
    expect(config.maxMessagesPerMinute).toBe(10);
    expect(config.blockedWords).toContain('spam');
    expect(config.blockedWords).toContain('bad');
    expect(config.blockedWords).toContain('inappropriate');
  });

  it('should create filter without presets', () => {
    filter = createSpamFilterWithPresets({}, undefined);
    
    const config = filter.getConfig();
    expect(config.blockedWords).toEqual([]);
  });
});
