/**
 * 聊天消息发送者接口
 */
export interface ChatSender {
  /** 用户 ID */
  id: string;
  /** 用户名 */
  username: string;
  /** 显示名称 */
  displayName: string;
  /** 是否为管理员 */
  isModerator: boolean;
  /** 是否为订阅者 */
  isSubscriber: boolean;
}

/**
 * 聊天消息接口
 */
export interface ChatMessage {
  /** 消息 ID */
  id: string;
  /** 平台 */
  platform: 'twitch' | 'youtube';
  /** 发送者信息 */
  sender: ChatSender;
  /** 消息内容 */
  content: string;
  /** 时间戳 */
  timestamp: Date;
}

/**
 * 平台凭证接口
 */
export interface PlatformCredentials {
  /** 平台类型 */
  platform: 'twitch' | 'youtube';
  /** 访问令牌 */
  accessToken: string;
  /** 刷新令牌（可选） */
  refreshToken?: string;
  /** 频道 ID */
  channelId: string;
}

/**
 * 垃圾过滤配置接口
 */
export interface SpamFilterConfig {
  /** 是否启用 */
  enabled: boolean;
  /** 每分钟最大消息数 */
  maxMessagesPerMinute: number;
  /** 屏蔽词列表 */
  blockedWords: string[];
  /** 最小账号年龄（天，可选） */
  minAccountAge?: number;
}

/**
 * 聊天平台类型
 */
export type ChatPlatform = 'twitch' | 'youtube';
