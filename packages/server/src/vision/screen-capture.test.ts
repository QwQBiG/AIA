import { ScreenCapture } from './screen-capture.js';
import { CapturedFrame } from './types.js';

// 定义 CaptureConfig 类型
interface CaptureConfig {
  targetWindow?: string;
  region?: { x: number; y: number; width: number; height: number };
  fps: number;
}

describe('ScreenCapture', () => {
  let screenCapture: ScreenCapture;

  beforeEach(() => {
    screenCapture = new ScreenCapture();
  });

  afterEach(() => {
    screenCapture.stop();
  });

  describe('isCapturing', () => {
    it('should return false initially', () => {
      expect(screenCapture.isCapturing()).toBe(false);
    });

    it('should return true after starting capture', () => {
      const config: CaptureConfig = { fps: 10 };

      screenCapture.start(config);

      expect(screenCapture.isCapturing()).toBe(true);
    });

    it('should return false after stopping capture', () => {
      const config: CaptureConfig = { fps: 10 };

      screenCapture.start(config);
      screenCapture.stop();

      expect(screenCapture.isCapturing()).toBe(false);
    });
  });

  describe('start', () => {
    it('should stop previous capture before starting new one', () => {
      const config1: CaptureConfig = { fps: 10 };
      const config2: CaptureConfig = { fps: 20 };

      screenCapture.start(config1);
      screenCapture.start(config2);

      expect(screenCapture.isCapturing()).toBe(true);
    });
  });

  describe('stop', () => {
    it('should reset FPS counter', () => {
      const config: CaptureConfig = { fps: 10 };

      screenCapture.start(config);
      screenCapture.stop();

      expect(screenCapture.getCurrentFps()).toBe(0);
    });
  });

  describe('getCurrentFps', () => {
    it('should return 0 when not capturing', () => {
      expect(screenCapture.getCurrentFps()).toBe(0);
    });
  });

  describe('onFrame', () => {
    it('should register frame callback', () => {
      const callback = jest.fn();

      screenCapture.onFrame(callback);

      // 验证回调已注册
      const callbacks = (screenCapture as unknown as { frameCallbacks: Array<(frame: CapturedFrame) => void> })
        .frameCallbacks;
      expect(callbacks).toContain(callback);
    });
  });

  describe('onError', () => {
    it('should register error callback', () => {
      const callback = jest.fn();

      screenCapture.onError(callback);

      // 验证回调已注册
      const callbacks = (screenCapture as unknown as { errorCallbacks: Array<(error: Error) => void> })
        .errorCallbacks;
      expect(callbacks).toContain(callback);
    });
  });

  describe('removeFrameCallback', () => {
    it('should remove frame callback', () => {
      const callback = jest.fn();

      screenCapture.onFrame(callback);
      screenCapture.removeFrameCallback(callback);

      const callbacks = (screenCapture as unknown as { frameCallbacks: Array<(frame: CapturedFrame) => void> })
        .frameCallbacks;
      expect(callbacks).not.toContain(callback);
    });
  });

  describe('removeErrorCallback', () => {
    it('should remove error callback', () => {
      const callback = jest.fn();

      screenCapture.onError(callback);
      screenCapture.removeErrorCallback(callback);

      const callbacks = (screenCapture as unknown as { errorCallbacks: Array<(error: Error) => void> })
        .errorCallbacks;
      expect(callbacks).not.toContain(callback);
    });
  });

  describe('captureFrame', () => {
    it('should throw error when not configured', async () => {
      await expect(screenCapture.captureFrame()).rejects.toThrow(
        'Capture not configured. Call start() first.'
      );
    });
  });
});
