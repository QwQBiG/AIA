import { ControlMode } from './enums.js';

/**
 * 游戏输入接口
 */
export interface GameInput {
  /** 输入类型 */
  type: 'keyboard' | 'mouse' | 'gamepad';
  /** 动作类型 */
  action: 'press' | 'release' | 'move' | 'click';
  /** 按键（可选） */
  key?: string;
  /** 位置（可选） */
  position?: { x: number; y: number };
  /** 按钮（可选） */
  button?: string;
  /** 持续时间（可选，毫秒） */
  duration?: number;
}

/**
 * 游戏动作接口
 */
export interface GameAction {
  /** 动作名称 */
  name: string;
  /** 输入命令列表 */
  inputs: GameInput[];
  /** 动作描述 */
  description: string;
}

/**
 * 动作执行结果接口
 */
export interface ActionResult {
  /** 是否成功 */
  success: boolean;
  /** 错误信息（可选） */
  error?: string;
  /** 执行时间 */
  executedAt: Date;
}

/**
 * 检测到的对象接口
 */
export interface DetectedObject {
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
 * 游戏状态接口
 */
export interface GameState {
  /** 时间戳 */
  timestamp: Date;
  /** 原始帧数据（可选） */
  rawFrame?: Buffer;
  /** 分析结果 */
  analysis: {
    /** 玩家位置（可选） */
    playerPosition?: { x: number; y: number };
    /** 血量（可选） */
    health?: number;
    /** 物品栏（可选） */
    inventory?: string[];
    /** 环境描述 */
    environment: string;
    /** 检测到的对象列表 */
    detectedObjects: DetectedObject[];
  };
  /** 是否有显著变化 */
  significantChange: boolean;
}

/**
 * 捕获配置接口
 */
export interface CaptureConfig {
  /** 目标窗口名称（可选） */
  targetWindow?: string;
  /** 捕获区域（可选） */
  region?: { x: number; y: number; width: number; height: number };
  /** 帧率 */
  fps: number;
}

/**
 * 视觉提供者配置接口
 */
export interface VisionProvider {
  /** 提供者类型 */
  type: 'cloud' | 'local';
  /** 提供者名称 */
  name: string;
  /** 模型名称 */
  model: string;
  /** API 端点（可选） */
  endpoint?: string;
}

/**
 * 游戏控制器配置接口
 */
export interface GameControllerConfig {
  /** 控制模式 */
  mode: ControlMode;
  /** 允许的动作列表 */
  allowedActions: string[];
  /** 输入延迟（毫秒） */
  inputDelay: number;
}
