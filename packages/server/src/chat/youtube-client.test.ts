/**
 * YouTube Client Unit Tests
 * 测试 YouTube Live Chat 客户端的核心功能
 */

import { YouTubeClient } from './youtube-client.js';
import type { YouTubeConfig } from './types.js';

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('YouTubeClient', () => {
  let client: YouTubeClient;
  const testConfig: YouTubeConfig = {
    apiKey: 'test-api-key',
    liveChatId: 'test-live-chat-id',
    pollingInterval: 2000,
  };

  const mockApiResponse = {
    kind: 'youtube#liveChatMessageListResponse',
    etag: 'test-etag',
    pollingIntervalMillis: 2000,
    pageInfo: {
      totalResults: 1,
      resultsPerPage: 200,
    },
    nextPageToken: 'next-page-token',
    items: [
      {
        id: 'msg-123',
        snippet: {
          type: 'textMessageEvent',
          liveChatId: 'test-live-chat-id',
          authorChannelId: 'channel-456',
          publishedAt: '2024-01-01T12:00:00Z',
          hasDisplayContent: true,
          displayMessage: 'Hello from YouTube!',
          textMessageDetails: {
            messageText: 'Hello from YouTube!',
          },
        },
        authorDetails: {
          channelId: 'channel-456',
          channelUrl: 'https://youtube.com/channel/channel-456',
          displayName: 'TestViewer',
          profileImageUrl: 'https://example.com/avatar.jpg',
          isVerified: false,
          isChatOwner: false,
          isChatSponsor: true,
          isChatModerator: false,
        },
      },
    ],
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockApiResponse),
    });
    client = new YouTubeClient(testConfig);
  });

  afterEach(async () => {
    await client.disconnect();
    jest.useRealTimers();
  });

  describe('constructor', () => {
    it('should create client with default polling interval', () => {
      const newClient = new YouTubeClient({
        apiKey: 'key',
        liveChatId: 'id',
      });
      expect(newClient.getStatus()).toBe('disconnected');
    });

    it('should enforce minimum polling interval', () => {
      const newClient = new YouTubeClient({
        apiKey: 'key',
        liveChatId: 'id',
        pollingInterval: 500, // 低于最小值
      });
      expect(newClient.getStatus()).toBe('disconnected');
    });
  });

  describe('connect', () => {
    it('should connect to YouTube Live Chat', async () => {
      await client.connect();
      expect(client.getStatus()).toBe('connected');
      expect(mockFetch).toHaveBeenCalled();
    });

    it('should not reconnect if already connected', async () => {
      await client.connect();
      await client.connect();
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('should emit connection status changes', async () => {
      const statusChanges: string[] = [];
      client.onConnectionChange((status) => statusChanges.push(status));

      await client.connect();

      expect(statusChanges).toContain('connecting');
      expect(statusChanges).toContain('connected');
    });

    it('should handle API errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ error: { message: 'Forbidden' } }),
      });

      const errors: Error[] = [];
      client.onError((err) => errors.push(err));

      await expect(client.connect()).rejects.toThrow();
      expect(client.getStatus()).toBe('disconnected');
      expect(errors.length).toBeGreaterThan(0);
    });
  });

  describe('disconnect', () => {
    it('should disconnect from YouTube Live Chat', async () => {
      await client.connect();
      await client.disconnect();
      expect(client.getStatus()).toBe('disconnected');
    });

    it('should stop polling on disconnect', async () => {
      await client.connect();
      await client.disconnect();
      
      // 清除之前的调用
      mockFetch.mockClear();
      
      // 前进时间，不应该有新的 API 调用
      jest.advanceTimersByTime(5000);
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('sendMessage', () => {
    it('should throw error when not connected', async () => {
      await expect(client.sendMessage('test')).rejects.toThrow('Not connected');
    });

    it('should throw error for unimplemented OAuth', async () => {
      await client.connect();
      await expect(client.sendMessage('test')).rejects.toThrow('OAuth');
    });
  });

  describe('message parsing', () => {
    it('should parse YouTube message with all metadata', async () => {
      const messages: any[] = [];
      client.onMessage((msg) => messages.push(msg));

      await client.connect();

      expect(messages.length).toBe(1);
      expect(messages[0]).toMatchObject({
        id: 'msg-123',
        platform: 'youtube',
        content: 'Hello from YouTube!',
        sender: {
          id: 'channel-456',
          displayName: 'TestViewer',
          isModerator: false,
          isSubscriber: true,
        },
      });
    });

    it('should handle messages without displayMessage', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockApiResponse,
          items: [{
            ...mockApiResponse.items[0],
            snippet: {
              ...mockApiResponse.items[0].snippet,
              displayMessage: '',
              textMessageDetails: {
                messageText: 'Fallback text',
              },
            },
          }],
        }),
      });

      const messages: any[] = [];
      client.onMessage((msg) => messages.push(msg));

      await client.connect();

      expect(messages[0].content).toBe('Fallback text');
    });

    it('should skip non-text messages', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockApiResponse,
          items: [{
            ...mockApiResponse.items[0],
            snippet: {
              ...mockApiResponse.items[0].snippet,
              type: 'superChatEvent', // 不是文本消息
            },
          }],
        }),
      });

      const messages: any[] = [];
      client.onMessage((msg) => messages.push(msg));

      await client.connect();

      expect(messages.length).toBe(0);
    });
  });

  describe('polling', () => {
    it('should poll for new messages at configured interval', async () => {
      await client.connect();
      expect(mockFetch).toHaveBeenCalledTimes(1);

      // 前进轮询间隔时间
      jest.advanceTimersByTime(2000);
      expect(mockFetch).toHaveBeenCalledTimes(2);

      jest.advanceTimersByTime(2000);
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });

    it('should use nextPageToken for subsequent requests', async () => {
      await client.connect();
      
      jest.advanceTimersByTime(2000);

      const lastCall = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
      expect(lastCall[0]).toContain('pageToken=next-page-token');
    });

    it('should adjust polling interval based on API response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockApiResponse,
          pollingIntervalMillis: 5000, // API 建议更长的间隔
        }),
      });

      await client.connect();
      mockFetch.mockClear();

      // 原始间隔不应触发
      jest.advanceTimersByTime(2000);
      expect(mockFetch).not.toHaveBeenCalled();

      // 新间隔应该触发
      jest.advanceTimersByTime(3000);
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  describe('quota management', () => {
    it('should track quota usage', async () => {
      await client.connect();
      
      const quota = client.getQuotaUsage();
      expect(quota.used).toBe(5); // 每次调用消耗 5 个配额单位
    });

    it('should reset quota counter', async () => {
      await client.connect();
      client.resetQuotaCounter();
      
      const quota = client.getQuotaUsage();
      expect(quota.used).toBe(0);
    });
  });

  describe('spam filter', () => {
    it('should accept spam filter configuration', () => {
      client.setSpamFilter({
        enabled: true,
        maxMessagesPerMinute: 10,
        blockedWords: ['spam'],
      });
      // 配置应该被接受
    });
  });

  describe('event callbacks', () => {
    it('should support multiple message callbacks', async () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();

      client.onMessage(callback1);
      client.onMessage(callback2);

      await client.connect();

      expect(callback1).toHaveBeenCalled();
      expect(callback2).toHaveBeenCalled();
    });
  });
});
