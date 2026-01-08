import { EmotionType } from './enums.js';
import { ChatMessage } from './chat.js';
import { GameState, GameAction } from './game.js';
import { Memory } from './memory.js';

/**
 * 认知引擎输入接口
 */
export interface CognitionInput {
  /** 聊天消息（可选） */
  chatMessage?: ChatMessage;
  /** 游戏状态（可选） */
  gameState?: GameState;
  /** 相关记忆列表 */
  memories: Memory[];
  /** 系统提示词 */
  systemPrompt: string;
}

/**
 * 认知引擎输出接口
 */
export interface CognitionOutput {
  /** 响应文本 */
  responseText: string;
  /** 情绪状态 */
  emotion: EmotionType;
  /** 游戏动作列表（可选） */
  gameActions?: GameAction[];
  /** 是否需要语音输出 */
  shouldSpeak: boolean;
}

/**
 * LLM 提供者配置接口
 */
export interface LLMProvider {
  /** 提供者类型 */
  type: 'cloud' | 'local';
  /** 提供者名称 */
  name: string;
  /** 模型名称 */
  model: string;
  /** API 端点（可选） */
  endpoint?: string;
  /** API 密钥（可选） */
  apiKey?: string;
}

/**
 * 人格配置接口
 */
export interface PersonalityConfig {
  /** 人格名称 */
  name: string;
  /** 人格描述 */
  description: string;
  /** 说话风格 */
  speakingStyle: string;
  /** 背景故事 */
  backstory?: string;
  /** 特征列表 */
  traits: string[];
}
