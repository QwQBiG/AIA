/**
 * Chat Message Property Tests
 * 聊天消息解析完整性属性测试
 * 
 * **Feature: ai-vtuber-digital-human, Property 11: 聊天消息解析完整性**
 * **Validates: Requirements 4.1, 4.3**
 */

import * as fc from 'fast-check';
import type { ChatMessage, ChatSender } from '@digital-human/shared';

/**
 * 生成有效的 ChatSender
 */
const chatSenderArbitrary = fc.record({
  id: fc.string({ minLength: 1, maxLength: 50 }),
  username: fc.string({ minLength: 1, maxLength: 50 }),
  displayName: fc.string({ minLength: 1, maxLength: 100 }),
  isModerator: fc.boolean(),
  isSubscriber: fc.boolean(),
});

/**
 * 生成有效的 ChatMessage
 */
const chatMessageArbitrary = fc.record({
  id: fc.string({ minLength: 1, maxLength: 100 }),
  platform: fc.constantFrom('twitch' as const, 'youtube' as const),
  sender: chatSenderArbitrary,
  content: fc.string({ minLength: 0, maxLength: 500 }),
  timestamp: fc.date(),
});

/**
 * 模拟 Twitch IRC 消息标签
 */
interface TwitchTags {
  'id': string;
  'user-id': string;
  'username': string;
  'display-name': string;
  'mod': boolean;
  'subscriber': boolean;
  'tmi-sent-ts': string;
  'badges': Record<string, string>;
}

/**
 * 生成 Twitch IRC 标签
 */
const twitchTagsArbitrary = fc.record({
  'id': fc.string({ minLength: 1, maxLength: 100 }),
  'user-id': fc.string({ minLength: 1, maxLength: 50 }),
  'username': fc.string({ minLength: 1, maxLength: 50 }),
  'display-name': fc.string({ minLength: 1, maxLength: 100 }),
  'mod': fc.boolean(),
  'subscriber': fc.boolean(),
  'tmi-sent-ts': fc.nat().map(n => String(Date.now() - n)),
  'badges': fc.constant({}),
});

/**
 * 解析 Twitch 消息（从 TwitchClient 提取的逻辑）
 */
function parseTwitchMessage(tags: TwitchTags, message: string): ChatMessage {
  const badges = tags.badges || {};
  return {
    id: tags['id'] || `twitch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    platform: 'twitch',
    sender: {
      id: tags['user-id'] || '',
      username: tags.username || '',
      displayName: tags['display-name'] || tags.username || '',
      isModerator: tags.mod === true || badges.broadcaster === '1',
      isSubscriber: tags.subscriber === true,
    },
    content: message,
    timestamp: new Date(parseInt(tags['tmi-sent-ts'] || String(Date.now()))),
  };
}

/**
 * 模拟 YouTube API 消息
 */
interface YouTubeMessage {
  id: string;
  snippet: {
    type: string;
    publishedAt: string;
    hasDisplayContent: boolean;
    displayMessage: string;
  };
  authorDetails: {
    channelId: string;
    displayName: string;
    isChatOwner: boolean;
    isChatSponsor: boolean;
    isChatModerator: boolean;
  };
}

/**
 * 生成 YouTube API 消息
 */
const youtubeMessageArbitrary = fc.record({
  id: fc.string({ minLength: 1, maxLength: 100 }),
  snippet: fc.record({
    type: fc.constant('textMessageEvent'),
    publishedAt: fc.date().map(d => d.toISOString()),
    hasDisplayContent: fc.constant(true),
    displayMessage: fc.string({ minLength: 0, maxLength: 500 }),
  }),
  authorDetails: fc.record({
    channelId: fc.string({ minLength: 1, maxLength: 50 }),
    displayName: fc.string({ minLength: 1, maxLength: 100 }),
    isChatOwner: fc.boolean(),
    isChatSponsor: fc.boolean(),
    isChatModerator: fc.boolean(),
  }),
});

/**
 * 解析 YouTube 消息（从 YouTubeClient 提取的逻辑）
 */
function parseYouTubeMessage(item: YouTubeMessage): ChatMessage {
  return {
    id: item.id,
    platform: 'youtube',
    sender: {
      id: item.authorDetails.channelId,
      username: item.authorDetails.channelId,
      displayName: item.authorDetails.displayName,
      isModerator: item.authorDetails.isChatModerator || item.authorDetails.isChatOwner,
      isSubscriber: item.authorDetails.isChatSponsor,
    },
    content: item.snippet.displayMessage,
    timestamp: new Date(item.snippet.publishedAt),
  };
}

/**
 * 验证 ChatMessage 包含所有必需的 sender metadata
 */
function hasRequiredSenderMetadata(message: ChatMessage): boolean {
  const { sender } = message;
  return (
    typeof sender.id === 'string' &&
    typeof sender.username === 'string' &&
    typeof sender.displayName === 'string' &&
    typeof sender.isModerator === 'boolean' &&
    typeof sender.isSubscriber === 'boolean'
  );
}

/**
 * 验证 ChatMessage 结构完整性
 */
function isValidChatMessage(message: ChatMessage): boolean {
  return (
    typeof message.id === 'string' &&
    (message.platform === 'twitch' || message.platform === 'youtube') &&
    typeof message.content === 'string' &&
    message.timestamp instanceof Date &&
    hasRequiredSenderMetadata(message)
  );
}

describe('Chat Message Parsing Property Tests', () => {
  /**
   * Property 11: 聊天消息解析完整性
   * *For any* 接收到的聊天消息，解析后应该包含 sender metadata（id、username、displayName）
   */
  describe('Property 11: Chat Message Parsing Completeness', () => {
    it('should parse Twitch messages with complete sender metadata', () => {
      fc.assert(
        fc.property(
          twitchTagsArbitrary,
          fc.string({ minLength: 0, maxLength: 500 }),
          (tags, content) => {
            const message = parseTwitchMessage(tags, content);
            
            // 验证消息结构完整
            expect(isValidChatMessage(message)).toBe(true);
            
            // 验证 sender metadata 完整
            expect(hasRequiredSenderMetadata(message)).toBe(true);
            
            // 验证平台正确
            expect(message.platform).toBe('twitch');
            
            // 验证内容正确传递
            expect(message.content).toBe(content);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should parse YouTube messages with complete sender metadata', () => {
      fc.assert(
        fc.property(youtubeMessageArbitrary, (ytMessage) => {
          const message = parseYouTubeMessage(ytMessage);
          
          // 验证消息结构完整
          expect(isValidChatMessage(message)).toBe(true);
          
          // 验证 sender metadata 完整
          expect(hasRequiredSenderMetadata(message)).toBe(true);
          
          // 验证平台正确
          expect(message.platform).toBe('youtube');
          
          // 验证内容正确传递
          expect(message.content).toBe(ytMessage.snippet.displayMessage);
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve sender ID across parsing', () => {
      fc.assert(
        fc.property(twitchTagsArbitrary, fc.string(), (tags, content) => {
          const message = parseTwitchMessage(tags, content);
          
          // Twitch 用户 ID 应该被保留
          expect(message.sender.id).toBe(tags['user-id']);
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve display name across parsing', () => {
      fc.assert(
        fc.property(youtubeMessageArbitrary, (ytMessage) => {
          const message = parseYouTubeMessage(ytMessage);
          
          // YouTube 显示名称应该被保留
          expect(message.sender.displayName).toBe(ytMessage.authorDetails.displayName);
        }),
        { numRuns: 100 }
      );
    });

    it('should correctly identify moderators', () => {
      fc.assert(
        fc.property(
          twitchTagsArbitrary,
          fc.string(),
          (tags, content) => {
            const message = parseTwitchMessage(tags, content);
            
            // 如果 mod 标志为 true，则应该是管理员
            if (tags.mod === true) {
              expect(message.sender.isModerator).toBe(true);
            }
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should correctly identify subscribers', () => {
      fc.assert(
        fc.property(
          twitchTagsArbitrary,
          fc.string(),
          (tags, content) => {
            const message = parseTwitchMessage(tags, content);
            
            // subscriber 标志应该正确传递
            expect(message.sender.isSubscriber).toBe(tags.subscriber);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle YouTube moderator/owner status correctly', () => {
      fc.assert(
        fc.property(youtubeMessageArbitrary, (ytMessage) => {
          const message = parseYouTubeMessage(ytMessage);
          
          // 如果是管理员或频道主，应该标记为管理员
          const expectedModerator = 
            ytMessage.authorDetails.isChatModerator || 
            ytMessage.authorDetails.isChatOwner;
          
          expect(message.sender.isModerator).toBe(expectedModerator);
        }),
        { numRuns: 100 }
      );
    });

    it('should generate valid timestamps', () => {
      fc.assert(
        fc.property(
          twitchTagsArbitrary,
          fc.string(),
          (tags, content) => {
            const message = parseTwitchMessage(tags, content);
            
            // 时间戳应该是有效的 Date 对象
            expect(message.timestamp).toBeInstanceOf(Date);
            expect(isNaN(message.timestamp.getTime())).toBe(false);
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
