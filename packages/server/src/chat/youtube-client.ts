/**
 * YouTube Live Chat Client
 * 实现 YouTube Live Chat API 轮询、消息解析和配额管理
 * 
 * Requirements: 4.2
 */

import type { ChatMessage, SpamFilterConfig } from '@digital-human/shared';
import type {
  IChatInterface,
  YouTubeConfig,
  ConnectionStatus,
} from './types.js';

/**
 * YouTube API 响应类型
 */
interface YouTubeLiveChatMessage {
  id: string;
  snippet: {
    type: string;
    liveChatId: string;
    authorChannelId: string;
    publishedAt: string;
    hasDisplayContent: boolean;
    displayMessage: string;
    textMessageDetails?: {
      messageText: string;
    };
  };
  authorDetails: {
    channelId: string;
    channelUrl: string;
    displayName: string;
    profileImageUrl: string;
    isVerified: boolean;
    isChatOwner: boolean;
    isChatSponsor: boolean;
    isChatModerator: boolean;
  };
}

interface YouTubeLiveChatResponse {
  kind: string;
  etag: string;
  pollingIntervalMillis: number;
  pageInfo: {
    totalResults: number;
    resultsPerPage: number;
  };
  nextPageToken?: string;
  items: YouTubeLiveChatMessage[];
}

/**
 * 默认轮询间隔（毫秒）
 */
const DEFAULT_POLLING_INTERVAL = 2000;

/**
 * 最小轮询间隔（毫秒）
 */
const MIN_POLLING_INTERVAL = 1000;

/**
 * YouTube Live Chat 客户端
 * 使用 YouTube Data API v3 轮询直播聊天消息
 */
export class YouTubeClient implements IChatInterface {
  private config: YouTubeConfig;
  private spamFilter: SpamFilterConfig | null = null;
  private status: ConnectionStatus = 'disconnected';
  private pollingInterval: number;
  private pollingTimer: NodeJS.Timeout | null = null;
  private nextPageToken: string | null = null;
  private quotaUsed = 0;
  private lastQuotaReset: Date = new Date();

  // 事件回调
  private messageCallbacks: Array<(message: ChatMessage) => void> = [];
  private connectionCallbacks: Array<(status: ConnectionStatus) => void> = [];
  private errorCallbacks: Array<(error: Error) => void> = [];

  constructor(config: YouTubeConfig) {
    this.config = config;
    this.pollingInterval = Math.max(
      config.pollingInterval || DEFAULT_POLLING_INTERVAL,
      MIN_POLLING_INTERVAL
    );
  }

  /**
   * 连接到 YouTube Live Chat
   */
  async connect(): Promise<void> {
    if (this.status === 'connected' || this.status === 'connecting') {
      return;
    }

    this.setStatus('connecting');

    try {
      // 验证配置并获取初始消息
      await this.fetchMessages();
      
      this.setStatus('connected');
      
      // 开始轮询
      this.startPolling();
    } catch (error) {
      this.setStatus('disconnected');
      this.emitError(error instanceof Error ? error : new Error(String(error)));
      throw error;
    }
  }

  /**
   * 断开连接
   */
  async disconnect(): Promise<void> {
    this.stopPolling();
    this.setStatus('disconnected');
    this.nextPageToken = null;
  }

  /**
   * 发送消息（YouTube API 需要 OAuth 认证，此处简化实现）
   */
  async sendMessage(message: string): Promise<void> {
    if (this.status !== 'connected') {
      throw new Error('Not connected to YouTube Live Chat');
    }

    // YouTube 发送消息需要 OAuth 认证，这里抛出未实现错误
    throw new Error('Sending messages to YouTube requires OAuth authentication (not implemented)');
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
   * 获取当前配额使用情况
   */
  getQuotaUsage(): { used: number; lastReset: Date } {
    return {
      used: this.quotaUsed,
      lastReset: this.lastQuotaReset,
    };
  }

  /**
   * 开始轮询
   */
  private startPolling(): void {
    if (this.pollingTimer) {
      return;
    }

    this.pollingTimer = setInterval(async () => {
      try {
        await this.fetchMessages();
      } catch (error) {
        this.emitError(error instanceof Error ? error : new Error(String(error)));
      }
    }, this.pollingInterval);
  }

  /**
   * 停止轮询
   */
  private stopPolling(): void {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  }

  /**
   * 从 YouTube API 获取消息
   */
  private async fetchMessages(): Promise<void> {
    const url = this.buildApiUrl();
    
    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`YouTube API error: ${response.status} - ${JSON.stringify(errorData)}`);
      }

      const data = await response.json() as YouTubeLiveChatResponse;
      
      // 更新配额使用（每次 liveChatMessages.list 调用消耗约 5 个配额单位）
      this.quotaUsed += 5;
      
      // 更新下一页令牌
      this.nextPageToken = data.nextPageToken || null;
      
      // 根据 API 建议调整轮询间隔
      if (data.pollingIntervalMillis && data.pollingIntervalMillis > this.pollingInterval) {
        this.updatePollingInterval(data.pollingIntervalMillis);
      }

      // 处理消息
      for (const item of data.items) {
        if (item.snippet.type === 'textMessageEvent' && item.snippet.hasDisplayContent) {
          const chatMessage = this.parseYouTubeMessage(item);
          this.emitMessage(chatMessage);
        }
      }
    } catch (error) {
      // 检查是否是配额超限错误
      if (error instanceof Error && error.message.includes('quotaExceeded')) {
        this.handleQuotaExceeded();
      }
      throw error;
    }
  }

  /**
   * 构建 API URL
   */
  private buildApiUrl(): string {
    const baseUrl = 'https://www.googleapis.com/youtube/v3/liveChat/messages';
    const params = new URLSearchParams({
      liveChatId: this.config.liveChatId,
      part: 'id,snippet,authorDetails',
      key: this.config.apiKey,
    });

    if (this.nextPageToken) {
      params.set('pageToken', this.nextPageToken);
    }

    return `${baseUrl}?${params.toString()}`;
  }

  /**
   * 解析 YouTube 消息为 ChatMessage 格式
   */
  private parseYouTubeMessage(item: YouTubeLiveChatMessage): ChatMessage {
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
      content: item.snippet.displayMessage || item.snippet.textMessageDetails?.messageText || '',
      timestamp: new Date(item.snippet.publishedAt),
    };
  }

  /**
   * 更新轮询间隔
   */
  private updatePollingInterval(newInterval: number): void {
    this.pollingInterval = Math.max(newInterval, MIN_POLLING_INTERVAL);
    
    // 重启轮询以应用新间隔
    if (this.pollingTimer) {
      this.stopPolling();
      this.startPolling();
    }
  }

  /**
   * 处理配额超限
   */
  private handleQuotaExceeded(): void {
    this.emitError(new Error('YouTube API quota exceeded. Please wait for quota reset.'));
    
    // 停止轮询以避免进一步消耗配额
    this.stopPolling();
    this.setStatus('disconnected');
  }

  /**
   * 重置配额计数（应在每日配额重置时调用）
   */
  resetQuotaCounter(): void {
    this.quotaUsed = 0;
    this.lastQuotaReset = new Date();
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
