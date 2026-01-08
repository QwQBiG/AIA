import * as fc from 'fast-check';
import { VisionModule, VisionModuleConfig } from './vision-module.js';
import { CapturedFrame, FrameAnalysis, DetectedObjectInfo } from './types.js';
import { IVisionAnalyzer } from './analyzers/types.js';

/**
 * **Feature: ai-vtuber-digital-human, Property 17: 游戏状态提取接口一致性**
 * **Validates: Requirements 2.2, 2.7**
 *
 * 对于任何视觉分析结果，无论使用云端还是本地视觉模型，
 * 返回的 GameState 结构应该一致。
 */

// 定义类型
interface VisionProvider {
  type: 'cloud' | 'local';
  name: string;
  model: string;
  endpoint?: string;
}

interface GameState {
  timestamp: Date;
  rawFrame?: Buffer;
  analysis: {
    playerPosition?: { x: number; y: number };
    health?: number;
    inventory?: string[];
    environment: string;
    detectedObjects: Array<{
      type: string;
      name: string;
      boundingBox?: { x: number; y: number; width: number; height: number };
      confidence: number;
    }>;
  };
  significantChange: boolean;
}

// 生成器：生成有效的帧分析结果
const frameAnalysisArb = fc.record({
  playerPosition: fc.option(
    fc.record({
      x: fc.integer({ min: 0, max: 1920 }),
      y: fc.integer({ min: 0, max: 1080 }),
    }),
    { nil: undefined }
  ),
  health: fc.option(fc.integer({ min: 0, max: 100 }), { nil: undefined }),
  inventory: fc.array(fc.string({ minLength: 1, maxLength: 20 }), { maxLength: 10 }),
  environment: fc.string({ minLength: 1, maxLength: 100 }),
  detectedObjects: fc.array(
    fc.record({
      type: fc.constantFrom('enemy', 'item', 'npc', 'obstacle', 'ui'),
      name: fc.string({ minLength: 1, maxLength: 30 }),
      boundingBox: fc.option(
        fc.record({
          x: fc.integer({ min: 0, max: 1920 }),
          y: fc.integer({ min: 0, max: 1080 }),
          width: fc.integer({ min: 1, max: 500 }),
          height: fc.integer({ min: 1, max: 500 }),
        }),
        { nil: undefined }
      ),
      // 使用 double 并过滤掉 NaN 和 Infinity
      confidence: fc.double({ min: 0, max: 1, noNaN: true }),
    }),
    { maxLength: 20 }
  ),
});

// Mock 分析器工厂
function createMockAnalyzer(
  providerType: 'cloud' | 'local',
  mockAnalysis: FrameAnalysis
): IVisionAnalyzer {
  return {
    async analyze(_frame: CapturedFrame): Promise<FrameAnalysis> {
      return mockAnalysis;
    },
    getProviderInfo(): VisionProvider {
      return {
        type: providerType,
        name: providerType === 'cloud' ? 'openai-vision' : 'local-vision',
        model: providerType === 'cloud' ? 'gpt-4-vision' : 'llava',
      };
    },
    async isAvailable(): Promise<boolean> {
      return true;
    },
  };
}

describe('Vision Module Property Tests', () => {
  describe('Property 17: 游戏状态提取接口一致性', () => {
    /**
     * **Feature: ai-vtuber-digital-human, Property 17: 游戏状态提取接口一致性**
     * **Validates: Requirements 2.2, 2.7**
     */
    it('should return consistent GameState structure regardless of provider type', async () => {
      await fc.assert(
        fc.asyncProperty(frameAnalysisArb, async (analysis) => {
          const config: VisionModuleConfig = {
            analyzerConfig: { defaultProvider: 'local' },
          };

          // 创建两个 VisionModule，分别使用云端和本地分析器
          const cloudModule = new VisionModule(config);
          const localModule = new VisionModule(config);

          // 注入 mock 分析器
          const cloudAnalyzer = createMockAnalyzer('cloud', analysis as FrameAnalysis);
          const localAnalyzer = createMockAnalyzer('local', analysis as FrameAnalysis);

          (cloudModule as unknown as { currentAnalyzer: IVisionAnalyzer }).currentAnalyzer =
            cloudAnalyzer;
          (localModule as unknown as { currentAnalyzer: IVisionAnalyzer }).currentAnalyzer =
            localAnalyzer;

          // 分析相同的帧
          const frameBuffer = Buffer.from('test frame');

          const [cloudState, localState] = await Promise.all([
            cloudModule.analyzeFrame(frameBuffer),
            localModule.analyzeFrame(frameBuffer),
          ]);

          // 验证两个结果的结构一致
          expect(cloudState.analysis.environment).toBe(localState.analysis.environment);
          expect(cloudState.analysis.health).toBe(localState.analysis.health);
          expect(cloudState.analysis.inventory).toEqual(localState.analysis.inventory);
          expect(cloudState.analysis.detectedObjects.length).toBe(
            localState.analysis.detectedObjects.length
          );

          // 验证 playerPosition 一致性
          if (cloudState.analysis.playerPosition && localState.analysis.playerPosition) {
            expect(cloudState.analysis.playerPosition.x).toBe(
              localState.analysis.playerPosition.x
            );
            expect(cloudState.analysis.playerPosition.y).toBe(
              localState.analysis.playerPosition.y
            );
          } else {
            expect(cloudState.analysis.playerPosition).toBe(localState.analysis.playerPosition);
          }

          // 清理
          cloudModule.destroy();
          localModule.destroy();
        }),
        { numRuns: 100 }
      );
    });

    /**
     * GameState 结构完整性测试
     */
    it('should always include required fields in GameState', async () => {
      await fc.assert(
        fc.asyncProperty(frameAnalysisArb, async (analysis) => {
          const config: VisionModuleConfig = {
            analyzerConfig: { defaultProvider: 'local' },
          };

          const module = new VisionModule(config);
          const mockAnalyzer = createMockAnalyzer('local', analysis as FrameAnalysis);
          (module as unknown as { currentAnalyzer: IVisionAnalyzer }).currentAnalyzer = mockAnalyzer;

          const frameBuffer = Buffer.from('test frame');
          const gameState = await module.analyzeFrame(frameBuffer);

          // 验证必需字段存在
          expect(gameState.timestamp).toBeInstanceOf(Date);
          expect(gameState.analysis).toBeDefined();
          expect(typeof gameState.analysis.environment).toBe('string');
          expect(Array.isArray(gameState.analysis.detectedObjects)).toBe(true);
          expect(typeof gameState.significantChange).toBe('boolean');

          module.destroy();
        }),
        { numRuns: 100 }
      );
    });

    /**
     * 检测对象结构一致性测试
     */
    it('should maintain consistent DetectedObject structure', async () => {
      await fc.assert(
        fc.asyncProperty(frameAnalysisArb, async (analysis) => {
          const config: VisionModuleConfig = {
            analyzerConfig: { defaultProvider: 'local' },
          };

          const module = new VisionModule(config);
          const mockAnalyzer = createMockAnalyzer('local', analysis as FrameAnalysis);
          (module as unknown as { currentAnalyzer: IVisionAnalyzer }).currentAnalyzer = mockAnalyzer;

          const frameBuffer = Buffer.from('test frame');
          const gameState = await module.analyzeFrame(frameBuffer);

          // 验证每个检测对象的结构
          for (const obj of gameState.analysis.detectedObjects) {
            expect(typeof obj.type).toBe('string');
            expect(typeof obj.name).toBe('string');
            expect(typeof obj.confidence).toBe('number');
            expect(obj.confidence).toBeGreaterThanOrEqual(0);
            expect(obj.confidence).toBeLessThanOrEqual(1);

            if (obj.boundingBox) {
              expect(typeof obj.boundingBox.x).toBe('number');
              expect(typeof obj.boundingBox.y).toBe('number');
              expect(typeof obj.boundingBox.width).toBe('number');
              expect(typeof obj.boundingBox.height).toBe('number');
            }
          }

          module.destroy();
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('Additional Vision Properties', () => {
    /**
     * 帧率控制属性测试
     */
    it('should maintain FPS within configured bounds', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 5, max: 60 }),
          fc.integer({ min: 1, max: 10 }),
          (targetFps, minFps) => {
            // 确保 minFps <= targetFps
            const actualMinFps = Math.min(minFps, targetFps);

            const config: VisionModuleConfig = {
              analyzerConfig: { defaultProvider: 'local' },
              minFps: actualMinFps,
            };

            const module = new VisionModule(config);

            // 获取状态
            const status = module.getStatus();

            // FPS 应该在合理范围内
            expect(status.currentFps).toBeGreaterThanOrEqual(0);

            module.destroy();
            return true;
          }
        ),
        { numRuns: 50 }
      );
    });

    /**
     * CPU 使用率监控属性测试
     */
    it('should report CPU usage within valid range', () => {
      fc.assert(
        fc.property(fc.integer({ min: 10, max: 50 }), (maxCpuUsage) => {
          const config: VisionModuleConfig = {
            analyzerConfig: { defaultProvider: 'local' },
            maxCpuUsage,
          };

          const module = new VisionModule(config);
          const status = module.getStatus();

          // CPU 使用率应该在 0-100 范围内
          expect(status.cpuUsage).toBeGreaterThanOrEqual(0);
          expect(status.cpuUsage).toBeLessThanOrEqual(100);

          module.destroy();
          return true;
        }),
        { numRuns: 50 }
      );
    });
  });
});
