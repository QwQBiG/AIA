/**
 * Twitch IRC Client
 * 实现 Twitch IRC 连接、消息解析和断线重连
 * 
 * Requirements: 4.1, 4.5
 */

import type { ChatMessage, SpamFilterConfig } from '@digital-human/shared';
import type { Client as TmiClient, ChatUserstate } from 'tmi.js';
import type {
  IChatInterface,
  TwitchConfig,
  ConnectionStatus,
  ReconnectConfig,
} from './types.js';

/**
 * 默认重连配置
 */
const DEFAULT_RECONNECT_CONFIG: ReconnectConfig = {
  enabled: true,
  initialDelay: 1000,
  maxDelay: 30000,
  maxAttempts: 10,
};

/**
 * Twitch IRC 客户端
 * 使用 tmi.js 库连接 Twitch IRC
 */
export class TwitchClient implements IChatInterface {
  private config: TwitchConfig;
  private reconnectConfig: ReconnectConfig;
  private spamFilter: SpamFilterConfig | null = null;
  private status: ConnectionStatus = 'disconnected';
  private client: TmiClient | null = null;
  private reconnectAttempts = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;

  // 事件回调
  private messageCallbacks: Array<(message: ChatMessage) => void> = [];
  private connectionCallbacks: Array<(status: ConnectionStatus) => void> = [];
  private errorCallbacks: Array<(error: Error) => void> = [];

  constructor(config: TwitchConfig, reconnectConfig?: Partial<ReconnectConfig>) {
    this.config = config;
    this.reconnectConfig = { ...DEFAULT_RECONNECT_CONFIG, ...reconnectConfig };
  }

  /**
   * 连接到 Twitch IRC
   */
  async connect(): Promise<void> {
    if (this.status === 'connected' || this.status === 'connecting') {
      return;
    }

    this.setStatus('connecting');

    try {
      // 动态导入 tmi.js
      const tmi = await import('tmi.js');
      
      this.client = new tmi.Client({
        options: { debug: false },
        connection: {
          reconnect: false, // 我们自己处理重连
          secure: true,
        },
        identity: this.config.readOnly ? undefined : {
          username: this.config.username,
          password: this.config.oauthToken,
        },
        channels: [this.config.channel],
      });

      // 注册事件处理器
      this.setupEventHandlers();

      // 连接
      await this.client.connect();
      
      this.setStatus('connected');
      this.reconnectAttempts = 0;
    } catch (error) {
      this.setStatus('disconnected');
      this.emitError(error instanceof Error ? error : new Error(String(error)));
      
      // 尝试重连
      if (this.reconnectConfig.enabled) {
        this.scheduleReconnect();
      }
      
      throw error;
    }
  }

  /**
   * 断开连接
   */
  async disconnect(): Promise<void> {
    // 清除重连定时器
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.client) {
      try {
        await this.client.disconnect();
      } catch {
        // 忽略断开连接时的错误
      }
      this.client = null;
    }

    this.setStatus('disconnected');
  }

  /**
   * 发送消息到频道
   */
  async sendMessage(message: string): Promise<void> {
    if (this.status !== 'connected' || !this.client) {
      throw new Error('Not connected to Twitch');
    }

    if (this.config.readOnly) {
      throw new Error('Client is in read-only mode');
    }

    await this.client.say(this.config.channel, message);
  }

  /**
   * 获取连接状态
   */
  getStatus(): ConnectionStatus {
    return this.status;
  }

  /**
   * 设置垃圾过滤配置
   */
  setSpamFilter(config: SpamFilterConfig): void {
    this.spamFilter = config;
  }

  /**
   * 注册消息回调
   */
  onMessage(callback: (message: ChatMessage) => void): void {
    this.messageCallbacks.push(callback);
  }

  /**
   * 注册连接状态回调
   */
  onConnectionChange(callback: (status: ConnectionStatus) => void): void {
    this.connectionCallbacks.push(callback);
  }

  /**
   * 注册错误回调
   */
  onError(callback: (error: Error) => void): void {
    this.errorCallbacks.push(callback);
  }

  /**
   * 设置 tmi.js 事件处理器
   */
  private setupEventHandlers(): void {
    if (!this.client) return;

    // 消息事件
    this.client.on('message', (channel: string, tags: ChatUserstate, message: string, self: boolean) => {
      // 忽略自己发送的消息
      if (self) return;

      const chatMessage = this.parseTwitchMessage(channel, tags, message);
      this.emitMessage(chatMessage);
    });

    // 断开连接事件
    this.client.on('disconnected', (reason: string) => {
      this.setStatus('disconnected');
      this.emitError(new Error(`Disconnected: ${reason}`));

      // 尝试重连
      if (this.reconnectConfig.enabled) {
        this.scheduleReconnect();
      }
    });

    // 连接事件
    this.client.on('connected', () => {
      this.setStatus('connected');
      this.reconnectAttempts = 0;
    });
  }

  /**
   * 解析 Twitch 消息为 ChatMessage 格式
   */
  private parseTwitchMessage(channel: string, tags: ChatUserstate, message: string): ChatMessage {
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
   * 安排重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.reconnectConfig.maxAttempts) {
      this.emitError(new Error(`Max reconnect attempts (${this.reconnectConfig.maxAttempts}) reached`));
      return;
    }

    // 计算指数退避延迟
    const delay = Math.min(
      this.reconnectConfig.initialDelay * Math.pow(2, this.reconnectAttempts),
      this.reconnectConfig.maxDelay
    );

    this.setStatus('reconnecting');
    this.reconnectAttempts++;

    this.reconnectTimeout = setTimeout(async () => {
      try {
        await this.connect();
      } catch {
        // connect 方法内部会处理错误和重连
      }
    }, delay);
  }

  /**
   * 设置连接状态并通知回调
   */
  private setStatus(status: ConnectionStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.connectionCallbacks.forEach(cb => cb(status));
    }
  }

  /**
   * 发送消息事件
   */
  private emitMessage(message: ChatMessage): void {
    this.messageCallbacks.forEach(cb => cb(message));
  }

  /**
   * 发送错误事件
   */
  private emitError(error: Error): void {
    this.errorCallbacks.forEach(cb => cb(error));
  }
}

/**
 * 从 PlatformCredentials 创建 TwitchConfig
 */
export function createTwitchConfigFromCredentials(
  credentials: { accessToken: string; channelId: string },
  username: string
): TwitchConfig {
  return {
    username,
    oauthToken: credentials.accessToken.startsWith('oauth:')
      ? credentials.accessToken
      : `oauth:${credentials.accessToken}`,
    channel: credentials.channelId,
  };
}
