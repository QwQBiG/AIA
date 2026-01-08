import { GameState, CaptureConfig, VisionProvider } from '@digital-human/shared';

/**
 * 视觉模块接口
 */
export interface IVisionModule {
  /** 开始屏幕捕获 */
  startCapture(config: CaptureConfig): void;
  /** 停止屏幕捕获 */
  stopCapture(): void;
  /** 分析帧 */
  analyzeFrame(frame: Buffer): Promise<GameState>;
  /** 设置视觉提供者 */
  setVisionProvider(provider: VisionProvider): void;
  /** 获取当前状态 */
  getStatus(): VisionModuleStatus;
  /** 注册状态变化回调 */
  onStateChange(callback: (state: GameState) => void): void;
}

/**
 * 视觉模块状态
 */
export interface VisionModuleStatus {
  /** 是否正在捕获 */
  isCapturing: boolean;
  /** 当前帧率 */
  currentFps: number;
  /** CPU 使用率 */
  cpuUsage: number;
  /** 最后捕获时间 */
  lastCaptureTime?: Date;
  /** 错误信息 */
  lastError?: string;
  /** 当前提供者 */
  currentProvider: VisionProvider | null;
}

/**
 * 屏幕捕获器接口
 */
export interface IScreenCapture {
  /** 开始捕获 */
  start(config: CaptureConfig): void;
  /** 停止捕获 */
  stop(): void;
  /** 捕获单帧 */
  captureFrame(): Promise<CapturedFrame>;
  /** 是否正在捕获 */
  isCapturing(): boolean;
  /** 注册帧回调 */
  onFrame(callback: (frame: CapturedFrame) => void): void;
  /** 注册错误回调 */
  onError(callback: (error: Error) => void): void;
}

/**
 * 捕获的帧数据
 */
export interface CapturedFrame {
  /** 帧数据 */
  data: Buffer;
  /** 宽度 */
  width: number;
  /** 高度 */
  height: number;
  /** 捕获时间 */
  timestamp: Date;
  /** 格式 */
  format: 'png' | 'jpeg' | 'raw';
}

/**
 * 视觉分析提供者接口
 */
export interface IVisionAnalyzer {
  /** 分析帧 */
  analyze(frame: CapturedFrame): Promise<FrameAnalysis>;
  /** 获取提供者信息 */
  getProviderInfo(): VisionProvider;
  /** 是否可用 */
  isAvailable(): Promise<boolean>;
}

/**
 * 帧分析结果
 */
export interface FrameAnalysis {
  /** 玩家位置 */
  playerPosition?: { x: number; y: number };
  /** 血量 */
  health?: number;
  /** 物品栏 */
  inventory?: string[];
  /** 环境描述 */
  environment: string;
  /** 检测到的对象 */
  detectedObjects: DetectedObjectInfo[];
  /** 原始响应 */
  rawResponse?: string;
}

/**
 * 检测到的对象信息
 */
export interface DetectedObjectInfo {
  /** 对象类型 */
  type: string;
  /** 对象名称 */
  name: string;
  /** 边界框 */
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  /** 置信度 */
  confidence: number;
}

/**
 * CPU 监控器接口
 */
export interface ICpuMonitor {
  /** 获取当前 CPU 使用率 */
  getCurrentUsage(): number;
  /** 开始监控 */
  startMonitoring(intervalMs: number): void;
  /** 停止监控 */
  stopMonitoring(): void;
  /** 注册使用率变化回调 */
  onUsageChange(callback: (usage: number) => void): void;
}

/**
 * 帧率控制器配置
 */
export interface FrameRateControllerConfig {
  /** 目标帧率 */
  targetFps: number;
  /** 最小帧率 */
  minFps: number;
  /** 最大 CPU 使用率 */
  maxCpuUsage: number;
}

/**
 * 变化检测配置
 */
export interface ChangeDetectionConfig {
  /** 变化阈值 (0-1) */
  threshold: number;
  /** 最小变化区域 */
  minChangeArea: number;
  /** 忽略的区域 */
  ignoreRegions?: Array<{ x: number; y: number; width: number; height: number }>;
}
