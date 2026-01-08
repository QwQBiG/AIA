/**
 * VITS TTS Service
 * VITS 本地 TTS 服务实现
 */

import { TTSProvider, VoiceConfig, Voice, AudioStream } from '@digital-human/shared';
import { ITTSService, VITSConfig } from '../types.js';

/**
 * VITS TTS 服务类
 * 支持本地部署的 VITS 模型
 */
export class VITSTTSService implements ITTSService {
  private config: Required<Omit<VITSConfig, 'modelPath'>> & Pick<VITSConfig, 'modelPath'>;
  private provider: TTSProvider;

  constructor(config: VITSConfig) {
    this.config = {
      endpoint: config.endpoint,
      speakerId: config.speakerId ?? 0,
      modelPath: config.modelPath,
    };

    this.provider = {
      type: 'local',
      name: 'vits',
      endpoint: this.config.endpoint,
      voiceModelPath: this.config.modelPath,
    };
  }

  /**
   * 合成语音
   */
  async synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    const speakerId = voiceConfig?.voiceId 
      ? parseInt(voiceConfig.voiceId, 10) 
      : this.config.speakerId;

    // VITS API 请求
    const response = await fetch(`${this.config.endpoint}/voice/vits`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text,
        id: speakerId,
        format: 'wav',
        lang: 'auto',
        length: voiceConfig?.speed ? 1 / voiceConfig.speed : 1.0,
        noise: 0.667,
        noisew: 0.8,
        max: 50,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`VITS API error: ${response.status} - ${error}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 估算时长
    const estimatedDuration = (text.length / 150) * 60;

    return {
      format: 'wav',
      sampleRate: 22050,
      data: buffer,
      duration: estimatedDuration,
    };
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
      const response = await fetch(`${this.config.endpoint}/voice/speakers`, {
        method: 'GET',
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * 获取可用语音列表
   */
  async getAvailableVoices(): Promise<Voice[]> {
    try {
      const response = await fetch(`${this.config.endpoint}/voice/speakers`, {
        method: 'GET',
      });

      if (!response.ok) {
        return this.getDefaultVoices();
      }

      const data = await response.json() as { VITS?: Array<{ id: number; name: string; lang: string[] }> };
      const speakers = data.VITS || [];

      return speakers.map((speaker) => ({
        id: speaker.id.toString(),
        name: speaker.name,
        language: speaker.lang?.[0] || 'zh',
        gender: 'neutral' as const,
      }));
    } catch {
      return this.getDefaultVoices();
    }
  }

  /**
   * 获取默认语音列表
   */
  private getDefaultVoices(): Voice[] {
    return [
      { id: '0', name: 'Default Speaker', language: 'zh', gender: 'neutral' },
    ];
  }
}
