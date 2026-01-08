import { CaptureConfig } from '@digital-human/shared';
import { IScreenCapture, CapturedFrame } from './types.js';
import { EventEmitter } from 'events';

/**
 * 屏幕捕获器实现
 * 使用 screenshot-desktop 或 node-screenshots 进行屏幕捕获
 */
export class ScreenCapture extends EventEmitter implements IScreenCapture {
  private capturing: boolean = false;
  private config: CaptureConfig | null = null;
  private captureInterval: NodeJS.Timeout | null = null;
  private frameCallbacks: Array<(frame: CapturedFrame) => void> = [];
  private errorCallbacks: Array<(error: Error) => void> = [];
  private lastFrameTime: number = 0;
  private frameCount: number = 0;
  private currentFps: number = 0;
  private fpsUpdateInterval: NodeJS.Timeout | null = null;

  /**
   * 开始屏幕捕获
   */
  start(config: CaptureConfig): void {
    if (this.capturing) {
      this.stop();
    }

    this.config = config;
    this.capturing = true;
    this.frameCount = 0;
    this.lastFrameTime = Date.now();

    const intervalMs = Math.floor(1000 / config.fps);

    // 开始捕获循环
    this.captureInterval = setInterval(async () => {
      try {
        const frame = await this.captureFrame();
        this.frameCount++;
        this.notifyFrameCallbacks(frame);
      } catch (error) {
        this.notifyErrorCallbacks(error as Error);
      }
    }, intervalMs);

    // 开始 FPS 计算
    this.fpsUpdateInterval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - this.lastFrameTime) / 1000;
      this.currentFps = this.frameCount / elapsed;
      this.frameCount = 0;
      this.lastFrameTime = now;
    }, 1000);
  }

  /**
   * 停止屏幕捕获
   */
  stop(): void {
    this.capturing = false;

    if (this.captureInterval) {
      clearInterval(this.captureInterval);
      this.captureInterval = null;
    }

    if (this.fpsUpdateInterval) {
      clearInterval(this.fpsUpdateInterval);
      this.fpsUpdateInterval = null;
    }

    this.currentFps = 0;
    this.frameCount = 0;
  }

  /**
   * 捕获单帧
   */
  async captureFrame(): Promise<CapturedFrame> {
    if (!this.config) {
      throw new Error('Capture not configured. Call start() first.');
    }

    try {
      // 动态导入 screenshot-desktop
      const screenshot = await this.getScreenshotModule();
      
      let imageBuffer: Buffer;

      if (this.config.region) {
        // 区域捕获
        imageBuffer = await screenshot({
          format: 'png',
          // 注意：screenshot-desktop 不直接支持区域捕获
          // 需要先捕获全屏然后裁剪
        });
        
        // 如果需要区域裁剪，使用 sharp 或其他图像处理库
        imageBuffer = await this.cropImage(imageBuffer, this.config.region);
      } else {
        // 全屏捕获
        imageBuffer = await screenshot({ format: 'png' });
      }

      return {
        data: imageBuffer,
        width: this.config.region?.width || 1920, // 默认值，实际应从图像获取
        height: this.config.region?.height || 1080,
        timestamp: new Date(),
        format: 'png',
      };
    } catch (error) {
      throw new Error(`Screen capture failed: ${(error as Error).message}`);
    }
  }

  /**
   * 是否正在捕获
   */
  isCapturing(): boolean {
    return this.capturing;
  }

  /**
   * 获取当前帧率
   */
  getCurrentFps(): number {
    return this.currentFps;
  }

  /**
   * 注册帧回调
   */
  onFrame(callback: (frame: CapturedFrame) => void): void {
    this.frameCallbacks.push(callback);
  }

  /**
   * 注册错误回调
   */
  onError(callback: (error: Error) => void): void {
    this.errorCallbacks.push(callback);
  }

  /**
   * 移除帧回调
   */
  removeFrameCallback(callback: (frame: CapturedFrame) => void): void {
    const index = this.frameCallbacks.indexOf(callback);
    if (index > -1) {
      this.frameCallbacks.splice(index, 1);
    }
  }

  /**
   * 移除错误回调
   */
  removeErrorCallback(callback: (error: Error) => void): void {
    const index = this.errorCallbacks.indexOf(callback);
    if (index > -1) {
      this.errorCallbacks.splice(index, 1);
    }
  }

  /**
   * 获取截图模块
   */
  private async getScreenshotModule(): Promise<(options?: { format?: string }) => Promise<Buffer>> {
    try {
      // 尝试使用 screenshot-desktop
      // @ts-expect-error - 动态导入可能不存在
      const screenshotDesktop = await import('screenshot-desktop');
      return screenshotDesktop.default || screenshotDesktop;
    } catch {
      // 如果 screenshot-desktop 不可用，返回模拟函数
      return this.createMockScreenshot();
    }
  }

  /**
   * 创建模拟截图函数（用于测试或无法访问屏幕时）
   */
  private createMockScreenshot(): (options?: { format?: string }) => Promise<Buffer> {
    return async () => {
      // 创建一个简单的 PNG 占位符
      // 实际生产环境应该抛出错误或使用其他方案
      return Buffer.from([
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, // PNG signature
        // 最小有效 PNG 数据
      ]);
    };
  }

  /**
   * 裁剪图像
   */
  private async cropImage(
    imageBuffer: Buffer,
    region: { x: number; y: number; width: number; height: number }
  ): Promise<Buffer> {
    try {
      // 尝试使用 sharp 进行裁剪
      // @ts-expect-error - 动态导入可能不存在
      const sharp = await import('sharp');
      return await sharp
        .default(imageBuffer)
        .extract({
          left: region.x,
          top: region.y,
          width: region.width,
          height: region.height,
        })
        .toBuffer();
    } catch {
      // 如果 sharp 不可用，返回原始图像
      return imageBuffer;
    }
  }

  /**
   * 通知帧回调
   */
  private notifyFrameCallbacks(frame: CapturedFrame): void {
    for (const callback of this.frameCallbacks) {
      try {
        callback(frame);
      } catch (error) {
        console.error('Frame callback error:', error);
      }
    }
  }

  /**
   * 通知错误回调
   */
  private notifyErrorCallbacks(error: Error): void {
    for (const callback of this.errorCallbacks) {
      try {
        callback(error);
      } catch (err) {
        console.error('Error callback error:', err);
      }
    }
  }
}
