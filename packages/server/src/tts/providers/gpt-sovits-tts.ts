/**
 * GPT-SoVITS TTS Service
 * GPT-SoVITS 本地 TTS 服务实现（支持语音克隆）
 */

import { TTSProvider, VoiceConfig, Voice, AudioStream } from '@digital-human/shared';
import { ITTSService, GPTSoVITSConfig } from '../types.js';

/**
 * GPT-SoVITS TTS 服务类
 * 支持本地部署的 GPT-SoVITS 模型，具有语音克隆能力
 */
export class GPTSoVITSTTSService implements ITTSService {
  private config: Required<Omit<GPTSoVITSConfig, 'referenceAudioPath' | 'referenceText'>> & 
    Pick<GPTSoVITSConfig, 'referenceAudioPath' | 'referenceText'>;
  private provider: TTSProvider;

  constructor(config: GPTSoVITSConfig) {
    this.config = {
      endpoint: config.endpoint,
      referenceAudioPath: config.referenceAudioPath,
      referenceText: config.referenceText,
    };

    this.provider = {
      type: 'local',
      name: 'gpt-sovits',
      endpoint: this.config.endpoint,
      voiceModelPath: this.config.referenceAudioPath,
    };
  }

  /**
   * 合成语音
   */
  async synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    // GPT-SoVITS API 请求
    const requestBody: Record<string, unknown> = {
      text,
      text_lang: 'auto',
      speed: voiceConfig?.speed || 1.0,
    };

    // 如果有参考音频，添加到请求中
    if (this.config.referenceAudioPath) {
      requestBody.ref_audio_path = this.config.referenceAudioPath;
    }
    if (this.config.referenceText) {
      requestBody.prompt_text = this.config.referenceText;
      requestBody.prompt_lang = 'auto';
    }

    const response = await fetch(`${this.config.endpoint}/tts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`GPT-SoVITS API error: ${response.status} - ${error}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 估算时长
    const estimatedDuration = (text.length / 150) * 60;

    return {
      format: 'wav',
      sampleRate: 32000,
      data: buffer,
      duration: estimatedDuration,
    };
  }

  /**
   * 设置参考音频（用于语音克隆）
   */
  setReferenceAudio(audioPath: string, text?: string): void {
    this.config.referenceAudioPath = audioPath;
    if (text) {
      this.config.referenceText = text;
    }
    this.provider.voiceModelPath = audioPath;
  }

  /**
   * 获取当前提供者
   */
  getProvider(): TTSProvider {
    return this.provider;
  }

  /**
   * 检查服务是否可用
   */
  async isAvailable(): Promise<boolean> {
    try {
      // GPT-SoVITS 通常没有专门的健康检查端点
      // 尝试发送一个简单的请求
      const response = await fetch(`${this.config.endpoint}/`, {
        method: 'GET',
      });
      return response.ok || response.status === 404; // 404 也表示服务在运行
    } catch {
      return false;
    }
  }

  /**
   * 获取可用语音列表
   * GPT-SoVITS 使用参考音频进行语音克隆，不像传统 TTS 有预定义的语音列表
   */
  async getAvailableVoices(): Promise<Voice[]> {
    // GPT-SoVITS 是基于参考音频的语音克隆
    // 返回一个表示当前配置的语音
    const voices: Voice[] = [
      {
        id: 'clone',
        name: 'Voice Clone',
        language: 'multi',
        gender: 'neutral',
      },
    ];

    if (this.config.referenceAudioPath) {
      voices.push({
        id: 'custom',
        name: 'Custom Voice',
        language: 'multi',
        gender: 'neutral',
      });
    }

    return voices;
  }
}
