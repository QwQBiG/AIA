import {
  IGameController,
  IInputSimulator,
  ValidationResult,
  GameInput,
  GameAction,
  ActionResult,
  ControlMode,
  VALID_KEYBOARD_KEYS,
  VALID_MOUSE_BUTTONS,
  VALID_GAMEPAD_BUTTONS,
} from './types.js';
import { MockInputSimulator } from './input-simulator.js';

/**
 * 游戏控制器实现
 * 负责将游戏动作转换为输入命令并执行
 */
export class GameController implements IGameController {
  private mode: ControlMode = 'manual';
  private inputSimulator: IInputSimulator;
  private inputDelay: number;

  constructor(
    inputSimulator?: IInputSimulator,
    options?: { inputDelay?: number; mode?: ControlMode }
  ) {
    this.inputSimulator = inputSimulator || new MockInputSimulator();
    this.inputDelay = options?.inputDelay ?? 50;
    this.mode = options?.mode ?? 'manual';
  }

  /**
   * 设置控制模式
   */
  setMode(mode: ControlMode): void {
    this.mode = mode;
  }

  /**
   * 获取当前控制模式
   */
  getMode(): ControlMode {
    return this.mode;
  }

  /**
   * 发送单个输入
   */
  async sendInput(input: GameInput): Promise<void> {
    const validation = this.validateInput(input);
    if (!validation.valid) {
      throw new Error(`Invalid input: ${validation.errors.join(', ')}`);
    }

    switch (input.type) {
      case 'keyboard':
        if (input.key) {
          await this.inputSimulator.sendKeyboard(
            input.key.toLowerCase(),
            input.action as 'press' | 'release'
          );
        }
        break;

      case 'mouse':
        await this.inputSimulator.sendMouse(
          input.action as 'move' | 'click',
          input.position,
          input.button
        );
        break;

      case 'gamepad':
        if (input.button) {
          await this.inputSimulator.sendGamepad(
            input.button.toLowerCase(),
            input.action as 'press' | 'release'
          );
        }
        break;
    }

    // 应用输入延迟
    if (input.duration && input.duration > 0) {
      await this.delay(input.duration);
    } else if (this.inputDelay > 0) {
      await this.delay(this.inputDelay);
    }
  }

  /**
   * 验证单个输入
   */
  validateInput(input: GameInput): ValidationResult {
    const errors: string[] = [];

    // 验证输入类型
    if (!['keyboard', 'mouse', 'gamepad'].includes(input.type)) {
      errors.push(`Invalid input type: ${input.type}`);
    }

    // 验证动作类型
    if (!['press', 'release', 'move', 'click'].includes(input.action)) {
      errors.push(`Invalid action: ${input.action}`);
    }

    // 根据输入类型验证具体参数
    switch (input.type) {
      case 'keyboard':
        if (!input.key) {
          errors.push('Keyboard input requires a key');
        } else if (!this.isValidKeyboardKey(input.key)) {
          errors.push(`Invalid keyboard key: ${input.key}`);
        }
        if (!['press', 'release'].includes(input.action)) {
          errors.push(`Invalid keyboard action: ${input.action}`);
        }
        break;

      case 'mouse':
        if (input.action === 'move' && !input.position) {
          errors.push('Mouse move requires position');
        }
        if (input.action === 'click' && input.button && !this.isValidMouseButton(input.button)) {
          errors.push(`Invalid mouse button: ${input.button}`);
        }
        if (input.position) {
          if (typeof input.position.x !== 'number' || typeof input.position.y !== 'number') {
            errors.push('Mouse position must have numeric x and y');
          }
          if (input.position.x < 0 || input.position.y < 0) {
            errors.push('Mouse position cannot be negative');
          }
        }
        if (!['move', 'click'].includes(input.action)) {
          errors.push(`Invalid mouse action: ${input.action}`);
        }
        break;

      case 'gamepad':
        if (!input.button) {
          errors.push('Gamepad input requires a button');
        } else if (!this.isValidGamepadButton(input.button)) {
          errors.push(`Invalid gamepad button: ${input.button}`);
        }
        if (!['press', 'release'].includes(input.action)) {
          errors.push(`Invalid gamepad action: ${input.action}`);
        }
        break;
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * 验证游戏动作
   */
  validateAction(action: GameAction): ValidationResult {
    const errors: string[] = [];

    // 验证动作名称
    if (!action.name || action.name.trim() === '') {
      errors.push('Action name is required');
    }

    // 验证输入列表
    if (!action.inputs || !Array.isArray(action.inputs)) {
      errors.push('Action inputs must be an array');
    } else if (action.inputs.length === 0) {
      errors.push('Action must have at least one input');
    } else {
      // 验证每个输入
      action.inputs.forEach((input: GameInput, index: number) => {
        const inputValidation = this.validateInput(input);
        if (!inputValidation.valid) {
          errors.push(`Input ${index}: ${inputValidation.errors.join(', ')}`);
        }
      });
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * 将游戏动作转换为输入命令列表
   */
  actionToInputs(action: GameAction): GameInput[] {
    // 动作已经包含输入列表，直接返回
    // 这个方法主要用于验证和可能的转换
    return action.inputs.map((input: GameInput) => ({ ...input }));
  }

  /**
   * 执行游戏动作
   */
  async executeAction(action: GameAction): Promise<ActionResult> {
    const executedAt = new Date();

    // 验证动作
    const validation = this.validateAction(action);
    if (!validation.valid) {
      return {
        success: false,
        error: validation.errors.join('; '),
        executedAt,
      };
    }

    // 检查控制模式
    if (this.mode === 'manual') {
      return {
        success: false,
        error: 'Cannot execute action in manual mode',
        executedAt,
      };
    }

    try {
      // 获取输入命令
      const inputs = this.actionToInputs(action);

      // 依次执行每个输入
      for (const input of inputs) {
        await this.sendInput(input);
      }

      return {
        success: true,
        executedAt,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        executedAt,
      };
    }
  }

  /**
   * 检查是否为有效的键盘按键
   */
  private isValidKeyboardKey(key: string): boolean {
    return VALID_KEYBOARD_KEYS.includes(key.toLowerCase() as any);
  }

  /**
   * 检查是否为有效的鼠标按钮
   */
  private isValidMouseButton(button: string): boolean {
    return VALID_MOUSE_BUTTONS.includes(button.toLowerCase() as any);
  }

  /**
   * 检查是否为有效的手柄按钮
   */
  private isValidGamepadButton(button: string): boolean {
    return VALID_GAMEPAD_BUTTONS.includes(button.toLowerCase() as any);
  }

  /**
   * 延迟函数
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
