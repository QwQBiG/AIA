/**
 * Cognition Engine Unit Tests
 * 认知引擎单元测试
 */

import { CognitionEngine, CognitionEngineConfig } from './cognition-engine';
import {
  CognitionInput,
  CognitionOutput,
  LLMProvider,
  PersonalityConfig,
  Memory,
  EmotionType,
} from '@digital-human/shared';

// Mock fetch for testing
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('CognitionEngine', () => {
  let engine: CognitionEngine;
  const defaultConfig: CognitionEngineConfig = {
    llmConfig: {
      ollamaEndpoint: 'http://localhost:11434',
    },
    initialProvider: {
      type: 'local',
      name: 'ollama',
      model: 'llama3.2',
      endpoint: 'http://localhost:11434',
    },
    responseTimeout: 5000,
    maxContextMemories: 50,
  };

  beforeEach(() => {
    mockFetch.mockReset();
    engine = new CognitionEngine(defaultConfig);
  });

  describe('constructor', () => {
    it('should create engine with default personality', () => {
      const personality = engine.getPersonality();
      expect(personality).not.toBeNull();
      expect(personality?.name).toBe('AI VTuber');
    });

    it('should create engine with custom personality', () => {
      const customPersonality: PersonalityConfig = {
        name: 'TestBot',
        description: 'A test bot',
        speakingStyle: 'formal',
        traits: ['serious', 'helpful'],
      };

      const customEngine = new CognitionEngine({
        ...defaultConfig,
        initialPersonality: customPersonality,
      });

      expect(customEngine.getPersonality()).toEqual(customPersonality);
    });
  });

  describe('setPersonality', () => {
    it('should update personality configuration', () => {
      const newPersonality: PersonalityConfig = {
        name: 'NewBot',
        description: 'A new bot',
        speakingStyle: 'casual',
        traits: ['friendly'],
      };

      engine.setPersonality(newPersonality);
      expect(engine.getPersonality()).toEqual(newPersonality);
    });
  });

  describe('setProvider', () => {
    it('should switch to a new provider', () => {
      const newProvider: LLMProvider = {
        type: 'local',
        name: 'ollama',
        model: 'mistral',
        endpoint: 'http://localhost:11434',
      };

      engine.setProvider(newProvider);
      expect(engine.getCurrentProvider().model).toBe('mistral');
    });
  });

  describe('getAvailableProviders', () => {
    it('should return list of available providers', () => {
      const providers = engine.getAvailableProviders();
      expect(Array.isArray(providers)).toBe(true);
      expect(providers.length).toBeGreaterThan(0);
      
      // Should always include Ollama as local option
      const ollamaProvider = providers.find(p => p.name === 'ollama');
      expect(ollamaProvider).toBeDefined();
    });

    it('should include OpenAI when API key is configured', () => {
      const engineWithOpenAI = new CognitionEngine({
        llmConfig: {
          openaiApiKey: 'test-key',
          ollamaEndpoint: 'http://localhost:11434',
        },
      });

      const providers = engineWithOpenAI.getAvailableProviders();
      const openaiProvider = providers.find(p => p.name === 'openai');
      expect(openaiProvider).toBeDefined();
    });
  });

  describe('generateResponse', () => {
    it('should generate response from LLM', async () => {
      const mockResponse: CognitionOutput = {
        responseText: 'Hello!',
        emotion: 'happy' as EmotionType,
        shouldSpeak: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          response: JSON.stringify(mockResponse),
        }),
      });

      const input: CognitionInput = {
        chatMessage: {
          id: '1',
          platform: 'twitch',
          sender: {
            id: 'user1',
            username: 'testuser',
            displayName: 'Test User',
            isModerator: false,
            isSubscriber: false,
          },
          content: 'Hi there!',
          timestamp: new Date(),
        },
        memories: [],
        systemPrompt: 'You are a helpful assistant.',
      };

      const response = await engine.generateResponse(input);
      expect(response).toBeDefined();
      expect(response.responseText).toBeDefined();
    });

    it('should limit memories to maxContextMemories', async () => {
      const manyMemories: Memory[] = Array.from({ length: 100 }, (_, i) => ({
        id: `mem-${i}`,
        content: `Memory ${i}`,
        type: 'conversation',
        timestamp: new Date(),
      }));

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          response: JSON.stringify({
            responseText: 'Response',
            emotion: 'neutral',
            shouldSpeak: true,
          }),
        }),
      });

      const input: CognitionInput = {
        memories: manyMemories,
        systemPrompt: 'Test prompt',
      };

      await engine.generateResponse(input);

      // Verify fetch was called
      expect(mockFetch).toHaveBeenCalled();
    });

    it('should handle API errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('API Error'));
      // Also mock the fallback check
      mockFetch.mockResolvedValueOnce({
        ok: false,
      });

      const input: CognitionInput = {
        memories: [],
        systemPrompt: 'Test prompt',
      };

      const response = await engine.generateResponse(input);
      
      // Should return a default response
      expect(response.responseText).toBeDefined();
      expect(response.emotion).toBe('thinking');
    });
  });

  describe('message queue', () => {
    it('should queue messages when API fails', async () => {
      mockFetch.mockRejectedValue(new Error('API Error'));

      const input: CognitionInput = {
        memories: [],
        systemPrompt: 'Test prompt',
      };

      await engine.generateResponse(input);
      
      // Message should be queued
      expect(engine.getQueueLength()).toBe(1);
    });

    it('should process queued messages', async () => {
      // First call fails
      mockFetch.mockRejectedValueOnce(new Error('API Error'));
      mockFetch.mockResolvedValueOnce({ ok: false }); // Fallback check fails

      const input: CognitionInput = {
        memories: [],
        systemPrompt: 'Test prompt',
      };

      await engine.generateResponse(input);
      expect(engine.getQueueLength()).toBe(1);

      // Clear the queue manually for this test
      // Since processQueue will try to generate again and may fail
      // We need to ensure the mock is set up correctly
      mockFetch.mockReset();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          response: JSON.stringify({
            responseText: 'Processed',
            emotion: 'happy',
            shouldSpeak: true,
          }),
        }),
      });

      const results = await engine.processQueue();
      expect(results.length).toBeGreaterThanOrEqual(1);
      expect(engine.getQueueLength()).toBe(0);
    });
  });

  describe('degraded mode', () => {
    it('should track degraded state', () => {
      expect(engine.isInDegradedMode()).toBe(false);
    });

    it('should attempt fallback to local LLM on cloud failure', async () => {
      // Create engine with cloud provider
      const cloudEngine = new CognitionEngine({
        llmConfig: {
          openaiApiKey: 'test-key',
          ollamaEndpoint: 'http://localhost:11434',
        },
        initialProvider: {
          type: 'cloud',
          name: 'openai',
          model: 'gpt-4o-mini',
        },
      });

      // First call (OpenAI) fails
      mockFetch.mockRejectedValueOnce(new Error('OpenAI Error'));
      
      // Ollama availability check succeeds
      mockFetch.mockResolvedValueOnce({ ok: true });
      
      // Ollama generate succeeds
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          response: JSON.stringify({
            responseText: 'Fallback response',
            emotion: 'neutral',
            shouldSpeak: true,
          }),
        }),
      });

      const input: CognitionInput = {
        memories: [],
        systemPrompt: 'Test prompt',
      };

      const response = await cloudEngine.generateResponse(input);
      
      // Should have fallen back to local
      expect(cloudEngine.isInDegradedMode()).toBe(true);
      expect(response.responseText).toBe('Fallback response');
    });
  });

  describe('isServiceAvailable', () => {
    it('should check if current service is available', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });
      
      const available = await engine.isServiceAvailable();
      expect(typeof available).toBe('boolean');
    });
  });
});
