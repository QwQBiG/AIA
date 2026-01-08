import { ICpuMonitor } from './types.js';
import * as os from 'os';

/**
 * CPU 监控器实现
 * 监控系统 CPU 使用率，用于动态调整捕获帧率
 */
export class CpuMonitor implements ICpuMonitor {
  private monitoring: boolean = false;
  private monitorInterval: NodeJS.Timeout | null = null;
  private currentUsage: number = 0;
  private usageCallbacks: Array<(usage: number) => void> = [];
  private previousCpuInfo: { idle: number; total: number } | null = null;

  /**
   * 获取当前 CPU 使用率
   * @returns CPU 使用率 (0-100)
   */
  getCurrentUsage(): number {
    return this.currentUsage;
  }

  /**
   * 开始监控
   * @param intervalMs 监控间隔（毫秒）
   */
  startMonitoring(intervalMs: number = 1000): void {
    if (this.monitoring) {
      this.stopMonitoring();
    }

    this.monitoring = true;
    this.previousCpuInfo = this.getCpuInfo();

    this.monitorInterval = setInterval(() => {
      this.updateCpuUsage();
    }, intervalMs);
  }

  /**
   * 停止监控
   */
  stopMonitoring(): void {
    this.monitoring = false;

    if (this.monitorInterval) {
      clearInterval(this.monitorInterval);
      this.monitorInterval = null;
    }

    this.previousCpuInfo = null;
  }

  /**
   * 注册使用率变化回调
   */
  onUsageChange(callback: (usage: number) => void): void {
    this.usageCallbacks.push(callback);
  }

  /**
   * 移除使用率变化回调
   */
  removeUsageCallback(callback: (usage: number) => void): void {
    const index = this.usageCallbacks.indexOf(callback);
    if (index > -1) {
      this.usageCallbacks.splice(index, 1);
    }
  }

  /**
   * 获取 CPU 信息
   */
  private getCpuInfo(): { idle: number; total: number } {
    const cpus = os.cpus();
    let idle = 0;
    let total = 0;

    for (const cpu of cpus) {
      idle += cpu.times.idle;
      total += cpu.times.user + cpu.times.nice + cpu.times.sys + cpu.times.idle + cpu.times.irq;
    }

    return { idle, total };
  }

  /**
   * 更新 CPU 使用率
   */
  private updateCpuUsage(): void {
    const currentInfo = this.getCpuInfo();

    if (this.previousCpuInfo) {
      const idleDiff = currentInfo.idle - this.previousCpuInfo.idle;
      const totalDiff = currentInfo.total - this.previousCpuInfo.total;

      if (totalDiff > 0) {
        this.currentUsage = Math.round((1 - idleDiff / totalDiff) * 100);
        this.notifyUsageCallbacks();
      }
    }

    this.previousCpuInfo = currentInfo;
  }

  /**
   * 通知使用率变化回调
   */
  private notifyUsageCallbacks(): void {
    for (const callback of this.usageCallbacks) {
      try {
        callback(this.currentUsage);
      } catch (error) {
        console.error('CPU usage callback error:', error);
      }
    }
  }
}

/**
 * 帧率控制器
 * 根据 CPU 使用率动态调整捕获帧率
 */
export class FrameRateController {
  private targetFps: number;
  private minFps: number;
  private maxCpuUsage: number;
  private currentFps: number;
  private cpuMonitor: CpuMonitor;

  constructor(config: { targetFps: number; minFps: number; maxCpuUsage: number }) {
    this.targetFps = config.targetFps;
    this.minFps = config.minFps;
    this.maxCpuUsage = config.maxCpuUsage;
    this.currentFps = config.targetFps;
    this.cpuMonitor = new CpuMonitor();
  }

  /**
   * 开始帧率控制
   */
  start(): void {
    this.cpuMonitor.startMonitoring(500);
    this.cpuMonitor.onUsageChange((usage) => {
      this.adjustFrameRate(usage);
    });
  }

  /**
   * 停止帧率控制
   */
  stop(): void {
    this.cpuMonitor.stopMonitoring();
  }

  /**
   * 获取当前推荐帧率
   */
  getCurrentFps(): number {
    return this.currentFps;
  }

  /**
   * 获取 CPU 使用率
   */
  getCpuUsage(): number {
    return this.cpuMonitor.getCurrentUsage();
  }

  /**
   * 根据 CPU 使用率调整帧率
   */
  private adjustFrameRate(cpuUsage: number): void {
    if (cpuUsage > this.maxCpuUsage) {
      // CPU 使用率过高，降低帧率
      const reduction = Math.ceil((cpuUsage - this.maxCpuUsage) / 10);
      this.currentFps = Math.max(this.minFps, this.currentFps - reduction);
    } else if (cpuUsage < this.maxCpuUsage - 10 && this.currentFps < this.targetFps) {
      // CPU 使用率较低，可以提高帧率
      this.currentFps = Math.min(this.targetFps, this.currentFps + 1);
    }
  }
}
