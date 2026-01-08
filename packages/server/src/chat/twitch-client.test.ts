/**
 * Twitch Client Unit Tests
 * 测试 Twitch IRC 客户端的核心功能
 */

import { TwitchClient, createTwitchConfigFromCredentials } from './twitch-client.js';
import type { TwitchConfig } from './types.js';

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

describe('TwitchClient', () => {
  let client: TwitchClient;
  const testConfig: TwitchConfig = {
    username: 'testbot',
    oauthToken: 'oauth:test123',
    channel: 'testchannel',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    client = new TwitchClient(testConfig);
  });

  afterEach(async () => {
    await client.disconnect();
  });

  describe('constructor', () => {
    it('should create client with default reconnect config', () => {
      const newClient = new TwitchClient(testConfig);
      expect(newClient.getStatus()).toBe('disconnected');
    });

    it('should create client with custom reconnect config', () => {
      const newClient = new TwitchClient(testConfig, {
        maxAttempts: 5,
        initialDelay: 500,
      });
      expect(newClient.getStatus()).toBe('disconnected');
    });
  });

  describe('connect', () => {
    it('should connect to Twitch IRC', async () => {
      await client.connect();
      expect(client.getStatus()).toBe('connected');
    });

    it('should not reconnect if already connected', async () => {
      await client.connect();
      await client.connect(); // 第二次调用应该直接返回
      expect(client.getStatus()).toBe('connected');
    });

    it('should emit connection status changes', async () => {
      const statusChanges: string[] = [];
      client.onConnectionChange((status) => statusChanges.push(status));

      await client.connect();

      expect(statusChanges).toContain('connecting');
      expect(statusChanges).toContain('connected');
    });
  });

  describe('disconnect', () => {
    it('should disconnect from Twitch IRC', async () => {
      await client.connect();
      await client.disconnect();
      expect(client.getStatus()).toBe('disconnected');
    });

    it('should handle disconnect when not connected', async () => {
      await client.disconnect();
      expect(client.getStatus()).toBe('disconnected');
    });
  });

  describe('sendMessage', () => {
    it('should throw error when not connected', async () => {
      await expect(client.sendMessage('test')).rejects.toThrow('Not connected to Twitch');
    });

    it('should throw error in read-only mode', async () => {
      const readOnlyClient = new TwitchClient({ ...testConfig, readOnly: true });
      await readOnlyClient.connect();
      await expect(readOnlyClient.sendMessage('test')).rejects.toThrow('read-only mode');
    });
  });

  describe('message parsing', () => {
    it('should parse Twitch message with all metadata', async () => {
      const messages: any[] = [];
      client.onMessage((msg) => messages.push(msg));

      await client.connect();

      // 获取 mock client 并触发消息事件
      const tmi = require('tmi.js');
      const mockClient = tmi.__mockClient;
      
      // 找到 message 事件处理器并调用
      const messageHandler = mockClient.on.mock.calls.find(
        (call: any[]) => call[0] === 'message'
      )?.[1];

      if (messageHandler) {
        messageHandler(
          '#testchannel',
          {
            'id': 'msg-123',
            'user-id': 'user-456',
            'username': 'testuser',
            'display-name': 'TestUser',
            'mod': false,
            'subscriber': true,
            'tmi-sent-ts': '1704067200000',
            'badges': {},
          },
          'Hello World!',
          false
        );
      }

      expect(messages.length).toBe(1);
      expect(messages[0]).toMatchObject({
        id: 'msg-123',
        platform: 'twitch',
        content: 'Hello World!',
        sender: {
          id: 'user-456',
          username: 'testuser',
          displayName: 'TestUser',
          isModerator: false,
          isSubscriber: true,
        },
      });
    });

    it('should ignore self messages', async () => {
      const messages: any[] = [];
      client.onMessage((msg) => messages.push(msg));

      await client.connect();

      const tmi = require('tmi.js');
      const mockClient = tmi.__mockClient;
      
      const messageHandler = mockClient.on.mock.calls.find(
        (call: any[]) => call[0] === 'message'
      )?.[1];

      if (messageHandler) {
        messageHandler('#testchannel', {}, 'Self message', true);
      }

      expect(messages.length).toBe(0);
    });
  });

  describe('spam filter', () => {
    it('should accept spam filter configuration', () => {
      client.setSpamFilter({
        enabled: true,
        maxMessagesPerMinute: 10,
        blockedWords: ['spam', 'bad'],
      });
      // 配置应该被接受，不抛出错误
    });
  });

  describe('event callbacks', () => {
    it('should support multiple message callbacks', async () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();

      client.onMessage(callback1);
      client.onMessage(callback2);

      await client.connect();

      const tmi = require('tmi.js');
      const mockClient = tmi.__mockClient;
      
      const messageHandler = mockClient.on.mock.calls.find(
        (call: any[]) => call[0] === 'message'
      )?.[1];

      if (messageHandler) {
        messageHandler('#testchannel', { 'user-id': '1', username: 'test' }, 'test', false);
      }

      expect(callback1).toHaveBeenCalled();
      expect(callback2).toHaveBeenCalled();
    });

    it('should support error callbacks', () => {
      const errorCallback = jest.fn();
      client.onError(errorCallback);
      // 错误回调应该被注册
    });
  });
});

describe('createTwitchConfigFromCredentials', () => {
  it('should create config with oauth prefix', () => {
    const config = createTwitchConfigFromCredentials(
      { accessToken: 'token123', channelId: 'mychannel' },
      'mybot'
    );

    expect(config).toEqual({
      username: 'mybot',
      oauthToken: 'oauth:token123',
      channel: 'mychannel',
    });
  });

  it('should not duplicate oauth prefix', () => {
    const config = createTwitchConfigFromCredentials(
      { accessToken: 'oauth:token123', channelId: 'mychannel' },
      'mybot'
    );

    expect(config.oauthToken).toBe('oauth:token123');
  });
});
