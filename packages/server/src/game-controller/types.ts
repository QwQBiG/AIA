import { ControlMode } from '@digital-human/shared';
import { GameInput, GameAction, ActionResult, GameControllerConfig } from '@digital-human/shared';

/**
 * 输入模拟器接口
 * 定义底层输入模拟的抽象接口
 */
export interface IInputSimulator {
  /** 发送键盘输入 */
  sendKeyboard(key: string, action: 'press' | 'release'): Promise<void>;
  
  /** 发送鼠标输入 */
  sendMouse(
    action: 'move' | 'click',
    position?: { x: number; y: number },
    button?: string
  ): Promise<void>;
  
  /** 发送手柄输入 */
  sendGamepad(button: string, action: 'press' | 'release'): Promise<void>;
  
  /** 检查是否可用 */
  isAvailable(): boolean;
}

/**
 * 游戏控制器接口
 */
export interface IGameController {
  /** 发送输入 */
  sendInput(input: GameInput): Promise<void>;
  
  /** 设置控制模式 */
  setMode(mode: ControlMode): void;
  
  /** 获取当前控制模式 */
  getMode(): ControlMode;
  
  /** 执行游戏动作 */
  executeAction(action: GameAction): Promise<ActionResult>;
  
  /** 验证动作是否有效 */
  validateAction(action: GameAction): ValidationResult;
  
  /** 将动作转换为输入命令 */
  actionToInputs(action: GameAction): GameInput[];
}

/**
 * 验证结果接口
 */
export interface ValidationResult {
  /** 是否有效 */
  valid: boolean;
  /** 错误列表 */
  errors: string[];
}

/**
 * 有效的键盘按键列表
 */
export const VALID_KEYBOARD_KEYS = [
  // 字母键
  'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
  'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
  // 数字键
  '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
  // 功能键
  'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
  // 特殊键
  'space', 'enter', 'escape', 'tab', 'backspace', 'delete', 'insert',
  'home', 'end', 'pageup', 'pagedown',
  'up', 'down', 'left', 'right',
  'shift', 'ctrl', 'alt', 'win',
  'capslock', 'numlock', 'scrolllock',
  // 符号键
  'minus', 'equals', 'bracketleft', 'bracketright', 'backslash',
  'semicolon', 'quote', 'comma', 'period', 'slash', 'grave',
] as const;

/**
 * 有效的鼠标按钮列表
 */
export const VALID_MOUSE_BUTTONS = ['left', 'right', 'middle'] as const;

/**
 * 有效的手柄按钮列表
 */
export const VALID_GAMEPAD_BUTTONS = [
  'a', 'b', 'x', 'y',
  'lb', 'rb', 'lt', 'rt',
  'start', 'select', 'home',
  'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right',
  'left_stick', 'right_stick',
  'left_stick_x', 'left_stick_y',
  'right_stick_x', 'right_stick_y',
] as const;

export type ValidKeyboardKey = typeof VALID_KEYBOARD_KEYS[number];
export type ValidMouseButton = typeof VALID_MOUSE_BUTTONS[number];
export type ValidGamepadButton = typeof VALID_GAMEPAD_BUTTONS[number];

// Re-export shared types
export { GameInput, GameAction, ActionResult, GameControllerConfig, ControlMode };
