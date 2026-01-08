import { AvatarRenderer, createAvatarRenderer } from './avatar-renderer';
import { AvatarConfig, AudioStream } from './types';
import { EmotionType } from '@digital-human/shared';

describe('AvatarRenderer', () => {
  let renderer: AvatarRenderer;

  beforeEach(() => {
    renderer = new AvatarRenderer();
  });

  afterEach(() => {
    renderer.destroy();
  });

  describe('loadAvatar', () => {
    it('should load Live2D avatar successfully', async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      const result = await renderer.loadAvatar(config);

      expect(result.success).toBe(true);
      expect(result.loadTime).toBeLessThanOrEqual(5000);
      expect(renderer.isLoaded()).toBe(true);
    });

    it('should load 3D avatar successfully', async () => {
      const config: AvatarConfig = {
        type: '3d',
        modelPath: '/models/avatar.glb',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      const result = await renderer.loadAvatar(config);

      expect(result.success).toBe(true);
      expect(result.loadTime).toBeLessThanOrEqual(5000);
      expect(renderer.isLoaded()).toBe(true);
    });

    it('should unload previous avatar when loading new one', async () => {
      const config1: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar1.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      const config2: AvatarConfig = {
        type: '3d',
        modelPath: '/models/avatar2.glb',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      await renderer.loadAvatar(config1);
      expect(renderer.isLoaded()).toBe(true);

      await renderer.loadAvatar(config2);
      expect(renderer.isLoaded()).toBe(true);
    });

    it('should return load time within 5 seconds', async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      const result = await renderer.loadAvatar(config);

      expect(result.loadTime).toBeLessThanOrEqual(5000);
    });
  });


  describe('unloadAvatar', () => {
    it('should unload avatar and reset state', async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      await renderer.loadAvatar(config);
      expect(renderer.isLoaded()).toBe(true);

      renderer.unloadAvatar();
      expect(renderer.isLoaded()).toBe(false);
    });

    it('should reset expression to neutral after unload', async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };

      await renderer.loadAvatar(config);
      renderer.setExpression('happy');
      expect(renderer.getCurrentExpression()).toBe('happy');

      renderer.unloadAvatar();
      expect(renderer.getCurrentExpression()).toBe('neutral');
    });
  });

  describe('setExpression', () => {
    beforeEach(async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };
      await renderer.loadAvatar(config);
    });

    it('should set expression to happy', () => {
      renderer.setExpression('happy');
      expect(renderer.getCurrentExpression()).toBe('happy');
    });

    it('should set expression to sad', () => {
      renderer.setExpression('sad');
      expect(renderer.getCurrentExpression()).toBe('sad');
    });

    it('should set expression to surprised', () => {
      renderer.setExpression('surprised');
      expect(renderer.getCurrentExpression()).toBe('surprised');
    });

    it('should set expression to angry', () => {
      renderer.setExpression('angry');
      expect(renderer.getCurrentExpression()).toBe('angry');
    });

    it('should set expression to thinking', () => {
      renderer.setExpression('thinking');
      expect(renderer.getCurrentExpression()).toBe('thinking');
    });

    it('should set expression to neutral', () => {
      renderer.setExpression('happy');
      renderer.setExpression('neutral');
      expect(renderer.getCurrentExpression()).toBe('neutral');
    });

    it('should not change expression if not loaded', () => {
      renderer.unloadAvatar();
      renderer.setExpression('happy');
      expect(renderer.getCurrentExpression()).toBe('neutral');
    });
  });

  describe('playAnimation', () => {
    it('should not throw when playing animation on loaded avatar', async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };
      await renderer.loadAvatar(config);

      expect(() => renderer.playAnimation('idle')).not.toThrow();
    });

    it('should not throw when playing animation on unloaded avatar', () => {
      expect(() => renderer.playAnimation('idle')).not.toThrow();
    });
  });


  describe('lipSync', () => {
    beforeEach(async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };
      await renderer.loadAvatar(config);
    });

    it('should start lip sync without throwing', () => {
      const audioStream: AudioStream = {
        format: 'wav',
        sampleRate: 44100,
        data: new ArrayBuffer(1024),
        duration: 1000,
      };

      expect(() => renderer.startLipSync(audioStream)).not.toThrow();
    });

    it('should stop lip sync without throwing', () => {
      expect(() => renderer.stopLipSync()).not.toThrow();
    });
  });

  describe('idleAnimation', () => {
    beforeEach(async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };
      await renderer.loadAvatar(config);
    });

    it('should enable idle animation', () => {
      renderer.setIdleAnimation(true);
      // No error should be thrown
    });

    it('should disable idle animation', () => {
      renderer.setIdleAnimation(false);
      // No error should be thrown
    });
  });

  describe('getSupportedEmotions', () => {
    it('should return all supported emotion types', () => {
      const emotions = renderer.getSupportedEmotions();

      expect(emotions).toContain('neutral');
      expect(emotions).toContain('happy');
      expect(emotions).toContain('sad');
      expect(emotions).toContain('surprised');
      expect(emotions).toContain('angry');
      expect(emotions).toContain('thinking');
    });
  });

  describe('createAvatarRenderer', () => {
    it('should create a new AvatarRenderer instance', () => {
      const newRenderer = createAvatarRenderer();
      expect(newRenderer).toBeDefined();
      expect(newRenderer.isLoaded()).toBe(false);
      newRenderer.destroy();
    });
  });

  describe('destroy', () => {
    it('should clean up resources', async () => {
      const config: AvatarConfig = {
        type: 'live2d',
        modelPath: '/models/avatar.model3.json',
        scale: 1.0,
        position: { x: 0, y: 0 },
      };
      await renderer.loadAvatar(config);

      renderer.destroy();
      expect(renderer.isLoaded()).toBe(false);
    });
  });
});
