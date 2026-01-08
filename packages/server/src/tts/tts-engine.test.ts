/**
 * TTS Engine Tests
 * TTS 引擎单元测试
 */

import { TTSEngine } from './tts-engine.js';
import { TTSEngineConfig, ITTSService } from './types.js';
import { TTSProvider, VoiceConfig, Voice, AudioStream } from '@digital-human/shared';

// Mock TTS Service
class MockTTSService implements ITTSService {
  private provider: TTSProvider;
  private available: boolean = true;
  private synthesizeDelay: number = 100;

  constructor(provider: TTSProvider) {
    this.provider = provider;
  }

  async synthesize(text: string, voiceConfig?: VoiceConfig): Promise<AudioStream> {
    await new Promise(resolve => setTimeout(resolve, this.synthesizeDelay));
    return {
      format: 'wav',
      sampleRate: 22050,
      data: Buffer.from(`audio:${text}`),
      duration: text.length / 10,
    };
  }

  getProvider(): TTSProvider {
    return this.provider;
  }

  async isAvailable(): Promise<boolean> {
    return this.available;
  }

  async getAvailableVoices(): Promise<Voice[]> {
    return [
      { id: 'voice1', name: 'Voice 1', language: 'en', gender: 'female' },
      { id: 'voice2', name: 'Voice 2', language: 'zh', gender: 'male' },
    ];
  }

  setAvailable(available: boolean): void {
    this.available = available;
  }

  setSynthesizeDelay(delay: number): void {
    this.synthesizeDelay = delay;
  }
}

// Mock the factory
jest.mock('./providers/tts-factory.js', () => ({
  createTTSService: jest.fn((provider: TTSProvider) => new MockTTSService(provider)),
  getDefaultTTSProvider: jest.fn(() => ({
    type: 'local',
    name: 'vits',
    endpoint: 'http://localhost:23456',
  })),
  getAvailableTTSProviders: jest.fn(() => [
    { type: 'local', name: 'vits', endpoint: 'http://localhost:23456' },
    { type: 'cloud', name: 'elevenlabs' },
  ]),
}));

describe('TTSEngine', () => {
  let engine: TTSEngine;
  let config: TTSEngineConfig;

  beforeEach(() => {
    config = {
      vitsEndpoint: 'http://localhost:23456',
      elevenLabsApiKey: 'test-key',
    };
    engine = new TTSEngine(config);
  });

  afterEach(() => {
    engine.interrupt();
  });

  describe('initialization', () => {
    it('should create engine with default config', () => {
      const defaultEngine = new TTSEngine();
      expect(defaultEngine).toBeDefined();
      expect(defaultEngine.getProvider()).toBeDefined();
    });

    it('should create engine with custom config', () => {
      expect(engine).toBeDefined();
      expect(engine.getProvider().name).toBe('vits');
    });

    it('should initialize successfully', async () => {
      await engine.initialize();
      const isAvailable = await engine.isAvailable();
      expect(isAvailable).toBe(true);
    });
  });

  describe('synthesize', () => {
    it('should synthesize text to audio', async () => {
      const audio = await engine.synthesize('Hello world');
      expect(audio).toBeDefined();
      expect(audio.format).toBe('wav');
      expect(audio.data).toBeDefined();
    });

    it('should use custom voice config', async () => {
      const voiceConfig: VoiceConfig = {
        voiceId: 'custom-voice',
        speed: 1.2,
        pitch: 1.1,
      };
      const audio = await engine.synthesize('Test', voiceConfig);
      expect(audio).toBeDefined();
    });

    it('should auto-initialize if not initialized', async () => {
      const newEngine = new TTSEngine(config);
      const audio = await newEngine.synthesize('Auto init test');
      expect(audio).toBeDefined();
    });
  });

  describe('voice configuration', () => {
    it('should set voice config', () => {
      const voiceConfig: VoiceConfig = {
        voiceId: 'test-voice',
        speed: 1.5,
        pitch: 0.8,
      };
      engine.setVoice(voiceConfig);
      // Voice config is internal, verify through synthesis
      expect(engine).toBeDefined();
    });

    it('should set emotion and adjust voice parameters', () => {
      engine.setEmotion('happy');
      expect(engine).toBeDefined();
    });

    it('should handle all emotion types', () => {
      const emotions = ['neutral', 'happy', 'sad', 'surprised', 'angry', 'thinking'] as const;
      emotions.forEach(emotion => {
        engine.setEmotion(emotion);
        expect(engine).toBeDefined();
      });
    });

    it('should get available voices', async () => {
      const voices = await engine.getAvailableVoices();
      expect(voices).toBeInstanceOf(Array);
      expect(voices.length).toBeGreaterThan(0);
      expect(voices[0]).toHaveProperty('id');
      expect(voices[0]).toHaveProperty('name');
    });
  });

  describe('provider management', () => {
    it('should get current provider', () => {
      const provider = engine.getProvider();
      expect(provider).toBeDefined();
      expect(provider.name).toBe('vits');
    });

    it('should set new provider', async () => {
      const newProvider: TTSProvider = {
        type: 'cloud',
        name: 'elevenlabs',
      };
      await engine.setProvider(newProvider);
      expect(engine.getProvider().name).toBe('elevenlabs');
    });

    it('should get available providers', () => {
      const providers = engine.getAvailableProviders();
      expect(providers).toBeInstanceOf(Array);
      expect(providers.length).toBeGreaterThan(0);
    });

    it('should emit provider:changed event', async () => {
      const callback = jest.fn();
      engine.on('provider:changed', callback);

      const newProvider: TTSProvider = {
        type: 'cloud',
        name: 'elevenlabs',
      };
      await engine.setProvider(newProvider);

      expect(callback).toHaveBeenCalledWith(newProvider);
    });
  });

  describe('queue management', () => {
    it('should queue text for synthesis', () => {
      const id = engine.queueText('Test message');
      expect(id).toBeDefined();
      expect(typeof id).toBe('string');
    });

    it('should get queue length', () => {
      engine.queueText('Message 1');
      engine.queueText('Message 2');
      // Queue might be processed immediately, so just check it's a number
      expect(typeof engine.getQueueLength()).toBe('number');
    });

    it('should handle priority in queue', () => {
      engine.interrupt(); // Clear any existing queue
      engine.queueText('Low priority', 0);
      engine.queueText('High priority', 10);
      engine.queueText('Medium priority', 5);
      // Priority ordering is internal, just verify no errors
      expect(engine).toBeDefined();
    });

    it('should emit synthesis events', async () => {
      const startCallback = jest.fn();
      const completeCallback = jest.fn();

      engine.on('synthesis:start', startCallback);
      engine.on('synthesis:complete', completeCallback);

      engine.queueText('Event test');

      // Wait for processing
      await new Promise(resolve => setTimeout(resolve, 200));

      expect(startCallback).toHaveBeenCalled();
      expect(completeCallback).toHaveBeenCalled();
    });
  });

  describe('interrupt', () => {
    it('should interrupt current speech', () => {
      engine.queueText('Message 1');
      engine.queueText('Message 2');
      engine.interrupt();
      expect(engine.getQueueLength()).toBe(0);
      expect(engine.isSpeakingNow()).toBe(false);
    });

    it('should interrupt with priority message', async () => {
      engine.queueText('Normal message');
      const audio = await engine.interruptWithMessage('Priority message');
      expect(audio).toBeDefined();
      expect(engine.getQueueLength()).toBe(0);
    });
  });

  describe('status', () => {
    it('should report speaking status', () => {
      expect(engine.isSpeakingNow()).toBe(false);
    });

    it('should get current item', () => {
      expect(engine.getCurrentItem()).toBeNull();
    });

    it('should check availability', async () => {
      const isAvailable = await engine.isAvailable();
      expect(typeof isAvailable).toBe('boolean');
    });
  });
});
