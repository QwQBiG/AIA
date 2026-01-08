import { ModuleType, MessageType } from '../types/enums.js';

/**
 * SystemMessage 的 JSON Schema 定义
 */
export const SystemMessageSchema = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  type: 'object',
  required: ['id', 'type', 'timestamp', 'source', 'payload'],
  properties: {
    id: {
      type: 'string',
      pattern: '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
      description: 'UUID v4 格式的消息唯一标识',
    },
    type: {
      type: 'string',
      enum: Object.values(MessageType),
      description: '消息类型',
    },
    timestamp: {
      type: 'string',
      format: 'date-time',
      description: 'ISO 8601 格式的时间戳',
    },
    source: {
      type: 'string',
      enum: Object.values(ModuleType),
      description: '源模块类型',
    },
    target: {
      type: 'string',
      enum: Object.values(ModuleType),
      description: '目标模块类型（可选）',
    },
    payload: {
      type: 'object',
      description: '消息负载',
    },
    correlationId: {
      type: 'string',
      pattern: '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
      description: '关联 ID，用于追踪请求-响应对',
    },
  },
  additionalProperties: false,
} as const;

export type SystemMessageSchemaType = typeof SystemMessageSchema;
