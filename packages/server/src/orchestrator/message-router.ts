import { ModuleType, SystemMessage, serialize } from '@digital-human/shared';
import { ModuleRegistry } from './module-registry';
import { SocketEvents } from './types';

/**
 * 路由结果接口
 */
export interface RouteResult {
  success: boolean;
  targetModuleId?: string;
  error?: string;
  latencyMs: number;
}

/**
 * 消息路由器
 * 负责将消息路由到正确的目标模块
 */
export class MessageRouter {
  private registry: ModuleRegistry;

  constructor(registry: ModuleRegistry) {
    this.registry = registry;
  }

  /**
   * 路由消息到目标模块
   * @param message - 要路由的消息
   * @returns 路由结果
   */
  async routeMessage(message: SystemMessage): Promise<RouteResult> {
    const startTime = performance.now();

    try {
      // 如果没有指定目标，返回错误
      if (!message.target) {
        return {
          success: false,
          error: 'No target module specified',
          latencyMs: performance.now() - startTime,
        };
      }

      // 获取目标类型的模块
      const targetModules = this.registry.getModulesByType(message.target);

      if (targetModules.length === 0) {
        return {
          success: false,
          error: `No modules of type ${message.target} are registered`,
          latencyMs: performance.now() - startTime,
        };
      }

      // 选择第一个健康的模块
      const healthyModule = targetModules.find((m) => m.health === 'healthy' && m.socket.connected);
      const targetModule = healthyModule || targetModules[0];

      if (!targetModule.socket.connected) {
        return {
          success: false,
          error: `Target module ${targetModule.moduleId} is not connected`,
          latencyMs: performance.now() - startTime,
        };
      }

      // 发送消息
      const serialized = serialize(message);
      targetModule.socket.emit(SocketEvents.MESSAGE, serialized);

      return {
        success: true,
        targetModuleId: targetModule.moduleId,
        latencyMs: performance.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        latencyMs: performance.now() - startTime,
      };
    }
  }

  /**
   * 广播消息到指定类型的所有模块
   * @param message - 要广播的消息
   * @param targetTypes - 目标模块类型列表
   * @returns 广播结果列表
   */
  broadcast(message: SystemMessage, targetTypes: ModuleType[]): RouteResult[] {
    const startTime = performance.now();
    const results: RouteResult[] = [];
    const serialized = serialize(message);

    for (const targetType of targetTypes) {
      const modules = this.registry.getModulesByType(targetType);

      for (const module of modules) {
        const moduleStartTime = performance.now();

        if (module.socket.connected) {
          module.socket.emit(SocketEvents.MESSAGE, serialized);
          results.push({
            success: true,
            targetModuleId: module.moduleId,
            latencyMs: performance.now() - moduleStartTime,
          });
        } else {
          results.push({
            success: false,
            targetModuleId: module.moduleId,
            error: 'Module not connected',
            latencyMs: performance.now() - moduleStartTime,
          });
        }
      }
    }

    return results;
  }

  /**
   * 广播消息到所有已注册模块
   * @param message - 要广播的消息
   * @returns 广播结果列表
   */
  broadcastAll(message: SystemMessage): RouteResult[] {
    return this.broadcast(message, Object.values(ModuleType));
  }

  /**
   * 路由消息到指定模块 ID
   * @param message - 要路由的消息
   * @param moduleId - 目标模块 ID
   * @returns 路由结果
   */
  routeToModule(message: SystemMessage, moduleId: string): RouteResult {
    const startTime = performance.now();

    const module = this.registry.getModule(moduleId);

    if (!module) {
      return {
        success: false,
        error: `Module ${moduleId} not found`,
        latencyMs: performance.now() - startTime,
      };
    }

    if (!module.socket.connected) {
      return {
        success: false,
        targetModuleId: moduleId,
        error: 'Module not connected',
        latencyMs: performance.now() - startTime,
      };
    }

    const serialized = serialize(message);
    module.socket.emit(SocketEvents.MESSAGE, serialized);

    return {
      success: true,
      targetModuleId: moduleId,
      latencyMs: performance.now() - startTime,
    };
  }
}
