import {
  ModuleType,
  MessageType,
  HealthStatus,
  ErrorSeverity,
  RecoveryAction,
} from './enums.js';

/**
 * 系统消息接口
 * 所有模块间通信的统一消息格式
 */
export interface SystemMessage {
  /** 消息唯一标识 */
  id: string;
  /** 消息类型 */
  type: MessageType;
  /** 消息时间戳 */
  timestamp: Date;
  /** 源模块 */
  source: ModuleType;
  /** 目标模块（可选） */
  target?: ModuleType;
  /** 消息负载 */
  payload: unknown;
  /** 关联 ID，用于追踪请求-响应对 */
  correlationId?: string;
}

/**
 * 模块状态接口
 * 描述模块的当前状态
 */
export interface ModuleStatus {
  /** 模块 ID */
  moduleId: string;
  /** 模块类型 */
  moduleType: ModuleType;
  /** 是否已连接 */
  isConnected: boolean;
  /** 最后心跳时间 */
  lastHeartbeat: Date;
  /** 健康状态 */
  health: HealthStatus;
}

/**
 * 系统错误接口
 */
export interface SystemError {
  /** 错误代码 */
  code: string;
  /** 错误消息 */
  message: string;
  /** 严重程度 */
  severity: ErrorSeverity;
  /** 来源模块 */
  module: ModuleType;
  /** 时间戳 */
  timestamp: Date;
  /** 上下文信息 */
  context?: Record<string, unknown>;
  /** 恢复动作 */
  recoveryAction?: RecoveryAction;
}

/**
 * 验证结果接口
 */
export interface ValidationResult {
  /** 是否有效 */
  valid: boolean;
  /** 错误信息列表 */
  errors?: string[];
}
