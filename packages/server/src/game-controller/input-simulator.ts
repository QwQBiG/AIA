import {
  IInputSimulator,
  VALID_KEYBOARD_KEYS,
  VALID_MOUSE_BUTTONS,
  VALID_GAMEPAD_BUTTONS,
  ValidKeyboardKey,
  ValidMouseButton,
  ValidGamepadButton,
} from './types.js';

/**
 * 模拟输入模拟器
 * 用于测试和开发环境，不实际发送输入
 */
export class MockInputSimulator implements IInputSimulator {
  private inputLog: Array<{
    type: 'keyboard' | 'mouse' | 'gamepad';
    action: string;
    details: Record<string, unknown>;
    timestamp: Date;
  }> = [];

  async sendKeyboard(key: string, action: 'press' | 'release'): Promise<void> {
    this.inputLog.push({
      type: 'keyboard',
      action,
      details: { key },
      timestamp: new Date(),
    });
  }

  async sendMouse(
    action: 'move' | 'click',
    position?: { x: number; y: number },
    button?: string
  ): Promise<void> {
    this.inputLog.push({
      type: 'mouse',
      action,
      details: { position, button },
      timestamp: new Date(),
    });
  }

  async sendGamepad(button: string, action: 'press' | 'release'): Promise<void> {
    this.inputLog.push({
      type: 'gamepad',
      action,
      details: { button },
      timestamp: new Date(),
    });
  }

  isAvailable(): boolean {
    return true;
  }

  /** 获取输入日志（用于测试） */
  getInputLog() {
    return [...this.inputLog];
  }

  /** 清除输入日志 */
  clearInputLog() {
    this.inputLog = [];
  }
}
