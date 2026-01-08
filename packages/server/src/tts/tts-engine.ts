/**
 * TTS Engine
 * TTS 引擎主类
 */

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import {
  TTSProvider,
  VoiceConfig,
  Voice,
  AudioStream,
  EmotionType,
} from '@digital-human/shared';
import {
  ITTSService,
  TTSEngineConfig,
  TTSQueueItem,
  TTSSynthesisResult,
} from './types.js';
import {
  createTTSService,
  getDefaultTTSProvider,
  getAvailableTTSProviders,
} from './providers/tts-factory.js';

/**
 * TTS 引擎事件
 */
export interface TTSEngineEvents {
  'synthesis:start': (item: TTSQueueItem) => void;
  'synthesis:complete': (item: TTSQueueItem, audio: AudioStream) => void;
  'synthesis:error': (item: TTSQueueItem, error: Error) => void;
  'queue:empty': () => void;
  'provider:changed': (provider: TTSProvider) => void;
  'provider:fallback': (from: TTSProvider, to: TTSProvider) => void;
}

/**
 * TTS 引擎类
 */
export class TTSEngine extends EventEmitter {
  private config: TTSEngineConfig;
  private currentService: ITTSService | null = null;
  private currentProvider: TTSProvider;
  private fallbackProvider: TTSProvider | null = null;
  private voiceConfig: VoiceConfig;
  private queue: TTSQueueItem[] = [];
  private isProcessing: boolean = false;
  private isSpeaking: boolean = false;
  private currentItem: TTSQueueItem | null = null;

  constructor(config: TTSEngineConfig = {}) {
    super();
    this.config = config;
    this.currentProvider = config.defaultProvider || getDefaultTTSProvider();
    this.voiceConfig = config.defaultVoiceConfig || {
      voiceId: '',
      speed: 1.0,
      pitch: 1.0,
    };

    // 设置本地提供者作为降级选项
    this.setupFallbackProvider();
  }

  /**
   * 初始化 TTS 引擎
   */
  async initialize(): Promise<void> {
    this.currentService = createTTSService(this.currentProvider, this.config);
    
    // 检查服务是否可用
    const isAvailable = await this.currentService.isAvailable();
    if (!isAvailable && this.fallbackProvider) {
      console.warn(`TTS provider ${this.currentProvider.name} is not available, falling back to ${this.fallbackProvider.name}`);
      await this.setProvider(this.fallbackProvider);
    }
  }

  /**
   * 设置降级提供者
   */
  private setupFallbackProvider(): void {
    // 如果当前是云端提供者，设置本地提供者作为降级
    if (this.currentProvider.type === 'cloud') {
      if (this.config.gptSovitsEndpoint) {
        this.fallbackProvider = {
          type: 'local',
          name: 'gpt-sovits',
          endpoint: this.config.gptSovitsEndpoint,
        };
      } else if (this.config.vitsEndpoint) {
        this.fallbackProvider = {
          type: 'local',
          name: 'vits',
          endpoint: this.config.vitsEndpoint,
        };
      }
    }
  }

  /**
   * 合成语音
   */
  async synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    if (!this.currentService) {
      await this.initialize();
    }

    const startTime = Date.now();
    const config = voiceConfig || this.voiceConfig;

    try {
      const audio = await this.currentService!.synthesize(text, config);
      const synthesisTime = Date.now() - startTime;

      // 检查合成时间是否超过 500ms
      if (synthesisTime > 500) {
        console.warn(`TTS synthesis took ${synthesisTime}ms, exceeding 500ms target`);
      }

      return audio;
    } catch (error) {
      // 尝试降级到本地 TTS
      if (this.fallbackProvider && this.currentProvider.type === 'cloud') {
        console.warn(`Cloud TTS failed, falling back to local TTS: ${error}`);
        const previousProvider = this.currentProvider;
        await this.setProvider(this.fallbackProvider);
        this.emit('provider:fallback', previousProvider, this.fallbackProvider);
        return this.currentService!.synthesize(text, config);
      }
      throw error;
    }
  }

  /**
   * 设置语音配置
   */
  setVoice(voiceConfig: VoiceConfig): void {
    this.voiceConfig = { ...this.voiceConfig, ...voiceConfig };
  }

  /**
   * 根据情绪调整语音参数
   */
  setEmotion(emotion: EmotionType): void {
    // 根据情绪调整语速和音调
    const emotionSettings: Record<EmotionType, Partial<VoiceConfig>> = {
      neutral: { speed: 1.0, pitch: 1.0 },
      happy: { speed: 1.1, pitch: 1.1 },
      sad: { speed: 0.9, pitch: 0.9 },
      surprised: { speed: 1.2, pitch: 1.2 },
      angry: { speed: 1.15, pitch: 1.05 },
      thinking: { speed: 0.95, pitch: 1.0 },
    };

    const settings = emotionSettings[emotion] || emotionSettings.neutral;
    this.voiceConfig = { ...this.voiceConfig, ...settings, emotion };
  }

  /**
   * 获取可用语音列表
   */
  async getAvailableVoices(): Promise<Voice[]> {
    if (!this.currentService) {
      await this.initialize();
    }
    return this.currentService!.getAvailableVoices();
  }

  /**
   * 设置 TTS 提供者
   */
  async setProvider(provider: TTSProvider): Promise<void> {
    const previousProvider = this.currentProvider;
    this.currentProvider = provider;
    this.currentService = createTTSService(provider, this.config);
    
    // 更新降级提供者
    this.setupFallbackProvider();
    
    this.emit('provider:changed', provider);
  }

  /**
   * 获取当前提供者
   */
  getProvider(): TTSProvider {
    return this.currentProvider;
  }

  /**
   * 获取所有可用提供者
   */
  getAvailableProviders(): TTSProvider[] {
    return getAvailableTTSProviders(this.config);
  }

  /**
   * 将文本加入队列
   */
  queueText(text: string, priority: number = 0, voiceConfig?: VoiceConfig): string {
    const item: TTSQueueItem = {
      id: uuidv4(),
      text,
      priority,
      voiceConfig,
      timestamp: new Date(),
    };

    // 按优先级插入队列
    const insertIndex = this.queue.findIndex(q => q.priority < priority);
    if (insertIndex === -1) {
      this.queue.push(item);
    } else {
      this.queue.splice(insertIndex, 0, item);
    }

    // 开始处理队列
    this.processQueue();

    return item.id;
  }

  /**
   * 中断当前语音并清空队列
   */
  interrupt(): void {
    this.isSpeaking = false;
    this.currentItem = null;
    this.queue = [];
    this.isProcessing = false;
  }

  /**
   * 中断当前语音并插入优先消息
   */
  async interruptWithMessage(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    this.interrupt();
    return this.synthesize(text, voiceConfig);
  }

  /**
   * 处理队列
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessing || this.queue.length === 0) {
      return;
    }

    this.isProcessing = true;

    while (this.queue.length > 0) {
      const item = this.queue.shift()!;
      this.currentItem = item;
      this.isSpeaking = true;

      this.emit('synthesis:start', item);

      try {
        const audio = await this.synthesize(item.text, item.voiceConfig);
        this.emit('synthesis:complete', item, audio);
      } catch (error) {
        this.emit('synthesis:error', item, error as Error);
      }

      this.isSpeaking = false;
      this.currentItem = null;
    }

    this.isProcessing = false;
    this.emit('queue:empty');
  }

  /**
   * 获取队列长度
   */
  getQueueLength(): number {
    return this.queue.length;
  }

  /**
   * 检查是否正在说话
   */
  isSpeakingNow(): boolean {
    return this.isSpeaking;
  }

  /**
   * 获取当前正在处理的项目
   */
  getCurrentItem(): TTSQueueItem | null {
    return this.currentItem;
  }

  /**
   * 检查服务是否可用
   */
  async isAvailable(): Promise<boolean> {
    if (!this.currentService) {
      try {
        await this.initialize();
      } catch {
        return false;
      }
    }
    return this.currentService!.isAvailable();
  }
}
