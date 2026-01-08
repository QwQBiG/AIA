/**
 * TTS Service Factory
 * TTS 服务工厂
 */

import { TTSProvider } from '@digital-human/shared';
import { ITTSService, TTSEngineConfig } from '../types.js';
import { ElevenLabsTTSService } from './elevenlabs-tts.js';
import { AzureTTSService } from './azure-tts.js';
import { VITSTTSService } from './vits-tts.js';
import { GPTSoVITSTTSService } from './gpt-sovits-tts.js';

/**
 * 创建 TTS 服务
 */
export function createTTSService(
  provider: TTSProvider,
  config: TTSEngineConfig
): ITTSService {
  switch (provider.name) {
    case 'elevenlabs':
      if (!config.elevenLabsApiKey) {
        throw new Error('ElevenLabs API key is required for ElevenLabs TTS service');
      }
      return new ElevenLabsTTSService({
        apiKey: config.elevenLabsApiKey,
        baseUrl: provider.endpoint,
      });

    case 'azure':
      if (!config.azureSpeechKey || !config.azureSpeechRegion) {
        throw new Error('Azure Speech key and region are required for Azure TTS service');
      }
      return new AzureTTSService({
        speechKey: config.azureSpeechKey,
        speechRegion: config.azureSpeechRegion,
      });

    case 'vits':
      if (!config.vitsEndpoint && !provider.endpoint) {
        throw new Error('VITS endpoint is required');
      }
      return new VITSTTSService({
        endpoint: config.vitsEndpoint || provider.endpoint!,
        modelPath: provider.voiceModelPath,
      });

    case 'gpt-sovits':
      if (!config.gptSovitsEndpoint && !provider.endpoint) {
        throw new Error('GPT-SoVITS endpoint is required');
      }
      return new GPTSoVITSTTSService({
        endpoint: config.gptSovitsEndpoint || provider.endpoint!,
        referenceAudioPath: provider.voiceModelPath,
      });

    default:
      throw new Error(`Unknown TTS provider: ${provider.name}`);
  }
}

/**
 * 获取默认 TTS 提供者配置
 */
export function getDefaultTTSProvider(): TTSProvider {
  // 优先使用本地 GPT-SoVITS
  if (process.env.GPT_SOVITS_ENDPOINT || process.env.USE_LOCAL_TTS === 'true') {
    return {
      type: 'local',
      name: 'gpt-sovits',
      endpoint: process.env.GPT_SOVITS_ENDPOINT || 'http://localhost:9880',
    };
  }

  // 如果有 VITS 端点
  if (process.env.VITS_ENDPOINT) {
    return {
      type: 'local',
      name: 'vits',
      endpoint: process.env.VITS_ENDPOINT,
    };
  }

  // 如果有 ElevenLabs API Key
  if (process.env.ELEVENLABS_API_KEY) {
    return {
      type: 'cloud',
      name: 'elevenlabs',
    };
  }

  // 如果有 Azure Speech Key
  if (process.env.AZURE_SPEECH_KEY && process.env.AZURE_SPEECH_REGION) {
    return {
      type: 'cloud',
      name: 'azure',
    };
  }

  // 默认使用本地 VITS
  return {
    type: 'local',
    name: 'vits',
    endpoint: 'http://localhost:23456',
  };
}

/**
 * 获取所有可用的 TTS 提供者
 */
export function getAvailableTTSProviders(config: TTSEngineConfig): TTSProvider[] {
  const providers: TTSProvider[] = [];

  // ElevenLabs
  if (config.elevenLabsApiKey) {
    providers.push({
      type: 'cloud',
      name: 'elevenlabs',
    });
  }

  // Azure
  if (config.azureSpeechKey && config.azureSpeechRegion) {
    providers.push({
      type: 'cloud',
      name: 'azure',
    });
  }

  // VITS (本地)
  if (config.vitsEndpoint) {
    providers.push({
      type: 'local',
      name: 'vits',
      endpoint: config.vitsEndpoint,
    });
  }

  // GPT-SoVITS (本地)
  if (config.gptSovitsEndpoint) {
    providers.push({
      type: 'local',
      name: 'gpt-sovits',
      endpoint: config.gptSovitsEndpoint,
    });
  }

  // 如果没有配置任何提供者，添加默认的本地选项
  if (providers.length === 0) {
    providers.push({
      type: 'local',
      name: 'vits',
      endpoint: 'http://localhost:23456',
    });
  }

  return providers;
}
