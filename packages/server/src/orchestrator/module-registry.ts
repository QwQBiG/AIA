import { Socket } from 'socket.io';
import { ModuleType, HealthStatus, ModuleStatus } from '@digital-human/shared';
import { RegisteredModule, OrchestratorConfig, DEFAULT_CONFIG } from './types';

/**
 * 模块注册表
 * 负责管理模块的注册、注销和健康监控
 */
export class ModuleRegistry {
  private modules: Map<string, RegisteredModule> = new Map();
  private modulesByType: Map<ModuleType, Set<string>> = new Map();
  private config: OrchestratorConfig;
  private healthCheckTimer: NodeJS.Timeout | null = null;

  constructor(config: Partial<OrchestratorConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    // 初始化模块类型映射
    Object.values(ModuleType).forEach((type) => {
      this.modulesByType.set(type, new Set());
    });
  }

  /**
   * 注册模块
   */
  registerModule(moduleId: string, moduleType: ModuleType, socket: Socket): void {
    if (this.modules.has(moduleId)) {
      throw new Error(`Module ${moduleId} is already registered`);
    }

    const now = new Date();
    const module: RegisteredModule = {
      moduleId,
      moduleType,
      socket,
      registeredAt: now,
      lastHeartbeat: now,
      health: 'healthy',
    };

    this.modules.set(moduleId, module);
    this.modulesByType.get(moduleType)?.add(moduleId);
  }

  /**
   * 注销模块
   */
  unregisterModule(moduleId: string): boolean {
    const module = this.modules.get(moduleId);
    if (!module) {
      return false;
    }

    this.modulesByType.get(module.moduleType)?.delete(moduleId);
    this.modules.delete(moduleId);
    return true;
  }

  /**
   * 获取模块状态
   */
  getModuleStatus(moduleId: string): ModuleStatus | null {
    const module = this.modules.get(moduleId);
    if (!module) {
      return null;
    }

    return {
      moduleId: module.moduleId,
      moduleType: module.moduleType,
      isConnected: module.socket.connected,
      lastHeartbeat: module.lastHeartbeat,
      health: module.health,
    };
  }

  /**
   * 获取所有模块状态
   */
  getAllModuleStatus(): ModuleStatus[] {
    return Array.from(this.modules.values()).map((module) => ({
      moduleId: module.moduleId,
      moduleType: module.moduleType,
      isConnected: module.socket.connected,
      lastHeartbeat: module.lastHeartbeat,
      health: module.health,
    }));
  }

  /**
   * 更新模块心跳
   */
  updateHeartbeat(moduleId: string): boolean {
    const module = this.modules.get(moduleId);
    if (!module) {
      return false;
    }

    module.lastHeartbeat = new Date();
    module.health = 'healthy';
    return true;
  }

  /**
   * 获取指定类型的模块
   */
  getModulesByType(moduleType: ModuleType): RegisteredModule[] {
    const moduleIds = this.modulesByType.get(moduleType);
    if (!moduleIds) {
      return [];
    }

    return Array.from(moduleIds)
      .map((id) => this.modules.get(id))
      .filter((m): m is RegisteredModule => m !== undefined);
  }

  /**
   * 获取模块
   */
  getModule(moduleId: string): RegisteredModule | undefined {
    return this.modules.get(moduleId);
  }

  /**
   * 检查模块是否已注册
   */
  hasModule(moduleId: string): boolean {
    return this.modules.has(moduleId);
  }

  /**
   * 获取已注册模块数量
   */
  getModuleCount(): number {
    return this.modules.size;
  }

  /**
   * 启动健康检查
   */
  startHealthCheck(onUnhealthy?: (moduleId: string, module: RegisteredModule) => void): void {
    if (this.healthCheckTimer) {
      return;
    }

    this.healthCheckTimer = setInterval(() => {
      const now = Date.now();
      const timeout = this.config.heartbeatTimeout;

      this.modules.forEach((module, moduleId) => {
        const timeSinceHeartbeat = now - module.lastHeartbeat.getTime();

        if (timeSinceHeartbeat > timeout) {
          module.health = 'unhealthy';
          onUnhealthy?.(moduleId, module);
        } else if (timeSinceHeartbeat > timeout / 2) {
          module.health = 'degraded';
        } else {
          module.health = 'healthy';
        }
      });
    }, this.config.heartbeatInterval);
  }

  /**
   * 停止健康检查
   */
  stopHealthCheck(): void {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
  }

  /**
   * 清除所有模块
   */
  clear(): void {
    this.modules.clear();
    this.modulesByType.forEach((set) => set.clear());
  }
}
