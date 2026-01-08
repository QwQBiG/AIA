/**
 * Chat Interface Types
 * 聊天接口模块的类型定义
 */

import type { ChatMessage, ChatPlatform, PlatformCredentials, SpamFilterConfig } from '@digital-human/shared';

/**
 * 聊天接口配置
 */
export interface ChatInterfaceConfig {
  /** 平台类型 */
  platform: ChatPlatform;
  /** 平台凭证 */
  credentials: PlatformCredentials;
  /** 垃圾过滤配置 */
  spamFilter?: SpamFilterConfig;
  /** 重连配置 */
  reconnect?: ReconnectConfig;
}

/**
 * 重连配置
 */
export interface ReconnectConfig {
  /** 是否启用自动重连 */
  enabled: boolean;
  /** 初始重连延迟（毫秒） */
  initialDelay: number;
  /** 最大重连延迟（毫秒） */
  maxDelay: number;
  /** 最大重连次数 */
  maxAttempts: number;
}

/**
 * 连接状态
 */
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

/**
 * 聊天接口事件
 */
export interface ChatInterfaceEvents {
  /** 消息接收事件 */
  message: (message: ChatMessage) => void;
  /** 连接状态变化事件 */
  connectionChange: (status: ConnectionStatus) => void;
  /** 错误事件 */
  error: (error: Error) => void;
}

/**
 * 聊天接口基础接口
 */
export interface IChatInterface {
  /** 连接到平台 */
  connect(): Promise<void>;
  /** 断开连接 */
  disconnect(): Promise<void>;
  /** 发送消息 */
  sendMessage(message: string): Promise<void>;
  /** 获取连接状态 */
  getStatus(): ConnectionStatus;
  /** 设置垃圾过滤配置 */
  setSpamFilter(config: SpamFilterConfig): void;
  /** 注册消息回调 */
  onMessage(callback: (message: ChatMessage) => void): void;
  /** 注册连接状态回调 */
  onConnectionChange(callback: (status: ConnectionStatus) => void): void;
  /** 注册错误回调 */
  onError(callback: (error: Error) => void): void;
}

/**
 * Twitch IRC 配置
 */
export interface TwitchConfig {
  /** 用户名 */
  username: string;
  /** OAuth 令牌 */
  oauthToken: string;
  /** 频道名称 */
  channel: string;
  /** 是否启用安全模式（只读） */
  readOnly?: boolean;
}

/**
 * YouTube Live Chat 配置
 */
export interface YouTubeConfig {
  /** API 密钥 */
  apiKey: string;
  /** 直播 ID */
  liveChatId: string;
  /** 轮询间隔（毫秒） */
  pollingInterval?: number;
}

/**
 * 用户消息频率追踪
 */
export interface UserMessageTracker {
  /** 用户 ID */
  userId: string;
  /** 消息时间戳列表 */
  timestamps: number[];
}
