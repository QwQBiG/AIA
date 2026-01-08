/**
 * Chat Interface
 * 统一的聊天接口，整合 Twitch 和 YouTube 客户端，并转发消息到 Orchestrator
 * 
 * Requirements: 4.3
 */

import { v4 as uuidv4 } from 'uuid';
import type { ChatMessage, SpamFilterConfig, PlatformCredentials } from '@digital-human/shared';
import { MessageType, ModuleType } from '@digital-human/shared';
import type { SystemMessage } from '@digital-human/shared';
import { TwitchClient, createTwitchConfigFromCredentials } from './twitch-client.js';
import { YouTubeClient } from './youtube-client.js';
import { SpamFilter } from './spam-filter.js';
import type { IChatInterface, ConnectionStatus, TwitchConfig, YouTubeConfig } from './types.js';

/**
 * 消息转发回调类型
 */
export type MessageForwarder = (message: SystemMessage) => Promise<void>;

/**
 * 聊天接口配置
 */
export interface ChatInterfaceManagerConfig {
  /** 垃圾过滤配置 */
  spamFilter?: SpamFilterConfig;
  /** Twitch 用户名（用于 Twitch 连接） */
  twitchUsername?: string;
}

/**
 * 聊天接口管理器
 * 管理多个平台的聊天连接，并统一转发消息到 Orchestrator
 */
export class ChatInterfaceManager {
  private clients: Map<string, IChatInterface> = new Map();
  private spamFilter: SpamFilter;
  private messageForwarder: MessageForwarder | null = null;
  private config: ChatInterfaceManagerConfig;

  // 事件回调
  private messageCallbacks: Array<(message: ChatMessage) => void> = [];
  private filteredCallbacks: Array<(message: ChatMessage, reason: string) => void> = [];

  constructor(config?: ChatInterfaceManagerConfig) {
    this.config = config || {};
    this.spamFilter = new SpamFilter(config?.spamFilter);
  }

  /**
   * 设置消息转发器（用于转发到 Orchestrator）
   */
  setMessageForwarder(forwarder: MessageForwarder): void {
    this.messageForwarder = forwarder;
  }

  /**
   * 连接到 Twitch
   */
  async connectTwitch(credentials: PlatformCredentials): Promise<void> {
    if (credentials.platform !== 'twitch') {
      throw new Error('Invalid platform credentials for Twitch');
    }

    const twitchConfig = createTwitchConfigFromCredentials(
      credentials,
      this.config.twitchUsername || 'bot'
    );

    const client = new TwitchClient(twitchConfig);
    this.setupClientHandlers(client, 'twitch');
    
    await client.connect();
    this.clients.set('twitch', client);
  }

  /**
   * 连接到 YouTube
   */
  async connectYouTube(config: YouTubeConfig): Promise<void> {
    const client = new YouTubeClient(config);
    this.setupClientHandlers(client, 'youtube');
    
    await client.connect();
    this.clients.set('youtube', client);
  }

  /**
   * 断开指定平台的连接
   */
  async disconnect(platform: 'twitch' | 'youtube'): Promise<void> {
    const client = this.clients.get(platform);
    if (client) {
      await client.disconnect();
      this.clients.delete(platform);
    }
  }

  /**
   * 断开所有连接
   */
  async disconnectAll(): Promise<void> {
    const disconnectPromises = Array.from(this.clients.values()).map(client => 
      client.disconnect()
    );
    await Promise.all(disconnectPromises);
    this.clients.clear();
  }

  /**
   * 获取平台连接状态
   */
  getStatus(platform: 'twitch' | 'youtube'): ConnectionStatus {
    const client = this.clients.get(platform);
    return client?.getStatus() || 'disconnected';
  }

  /**
   * 获取所有平台的连接状态
   */
  getAllStatuses(): Record<string, ConnectionStatus> {
    const statuses: Record<string, ConnectionStatus> = {};
    for (const [platform, client] of this.clients) {
      statuses[platform] = client.getStatus();
    }
    return statuses;
  }

  /**
   * 更新垃圾过滤配置
   */
  setSpamFilter(config: SpamFilterConfig): void {
    this.spamFilter.setConfig(config);
    
    // 同时更新所有客户端的配置
    for (const client of this.clients.values()) {
      client.setSpamFilter(config);
    }
  }

  /**
   * 注册消息回调（过滤后的消息）
   */
  onMessage(callback: (message: ChatMessage) => void): void {
    this.messageCallbacks.push(callback);
  }

  /**
   * 注册被过滤消息的回调
   */
  onFiltered(callback: (message: ChatMessage, reason: string) => void): void {
    this.filteredCallbacks.push(callback);
  }

  /**
   * 停止管理器（清理资源）
   */
  async stop(): Promise<void> {
    await this.disconnectAll();
    this.spamFilter.stop();
  }

  /**
   * 设置客户端事件处理器
   */
  private setupClientHandlers(client: IChatInterface, platform: string): void {
    client.onMessage((message) => {
      this.handleIncomingMessage(message);
    });

    client.onError((error) => {
      console.error(`[ChatInterface] ${platform} error:`, error.message);
    });

    client.onConnectionChange((status) => {
      console.log(`[ChatInterface] ${platform} connection status: ${status}`);
    });
  }

  /**
   * 处理接收到的消息
   */
  private async handleIncomingMessage(message: ChatMessage): Promise<void> {
    // 应用垃圾过滤
    const filterResult = this.spamFilter.filter(message);
    
    if (!filterResult.passed) {
      // 通知被过滤的消息
      const reason = filterResult.reason === 'blocked_word' 
        ? `blocked_word:${filterResult.matchedWord}`
        : filterResult.reason || 'unknown';
      
      this.filteredCallbacks.forEach(cb => cb(message, reason));
      return;
    }

    // 通知本地回调
    this.messageCallbacks.forEach(cb => cb(message));

    // 转发到 Orchestrator
    if (this.messageForwarder) {
      const systemMessage = this.createSystemMessage(message);
      try {
        await this.messageForwarder(systemMessage);
      } catch (error) {
        console.error('[ChatInterface] Failed to forward message:', error);
      }
    }
  }

  /**
   * 创建 SystemMessage 用于转发到 Orchestrator
   */
  private createSystemMessage(chatMessage: ChatMessage): SystemMessage {
    return {
      id: uuidv4(),
      type: MessageType.CHAT_MESSAGE,
      timestamp: new Date(),
      source: ModuleType.CHAT,
      payload: {
        chatMessage: {
          id: chatMessage.id,
          platform: chatMessage.platform,
          sender: {
            id: chatMessage.sender.id,
            username: chatMessage.sender.username,
            displayName: chatMessage.sender.displayName,
            isModerator: chatMessage.sender.isModerator,
            isSubscriber: chatMessage.sender.isSubscriber,
          },
          content: chatMessage.content,
          timestamp: chatMessage.timestamp.toISOString(),
        },
      },
    };
  }
}

/**
 * 从 ChatMessage 创建 SystemMessage（用于测试和外部使用）
 */
export function createChatSystemMessage(chatMessage: ChatMessage): SystemMessage {
  return {
    id: uuidv4(),
    type: MessageType.CHAT_MESSAGE,
    timestamp: new Date(),
    source: ModuleType.CHAT,
    payload: {
      chatMessage: {
        id: chatMessage.id,
        platform: chatMessage.platform,
        sender: {
          id: chatMessage.sender.id,
          username: chatMessage.sender.username,
          displayName: chatMessage.sender.displayName,
          isModerator: chatMessage.sender.isModerator,
          isSubscriber: chatMessage.sender.isSubscriber,
        },
        content: chatMessage.content,
        timestamp: chatMessage.timestamp instanceof Date 
          ? chatMessage.timestamp.toISOString() 
          : chatMessage.timestamp,
      },
    },
  };
}
