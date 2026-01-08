import { CpuMonitor, FrameRateController } from './cpu-monitor.js';

describe('CpuMonitor', () => {
  let cpuMonitor: CpuMonitor;

  beforeEach(() => {
    cpuMonitor = new CpuMonitor();
  });

  afterEach(() => {
    cpuMonitor.stopMonitoring();
  });

  describe('getCurrentUsage', () => {
    it('should return 0 initially', () => {
      expect(cpuMonitor.getCurrentUsage()).toBe(0);
    });
  });

  describe('startMonitoring', () => {
    it('should start monitoring without error', () => {
      expect(() => cpuMonitor.startMonitoring(1000)).not.toThrow();
    });

    it('should stop previous monitoring before starting new one', () => {
      cpuMonitor.startMonitoring(1000);
      expect(() => cpuMonitor.startMonitoring(500)).not.toThrow();
    });
  });

  describe('stopMonitoring', () => {
    it('should stop monitoring without error', () => {
      cpuMonitor.startMonitoring(1000);
      expect(() => cpuMonitor.stopMonitoring()).not.toThrow();
    });

    it('should be safe to call multiple times', () => {
      cpuMonitor.startMonitoring(1000);
      cpuMonitor.stopMonitoring();
      expect(() => cpuMonitor.stopMonitoring()).not.toThrow();
    });
  });

  describe('onUsageChange', () => {
    it('should register usage change callback', () => {
      const callback = jest.fn();

      cpuMonitor.onUsageChange(callback);

      const callbacks = (cpuMonitor as unknown as { usageCallbacks: Array<(usage: number) => void> })
        .usageCallbacks;
      expect(callbacks).toContain(callback);
    });
  });

  describe('removeUsageCallback', () => {
    it('should remove usage change callback', () => {
      const callback = jest.fn();

      cpuMonitor.onUsageChange(callback);
      cpuMonitor.removeUsageCallback(callback);

      const callbacks = (cpuMonitor as unknown as { usageCallbacks: Array<(usage: number) => void> })
        .usageCallbacks;
      expect(callbacks).not.toContain(callback);
    });
  });

  describe('CPU usage calculation', () => {
    it('should update CPU usage after monitoring interval', (done) => {
      cpuMonitor.startMonitoring(100);

      // 等待两个监控周期
      setTimeout(() => {
        const usage = cpuMonitor.getCurrentUsage();
        // CPU 使用率应该是 0-100 之间的数字
        expect(typeof usage).toBe('number');
        expect(usage).toBeGreaterThanOrEqual(0);
        expect(usage).toBeLessThanOrEqual(100);
        done();
      }, 250);
    });
  });
});

describe('FrameRateController', () => {
  let controller: FrameRateController;

  beforeEach(() => {
    controller = new FrameRateController({
      targetFps: 30,
      minFps: 10,
      maxCpuUsage: 30,
    });
  });

  afterEach(() => {
    controller.stop();
  });

  describe('getCurrentFps', () => {
    it('should return target FPS initially', () => {
      expect(controller.getCurrentFps()).toBe(30);
    });
  });

  describe('getCpuUsage', () => {
    it('should return 0 initially', () => {
      expect(controller.getCpuUsage()).toBe(0);
    });
  });

  describe('start', () => {
    it('should start without error', () => {
      expect(() => controller.start()).not.toThrow();
    });
  });

  describe('stop', () => {
    it('should stop without error', () => {
      controller.start();
      expect(() => controller.stop()).not.toThrow();
    });
  });

  describe('frame rate adjustment', () => {
    it('should maintain FPS within bounds', () => {
      controller.start();

      const fps = controller.getCurrentFps();
      expect(fps).toBeGreaterThanOrEqual(10);
      expect(fps).toBeLessThanOrEqual(30);
    });
  });
});
