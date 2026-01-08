/**
 * 记忆输入接口
 */
export interface MemoryInput {
  /** 记忆内容 */
  content: string;
  /** 记忆类型 */
  type: 'conversation' | 'game_event' | 'system';
  /** 参与者列表（可选） */
  participants?: string[];
  /** 元数据（可选） */
  metadata?: Record<string, unknown>;
}

/**
 * 记忆接口
 */
export interface Memory {
  /** 记忆 ID */
  id: string;
  /** 记忆内容 */
  content: string;
  /** 记忆类型 */
  type: string;
  /** 时间戳 */
  timestamp: Date;
  /** 向量嵌入（可选） */
  embedding?: number[];
  /** 相关性分数（可选） */
  relevanceScore?: number;
}

/**
 * 嵌入提供者配置接口
 */
export interface EmbeddingProvider {
  /** 提供者类型 */
  type: 'cloud' | 'local';
  /** 提供者名称 */
  name: string;
  /** 模型名称 */
  model: string;
  /** 嵌入维度 */
  dimensions: number;
}
