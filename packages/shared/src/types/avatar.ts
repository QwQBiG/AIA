/**
 * 虚拟形象配置接口
 */
export interface AvatarConfig {
  /** 形象类型 */
  type: 'live2d' | '3d';
  /** 模型路径 */
  modelPath: string;
  /** 缩放比例 */
  scale: number;
  /** 位置 */
  position: { x: number; y: number };
}

/**
 * 表情映射接口
 */
export interface ExpressionMapping {
  /** 情绪类型 */
  emotion: string;
  /** 表情名称 */
  expressionName: string;
  /** 过渡时间（毫秒） */
  transitionDuration: number;
}

/**
 * 口型数据接口
 */
export interface LipSyncData {
  /** 音素 */
  phoneme: string;
  /** 开始时间（毫秒） */
  startTime: number;
  /** 持续时间（毫秒） */
  duration: number;
  /** 强度 (0-1) */
  intensity: number;
}

/**
 * 空闲动画配置接口
 */
export interface IdleAnimationConfig {
  /** 是否启用 */
  enabled: boolean;
  /** 动画列表 */
  animations: string[];
  /** 切换间隔（毫秒） */
  interval: number;
}
