/**
 * 模块类型枚举
 * 定义系统中所有模块的类型标识
 */
export enum ModuleType {
  COGNITION = 'cognition',
  VISION = 'vision',
  MEMORY = 'memory',
  TTS = 'tts',
  CHAT = 'chat',
  GAME_CONTROLLER = 'game_controller',
  AVATAR = 'avatar',
  DASHBOARD = 'dashboard',
}

/**
 * 消息类型枚举
 * 定义系统中所有消息的类型标识
 */
export enum MessageType {
  // 系统消息
  MODULE_REGISTER = 'module.register',
  MODULE_HEARTBEAT = 'module.heartbeat',
  MODULE_STATUS = 'module.status',

  // 聊天消息
  CHAT_MESSAGE = 'chat.message',
  CHAT_RESPONSE = 'chat.response',

  // 游戏相关
  GAME_STATE = 'game.state',
  GAME_ACTION = 'game.action',
  GAME_ACTION_RESULT = 'game.action.result',

  // AI 相关
  COGNITION_REQUEST = 'cognition.request',
  COGNITION_RESPONSE = 'cognition.response',
  MEMORY_QUERY = 'memory.query',
  MEMORY_RESULT = 'memory.result',

  // 输出相关
  TTS_REQUEST = 'tts.request',
  TTS_AUDIO = 'tts.audio',
  AVATAR_EXPRESSION = 'avatar.expression',
  AVATAR_LIPSYNC = 'avatar.lipsync',

  // 控制面板
  DASHBOARD_COMMAND = 'dashboard.command',
  DASHBOARD_OVERRIDE = 'dashboard.override',
  SYSTEM_ALERT = 'system.alert',
}

/**
 * 情绪类型枚举
 * 定义 AI 可以表达的情绪状态
 */
export type EmotionType = 'neutral' | 'happy' | 'sad' | 'surprised' | 'angry' | 'thinking';

/**
 * 控制模式枚举
 * 定义游戏控制器的操作模式
 */
export type ControlMode = 'autonomous' | 'semi-autonomous' | 'manual';

/**
 * 健康状态枚举
 * 定义模块的健康状态
 */
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

/**
 * 错误严重程度枚举
 */
export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

/**
 * 恢复动作枚举
 */
export enum RecoveryAction {
  RETRY = 'retry',
  FALLBACK = 'fallback',
  RESTART_MODULE = 'restart_module',
  NOTIFY_CREATOR = 'notify_creator',
  SHUTDOWN = 'shutdown',
}
