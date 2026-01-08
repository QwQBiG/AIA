import { VisionModule, VisionModuleConfig } from './vision-module.js';
import { CapturedFrame, FrameAnalysis } from './types.js';
import { IVisionAnalyzer } from './analyzers/types.js';

// 从 shared 包导入类型
interface CaptureConfig {
  targetWindow?: string;
  region?: { x: number; y: number; width: number; height: number };
  fps: number;
}

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

// Mock 分析器
class MockVisionAnalyzer implements IVisionAnalyzer {
  private mockAnalysis: FrameAnalysis = {
    environment: 'Test environment',
    detectedObjects: [],
    playerPosition: { x: 100, y: 200 },
    health: 100,
    inventory: ['sword', 'shield'],
  };

  setMockAnalysis(analysis: Partial<FrameAnalysis>): void {
    this.mockAnalysis = { ...this.mockAnalysis, ...analysis };
  }

  async analyze(_frame: CapturedFrame): Promise<FrameAnalysis> {
    return this.mockAnalysis;
  }

  getProviderInfo(): VisionProvider {
    return {
      type: 'local',
      name: 'mock-vision',
      model: 'mock-model',
    };
  }

  async isAvailable(): Promise<boolean> {
    return true;
  }
}

describe('VisionModule', () => {
  let visionModule: VisionModule;
  let mockAnalyzer: MockVisionAnalyzer;

  const defaultConfig: VisionModuleConfig = {
    analyzerConfig: {
      defaultProvider: 'local',
    },
    maxCpuUsage: 30,
    minFps: 5,
    analysisInterval: 100,
  };

  beforeEach(() => {
    mockAnalyzer = new MockVisionAnalyzer();
    visionModule = new VisionModule(defaultConfig);
    // 注入 mock 分析器
    (visionModule as unknown as { currentAnalyzer: IVisionAnalyzer }).currentAnalyzer = mockAnalyzer;
    (visionModule as unknown as { currentProvider: VisionProvider }).currentProvider =
      mockAnalyzer.getProviderInfo();
  });

  afterEach(() => {
    visionModule.destroy();
  });

  describe('getStatus', () => {
    it('should return initial status when not capturing', () => {
      const status = visionModule.getStatus();

      expect(status.isCapturing).toBe(false);
      expect(status.currentFps).toBe(0);
      expect(status.cpuUsage).toBe(0);
      expect(status.lastCaptureTime).toBeUndefined();
      expect(status.lastError).toBeUndefined();
    });

    it('should include current provider info', () => {
      const status = visionModule.getStatus();

      expect(status.currentProvider).toBeDefined();
      expect(status.currentProvider?.name).toBe('mock-vision');
    });
  });

  describe('analyzeFrame', () => {
    it('should analyze a frame and return GameState', async () => {
      const frameBuffer = Buffer.from('test frame data');

      const gameState = await visionModule.analyzeFrame(frameBuffer);

      expect(gameState).toBeDefined();
      expect(gameState.timestamp).toBeInstanceOf(Date);
      expect(gameState.analysis).toBeDefined();
      expect(gameState.analysis.environment).toBe('Test environment');
      expect(gameState.analysis.playerPosition).toEqual({ x: 100, y: 200 });
      expect(gameState.analysis.health).toBe(100);
      expect(gameState.analysis.inventory).toEqual(['sword', 'shield']);
    });

    it('should include detected objects in analysis', async () => {
      mockAnalyzer.setMockAnalysis({
        detectedObjects: [
          { type: 'enemy', name: 'Goblin', confidence: 0.9 },
          { type: 'item', name: 'Health Potion', confidence: 0.85 },
        ],
      });

      const frameBuffer = Buffer.from('test frame data');
      const gameState = await visionModule.analyzeFrame(frameBuffer);

      expect(gameState.analysis.detectedObjects).toHaveLength(2);
      expect(gameState.analysis.detectedObjects[0].type).toBe('enemy');
      expect(gameState.analysis.detectedObjects[0].name).toBe('Goblin');
    });
  });

  describe('onStateChange', () => {
    it('should register state change callback', () => {
      const callback = jest.fn();

      visionModule.onStateChange(callback);

      // 触发状态变化事件
      visionModule.emit('stateChange', {
        timestamp: new Date(),
        analysis: { environment: 'test', detectedObjects: [] },
        significantChange: true,
      } as GameState);

      // 注意：onStateChange 回调是通过内部机制触发的，不是直接通过 emit
      // 这里我们测试回调是否被正确注册
      expect(
        (visionModule as unknown as { stateChangeCallbacks: Array<(state: GameState) => void> })
          .stateChangeCallbacks
      ).toContain(callback);
    });

    it('should remove state change callback', () => {
      const callback = jest.fn();

      visionModule.onStateChange(callback);
      visionModule.removeStateChangeCallback(callback);

      expect(
        (visionModule as unknown as { stateChangeCallbacks: Array<(state: GameState) => void> })
          .stateChangeCallbacks
      ).not.toContain(callback);
    });
  });

  describe('startCapture and stopCapture', () => {
    it('should update isCapturing status when starting capture', () => {
      const config: CaptureConfig = {
        fps: 10,
      };

      visionModule.startCapture(config);

      const status = visionModule.getStatus();
      expect(status.isCapturing).toBe(true);

      visionModule.stopCapture();
    });

    it('should update isCapturing status when stopping capture', () => {
      const config: CaptureConfig = {
        fps: 10,
      };

      visionModule.startCapture(config);
      visionModule.stopCapture();

      const status = visionModule.getStatus();
      expect(status.isCapturing).toBe(false);
    });

    it('should emit captureStarted event', (done) => {
      const config: CaptureConfig = {
        fps: 10,
      };

      visionModule.on('captureStarted', (captureConfig) => {
        expect(captureConfig).toEqual(config);
        visionModule.stopCapture();
        done();
      });

      visionModule.startCapture(config);
    });

    it('should emit captureStopped event', (done) => {
      const config: CaptureConfig = {
        fps: 10,
      };

      visionModule.on('captureStopped', () => {
        done();
      });

      visionModule.startCapture(config);
      visionModule.stopCapture();
    });
  });

  describe('setVisionProvider', () => {
    it('should throw error for unknown provider', () => {
      const unknownProvider: VisionProvider = {
        type: 'cloud',
        name: 'unknown-provider',
        model: 'unknown-model',
      };

      expect(() => visionModule.setVisionProvider(unknownProvider)).toThrow(
        'Vision provider not found: unknown-provider'
      );
    });
  });

  describe('getAvailableProviders', () => {
    it('should return list of available providers', () => {
      const providers = visionModule.getAvailableProviders();

      expect(Array.isArray(providers)).toBe(true);
    });
  });

  describe('getLastGameState', () => {
    it('should return null when no analysis has been performed', () => {
      const lastState = visionModule.getLastGameState();

      expect(lastState).toBeNull();
    });
  });

  describe('destroy', () => {
    it('should stop capture and clear callbacks', () => {
      const config: CaptureConfig = {
        fps: 10,
      };

      visionModule.startCapture(config);
      visionModule.onStateChange(() => {});

      visionModule.destroy();

      const status = visionModule.getStatus();
      expect(status.isCapturing).toBe(false);
      expect(
        (visionModule as unknown as { stateChangeCallbacks: Array<(state: GameState) => void> })
          .stateChangeCallbacks
      ).toHaveLength(0);
    });
  });
});

describe('VisionModule - Change Detection', () => {
  let visionModule: VisionModule;
  let mockAnalyzer: MockVisionAnalyzer;

  beforeEach(() => {
    mockAnalyzer = new MockVisionAnalyzer();
    visionModule = new VisionModule({
      analyzerConfig: { defaultProvider: 'local' },
      changeDetection: {
        threshold: 0.1,
        minChangeArea: 50,
      },
    });
    (visionModule as unknown as { currentAnalyzer: IVisionAnalyzer }).currentAnalyzer = mockAnalyzer;
  });

  afterEach(() => {
    visionModule.destroy();
  });

  it('should detect significant change when environment changes', async () => {
    // 第一次分析
    mockAnalyzer.setMockAnalysis({ environment: 'Forest' });
    await visionModule.analyzeFrame(Buffer.from('frame1'));

    // 设置 lastAnalysis
    (visionModule as unknown as { lastAnalysis: FrameAnalysis }).lastAnalysis = {
      environment: 'Forest',
      detectedObjects: [],
    };

    // 第二次分析 - 环境变化
    mockAnalyzer.setMockAnalysis({ environment: 'Cave' });

    const detectSignificantChange = (
      visionModule as unknown as { detectSignificantChange: (analysis: FrameAnalysis) => boolean }
    ).detectSignificantChange.bind(visionModule);

    const isSignificant = detectSignificantChange({
      environment: 'Cave',
      detectedObjects: [],
    });

    expect(isSignificant).toBe(true);
  });

  it('should detect significant change when health changes significantly', () => {
    (visionModule as unknown as { lastAnalysis: FrameAnalysis }).lastAnalysis = {
      environment: 'Forest',
      detectedObjects: [],
      health: 100,
    };

    const detectSignificantChange = (
      visionModule as unknown as { detectSignificantChange: (analysis: FrameAnalysis) => boolean }
    ).detectSignificantChange.bind(visionModule);

    const isSignificant = detectSignificantChange({
      environment: 'Forest',
      detectedObjects: [],
      health: 50, // 50 点血量变化
    });

    expect(isSignificant).toBe(true);
  });

  it('should not detect significant change for minor health changes', () => {
    (visionModule as unknown as { lastAnalysis: FrameAnalysis }).lastAnalysis = {
      environment: 'Forest',
      detectedObjects: [],
      health: 100,
    };

    const detectSignificantChange = (
      visionModule as unknown as { detectSignificantChange: (analysis: FrameAnalysis) => boolean }
    ).detectSignificantChange.bind(visionModule);

    const isSignificant = detectSignificantChange({
      environment: 'Forest',
      detectedObjects: [],
      health: 95, // 只有 5 点血量变化
    });

    expect(isSignificant).toBe(false);
  });
});
