/**
 * Azure TTS Service
 * Azure TTS 服务实现
 */

import { TTSProvider, VoiceConfig, Voice, AudioStream } from '@digital-human/shared';
import { ITTSService, AzureTTSConfig, AzureVoiceInfo } from '../types.js';

/**
 * Azure TTS 服务类
 */
export class AzureTTSService implements ITTSService {
  private config: Required<Omit<AzureTTSConfig, 'voiceName'>> & Pick<AzureTTSConfig, 'voiceName'>;
  private provider: TTSProvider;
  private accessToken: string | null = null;
  private tokenExpiry: Date | null = null;

  constructor(config: AzureTTSConfig) {
    this.config = {
      speechKey: config.speechKey,
      speechRegion: config.speechRegion,
      voiceName: config.voiceName || 'en-US-JennyNeural',
    };

    this.provider = {
      type: 'cloud',
      name: 'azure',
      endpoint: `https://${this.config.speechRegion}.tts.speech.microsoft.com`,
    };
  }

  /**
   * 获取访问令牌
   */
  private async getAccessToken(): Promise<string> {
    // 检查缓存的令牌是否有效
    if (this.accessToken && this.tokenExpiry && new Date() < this.tokenExpiry) {
      return this.accessToken;
    }

    const tokenUrl = `https://${this.config.speechRegion}.api.cognitive.microsoft.com/sts/v1.0/issueToken`;
    
    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Ocp-Apim-Subscription-Key': this.config.speechKey,
        'Content-Length': '0',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get Azure access token: ${response.status}`);
    }

    this.accessToken = await response.text();
    // 令牌有效期 10 分钟，提前 1 分钟刷新
    this.tokenExpiry = new Date(Date.now() + 9 * 60 * 1000);
    
    return this.accessToken;
  }

  /**
   * 合成语音
   */
  async synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    const token = await this.getAccessToken();
    const voiceName = voiceConfig?.voiceId || this.config.voiceName;
    
    // 构建 SSML
    const ssml = this.buildSSML(text, voiceName!, voiceConfig);
    
    const url = `https://${this.config.speechRegion}.tts.speech.microsoft.com/cognitiveservices/v1`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3',
        'User-Agent': 'digital-human-tts',
      },
      body: ssml,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Azure TTS API error: ${response.status} - ${error}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 估算时长
    const estimatedDuration = (text.length / 150) * 60;

    return {
      format: 'mp3',
      sampleRate: 16000,
      data: buffer,
      duration: estimatedDuration,
    };
  }

  /**
   * 构建 SSML
   */
  private buildSSML(text: string, voiceName: string, voiceConfig?: VoiceConfig): string {
    const rate = voiceConfig?.speed ? `${Math.round((voiceConfig.speed - 1) * 100)}%` : '0%';
    const pitch = voiceConfig?.pitch ? `${Math.round((voiceConfig.pitch - 1) * 50)}%` : '0%';

    return `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
      <voice name='${voiceName}'>
        <prosody rate='${rate}' pitch='${pitch}'>
          ${this.escapeXml(text)}
        </prosody>
      </voice>
    </speak>`;
  }

  /**
   * 转义 XML 特殊字符
   */
  private escapeXml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');
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
      await this.getAccessToken();
      return true;
    } catch {
      return false;
    }
  }

  /**
   * 获取可用语音列表
   */
  async getAvailableVoices(): Promise<Voice[]> {
    const token = await this.getAccessToken();
    const url = `https://${this.config.speechRegion}.tts.speech.microsoft.com/cognitiveservices/voices/list`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch voices: ${response.status}`);
    }

    const voices = await response.json() as AzureVoiceInfo[];
    
    return voices.map((voice) => ({
      id: voice.ShortName,
      name: voice.DisplayName,
      language: voice.Locale,
      gender: this.mapGender(voice.Gender),
    }));
  }

  /**
   * 映射性别
   */
  private mapGender(gender: string): 'male' | 'female' | 'neutral' {
    const lower = gender.toLowerCase();
    if (lower === 'male') return 'male';
    if (lower === 'female') return 'female';
    return 'neutral';
  }
}
