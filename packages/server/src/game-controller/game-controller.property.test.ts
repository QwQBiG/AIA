/**
 * Game Controller Property Tests
 * 游戏控制器属性测试
 *
 * 使用 fast-check 进行属性测试，验证游戏控制器的正确性属性
 */

import * as fc from 'fast-check';
import { GameController } from './game-controller.js';
import { MockInputSimulator } from './input-simulator.js';
import {
  GameInput,
  GameAction,
  VALID_KEYBOARD_KEYS,
  VALID_MOUSE_BUTTONS,
  VALID_GAMEPAD_BUTTONS,
} from './types.js';

describe('GameController Property Tests', () => {
  let controller: GameController;
  let mockSimulator: MockInputSimulator;

  beforeEach(() => {
    mockSimulator = new MockInputSimulator();
    controller = new GameController(mockSimulator, { inputDelay: 0, mode: 'autonomous' });
  });

  // 生成有效的键盘输入
  const validKeyboardInputArb = fc.record({
    type: fc.constant('keyboard' as const),
    action: fc.constantFrom('press' as const, 'release' as const),
    key: fc.constantFrom(...VALID_KEYBOARD_KEYS),
    duration: fc.option(fc.integer({ min: 0, max: 1000 }), { nil: undefined }),
  });

  // 生成有效的鼠标输入
  const validMouseMoveInputArb = fc.record({
    type: fc.constant('mouse' as const),
    action: fc.constant('move' as const),
    position: fc.record({
      x: fc.integer({ min: 0, max: 3840 }),
      y: fc.integer({ min: 0, max: 2160 }),
    }),
    duration: fc.option(fc.integer({ min: 0, max: 1000 }), { nil: undefined }),
  });

  const validMouseClickInputArb = fc.record({
    type: fc.constant('mouse' as const),
    action: fc.constant('click' as const),
    button: fc.constantFrom(...VALID_MOUSE_BUTTONS),
    position: fc.option(
      fc.record({
        x: fc.integer({ min: 0, max: 3840 }),
        y: fc.integer({ min: 0, max: 2160 }),
      }),
      { nil: undefined }
    ),
    duration: fc.option(fc.integer({ min: 0, max: 1000 }), { nil: undefined }),
  });

  const validMouseInputArb = fc.oneof(validMouseMoveInputArb, validMouseClickInputArb);

  // 生成有效的手柄输入
  const validGamepadInputArb = fc.record({
    type: fc.constant('gamepad' as const),
    action: fc.constantFrom('press' as const, 'release' as const),
    button: fc.constantFrom(...VALID_GAMEPAD_BUTTONS),
    duration: fc.option(fc.integer({ min: 0, max: 1000 }), { nil: undefined }),
  });

  // 生成任意有效输入
  const validInputArb: fc.Arbitrary<GameInput> = fc.oneof(
    validKeyboardInputArb,
    validMouseInputArb,
    validGamepadInputArb
  ) as fc.Arbitrary<GameInput>;

  // 生成有效的游戏动作
  const validActionArb: fc.Arbitrary<GameAction> = fc
    .record({
      name: fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0),
      description: fc.string({ minLength: 0, maxLength: 200 }),
      inputs: fc.array(validInputArb, { minLength: 1, maxLength: 10 }),
    })
    .map(({ name, description, inputs }) => ({
      name: name.trim(),
      description,
      inputs,
    }));

  // 生成无效的键盘按键
  const invalidKeyArb = fc
    .string({ minLength: 1, maxLength: 20 })
    .filter(key => !VALID_KEYBOARD_KEYS.includes(key.toLowerCase() as any));

  // 生成无效的手柄按钮
  const invalidGamepadButtonArb = fc
    .string({ minLength: 1, maxLength: 20 })
    .filter(button => !VALID_GAMEPAD_BUTTONS.includes(button.toLowerCase() as any));

  /**
   * Property 9: 输入类型支持
   * *For any* GameInput，系统应该支持 keyboard、mouse 和 gamepad 三种输入类型。
   * **Validates: Requirements 3.2**
   */
  describe('Property 9: Input Type Support', () => {
    it('should support all three input types: keyboard, mouse, and gamepad', () => {
      fc.assert(
        fc.property(validInputArb, input => {
          // 验证输入类型是三种之一
          expect(['keyboard', 'mouse', 'gamepad']).toContain(input.type);

          // 验证输入可以通过验证
          const validation = controller.validateInput(input);
          expect(validation.valid).toBe(true);
        }),
        { numRuns: 100 }
      );
    });

    it('should validate keyboard inputs correctly', () => {
      fc.assert(
        fc.property(validKeyboardInputArb, input => {
          const validation = controller.validateInput(input as GameInput);
          expect(validation.valid).toBe(true);
          expect(validation.errors).toHaveLength(0);
        }),
        { numRuns: 100 }
      );
    });

    it('should validate mouse inputs correctly', () => {
      fc.assert(
        fc.property(validMouseInputArb, input => {
          const validation = controller.validateInput(input as GameInput);
          expect(validation.valid).toBe(true);
          expect(validation.errors).toHaveLength(0);
        }),
        { numRuns: 100 }
      );
    });

    it('should validate gamepad inputs correctly', () => {
      fc.assert(
        fc.property(validGamepadInputArb, input => {
          const validation = controller.validateInput(input as GameInput);
          expect(validation.valid).toBe(true);
          expect(validation.errors).toHaveLength(0);
        }),
        { numRuns: 100 }
      );
    });

    it('should successfully send all valid input types', async () => {
      await fc.assert(
        fc.asyncProperty(validInputArb, async input => {
          mockSimulator.clearInputLog();
          await controller.sendInput(input);

          const log = mockSimulator.getInputLog();
          expect(log.length).toBeGreaterThan(0);
          expect(log[0].type).toBe(input.type);
        }),
        { numRuns: 20 }
      );
    }, 30000);
  });

  /**
   * Property 8: 游戏动作到输入命令转换
   * *For any* 有效的 GameAction，Game_Controller 应该能够将其转换为一个或多个 GameInput 命令。
   * **Validates: Requirements 3.1**
   */
  describe('Property 8: Game Action to Input Command Conversion', () => {
    it('should convert valid actions to input commands', () => {
      fc.assert(
        fc.property(validActionArb, action => {
          const inputs = controller.actionToInputs(action);

          // 转换后的输入数量应该与原始动作中的输入数量相同
          expect(inputs.length).toBe(action.inputs.length);

          // 每个输入都应该是有效的
          inputs.forEach(input => {
            const validation = controller.validateInput(input);
            expect(validation.valid).toBe(true);
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve input properties during conversion', () => {
      fc.assert(
        fc.property(validActionArb, action => {
          const inputs = controller.actionToInputs(action);

          // 验证每个输入的属性都被保留
          action.inputs.forEach((originalInput, index) => {
            const convertedInput = inputs[index];
            expect(convertedInput.type).toBe(originalInput.type);
            expect(convertedInput.action).toBe(originalInput.action);

            if (originalInput.key) {
              expect(convertedInput.key).toBe(originalInput.key);
            }
            if (originalInput.button) {
              expect(convertedInput.button).toBe(originalInput.button);
            }
            if (originalInput.position) {
              expect(convertedInput.position).toEqual(originalInput.position);
            }
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should execute valid actions successfully in autonomous mode', async () => {
      // 使用简化的动作生成器，减少输入数量
      const simpleActionArb = fc
        .record({
          name: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
          description: fc.string({ minLength: 0, maxLength: 50 }),
          inputs: fc.array(validKeyboardInputArb, { minLength: 1, maxLength: 3 }),
        })
        .map(({ name, description, inputs }) => ({
          name: name.trim(),
          description,
          inputs: inputs as GameInput[],
        }));

      await fc.assert(
        fc.asyncProperty(simpleActionArb, async action => {
          mockSimulator.clearInputLog();
          controller.setMode('autonomous');

          const result = await controller.executeAction(action);

          expect(result.success).toBe(true);
          expect(result.executedAt).toBeInstanceOf(Date);

          // 验证所有输入都被执行
          const log = mockSimulator.getInputLog();
          expect(log.length).toBe(action.inputs.length);
        }),
        { numRuns: 20 }
      );
    }, 60000);
  });

  /**
   * Property 10: 无效动作拒绝
   * *For any* 无效的 GameAction（如不存在的按键、超出范围的坐标），Game_Controller 应该返回错误结果而不是执行。
   * **Validates: Requirements 3.5**
   */
  describe('Property 10: Invalid Action Rejection', () => {
    it('should reject actions with invalid keyboard keys', () => {
      fc.assert(
        fc.property(invalidKeyArb, invalidKey => {
          const action: GameAction = {
            name: 'invalid_action',
            description: 'Action with invalid key',
            inputs: [{ type: 'keyboard', action: 'press', key: invalidKey }],
          };

          const validation = controller.validateAction(action);
          expect(validation.valid).toBe(false);
          expect(validation.errors.length).toBeGreaterThan(0);
        }),
        { numRuns: 100 }
      );
    });

    it('should reject actions with invalid gamepad buttons', () => {
      fc.assert(
        fc.property(invalidGamepadButtonArb, invalidButton => {
          const action: GameAction = {
            name: 'invalid_action',
            description: 'Action with invalid button',
            inputs: [{ type: 'gamepad', action: 'press', button: invalidButton }],
          };

          const validation = controller.validateAction(action);
          expect(validation.valid).toBe(false);
          expect(validation.errors.length).toBeGreaterThan(0);
        }),
        { numRuns: 100 }
      );
    });

    it('should reject actions with negative mouse coordinates', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: -1000, max: -1 }),
          fc.integer({ min: -1000, max: -1 }),
          (x, y) => {
            const action: GameAction = {
              name: 'invalid_mouse',
              description: 'Action with negative coordinates',
              inputs: [{ type: 'mouse', action: 'move', position: { x, y } }],
            };

            const validation = controller.validateAction(action);
            expect(validation.valid).toBe(false);
            expect(validation.errors.some(e => e.includes('negative'))).toBe(true);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should reject actions with empty name', () => {
      fc.assert(
        fc.property(validInputArb, input => {
          const action: GameAction = {
            name: '',
            description: 'Action with empty name',
            inputs: [input],
          };

          const validation = controller.validateAction(action);
          expect(validation.valid).toBe(false);
          expect(validation.errors).toContain('Action name is required');
        }),
        { numRuns: 50 }
      );
    });

    it('should reject actions with no inputs', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0),
          name => {
            const action: GameAction = {
              name: name.trim(),
              description: 'Action with no inputs',
              inputs: [],
            };

            const validation = controller.validateAction(action);
            expect(validation.valid).toBe(false);
            expect(validation.errors).toContain('Action must have at least one input');
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should return error result when executing invalid actions', async () => {
      await fc.assert(
        fc.asyncProperty(invalidKeyArb, async invalidKey => {
          controller.setMode('autonomous');
          const action: GameAction = {
            name: 'invalid_action',
            description: 'Invalid action',
            inputs: [{ type: 'keyboard', action: 'press', key: invalidKey }],
          };

          const result = await controller.executeAction(action);

          expect(result.success).toBe(false);
          expect(result.error).toBeDefined();
          expect(result.executedAt).toBeInstanceOf(Date);
        }),
        { numRuns: 20 }
      );
    }, 30000);

    it('should not execute any inputs when action is invalid', async () => {
      await fc.assert(
        fc.asyncProperty(invalidKeyArb, async invalidKey => {
          mockSimulator.clearInputLog();
          controller.setMode('autonomous');

          const action: GameAction = {
            name: 'invalid_action',
            description: 'Invalid action',
            inputs: [{ type: 'keyboard', action: 'press', key: invalidKey }],
          };

          await controller.executeAction(action);

          // 无效动作不应该执行任何输入
          const log = mockSimulator.getInputLog();
          expect(log.length).toBe(0);
        }),
        { numRuns: 20 }
      );
    }, 30000);
  });

  /**
   * 控制模式属性测试
   */
  describe('Control Mode Properties', () => {
    it('should reject all actions in manual mode', async () => {
      await fc.assert(
        fc.asyncProperty(validActionArb, async action => {
          controller.setMode('manual');
          const result = await controller.executeAction(action);

          expect(result.success).toBe(false);
          expect(result.error).toBe('Cannot execute action in manual mode');
        }),
        { numRuns: 20 }
      );
    }, 30000);

    it('should execute valid actions in semi-autonomous mode', async () => {
      // 使用简化的动作生成器
      const simpleActionArb = fc
        .record({
          name: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
          description: fc.string({ minLength: 0, maxLength: 50 }),
          inputs: fc.array(validKeyboardInputArb, { minLength: 1, maxLength: 3 }),
        })
        .map(({ name, description, inputs }) => ({
          name: name.trim(),
          description,
          inputs: inputs as GameInput[],
        }));

      await fc.assert(
        fc.asyncProperty(simpleActionArb, async action => {
          mockSimulator.clearInputLog();
          controller.setMode('semi-autonomous');

          const result = await controller.executeAction(action);

          expect(result.success).toBe(true);
        }),
        { numRuns: 20 }
      );
    }, 60000);
  });
});
