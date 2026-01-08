import { EventEmitter } from 'events';
import { GameState, CaptureConfig, VisionProvider } from '@digital-human/shared';
import {
  IVisionModule,
  VisionModuleStatus,
  CapturedFrame,
  FrameAnalysis,
  ChangeDetectionConfig,
} from './types.js';
import { ScreenCapture } from './screen-capture.js';
import { CpuMonitor, FrameRateController } from './cpu-monitor.js';
import { IVisionAnalyzer } from './analyzers/types.js';
import { VisionAnalyzerFactory, VisionFactoryConfig } from './analyzers/vision-factory.js';

/**
 * Vision Module 配置
 */
export interface VisionModuleConfig {
  /** 视觉分析器工厂配置 */
  analyzerConfig: VisionFactoryConfig;
  /** 变化检测配置 */
  changeDetection?: ChangeDetectionConfig;
  /** 最大 CPU 使用率 */
  maxCpuUsage?: number;
  /** 最小帧率 */
  minFps?: number;
  /** 分析间隔（毫秒） */
  analysisInterval?: number;
}

/**
 * Vision Module 实现
 * 负责屏幕捕获、游戏状态分析和状态变化检测
 */
export class VisionModule extends EventEmitter implements IVisionModule {
  private screenCapture: ScreenCapture;
  private cpuMonitor: CpuMonitor;
  private frameRateController: FrameRateController | null = null;
  private analyzerFactory: VisionAnalyzerFactory;
  private currentAnalyzer: IVisionAnalyzer | null = null;
  private currentProvider: VisionProvider | null = null;

  private config: VisionModuleConfig;
  private captureConfig: CaptureConfig | null = null;
  private isCapturing: boolean = false;
  private lastAnalysis: FrameAnalysis | null = null;
  private lastGameState: GameState | null = null;
  private lastError: string | undefined;

  private stateChangeCallbacks: Array<(state: GameState) => void> = [];
  private analysisInterval: NodeJS.Timeout | null = null;
  private pendingFrame: CapturedFrame | null = null;
  private isAnalyzing: boolean = false;

  constructor(config: VisionModuleConfig) {
    super();

    this.config = {
      maxCpuUsage: 30,
      minFps: 5,
      analysisInterval: 500, // 每 500ms 分析一次
      changeDetection: {
        threshold: 0.1,
        minChangeArea: 100,
      },
      ...config,
    };

    this.screenCapture = new ScreenCapture();
    this.cpuMonitor = new CpuMonitor();
    this.analyzerFactory = new VisionAnalyzerFactory(config.analyzerConfig);

    // 设置默认分析器
    this.currentAnalyzer = this.analyzerFactory.getDefaultAnalyzer();
    if (this.currentAnalyzer) {
      this.currentProvider = this.currentAnalyzer.getProviderInfo();
    }

    this.setupEventHandlers();
  }

  /**
   * 开始屏幕捕获
   */
  startCapture(config: CaptureConfig): void {
    if (this.isCapturing) {
      this.stopCapture();
    }

    this.captureConfig = config;
    this.isCapturing = true;
    this.lastError = undefined;

    // 初始化帧率控制器
    this.frameRateController = new FrameRateController({
      targetFps: config.fps,
      minFps: this.config.minFps!,
      maxCpuUsage: this.config.maxCpuUsage!,
    });
    this.frameRateController.start();

    // 开始 CPU 监控
    this.cpuMonitor.startMonitoring(1000);

    // 开始屏幕捕获
    this.screenCapture.start(config);

    // 开始分析循环
    this.startAnalysisLoop();

    this.emit('captureStarted', config);
  }

  /**
   * 停止屏幕捕获
   */
  stopCapture(): void {
    this.isCapturing = false;

    this.screenCapture.stop();
    this.cpuMonitor.stopMonitoring();

    if (this.frameRateController) {
      this.frameRateController.stop();
      this.frameRateController = null;
    }

    if (this.analysisInterval) {
      clearInterval(this.analysisInterval);
      this.analysisInterval = null;
    }

    this.pendingFrame = null;
    this.emit('captureStopped');
  }

  /**
   * 分析帧
   */
  async analyzeFrame(frame: Buffer): Promise<GameState> {
    const capturedFrame: CapturedFrame = {
      data: frame,
      width: this.captureConfig?.region?.width || 1920,
      height: this.captureConfig?.region?.height || 1080,
      timestamp: new Date(),
      format: 'png',
    };

    const analysis = await this.performAnalysis(capturedFrame);
    return this.createGameState(analysis, capturedFrame);
  }

  /**
   * 设置视觉提供者
   */
  setVisionProvider(provider: VisionProvider): void {
    const analyzer = this.analyzerFactory.getAnalyzer(provider);

    if (!analyzer) {
      throw new Error(`Vision provider not found: ${provider.name}`);
    }

    this.currentAnalyzer = analyzer;
    this.currentProvider = provider;

    this.emit('providerChanged', provider);
  }

  /**
   * 获取当前状态
   */
  getStatus(): VisionModuleStatus {
    return {
      isCapturing: this.isCapturing,
      currentFps: this.screenCapture.getCurrentFps(),
      cpuUsage: this.cpuMonitor.getCurrentUsage(),
      lastCaptureTime: this.lastGameState?.timestamp,
      lastError: this.lastError,
      currentProvider: this.currentProvider,
    };
  }

  /**
   * 注册状态变化回调
   */
  onStateChange(callback: (state: GameState) => void): void {
    this.stateChangeCallbacks.push(callback);
  }

  /**
   * 移除状态变化回调
   */
  removeStateChangeCallback(callback: (state: GameState) => void): void {
    const index = this.stateChangeCallbacks.indexOf(callback);
    if (index > -1) {
      this.stateChangeCallbacks.splice(index, 1);
    }
  }

  /**
   * 获取可用的视觉提供者
   */
  getAvailableProviders(): VisionProvider[] {
    return this.analyzerFactory.getAvailableProviders();
  }

  /**
   * 获取最后的游戏状态
   */
  getLastGameState(): GameState | null {
    return this.lastGameState;
  }

  /**
   * 设置事件处理器
   */
  private setupEventHandlers(): void {
    // 处理捕获的帧
    this.screenCapture.onFrame((frame) => {
      this.pendingFrame = frame;
    });

    // 处理捕获错误
    this.screenCapture.onError((error) => {
      this.lastError = error.message;
      this.emit('captureError', error);

      // 尝试重连
      this.attemptReconnect();
    });

    // 监控 CPU 使用率
    this.cpuMonitor.onUsageChange((usage) => {
      if (usage > this.config.maxCpuUsage!) {
        this.emit('highCpuUsage', usage);
      }
    });
  }

  /**
   * 开始分析循环
   */
  private startAnalysisLoop(): void {
    this.analysisInterval = setInterval(async () => {
      if (!this.pendingFrame || this.isAnalyzing || !this.currentAnalyzer) {
        return;
      }

      this.isAnalyzing = true;
      const frame = this.pendingFrame;
      this.pendingFrame = null;

      try {
        const analysis = await this.performAnalysis(frame);
        const gameState = this.createGameState(analysis, frame);

        // 检测显著变化
        gameState.significantChange = this.detectSignificantChange(analysis);

        // 更新最后状态
        this.lastAnalysis = analysis;
        this.lastGameState = gameState;

        // 通知状态变化
        if (gameState.significantChange) {
          this.notifyStateChange(gameState);
        }

        this.emit('frameAnalyzed', gameState);
      } catch (error) {
        this.lastError = (error as Error).message;
        this.emit('analysisError', error);
      } finally {
        this.isAnalyzing = false;
      }
    }, this.config.analysisInterval);
  }

  /**
   * 执行分析
   */
  private async performAnalysis(frame: CapturedFrame): Promise<FrameAnalysis> {
    if (!this.currentAnalyzer) {
      return {
        environment: 'No analyzer available',
        detectedObjects: [],
      };
    }

    return this.currentAnalyzer.analyze(frame);
  }

  /**
   * 创建游戏状态
   */
  private createGameState(analysis: FrameAnalysis, frame: CapturedFrame): GameState {
    return {
      timestamp: frame.timestamp,
      rawFrame: frame.data,
      analysis: {
        playerPosition: analysis.playerPosition,
        health: analysis.health,
        inventory: analysis.inventory,
        environment: analysis.environment,
        detectedObjects: analysis.detectedObjects.map((obj) => ({
          type: obj.type,
          name: obj.name,
          boundingBox: obj.boundingBox,
          confidence: obj.confidence,
        })),
      },
      significantChange: false,
    };
  }

  /**
   * 检测显著变化
   */
  private detectSignificantChange(currentAnalysis: FrameAnalysis): boolean {
    if (!this.lastAnalysis) {
      return true; // 第一帧总是显著变化
    }

    const config = this.config.changeDetection!;

    // 检查环境变化
    if (currentAnalysis.environment !== this.lastAnalysis.environment) {
      return true;
    }

    // 检查血量变化
    if (
      currentAnalysis.health !== undefined &&
      this.lastAnalysis.health !== undefined &&
      Math.abs(currentAnalysis.health - this.lastAnalysis.health) > 10
    ) {
      return true;
    }

    // 检查玩家位置变化
    if (currentAnalysis.playerPosition && this.lastAnalysis.playerPosition) {
      const dx = currentAnalysis.playerPosition.x - this.lastAnalysis.playerPosition.x;
      const dy = currentAnalysis.playerPosition.y - this.lastAnalysis.playerPosition.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance > config.minChangeArea) {
        return true;
      }
    }

    // 检查检测对象数量变化
    const currentObjectCount = currentAnalysis.detectedObjects.length;
    const lastObjectCount = this.lastAnalysis.detectedObjects.length;

    if (Math.abs(currentObjectCount - lastObjectCount) >= 2) {
      return true;
    }

    return false;
  }

  /**
   * 通知状态变化
   */
  private notifyStateChange(state: GameState): void {
    for (const callback of this.stateChangeCallbacks) {
      try {
        callback(state);
      } catch (error) {
        console.error('State change callback error:', error);
      }
    }

    this.emit('stateChange', state);
  }

  /**
   * 尝试重连
   */
  private attemptReconnect(): void {
    if (!this.captureConfig) {
      return;
    }

    const maxRetries = 3;
    let retryCount = 0;

    const retry = () => {
      if (retryCount >= maxRetries) {
        this.emit('reconnectFailed');
        return;
      }

      retryCount++;
      const delay = Math.pow(2, retryCount) * 1000; // 指数退避

      setTimeout(() => {
        try {
          this.screenCapture.start(this.captureConfig!);
          this.emit('reconnected');
        } catch {
          retry();
        }
      }, delay);
    };

    retry();
  }

  /**
   * 销毁模块
   */
  destroy(): void {
    this.stopCapture();
    this.stateChangeCallbacks = [];
    this.removeAllListeners();
  }
}
