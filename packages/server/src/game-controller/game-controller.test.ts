import { GameController } from './game-controller.js';
import { MockInputSimulator } from './input-simulator.js';
import { GameInput, GameAction } from './types.js';

describe('GameController', () => {
  let controller: GameController;
  let mockSimulator: MockInputSimulator;

  beforeEach(() => {
    mockSimulator = new MockInputSimulator();
    controller = new GameController(mockSimulator, { inputDelay: 0, mode: 'autonomous' });
  });

  describe('Control Mode', () => {
    it('should start with the configured mode', () => {
      expect(controller.getMode()).toBe('autonomous');
    });

    it('should allow changing control mode', () => {
      controller.setMode('manual');
      expect(controller.getMode()).toBe('manual');

      controller.setMode('semi-autonomous');
      expect(controller.getMode()).toBe('semi-autonomous');
    });
  });

  describe('Input Validation', () => {
    it('should validate valid keyboard input', () => {
      const input: GameInput = {
        type: 'keyboard',
        action: 'press',
        key: 'w',
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject invalid keyboard key', () => {
      const input: GameInput = {
        type: 'keyboard',
        action: 'press',
        key: 'invalid_key_123',
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid keyboard key: invalid_key_123');
    });

    it('should validate valid mouse input', () => {
      const input: GameInput = {
        type: 'mouse',
        action: 'click',
        position: { x: 100, y: 200 },
        button: 'left',
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(true);
    });

    it('should reject mouse move without position', () => {
      const input: GameInput = {
        type: 'mouse',
        action: 'move',
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Mouse move requires position');
    });

    it('should reject negative mouse position', () => {
      const input: GameInput = {
        type: 'mouse',
        action: 'move',
        position: { x: -10, y: 100 },
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Mouse position cannot be negative');
    });

    it('should validate valid gamepad input', () => {
      const input: GameInput = {
        type: 'gamepad',
        action: 'press',
        button: 'a',
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(true);
    });

    it('should reject invalid gamepad button', () => {
      const input: GameInput = {
        type: 'gamepad',
        action: 'press',
        button: 'invalid_button',
      };
      const result = controller.validateInput(input);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid gamepad button: invalid_button');
    });
  });

  describe('Action Validation', () => {
    it('should validate valid action', () => {
      const action: GameAction = {
        name: 'jump',
        description: 'Jump action',
        inputs: [
          { type: 'keyboard', action: 'press', key: 'space' },
          { type: 'keyboard', action: 'release', key: 'space' },
        ],
      };
      const result = controller.validateAction(action);
      expect(result.valid).toBe(true);
    });

    it('should reject action without name', () => {
      const action: GameAction = {
        name: '',
        description: 'Empty name action',
        inputs: [{ type: 'keyboard', action: 'press', key: 'w' }],
      };
      const result = controller.validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Action name is required');
    });

    it('should reject action without inputs', () => {
      const action: GameAction = {
        name: 'empty',
        description: 'No inputs',
        inputs: [],
      };
      const result = controller.validateAction(action);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Action must have at least one input');
    });

    it('should reject action with invalid inputs', () => {
      const action: GameAction = {
        name: 'invalid',
        description: 'Invalid inputs',
        inputs: [{ type: 'keyboard', action: 'press', key: 'invalid_key' }],
      };
      const result = controller.validateAction(action);
      expect(result.valid).toBe(false);
    });
  });

  describe('Action Execution', () => {
    it('should execute valid action in autonomous mode', async () => {
      const action: GameAction = {
        name: 'move_forward',
        description: 'Move forward',
        inputs: [{ type: 'keyboard', action: 'press', key: 'w' }],
      };

      const result = await controller.executeAction(action);
      expect(result.success).toBe(true);
      expect(result.executedAt).toBeInstanceOf(Date);
    });

    it('should reject action in manual mode', async () => {
      controller.setMode('manual');
      const action: GameAction = {
        name: 'move_forward',
        description: 'Move forward',
        inputs: [{ type: 'keyboard', action: 'press', key: 'w' }],
      };

      const result = await controller.executeAction(action);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Cannot execute action in manual mode');
    });

    it('should execute action in semi-autonomous mode', async () => {
      controller.setMode('semi-autonomous');
      const action: GameAction = {
        name: 'attack',
        description: 'Attack',
        inputs: [{ type: 'mouse', action: 'click', button: 'left' }],
      };

      const result = await controller.executeAction(action);
      expect(result.success).toBe(true);
    });

    it('should return error for invalid action', async () => {
      const action: GameAction = {
        name: '',
        description: 'Invalid',
        inputs: [],
      };

      const result = await controller.executeAction(action);
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it('should execute multiple inputs in sequence', async () => {
      const action: GameAction = {
        name: 'combo',
        description: 'Combo action',
        inputs: [
          { type: 'keyboard', action: 'press', key: 'w' },
          { type: 'keyboard', action: 'press', key: 'space' },
          { type: 'keyboard', action: 'release', key: 'w' },
          { type: 'keyboard', action: 'release', key: 'space' },
        ],
      };

      const result = await controller.executeAction(action);
      expect(result.success).toBe(true);

      const log = mockSimulator.getInputLog();
      expect(log).toHaveLength(4);
      expect(log[0].details.key).toBe('w');
      expect(log[1].details.key).toBe('space');
    });
  });

  describe('Action to Inputs Conversion', () => {
    it('should convert action to inputs', () => {
      const action: GameAction = {
        name: 'test',
        description: 'Test action',
        inputs: [
          { type: 'keyboard', action: 'press', key: 'a' },
          { type: 'mouse', action: 'click', button: 'left' },
        ],
      };

      const inputs = controller.actionToInputs(action);
      expect(inputs).toHaveLength(2);
      expect(inputs[0].type).toBe('keyboard');
      expect(inputs[1].type).toBe('mouse');
    });

    it('should return a copy of inputs', () => {
      const action: GameAction = {
        name: 'test',
        description: 'Test',
        inputs: [{ type: 'keyboard', action: 'press', key: 'w' }],
      };

      const inputs = controller.actionToInputs(action);
      inputs[0].key = 'modified';

      expect(action.inputs[0].key).toBe('w');
    });
  });

  describe('Send Input', () => {
    it('should send keyboard input', async () => {
      const input: GameInput = {
        type: 'keyboard',
        action: 'press',
        key: 'W',
      };

      await controller.sendInput(input);

      const log = mockSimulator.getInputLog();
      expect(log).toHaveLength(1);
      expect(log[0].type).toBe('keyboard');
      expect(log[0].details.key).toBe('w'); // Should be lowercase
    });

    it('should send mouse input', async () => {
      const input: GameInput = {
        type: 'mouse',
        action: 'move',
        position: { x: 500, y: 300 },
      };

      await controller.sendInput(input);

      const log = mockSimulator.getInputLog();
      expect(log).toHaveLength(1);
      expect(log[0].type).toBe('mouse');
      expect(log[0].details.position).toEqual({ x: 500, y: 300 });
    });

    it('should send gamepad input', async () => {
      const input: GameInput = {
        type: 'gamepad',
        action: 'press',
        button: 'A',
      };

      await controller.sendInput(input);

      const log = mockSimulator.getInputLog();
      expect(log).toHaveLength(1);
      expect(log[0].type).toBe('gamepad');
      expect(log[0].details.button).toBe('a'); // Should be lowercase
    });

    it('should throw error for invalid input', async () => {
      const input: GameInput = {
        type: 'keyboard',
        action: 'press',
        key: 'invalid_key',
      };

      await expect(controller.sendInput(input)).rejects.toThrow('Invalid input');
    });
  });
});
