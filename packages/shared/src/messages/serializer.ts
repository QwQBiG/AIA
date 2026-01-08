import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { v4 as uuidv4 } from 'uuid';
import { SystemMessage, ValidationResult } from '../types/system.js';
import { ModuleType, MessageType } from '../types/enums.js';
import { SystemMessageSchema } from './schema.js';

// 创建 Ajv 实例并添加格式支持
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

// 编译 Schema
const validateSchema = ajv.compile(SystemMessageSchema);

/**
 * 序列化后的消息接口（用于 JSON 传输）
 */
interface SerializedMessage {
  id: string;
  type: string;
  timestamp: string;
  source: string;
  target?: string;
  payload: unknown;
  correlationId?: string;
}

/**
 * 将 SystemMessage 序列化为 JSON 字符串
 * @param message - 要序列化的消息对象
 * @returns JSON 字符串
 */
export function serialize(message: SystemMessage): string {
  const serialized: SerializedMessage = {
    id: message.id,
    type: message.type,
    timestamp: message.timestamp.toISOString(),
    source: message.source,
    payload: message.payload,
  };

  if (message.target !== undefined) {
    serialized.target = message.target;
  }

  if (message.correlationId !== undefined) {
    serialized.correlationId = message.correlationId;
  }

  return JSON.stringify(serialized);
}

/**
 * 将 JSON 字符串反序列化为 SystemMessage
 * @param json - JSON 字符串
 * @returns SystemMessage 对象
 * @throws Error 如果 JSON 格式无效或不符合 Schema
 */
export function deserialize(json: string): SystemMessage {
  const validation = validate(json);

  if (!validation.valid) {
    throw new Error(`Invalid message format: ${validation.errors?.join(', ')}`);
  }

  const parsed = JSON.parse(json) as SerializedMessage;

  const message: SystemMessage = {
    id: parsed.id,
    type: parsed.type as MessageType,
    timestamp: new Date(parsed.timestamp),
    source: parsed.source as ModuleType,
    payload: parsed.payload,
  };

  if (parsed.target !== undefined) {
    message.target = parsed.target as ModuleType;
  }

  if (parsed.correlationId !== undefined) {
    message.correlationId = parsed.correlationId;
  }

  return message;
}

/**
 * 验证 JSON 字符串是否符合 SystemMessage Schema
 * @param json - JSON 字符串
 * @returns ValidationResult 对象
 */
export function validate(json: string): ValidationResult {
  let parsed: unknown;

  try {
    parsed = JSON.parse(json);
  } catch {
    return {
      valid: false,
      errors: ['Invalid JSON format'],
    };
  }

  const isValid = validateSchema(parsed);

  if (isValid) {
    return { valid: true };
  }

  const errors =
    validateSchema.errors?.map((err) => {
      const path = err.instancePath || 'root';
      return `${path}: ${err.message}`;
    }) || [];

  return {
    valid: false,
    errors,
  };
}

/**
 * 创建新的 SystemMessage
 * @param type - 消息类型
 * @param source - 源模块
 * @param payload - 消息负载
 * @param options - 可选参数
 * @returns SystemMessage 对象
 */
export function createMessage(
  type: MessageType,
  source: ModuleType,
  payload: unknown,
  options?: {
    target?: ModuleType;
    correlationId?: string;
  }
): SystemMessage {
  const message: SystemMessage = {
    id: uuidv4(),
    type,
    timestamp: new Date(),
    source,
    payload,
  };

  if (options?.target !== undefined) {
    message.target = options.target;
  }

  if (options?.correlationId !== undefined) {
    message.correlationId = options.correlationId;
  }

  return message;
}

/**
 * 检查消息是否为有效的 SystemMessage 对象
 * @param obj - 要检查的对象
 * @returns 是否为有效的 SystemMessage
 */
export function isValidMessage(obj: unknown): obj is SystemMessage {
  if (typeof obj !== 'object' || obj === null) {
    return false;
  }

  const msg = obj as Record<string, unknown>;

  return (
    typeof msg.id === 'string' &&
    typeof msg.type === 'string' &&
    msg.timestamp instanceof Date &&
    typeof msg.source === 'string' &&
    'payload' in msg
  );
}
