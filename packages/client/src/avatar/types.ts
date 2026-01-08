import { EmotionType } from '@digital-human/shared';

/**
 * Avatar 配置接口
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
 * Avatar 加载结果
 */
export interface AvatarLoadResult {
  success: boolean;
  loadTime: number;
  error?: string;
}

/**
 * 音频流接口
 */
export interface AudioStream {
  format: 'wav' | 'mp3' | 'pcm';
  sampleRate: number;
  data: ArrayBuffer | ReadableStream<Uint8Array>;
  duration: number;
}

/**
 * 表情映射配置
 */
export interface ExpressionMapping {
  emotion: EmotionType;
  expressionName: string;
  transitionDuration: number;
}

/**
 * 空闲动画配置
 */
export interface IdleAnimationConfig {
  enabled: boolean;
  animations: string[];
  interval: number;
}

/**
 * Avatar 渲染器接口
 */
export interface IAvatarRenderer {
  /** 加载 Avatar */
  loadAvatar(config: AvatarConfig): Promise<AvatarLoadResult>;
  
  /** 卸载 Avatar */
  unloadAvatar(): void;
  
  /** 设置表情 */
  setExpression(emotion: EmotionType): void;
  
  /** 播放动画 */
  playAnimation(animationName: string): void;
  
  /** 开始口型同步 */
  startLipSync(audioStream: AudioStream): void;
  
  /** 停止口型同步 */
  stopLipSync(): void;
  
  /** 设置空闲动画 */
  setIdleAnimation(enabled: boolean): void;
  
  /** 获取当前表情 */
  getCurrentExpression(): EmotionType;
  
  /** 检查是否已加载 */
  isLoaded(): boolean;
  
  /** 销毁渲染器 */
  destroy(): void;
}

/**
 * Live2D 模型接口（简化版）
 */
export interface Live2DModel {
  expression(name: string): void;
  motion(group: string, index?: number): void;
  speak(audioUrl: string): void;
  stopSpeaking(): void;
  destroy(): void;
}

/**
 * 3D 模型接口（简化版）
 */
export interface ThreeModel {
  setMorphTarget(name: string, value: number): void;
  playAnimation(name: string): void;
  stopAnimation(): void;
  dispose(): void;
}
