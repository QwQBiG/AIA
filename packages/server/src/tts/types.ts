/**
 * TTS Engine Types
 * TTS 引擎类型定义
 */

import { TTSProvider, VoiceConfig, Voice, AudioStream, EmotionType } from '@digital-human/shared';

/**
 * TTS 服务接口
 */
export interface ITTSService {
  /** 合成语音 */
  synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream>;
  /** 获取当前提供者 */
  getProvider(): TTSProvider;
  /** 检查服务是否可用 */
  isAvailable(): Promise<boolean>;
  /** 获取可用语音列表 */
  getAvailableVoices(): Promise<Voice[]>;
}

/**
 * TTS 引擎配置
 */
export interface TTSEngineConfig {
  /** 默认提供者 */
  defaultProvider?: TTSProvider;
  /** ElevenLabs API Key */
  elevenLabsApiKey?: string;
  /** Azure Speech Key */
  azureSpeechKey?: string;
  /** Azure Speech Region */
  azureSpeechRegion?: string;
  /** 本地 VITS 端点 */
  vitsEndpoint?: string;
  /** 本地 GPT-SoVITS 端点 */
  gptSovitsEndpoint?: string;
  /** 默认语音配置 */
  defaultVoiceConfig?: VoiceConfig;
}

/**
 * ElevenLabs 配置
 */
export interface ElevenLabsConfig {
  apiKey: string;
  voiceId?: string;
  modelId?: string;
  baseUrl?: string;
}

/**
 * Azure TTS 配置
 */
export interface AzureTTSConfig {
  speechKey: string;
  speechRegion: string;
  voiceName?: string;
}

/**
 * VITS 配置
 */
export interface VITSConfig {
  endpoint: string;
  speakerId?: number;
  modelPath?: string;
}

/**
 * GPT-SoVITS 配置
 */
export interface GPTSoVITSConfig {
  endpoint: string;
  referenceAudioPath?: string;
  referenceText?: string;
}

/**
 * TTS 队列项
 */
export interface TTSQueueItem {
  id: string;
  text: string;
  priority: number;
  voiceConfig?: VoiceConfig;
  timestamp: Date;
}

/**
 * TTS 合成结果
 */
export interface TTSSynthesisResult {
  success: boolean;
  audio?: AudioStream;
  error?: string;
  duration?: number;
  synthesisTime?: number;
}

/**
 * ElevenLabs 语音响应
 */
export interface ElevenLabsVoice {
  voice_id: string;
  name: string;
  category?: string;
  labels?: Record<string, string>;
}

/**
 * ElevenLabs 语音列表响应
 */
export interface ElevenLabsVoicesResponse {
  voices: ElevenLabsVoice[];
}

/**
 * Azure 语音信息
 */
export interface AzureVoiceInfo {
  Name: string;
  DisplayName: string;
  LocalName: string;
  ShortName: string;
  Gender: string;
  Locale: string;
  LocaleName: string;
  VoiceType: string;
}
