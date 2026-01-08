/**
 * ElevenLabs TTS Service
 * ElevenLabs TTS 服务实现
 */

import { TTSProvider, VoiceConfig, Voice, AudioStream } from '@digital-human/shared';
import { ITTSService, ElevenLabsConfig, ElevenLabsVoice, ElevenLabsVoicesResponse } from '../types.js';

/**
 * ElevenLabs TTS 服务类
 */
export class ElevenLabsTTSService implements ITTSService {
  private config: Required<Omit<ElevenLabsConfig, 'voiceId' | 'modelId'>> & Pick<ElevenLabsConfig, 'voiceId' | 'modelId'>;
  private provider: TTSProvider;

  constructor(config: ElevenLabsConfig) {
    this.config = {
      apiKey: config.apiKey,
      voiceId: config.voiceId || '21m00Tcm4TlvDq8ikWAM', // Rachel - 默认语音
      modelId: config.modelId || 'eleven_monolingual_v1',
      baseUrl: config.baseUrl || 'https://api.elevenlabs.io/v1',
    };

    this.provider = {
      type: 'cloud',
      name: 'elevenlabs',
      endpoint: this.config.baseUrl,
    };
  }

  /**
   * 合成语音
   */
  async synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    const voiceId = voiceConfig?.voiceId || this.config.voiceId;
    const url = `${this.config.baseUrl}/text-to-speech/${voiceId}`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'xi-api-key': this.config.apiKey,
        'Accept': 'audio/mpeg',
      },
      body: JSON.stringify({
        text,
        model_id: this.config.modelId,
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
          style: 0.0,
          use_speaker_boost: true,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`ElevenLabs API error: ${response.status} - ${error}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 估算时长（基于文本长度，约 150 字/分钟）
    const estimatedDuration = (text.length / 150) * 60;

    return {
      format: 'mp3',
      sampleRate: 44100,
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
      const response = await fetch(`${this.config.baseUrl}/voices`, {
        method: 'GET',
        headers: {
          'xi-api-key': this.config.apiKey,
        },
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
    const response = await fetch(`${this.config.baseUrl}/voices`, {
      method: 'GET',
      headers: {
        'xi-api-key': this.config.apiKey,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch voices: ${response.status}`);
    }

    const data = await response.json() as ElevenLabsVoicesResponse;
    
    return data.voices.map((voice: ElevenLabsVoice) => ({
      id: voice.voice_id,
      name: voice.name,
      language: voice.labels?.language || 'en',
      gender: this.mapGender(voice.labels?.gender),
    }));
  }

  /**
   * 映射性别
   */
  private mapGender(gender?: string): 'male' | 'female' | 'neutral' {
    if (!gender) return 'neutral';
    const lower = gender.toLowerCase();
    if (lower === 'male') return 'male';
    if (lower === 'female') return 'female';
    return 'neutral';
  }
}
