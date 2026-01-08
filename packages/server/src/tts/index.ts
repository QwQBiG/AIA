/**
 * TTS Module Index
 * TTS 模块索引
 */

export { TTSEngine } from './tts-engine.js';
export type { TTSEngineEvents } from './tts-engine.js';
export type {
  ITTSService,
  TTSEngineConfig,
  TTSQueueItem,
  TTSSynthesisResult,
  ElevenLabsConfig,
  AzureTTSConfig,
  VITSConfig,
  GPTSoVITSConfig,
} from './types.js';
export {
  ElevenLabsTTSService,
  AzureTTSService,
  VITSTTSService,
  GPTSoVITSTTSService,
  createTTSService,
  getDefaultTTSProvider,
  getAvailableTTSProviders,
} from './providers/index.js';
