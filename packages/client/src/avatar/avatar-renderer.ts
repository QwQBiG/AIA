/// <reference lib="dom" />
/// <reference lib="dom.iterable" />

import { EmotionType } from '@digital-human/shared';
import {
  AvatarConfig,
  AvatarLoadResult,
  AudioStream,
  IAvatarRenderer,
  ExpressionMapping,
  IdleAnimationConfig,
} from './types.js';

// 声明全局类型以支持测试环境
declare const window: Window & typeof globalThis;
declare const document: Document;
declare function requestAnimationFrame(callback: FrameRequestCallback): number;
declare function cancelAnimationFrame(handle: number): void;

/**
 * 默认表情映射
 */
const DEFAULT_EXPRESSION_MAPPINGS: ExpressionMapping[] = [
  { emotion: 'neutral', expressionName: 'neutral', transitionDuration: 300 },
  { emotion: 'happy', expressionName: 'happy', transitionDuration: 200 },
  { emotion: 'sad', expressionName: 'sad', transitionDuration: 400 },
  { emotion: 'surprised', expressionName: 'surprised', transitionDuration: 150 },
  { emotion: 'angry', expressionName: 'angry', transitionDuration: 250 },
  { emotion: 'thinking', expressionName: 'thinking', transitionDuration: 350 },
];

/**
 * 默认空闲动画配置
 */
const DEFAULT_IDLE_CONFIG: IdleAnimationConfig = {
  enabled: true,
  animations: ['idle', 'blink', 'breathe'],
  interval: 5000,
};

/**
 * 加载超时时间（毫秒）
 */
const LOAD_TIMEOUT = 5000;

/**
 * 检查是否在浏览器环境
 */
function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

/**
 * Avatar 渲染器实现
 * 支持 Live2D 和 Three.js 3D 模型
 */
export class AvatarRenderer implements IAvatarRenderer {
  private config: AvatarConfig | null = null;
  private loaded = false;
  private currentExpression: EmotionType = 'neutral';
  private expressionMappings: ExpressionMapping[] = DEFAULT_EXPRESSION_MAPPINGS;
  private idleConfig: IdleAnimationConfig = { ...DEFAULT_IDLE_CONFIG };
  private idleAnimationTimer: ReturnType<typeof setInterval> | null = null;
  private lipSyncActive = false;
  private canvas: HTMLCanvasElement | null = null;

  
  // Live2D 相关
  private live2dApp: unknown = null;
  private live2dModel: unknown = null;
  
  // Three.js 相关
  private threeRenderer: unknown = null;
  private threeScene: unknown = null;
  private threeCamera: unknown = null;
  private threeModel: unknown = null;
  private animationFrameId: number | null = null;

  constructor(canvas?: HTMLCanvasElement) {
    this.canvas = canvas || null;
  }

  /**
   * 加载 Avatar 模型
   * @param config Avatar 配置
   * @returns 加载结果
   */
  async loadAvatar(config: AvatarConfig): Promise<AvatarLoadResult> {
    const startTime = Date.now();
    
    try {
      // 如果已加载，先卸载
      if (this.loaded) {
        this.unloadAvatar();
      }

      this.config = config;

      // 创建带超时的加载 Promise
      const loadPromise = config.type === 'live2d'
        ? this.loadLive2DModel(config)
        : this.load3DModel(config);

      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('Avatar load timeout')), LOAD_TIMEOUT);
      });

      await Promise.race([loadPromise, timeoutPromise]);

      this.loaded = true;
      const loadTime = Date.now() - startTime;

      // 启动空闲动画
      if (this.idleConfig.enabled) {
        this.startIdleAnimations();
      }

      return {
        success: true,
        loadTime,
      };
    } catch (error) {
      const loadTime = Date.now() - startTime;
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      // 显示占位符
      this.showPlaceholder();
      
      return {
        success: false,
        loadTime,
        error: errorMessage,
      };
    }
  }

  /**
   * 加载 Live2D 模型
   */
  private async loadLive2DModel(_config: AvatarConfig): Promise<void> {
    // 在浏览器环境中尝试加载真实的 Live2D 模型
    // 在测试环境中使用模拟实现
    if (isBrowser() && this.canvas) {
      try {
        // 动态导入 - 在实际环境中会加载真实模块
        const PIXI = await import('pixi.js');
        const { Live2DModel } = await import('pixi-live2d-display');
        
        this.live2dApp = new PIXI.Application({
          view: this.canvas as unknown as HTMLCanvasElement,
          autoStart: true,
          backgroundAlpha: 0,
        });

        this.live2dModel = await Live2DModel.from(_config.modelPath);
        const model = this.live2dModel as { scale: { set: (s: number) => void }; x: number; y: number };
        model.scale.set(_config.scale);
        model.x = _config.position.x;
        model.y = _config.position.y;
        
        (this.live2dApp as { stage: { addChild: (m: unknown) => void } }).stage.addChild(this.live2dModel);
      } catch {
        // 如果导入失败，使用模拟模式
        this.live2dModel = this.createMockLive2DModel();
      }
    } else {
      // 测试环境或无 canvas，使用模拟模式
      this.live2dModel = this.createMockLive2DModel();
    }
  }

  /**
   * 创建模拟 Live2D 模型（用于测试）
   */
  private createMockLive2DModel(): Record<string, unknown> {
    return {
      expression: (_name: string) => {},
      motion: (_group: string, _index?: number) => {},
      speak: (_audioUrl: string) => {},
      stopSpeaking: () => {},
      destroy: () => {},
    };
  }


  /**
   * 加载 3D 模型
   */
  private async load3DModel(_config: AvatarConfig): Promise<void> {
    if (isBrowser() && this.canvas) {
      try {
        const THREE = await import('three');
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
        
        // 创建场景
        this.threeScene = new THREE.Scene();
        
        // 创建相机
        this.threeCamera = new THREE.PerspectiveCamera(
          75,
          this.canvas.width / this.canvas.height,
          0.1,
          1000
        );
        (this.threeCamera as { position: { z: number } }).position.z = 5;
        
        // 创建渲染器
        this.threeRenderer = new THREE.WebGLRenderer({
          canvas: this.canvas,
          alpha: true,
        });
        
        // 添加光源
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        (this.threeScene as { add: (obj: unknown) => void }).add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(0, 1, 1);
        (this.threeScene as { add: (obj: unknown) => void }).add(directionalLight);
        
        // 加载模型
        const loader = new GLTFLoader();
        const gltf = await new Promise<{ scene: unknown }>((resolve, reject) => {
          loader.load(_config.modelPath, resolve as (gltf: unknown) => void, undefined, reject);
        });
        
        this.threeModel = gltf.scene;
        const model = this.threeModel as { 
          scale: { setScalar: (s: number) => void }; 
          position: { set: (x: number, y: number, z: number) => void } 
        };
        model.scale.setScalar(_config.scale);
        model.position.set(_config.position.x, _config.position.y, 0);
        (this.threeScene as { add: (obj: unknown) => void }).add(this.threeModel);
        
        // 开始渲染循环
        this.startRenderLoop();
      } catch {
        // 如果导入失败，使用模拟模式
        this.threeModel = this.createMock3DModel();
      }
    } else {
      // 测试环境或无 canvas，使用模拟模式
      this.threeModel = this.createMock3DModel();
    }
  }

  /**
   * 创建模拟 3D 模型（用于测试）
   */
  private createMock3DModel(): Record<string, unknown> {
    return {
      setMorphTarget: (_name: string, _value: number) => {},
      playAnimation: (_name: string) => {},
      stopAnimation: () => {},
      dispose: () => {},
    };
  }

  /**
   * 开始 Three.js 渲染循环
   */
  private startRenderLoop(): void {
    if (!isBrowser()) return;
    
    const animate = () => {
      this.animationFrameId = requestAnimationFrame(animate);
      if (this.threeRenderer && this.threeScene && this.threeCamera) {
        const renderer = this.threeRenderer as { render: (scene: unknown, camera: unknown) => void };
        renderer.render(this.threeScene, this.threeCamera);
      }
    };
    animate();
  }

  /**
   * 显示占位符（加载失败时）
   */
  private showPlaceholder(): void {
    if (this.canvas && isBrowser()) {
      const ctx = this.canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#333';
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Avatar Loading Failed', this.canvas.width / 2, this.canvas.height / 2);
      }
    }
  }


  /**
   * 卸载 Avatar
   */
  unloadAvatar(): void {
    this.stopIdleAnimations();
    this.stopLipSync();
    
    if (this.config?.type === 'live2d') {
      if (this.live2dModel) {
        const model = this.live2dModel as { destroy?: () => void };
        model.destroy?.();
        this.live2dModel = null;
      }
      if (this.live2dApp) {
        const app = this.live2dApp as { destroy?: (removeView?: boolean) => void };
        app.destroy?.(true);
        this.live2dApp = null;
      }
    } else {
      if (this.animationFrameId !== null && isBrowser()) {
        cancelAnimationFrame(this.animationFrameId);
        this.animationFrameId = null;
      }
      if (this.threeModel) {
        const model = this.threeModel as { dispose?: () => void };
        model.dispose?.();
        this.threeModel = null;
      }
      if (this.threeRenderer) {
        const renderer = this.threeRenderer as { dispose?: () => void };
        renderer.dispose?.();
        this.threeRenderer = null;
      }
      this.threeScene = null;
      this.threeCamera = null;
    }
    
    this.loaded = false;
    this.config = null;
    this.currentExpression = 'neutral';
  }

  /**
   * 设置表情
   * @param emotion 情绪类型
   */
  setExpression(emotion: EmotionType): void {
    if (!this.loaded) return;
    
    const mapping = this.expressionMappings.find(m => m.emotion === emotion);
    if (!mapping) return;
    
    this.currentExpression = emotion;
    
    if (this.config?.type === 'live2d' && this.live2dModel) {
      const model = this.live2dModel as { expression?: (name: string) => void };
      model.expression?.(mapping.expressionName);
    } else if (this.threeModel) {
      // 3D 模型使用 morph targets
      this.setMorphTargetForEmotion(emotion);
    }
  }

  /**
   * 为 3D 模型设置表情 morph target
   */
  private setMorphTargetForEmotion(emotion: EmotionType): void {
    if (!this.threeModel) return;
    
    const model = this.threeModel as { setMorphTarget?: (name: string, value: number) => void };
    // 重置所有表情
    const emotions: EmotionType[] = ['neutral', 'happy', 'sad', 'surprised', 'angry', 'thinking'];
    emotions.forEach(e => {
      model.setMorphTarget?.(e, e === emotion ? 1 : 0);
    });
  }

  /**
   * 播放动画
   * @param animationName 动画名称
   */
  playAnimation(animationName: string): void {
    if (!this.loaded) return;
    
    if (this.config?.type === 'live2d' && this.live2dModel) {
      const model = this.live2dModel as { motion?: (group: string, index?: number) => void };
      model.motion?.(animationName);
    } else if (this.threeModel) {
      const model = this.threeModel as { playAnimation?: (name: string) => void };
      model.playAnimation?.(animationName);
    }
  }

  /**
   * 开始口型同步
   * @param audioStream 音频流
   */
  startLipSync(audioStream: AudioStream): void {
    if (!this.loaded || this.lipSyncActive) return;
    
    this.lipSyncActive = true;
    
    if (this.config?.type === 'live2d' && this.live2dModel) {
      // Live2D 使用内置的口型同步
      if (audioStream.data instanceof ArrayBuffer && isBrowser()) {
        const blob = new Blob([audioStream.data], { type: `audio/${audioStream.format}` });
        const url = URL.createObjectURL(blob);
        const model = this.live2dModel as { speak?: (url: string) => void };
        model.speak?.(url);
      }
    } else if (this.threeModel) {
      // 3D 模型使用音频分析进行口型同步
      this.startAudioAnalysisLipSync(audioStream);
    }
  }


  /**
   * 基于音频分析的口型同步（3D 模型）
   */
  private startAudioAnalysisLipSync(audioStream: AudioStream): void {
    if (!isBrowser()) return;
    
    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;
      
      const audioContext = new AudioContextClass();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      
      if (audioStream.data instanceof ArrayBuffer) {
        audioContext.decodeAudioData(audioStream.data).then(buffer => {
          const source = audioContext.createBufferSource();
          source.buffer = buffer;
          source.connect(analyser);
          analyser.connect(audioContext.destination);
          source.start();
          
          // 分析音频并更新口型
          const dataArray = new Uint8Array(analyser.frequencyBinCount);
          const updateLipSync = () => {
            if (!this.lipSyncActive) return;
            
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            const mouthOpen = Math.min(average / 128, 1);
            
            const model = this.threeModel as { setMorphTarget?: (name: string, value: number) => void };
            model?.setMorphTarget?.('mouthOpen', mouthOpen);
            
            requestAnimationFrame(updateLipSync);
          };
          updateLipSync();
          
          source.onended = () => {
            this.lipSyncActive = false;
            const model = this.threeModel as { setMorphTarget?: (name: string, value: number) => void };
            model?.setMorphTarget?.('mouthOpen', 0);
          };
        }).catch(() => {
          this.lipSyncActive = false;
        });
      }
    } catch {
      // 音频分析失败，静默处理
      this.lipSyncActive = false;
    }
  }

  /**
   * 停止口型同步
   */
  stopLipSync(): void {
    this.lipSyncActive = false;
    
    if (this.config?.type === 'live2d' && this.live2dModel) {
      const model = this.live2dModel as { stopSpeaking?: () => void };
      model.stopSpeaking?.();
    } else if (this.threeModel) {
      const model = this.threeModel as { setMorphTarget?: (name: string, value: number) => void };
      model.setMorphTarget?.('mouthOpen', 0);
    }
  }

  /**
   * 设置空闲动画
   * @param enabled 是否启用
   */
  setIdleAnimation(enabled: boolean): void {
    this.idleConfig.enabled = enabled;
    
    if (enabled && this.loaded) {
      this.startIdleAnimations();
    } else {
      this.stopIdleAnimations();
    }
  }

  /**
   * 开始空闲动画循环
   */
  private startIdleAnimations(): void {
    if (this.idleAnimationTimer) return;
    
    let animationIndex = 0;
    
    const playNextIdle = () => {
      if (!this.loaded || !this.idleConfig.enabled) return;
      
      const animation = this.idleConfig.animations[animationIndex];
      this.playAnimation(animation);
      
      animationIndex = (animationIndex + 1) % this.idleConfig.animations.length;
    };
    
    // 立即播放第一个
    playNextIdle();
    
    // 设置定时器循环播放
    this.idleAnimationTimer = setInterval(playNextIdle, this.idleConfig.interval);
  }

  /**
   * 停止空闲动画循环
   */
  private stopIdleAnimations(): void {
    if (this.idleAnimationTimer) {
      clearInterval(this.idleAnimationTimer);
      this.idleAnimationTimer = null;
    }
  }


  /**
   * 获取当前表情
   */
  getCurrentExpression(): EmotionType {
    return this.currentExpression;
  }

  /**
   * 检查是否已加载
   */
  isLoaded(): boolean {
    return this.loaded;
  }

  /**
   * 配置表情映射
   * @param mappings 表情映射配置
   */
  setExpressionMappings(mappings: ExpressionMapping[]): void {
    this.expressionMappings = mappings;
  }

  /**
   * 配置空闲动画
   * @param config 空闲动画配置
   */
  setIdleAnimationConfig(config: IdleAnimationConfig): void {
    this.idleConfig = { ...config };
    
    // 如果配置改变且已加载，重新启动空闲动画
    if (this.loaded) {
      this.stopIdleAnimations();
      if (config.enabled) {
        this.startIdleAnimations();
      }
    }
  }

  /**
   * 获取所有支持的表情类型
   */
  getSupportedEmotions(): EmotionType[] {
    return this.expressionMappings.map(m => m.emotion);
  }

  /**
   * 销毁渲染器
   */
  destroy(): void {
    this.unloadAvatar();
    this.canvas = null;
  }
}

/**
 * 创建 Avatar 渲染器实例
 * @param canvas 可选的 canvas 元素
 */
export function createAvatarRenderer(canvas?: HTMLCanvasElement): IAvatarRenderer {
  return new AvatarRenderer(canvas);
}
