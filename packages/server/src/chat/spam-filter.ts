/**
 * Spam Filter
 * 实现聊天消息的垃圾过滤功能
 * 
 * Requirements: 4.4
 */

import type { ChatMessage, SpamFilterConfig } from '@digital-human/shared';
import type { UserMessageTracker } from './types.js';

/**
 * 过滤结果
 */
export interface FilterResult {
  /** 是否通过过滤 */
  passed: boolean;
  /** 被拒绝的原因（如果被拒绝） */
  reason?: 'blocked_word' | 'rate_limit' | 'disabled';
  /** 匹配到的屏蔽词（如果有） */
  matchedWord?: string;
}

/**
 * 默认垃圾过滤配置
 */
export const DEFAULT_SPAM_FILTER_CONFIG: SpamFilterConfig = {
  enabled: true,
  maxMessagesPerMinute: 20,
  blockedWords: [],
};

/**
 * 获取默认配置的副本
 */
function getDefaultConfig(): SpamFilterConfig {
  return {
    ...DEFAULT_SPAM_FILTER_CONFIG,
    blockedWords: [...DEFAULT_SPAM_FILTER_CONFIG.blockedWords],
  };
}

/**
 * 垃圾过滤器
 * 实现屏蔽词过滤和频率限制
 */
export class SpamFilter {
  private config: SpamFilterConfig;
  private userTrackers: Map<string, UserMessageTracker> = new Map();
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor(config?: Partial<SpamFilterConfig>) {
    const defaultConfig = getDefaultConfig();
    this.config = {
      ...defaultConfig,
      ...config,
      blockedWords: config?.blockedWords ? [...config.blockedWords] : defaultConfig.blockedWords,
    };
    
    // 启动定期清理过期的用户追踪数据
    this.startCleanup();
  }

  /**
   * 过滤消息
   * @param message 聊天消息
   * @returns 过滤结果
   */
  filter(message: ChatMessage): FilterResult {
    // 如果过滤器未启用，直接通过
    if (!this.config.enabled) {
      return { passed: true };
    }

    // 检查屏蔽词
    const blockedWordResult = this.checkBlockedWords(message.content);
    if (!blockedWordResult.passed) {
      return blockedWordResult;
    }

    // 检查频率限制
    const rateLimitResult = this.checkRateLimit(message.sender.id);
    if (!rateLimitResult.passed) {
      return rateLimitResult;
    }

    // 记录消息
    this.recordMessage(message.sender.id);

    return { passed: true };
  }

  /**
   * 更新配置
   */
  setConfig(config: Partial<SpamFilterConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * 获取当前配置
   */
  getConfig(): SpamFilterConfig {
    return { ...this.config };
  }

  /**
   * 添加屏蔽词
   */
  addBlockedWord(word: string): void {
    const normalizedWord = word.toLowerCase().trim();
    if (normalizedWord && !this.config.blockedWords.includes(normalizedWord)) {
      this.config.blockedWords.push(normalizedWord);
    }
  }

  /**
   * 移除屏蔽词
   */
  removeBlockedWord(word: string): void {
    const normalizedWord = word.toLowerCase().trim();
    const index = this.config.blockedWords.indexOf(normalizedWord);
    if (index !== -1) {
      this.config.blockedWords.splice(index, 1);
    }
  }

  /**
   * 清除用户的频率限制记录
   */
  clearUserHistory(userId: string): void {
    this.userTrackers.delete(userId);
  }

  /**
   * 清除所有用户的频率限制记录
   */
  clearAllHistory(): void {
    this.userTrackers.clear();
  }

  /**
   * 获取用户当前的消息频率
   */
  getUserMessageRate(userId: string): number {
    const tracker = this.userTrackers.get(userId);
    if (!tracker) {
      return 0;
    }

    const now = Date.now();
    const oneMinuteAgo = now - 60000;
    
    // 计算最近一分钟内的消息数
    return tracker.timestamps.filter(ts => ts > oneMinuteAgo).length;
  }

  /**
   * 停止过滤器（清理资源）
   */
  stop(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.userTrackers.clear();
  }

  /**
   * 检查屏蔽词
   */
  private checkBlockedWords(content: string): FilterResult {
    if (this.config.blockedWords.length === 0) {
      return { passed: true };
    }

    const normalizedContent = content.toLowerCase();
    
    for (const word of this.config.blockedWords) {
      if (normalizedContent.includes(word)) {
        return {
          passed: false,
          reason: 'blocked_word',
          matchedWord: word,
        };
      }
    }

    return { passed: true };
  }

  /**
   * 检查频率限制
   */
  private checkRateLimit(userId: string): FilterResult {
    const currentRate = this.getUserMessageRate(userId);
    
    if (currentRate >= this.config.maxMessagesPerMinute) {
      return {
        passed: false,
        reason: 'rate_limit',
      };
    }

    return { passed: true };
  }

  /**
   * 记录用户消息
   */
  private recordMessage(userId: string): void {
    const now = Date.now();
    let tracker = this.userTrackers.get(userId);
    
    if (!tracker) {
      tracker = { userId, timestamps: [] };
      this.userTrackers.set(userId, tracker);
    }

    tracker.timestamps.push(now);
  }

  /**
   * 启动定期清理
   */
  private startCleanup(): void {
    // 每分钟清理一次过期的时间戳
    this.cleanupInterval = setInterval(() => {
      this.cleanupExpiredTimestamps();
    }, 60000);
  }

  /**
   * 清理过期的时间戳
   */
  private cleanupExpiredTimestamps(): void {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;

    for (const [userId, tracker] of this.userTrackers.entries()) {
      // 过滤掉超过一分钟的时间戳
      tracker.timestamps = tracker.timestamps.filter(ts => ts > oneMinuteAgo);
      
      // 如果用户没有任何记录，删除追踪器
      if (tracker.timestamps.length === 0) {
        this.userTrackers.delete(userId);
      }
    }
  }
}

/**
 * 创建带有预设屏蔽词的垃圾过滤器
 */
export function createSpamFilterWithPresets(
  config?: Partial<SpamFilterConfig>,
  presetBlockedWords?: string[]
): SpamFilter {
  const filter = new SpamFilter(config);
  
  if (presetBlockedWords) {
    for (const word of presetBlockedWords) {
      filter.addBlockedWord(word);
    }
  }

  return filter;
}
