import { Socket } from 'socket.io';
import { ModuleType, HealthStatus } from '@digital-human/shared';

/**
 * 已注册模块的信息
 */
export interface RegisteredModule {
  /** 模块 ID */
  moduleId: string;
  /** 模块类型 */
  moduleType: ModuleType;
  /** Socket 连接 */
  socket: Socket;
  /** 注册时间 */
  registeredAt: Date;
  /** 最后心跳时间 */
  lastHeartbeat: Date;
  /** 健康状态 */
  health: HealthStatus;
}

/**
 * Orchestrator 配置
 */
export interface OrchestratorConfig {
  /** 服务器端口 */
  port: number;
  /** 心跳间隔（毫秒） */
  heartbeatInterval: number;
  /** 心跳超时（毫秒） */
  heartbeatTimeout: number;
  /** 是否启用 CORS */
  cors: boolean;
}

/**
 * 默认配置
 */
export const DEFAULT_CONFIG: OrchestratorConfig = {
  port: 3000,
  heartbeatInterval: 5000,
  heartbeatTimeout: 15000,
  cors: true,
};

/**
 * Socket 事件名称
 */
export const SocketEvents = {
  // 连接事件
  CONNECTION: 'connection',
  DISCONNECT: 'disconnect',

  // 模块管理事件
  MODULE_REGISTER: 'module:register',
  MODULE_UNREGISTER: 'module:unregister',
  MODULE_HEARTBEAT: 'module:heartbeat',
  MODULE_STATUS: 'module:status',

  // 消息事件
  MESSAGE: 'message',
  BROADCAST: 'broadcast',

  // 错误事件
  ERROR: 'error',
} as const;
