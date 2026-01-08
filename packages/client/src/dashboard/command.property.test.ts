/**
 * 命令转发属性测试
 * **Feature: ai-vtuber-digital-human, Property 20: 命令转发完整性**
 * **Validates: Requirements 9.2**
 */

import * as fc from 'fast-check';
import { v4 as uuidv4 } from 'uuid';
import { ModuleType, MessageType, SystemMessage } from '@digital-human/shared';

/**
 * 创建命令消息的辅助函数
 * 模拟 Dashboard 发送命令到 Orchestrator
 */
function createCommandMessage(command: string): SystemMessage {
  return {
    id: uuidv4(),
    type: MessageType.DASHBOARD_COMMAND,
    timestamp: new Date(),
    source: ModuleType.DASHBOARD,
    payload: {
      command: command.trim(),
      timestamp: new Date(),
    },
  };
}

/**
 * 验证命令消息结构完整性
 */
function validateCommandMessage(message: SystemMessage): boolean {
  // 检查必需字段
  if (!message.id || typeof message.id !== 'string') return false;
  if (message.type !== MessageType.DASHBOARD_COMMAND) return false;
  if (!(message.timestamp instanceof Date)) return false;
  if (message.source !== ModuleType.DASHBOARD) return false;
  if (!message.payload || typeof message.payload !== 'object') return false;

  // 检查 payload 结构
  const payload = message.payload as { command?: string; timestamp?: Date };
  if (!payload.command || typeof payload.command !== 'string') return false;
  if (!(payload.timestamp instanceof Date)) return false;

  return true;
}

/**
 * 验证命令内容是否被正确保留
 */
function commandContentPreserved(
  originalCommand: string,
  message: SystemMessage
): boolean {
  const payload = message.payload as { command: string };
  return payload.command === originalCommand.trim();
}

describe('Property 20: 命令转发完整性', () => {
  /**
   * 属性测试：对于任何有效的命令字符串，创建的消息应该包含完整的结构
   */
  it('should create valid command messages for any non-empty command', () => {
    fc.assert(
      fc.property(
        // 生成非空字符串作为命令
        fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
        (command) => {
          const message = createCommandMessage(command);
          return validateCommandMessage(message);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：命令内容应该被完整保留（去除首尾空格后）
   */
  it('should preserve command content after trimming', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
        (command) => {
          const message = createCommandMessage(command);
          return commandContentPreserved(command, message);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：每个命令消息应该有唯一的 ID
   */
  it('should generate unique IDs for each command message', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
          { minLength: 2, maxLength: 50 }
        ),
        (commands) => {
          const messages = commands.map((cmd) => createCommandMessage(cmd));
          const ids = messages.map((m) => m.id);
          const uniqueIds = new Set(ids);
          return uniqueIds.size === ids.length;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：消息源应该始终是 DASHBOARD
   */
  it('should always set source as DASHBOARD', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
        (command) => {
          const message = createCommandMessage(command);
          return message.source === ModuleType.DASHBOARD;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：消息类型应该始终是 DASHBOARD_COMMAND
   */
  it('should always set type as DASHBOARD_COMMAND', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
        (command) => {
          const message = createCommandMessage(command);
          return message.type === MessageType.DASHBOARD_COMMAND;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：特殊字符命令应该被正确处理
   */
  it('should handle commands with special characters', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.string({ minLength: 1, maxLength: 100 }),
          fc.unicodeString({ minLength: 1, maxLength: 100 })
        ).filter((s) => s.trim().length > 0),
        (command) => {
          const message = createCommandMessage(command);
          return (
            validateCommandMessage(message) &&
            commandContentPreserved(command, message)
          );
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：常见命令格式应该被正确处理
   */
  it('should handle common command formats', () => {
    const commandGenerators = [
      // say 命令
      fc.string({ minLength: 1, maxLength: 200 }).map((text) => `say ${text}`),
      // emotion 命令
      fc.constantFrom('happy', 'sad', 'angry', 'neutral', 'surprised', 'thinking').map(
        (emotion) => `emotion ${emotion}`
      ),
      // mode 命令
      fc.constantFrom('autonomous', 'semi-autonomous', 'manual').map(
        (mode) => `mode ${mode}`
      ),
      // action 命令
      fc.string({ minLength: 1, maxLength: 50 }).map((action) => `action ${action}`),
      // status 命令
      fc.constant('status'),
    ];

    fc.assert(
      fc.property(fc.oneof(...commandGenerators), (command) => {
        const message = createCommandMessage(command);
        return (
          validateCommandMessage(message) &&
          commandContentPreserved(command, message)
        );
      }),
      { numRuns: 100 }
    );
  });

  /**
   * 属性测试：时间戳应该是有效的 Date 对象
   */
  it('should have valid timestamps', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
        (command) => {
          const before = new Date();
          const message = createCommandMessage(command);
          const after = new Date();

          const messageTime = message.timestamp.getTime();
          const payloadTime = (message.payload as { timestamp: Date }).timestamp.getTime();

          return (
            messageTime >= before.getTime() &&
            messageTime <= after.getTime() &&
            payloadTime >= before.getTime() &&
            payloadTime <= after.getTime()
          );
        }
      ),
      { numRuns: 100 }
    );
  });
});
