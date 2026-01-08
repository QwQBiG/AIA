/**
 * Chat Interface Manager Unit Tests
 * 测试聊天接口管理器的核心功能
 */

import { ChatInterfaceManager, createChatSystemMessage } from './chat-interface.js';
import type { ChatMessage, SystemMessage } from '@digital-human/shared';
import { MessageType, ModuleType } from '@digital-human/shared';

// Mock tmi.js
jest.mock('tmi.js', () => {
  const mockClient = {
    connect: jest.fn().mockResolvedValue(undefined),
    disconnect: jest.fn().mockResolvedValue(undefined),
    say: jest.fn().mockResolvedValue(undefined),
    on: jest.fn(),
  };

  return {
    Client: jest.fn(() => mockClient),
    __mockClient: mockClient,
  };
});

// Mock fetch for YouTube
const mockFetch = jest.fn();
global.fetch = mockFetch;

/**
 * 创建测试用的 ChatMessage
 */
function createTestMessage(
  content: string,
  platform: 'twitch' | 'youtube' = 'twitch',
  senderId: string = 'user-123'
): ChatMessage {
  return {
    id: `msg-${Date.now()}`,
    platform,
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

describe('ChatInterfaceManager', () => {
  let manager: ChatInterfaceManager;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        kind: 'youtube#liveChatMessageListResponse',
        pollingIntervalMillis: 2000,
        pageInfo: { totalResults: 0, resultsPerPage: 200 },
        items: [],
      }),
    });

    manager = new ChatInterfaceManager();
  });

  afterEach(async () => {
    await manager.stop();
    jest.useRealTimers();
  });

  describe('constructor', () => {
    it('should create manager with default config', () => {
      const newManager = new ChatInterfaceManager();
      expect(newManager.getStatus('twitch')).toBe('disconnected');
      expect(newManager.getStatus('youtube')).toBe('disconnected');
    });

    it('should create manager with custom spam filter config', () => {
      const newManager = new ChatInterfaceManager({
        spamFilter: {
          enabled: true,
          maxMessagesPerMinute: 10,
          blockedWords: ['spam'],
        },
      });
      expect(newManager.getStatus('twitch')).toBe('disconnected');
    });
  });

  describe('connectTwitch', () => {
    it('should connect to Twitch', async () => {
      await manager.connectTwitch({
        platform: 'twitch',
        accessToken: 'oauth:test123',
        channelId: 'testchannel',
      });

      expect(manager.getStatus('twitch')).toBe('connected');
    });

    it('should reject invalid platform credentials', async () => {
      await expect(manager.connectTwitch({
        platform: 'youtube' as any,
        accessToken: 'test',
        channelId: 'test',
      })).rejects.toThrow('Invalid platform credentials');
    });
  });

  describe('connectYouTube', () => {
    it('should connect to YouTube', async () => {
      await manager.connectYouTube({
        apiKey: 'test-api-key',
        liveChatId: 'test-live-chat-id',
      });

      expect(manager.getStatus('youtube')).toBe('connected');
    });
  });

  describe('disconnect', () => {
    it('should disconnect from specific platform', async () => {
      await manager.connectTwitch({
        platform: 'twitch',
        accessToken: 'oauth:test123',
        channelId: 'testchannel',
      });

      await manager.disconnect('twitch');
      expect(manager.getStatus('twitch')).toBe('disconnected');
    });

    it('should handle disconnecting non-connected platform', async () => {
      await manager.disconnect('twitch');
      expect(manager.getStatus('twitch')).toBe('disconnected');
    });
  });

  describe('disconnectAll', () => {
    it('should disconnect all platforms', async () => {
      await manager.connectTwitch({
        platform: 'twitch',
        accessToken: 'oauth:test123',
        channelId: 'testchannel',
      });

      await manager.connectYouTube({
        apiKey: 'test-api-key',
        liveChatId: 'test-live-chat-id',
      });

      await manager.disconnectAll();

      expect(manager.getStatus('twitch')).toBe('disconnected');
      expect(manager.getStatus('youtube')).toBe('disconnected');
    });
  });

  describe('getAllStatuses', () => {
    it('should return all platform statuses', async () => {
      await manager.connectTwitch({
        platform: 'twitch',
        accessToken: 'oauth:test123',
        channelId: 'testchannel',
      });

      const statuses = manager.getAllStatuses();
      expect(statuses.twitch).toBe('connected');
    });
  });

  describe('spam filter', () => {
    it('should update spam filter config', () => {
      manager.setSpamFilter({
        enabled: true,
        maxMessagesPerMinute: 5,
        blockedWords: ['test'],
      });
      // 配置应该被接受
    });
  });

  describe('message callbacks', () => {
    it('should register message callback', () => {
      const callback = jest.fn();
      manager.onMessage(callback);
      // 回调应该被注册
    });

    it('should register filtered callback', () => {
      const callback = jest.fn();
      manager.onFiltered(callback);
      // 回调应该被注册
    });
  });

  describe('message forwarding', () => {
    it('should set message forwarder', () => {
      const forwarder = jest.fn();
      manager.setMessageForwarder(forwarder);
      // 转发器应该被设置
    });
  });
});

describe('createChatSystemMessage', () => {
  it('should create valid SystemMessage from ChatMessage', () => {
    const chatMessage = createTestMessage('Hello world');
    const systemMessage = createChatSystemMessage(chatMessage);

    expect(systemMessage.type).toBe(MessageType.CHAT_MESSAGE);
    expect(systemMessage.source).toBe(ModuleType.CHAT);
    expect(systemMessage.id).toBeDefined();
    expect(systemMessage.timestamp).toBeInstanceOf(Date);
  });

  it('should include complete sender metadata in payload', () => {
    const chatMessage = createTestMessage('Hello world');
    const systemMessage = createChatSystemMessage(chatMessage);

    const payload = systemMessage.payload as any;
    expect(payload.chatMessage).toBeDefined();
    expect(payload.chatMessage.sender.id).toBe(chatMessage.sender.id);
    expect(payload.chatMessage.sender.username).toBe(chatMessage.sender.username);
    expect(payload.chatMessage.sender.displayName).toBe(chatMessage.sender.displayName);
    expect(payload.chatMessage.sender.isModerator).toBe(chatMessage.sender.isModerator);
    expect(payload.chatMessage.sender.isSubscriber).toBe(chatMessage.sender.isSubscriber);
  });

  it('should include message content and platform', () => {
    const chatMessage = createTestMessage('Test content', 'youtube');
    const systemMessage = createChatSystemMessage(chatMessage);

    const payload = systemMessage.payload as any;
    expect(payload.chatMessage.content).toBe('Test content');
    expect(payload.chatMessage.platform).toBe('youtube');
  });

  it('should convert timestamp to ISO string', () => {
    const chatMessage = createTestMessage('Hello');
    const systemMessage = createChatSystemMessage(chatMessage);

    const payload = systemMessage.payload as any;
    expect(typeof payload.chatMessage.timestamp).toBe('string');
    expect(payload.chatMessage.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it('should preserve message ID', () => {
    const chatMessage = createTestMessage('Hello');
    const systemMessage = createChatSystemMessage(chatMessage);

    const payload = systemMessage.payload as any;
    expect(payload.chatMessage.id).toBe(chatMessage.id);
  });
});
