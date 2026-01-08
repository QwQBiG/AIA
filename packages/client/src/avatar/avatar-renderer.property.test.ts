import * as fc from 'fast-check';
import { AvatarRenderer } from './avatar-renderer';
import { AvatarConfig } from './types';
import { EmotionType } from '@digital-human/shared';

/**
 * Property-based tests for Avatar Renderer
 * 
 * **Feature: ai-vtuber-digital-human, Property 16: 表情状态映射**
 * **Validates: Requirements 6.3**
 */
describe('AvatarRenderer Property Tests', () => {
  /**
   * Property 16: 表情状态映射
   * *For any* EmotionType，Avatar_Renderer 应该能够映射到对应的面部表情状态。
   * **Validates: Requirements 6.3**
   */
  describe('Property 16: Expression State Mapping', () => {
    const emotionTypes: EmotionType[] = ['neutral', 'happy', 'sad', 'surprised', 'angry', 'thinking'];

    it('should map any EmotionType to a corresponding expression state', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.constantFrom(...emotionTypes),
          async (emotion: EmotionType) => {
            const renderer = new AvatarRenderer();
            
            // Load avatar first
            const config: AvatarConfig = {
              type: 'live2d',
              modelPath: '/models/test.model3.json',
              scale: 1.0,
              position: { x: 0, y: 0 },
            };
            await renderer.loadAvatar(config);
            
            // Set expression
            renderer.setExpression(emotion);
            
            // Verify the expression was set correctly
            const currentExpression = renderer.getCurrentExpression();
            expect(currentExpression).toBe(emotion);
            
            renderer.destroy();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should support all defined emotion types', () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...emotionTypes),
          (emotion: EmotionType) => {
            const renderer = new AvatarRenderer();
            const supportedEmotions = renderer.getSupportedEmotions();
            
            // Every emotion type should be in the supported list
            expect(supportedEmotions).toContain(emotion);
            
            renderer.destroy();
          }
        ),
        { numRuns: 100 }
      );
    });


    it('should maintain expression state after multiple changes', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(fc.constantFrom(...emotionTypes), { minLength: 1, maxLength: 10 }),
          async (emotions: EmotionType[]) => {
            const renderer = new AvatarRenderer();
            
            const config: AvatarConfig = {
              type: 'live2d',
              modelPath: '/models/test.model3.json',
              scale: 1.0,
              position: { x: 0, y: 0 },
            };
            await renderer.loadAvatar(config);
            
            // Apply each emotion in sequence
            for (const emotion of emotions) {
              renderer.setExpression(emotion);
            }
            
            // The final expression should be the last one in the array
            const lastEmotion = emotions[emotions.length - 1];
            expect(renderer.getCurrentExpression()).toBe(lastEmotion);
            
            renderer.destroy();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should reset to neutral after unload regardless of previous expression', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.constantFrom(...emotionTypes),
          async (emotion: EmotionType) => {
            const renderer = new AvatarRenderer();
            
            const config: AvatarConfig = {
              type: 'live2d',
              modelPath: '/models/test.model3.json',
              scale: 1.0,
              position: { x: 0, y: 0 },
            };
            await renderer.loadAvatar(config);
            
            // Set any expression
            renderer.setExpression(emotion);
            
            // Unload avatar
            renderer.unloadAvatar();
            
            // Expression should reset to neutral
            expect(renderer.getCurrentExpression()).toBe('neutral');
            
            renderer.destroy();
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Avatar Loading Properties', () => {
    const avatarTypes: Array<'live2d' | '3d'> = ['live2d', '3d'];

    it('should load any valid avatar configuration', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.constantFrom(...avatarTypes),
          fc.double({ min: 0.1, max: 10, noNaN: true }),
          fc.double({ min: -1000, max: 1000, noNaN: true }),
          fc.double({ min: -1000, max: 1000, noNaN: true }),
          async (type, scale, x, y) => {
            const renderer = new AvatarRenderer();
            
            const config: AvatarConfig = {
              type,
              modelPath: `/models/test.${type === 'live2d' ? 'model3.json' : 'glb'}`,
              scale,
              position: { x, y },
            };
            
            const result = await renderer.loadAvatar(config);
            
            // Should complete within 5 seconds
            expect(result.loadTime).toBeLessThanOrEqual(5000);
            // Should be loaded (mock mode always succeeds)
            expect(renderer.isLoaded()).toBe(true);
            
            renderer.destroy();
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should properly unload and allow reloading', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(fc.constantFrom(...avatarTypes), { minLength: 1, maxLength: 5 }),
          async (types) => {
            const renderer = new AvatarRenderer();
            
            for (const type of types) {
              const config: AvatarConfig = {
                type,
                modelPath: `/models/test.${type === 'live2d' ? 'model3.json' : 'glb'}`,
                scale: 1.0,
                position: { x: 0, y: 0 },
              };
              
              await renderer.loadAvatar(config);
              expect(renderer.isLoaded()).toBe(true);
            }
            
            renderer.unloadAvatar();
            expect(renderer.isLoaded()).toBe(false);
            
            renderer.destroy();
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
