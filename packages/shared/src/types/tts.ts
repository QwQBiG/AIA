import { EmotionType } from './enums.js';

/**
 * 语音配置接口
 */
export interface VoiceConfig {
  /** 语音 ID */
  voiceId: string;
  /** 语速 */
  speed: number;
  /** 音调 */
  pitch: number;
  /** 情绪（可选） */
  emotion?: EmotionType;
}

/**
 * 语音信息接口
 */
export interface Voice {
  /** 语音 ID */
  id: string;
  /** 语音名称 */
  name: string;
  /** 语言 */
  language: string;
  /** 性别 */
  gender: 'male' | 'female' | 'neutral';
}

/**
 * TTS 提供者配置接口
 */
export interface TTSProvider {
  /** 提供者类型 */
  type: 'cloud' | 'local';
  /** 提供者名称 */
  name: string;
  /** API 端点（可选） */
  endpoint?: string;
  /** 语音模型路径（可选，本地模式） */
  voiceModelPath?: string;
}

/**
 * 音频流接口
 */
export interface AudioStream {
  /** 音频格式 */
  format: 'wav' | 'mp3' | 'pcm';
  /** 采样率 */
  sampleRate: number;
  /** 音频数据 */
  data: Buffer | ReadableStream;
  /** 时长（秒） */
  duration: number;
}
