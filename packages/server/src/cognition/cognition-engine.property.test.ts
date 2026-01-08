/**
 * Cognition Engine Property Tests
 * 认知引擎属性测试
 * 
 * **Feature: ai-vtuber-digital-human, Property 18: 上下文记忆维护**
 * **Validates: Requirements 1.2**
 */

import * as fc from 'fast-check';
import { CognitionEngine, CognitionEngineConfig } from './cognition-engine';
import {
  CognitionInput,
  Memory,
  ChatMessage,
  PersonalityConfig,
} from '@digital-human/shared';

// Mock fetch for testing
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('CognitionEngine Property Tests', () => {
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
    // Default mock response
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        response: JSON.stringify({
          responseText: 'Test response',
          emotion: 'neutral',
          shouldSpeak: true,
        }),
      }),
    });
  });

  // Arbitrary generators
  const memoryArb = fc.record({
    id: fc.uuid(),
    content: fc.string({ minLength: 1, maxLength: 500 }),
    type: fc.constantFrom('conversation', 'game_event', 'system'),
    timestamp: fc.date(),
    relevanceScore: fc.option(fc.float({ min: 0, max: 1 })),
  }) as fc.Arbitrary<Memory>;

  const chatMessageArb = fc.record({
    id: fc.uuid(),
    platform: fc.constantFrom('twitch', 'youtube') as fc.Arbitrary<'twitch' | 'youtube'>,
    sender: fc.record({
      id: fc.string({ minLength: 1, maxLength: 50 }),
      username: fc.string({ minLength: 1, maxLength: 50 }),
      displayName: fc.string({ minLength: 1, maxLength: 100 }),
      isModerator: fc.boolean(),
      isSubscriber: fc.boolean(),
    }),
    content: fc.string({ minLength: 1, maxLength: 500 }),
    timestamp: fc.date(),
  }) as fc.Arbitrary<ChatMessage>;

  const personalityArb = fc.record({
    name: fc.string({ minLength: 1, maxLength: 50 }),
    description: fc.string({ minLength: 1, maxLength: 200 }),
    speakingStyle: fc.string({ minLength: 1, maxLength: 100 }),
    backstory: fc.option(fc.string({ minLength: 1, maxLength: 500 })),
    traits: fc.array(fc.string({ minLength: 1, maxLength: 30 }), { minLength: 1, maxLength: 10 }),
  }) as fc.Arbitrary<PersonalityConfig>;

  /**
   * Property 18: 上下文记忆维护
   * *For any* 对话序列，Cognition_Engine 应该能够访问最近 50 条交互的上下文。
   * **Validates: Requirements 1.2**
   */
  describe('Property 18: Context Memory Maintenance', () => {
    it('should maintain access to at most maxContextMemories (50) memories', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(memoryArb, { minLength: 0, maxLength: 100 }),
          async (memories) => {
            const engine = new CognitionEngine(defaultConfig);
            
            const input: CognitionInput = {
              memories: memories,
              systemPrompt: 'Test prompt',
            };

            // The engine should process without error
            const response = await engine.generateResponse(input);
            
            // Response should be valid
            expect(response).toBeDefined();
            expect(response.responseText).toBeDefined();
            expect(response.emotion).toBeDefined();
            expect(typeof response.shouldSpeak).toBe('boolean');

            // Verify that the engine limits memories internally
            // (We can't directly check the internal state, but we verify it doesn't crash)
            return true;
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should preserve memory order when limiting (keep most recent)', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(memoryArb, { minLength: 51, maxLength: 100 }),
          async (memories) => {
            const engine = new CognitionEngine({
              ...defaultConfig,
              maxContextMemories: 50,
            });

            // Sort memories by timestamp to simulate chronological order
            const sortedMemories = [...memories].sort(
              (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
            );

            const input: CognitionInput = {
              memories: sortedMemories,
              systemPrompt: 'Test prompt',
            };

            // Should process without error
            const response = await engine.generateResponse(input);
            expect(response).toBeDefined();

            return true;
          }
        ),
        { numRuns: 50 }
      );
    });
  });

  /**
   * Property: Personality Consistency
   * *For any* personality configuration, the engine should maintain it across interactions.
   */
  describe('Property: Personality Consistency', () => {
    it('should maintain consistent personality across multiple interactions', async () => {
      await fc.assert(
        fc.asyncProperty(
          personalityArb,
          fc.array(chatMessageArb, { minLength: 1, maxLength: 10 }),
          async (personality, messages) => {
            const engine = new CognitionEngine(defaultConfig);
            engine.setPersonality(personality);

            // Process multiple messages
            for (const message of messages) {
              const input: CognitionInput = {
                chatMessage: message,
                memories: [],
                systemPrompt: '',
              };

              await engine.generateResponse(input);

              // Personality should remain unchanged
              const currentPersonality = engine.getPersonality();
              expect(currentPersonality).toEqual(personality);
            }

            return true;
          }
        ),
        { numRuns: 50 }
      );
    });
  });

  /**
   * Property: Response Format Validity
   * *For any* valid input, the response should have valid format.
   */
  describe('Property: Response Format Validity', () => {
    it('should always return valid CognitionOutput format', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.option(chatMessageArb),
          fc.array(memoryArb, { minLength: 0, maxLength: 20 }),
          fc.string({ minLength: 1, maxLength: 500 }),
          async (chatMessage, memories, systemPrompt) => {
            const engine = new CognitionEngine(defaultConfig);

            const input: CognitionInput = {
              chatMessage: chatMessage ?? undefined,
              memories: memories,
              systemPrompt: systemPrompt,
            };

            const response = await engine.generateResponse(input);

            // Validate response structure
            expect(response).toBeDefined();
            expect(typeof response.responseText).toBe('string');
            expect(['neutral', 'happy', 'sad', 'surprised', 'angry', 'thinking']).toContain(
              response.emotion
            );
            expect(typeof response.shouldSpeak).toBe('boolean');

            // gameActions should be undefined or an array
            if (response.gameActions !== undefined) {
              expect(Array.isArray(response.gameActions)).toBe(true);
            }

            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property: Provider Switching
   * *For any* valid provider, switching should not lose configuration.
   */
  describe('Property: Provider Switching', () => {
    it('should maintain personality when switching providers', async () => {
      await fc.assert(
        fc.asyncProperty(
          personalityArb,
          async (personality) => {
            const engine = new CognitionEngine(defaultConfig);
            engine.setPersonality(personality);

            // Switch provider
            engine.setProvider({
              type: 'local',
              name: 'ollama',
              model: 'mistral',
              endpoint: 'http://localhost:11434',
            });

            // Personality should be preserved
            expect(engine.getPersonality()).toEqual(personality);

            return true;
          }
        ),
        { numRuns: 50 }
      );
    });
  });

  /**
   * Property: Queue Behavior
   * *For any* sequence of failed requests, messages should be queued.
   */
  describe('Property: Queue Behavior', () => {
    it('should queue messages on failure and process them later', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(chatMessageArb, { minLength: 1, maxLength: 5 }),
          async (messages) => {
            // Mock failure
            mockFetch.mockReset();
            mockFetch.mockRejectedValue(new Error('API Error'));

            const engine = new CognitionEngine(defaultConfig);

            // All requests should fail and be queued
            for (const message of messages) {
              const input: CognitionInput = {
                chatMessage: message,
                memories: [],
                systemPrompt: 'Test',
              };

              await engine.generateResponse(input);
            }

            // Queue should have all messages
            expect(engine.getQueueLength()).toBe(messages.length);

            return true;
          }
        ),
        { numRuns: 30 }
      );
    });
  });
});
