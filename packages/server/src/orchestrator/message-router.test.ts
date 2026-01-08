import { MessageRouter } from './message-router';
import { ModuleRegistry } from './module-registry';
import { ModuleType, MessageType, createMessage } from '@digital-human/shared';
import { Socket } from 'socket.io';

// Mock Socket factory
const createMockSocket = (connected = true): Socket => {
  return {
    id: `socket-${Math.random().toString(36).substr(2, 9)}`,
    connected,
    emit: jest.fn(),
    on: jest.fn(),
    disconnect: jest.fn(),
  } as unknown as Socket;
};

describe('MessageRouter', () => {
  let registry: ModuleRegistry;
  let router: MessageRouter;

  beforeEach(() => {
    registry = new ModuleRegistry();
    router = new MessageRouter(registry);
  });

  afterEach(() => {
    registry.clear();
  });

  describe('routeMessage', () => {
    it('should route message to target module', async () => {
      const socket = createMockSocket();
      registry.registerModule('cog-1', ModuleType.COGNITION, socket);

      const message = createMessage(
        MessageType.COGNITION_REQUEST,
        ModuleType.CHAT,
        { content: 'test' },
        { target: ModuleType.COGNITION }
      );

      const result = await router.routeMessage(message);

      expect(result.success).toBe(true);
      expect(result.targetModuleId).toBe('cog-1');
      expect(result.latencyMs).toBeLessThan(50);
      expect(socket.emit).toHaveBeenCalled();
    });

    it('should return error when no target specified', async () => {
      const message = createMessage(MessageType.CHAT_MESSAGE, ModuleType.CHAT, { content: 'test' });

      const result = await router.routeMessage(message);

      expect(result.success).toBe(false);
      expect(result.error).toBe('No target module specified');
    });

    it('should return error when no modules of target type exist', async () => {
      const message = createMessage(
        MessageType.COGNITION_REQUEST,
        ModuleType.CHAT,
        { content: 'test' },
        { target: ModuleType.COGNITION }
      );

      const result = await router.routeMessage(message);

      expect(result.success).toBe(false);
      expect(result.error).toContain('No modules of type');
    });

    it('should prefer healthy modules', async () => {
      const unhealthySocket = createMockSocket();
      const healthySocket = createMockSocket();

      registry.registerModule('cog-unhealthy', ModuleType.COGNITION, unhealthySocket);
      registry.registerModule('cog-healthy', ModuleType.COGNITION, healthySocket);

      // Mark first module as unhealthy
      const unhealthyModule = registry.getModule('cog-unhealthy');
      if (unhealthyModule) {
        unhealthyModule.health = 'unhealthy';
      }

      const message = createMessage(
        MessageType.COGNITION_REQUEST,
        ModuleType.CHAT,
        { content: 'test' },
        { target: ModuleType.COGNITION }
      );

      const result = await router.routeMessage(message);

      expect(result.success).toBe(true);
      expect(result.targetModuleId).toBe('cog-healthy');
    });

    it('should return error when target module is disconnected', async () => {
      const socket = createMockSocket(false); // disconnected
      registry.registerModule('cog-1', ModuleType.COGNITION, socket);

      const message = createMessage(
        MessageType.COGNITION_REQUEST,
        ModuleType.CHAT,
        { content: 'test' },
        { target: ModuleType.COGNITION }
      );

      const result = await router.routeMessage(message);

      expect(result.success).toBe(false);
      expect(result.error).toContain('not connected');
    });
  });

  describe('broadcast', () => {
    it('should broadcast to all modules of specified types', () => {
      const cogSocket = createMockSocket();
      const memSocket = createMockSocket();
      const ttsSocket = createMockSocket();

      registry.registerModule('cog-1', ModuleType.COGNITION, cogSocket);
      registry.registerModule('mem-1', ModuleType.MEMORY, memSocket);
      registry.registerModule('tts-1', ModuleType.TTS, ttsSocket);

      const message = createMessage(MessageType.SYSTEM_ALERT, ModuleType.DASHBOARD, {
        alert: 'test',
      });

      const results = router.broadcast(message, [ModuleType.COGNITION, ModuleType.MEMORY]);

      expect(results.length).toBe(2);
      expect(results.every((r) => r.success)).toBe(true);
      expect(cogSocket.emit).toHaveBeenCalled();
      expect(memSocket.emit).toHaveBeenCalled();
      expect(ttsSocket.emit).not.toHaveBeenCalled();
    });

    it('should handle disconnected modules in broadcast', () => {
      const connectedSocket = createMockSocket(true);
      const disconnectedSocket = createMockSocket(false);

      registry.registerModule('cog-1', ModuleType.COGNITION, connectedSocket);
      registry.registerModule('cog-2', ModuleType.COGNITION, disconnectedSocket);

      const message = createMessage(MessageType.SYSTEM_ALERT, ModuleType.DASHBOARD, {
        alert: 'test',
      });

      const results = router.broadcast(message, [ModuleType.COGNITION]);

      expect(results.length).toBe(2);
      expect(results.filter((r) => r.success).length).toBe(1);
      expect(results.filter((r) => !r.success).length).toBe(1);
    });
  });

  describe('broadcastAll', () => {
    it('should broadcast to all registered modules', () => {
      const cogSocket = createMockSocket();
      const memSocket = createMockSocket();

      registry.registerModule('cog-1', ModuleType.COGNITION, cogSocket);
      registry.registerModule('mem-1', ModuleType.MEMORY, memSocket);

      const message = createMessage(MessageType.SYSTEM_ALERT, ModuleType.DASHBOARD, {
        alert: 'test',
      });

      const results = router.broadcastAll(message);

      expect(results.length).toBe(2);
      expect(cogSocket.emit).toHaveBeenCalled();
      expect(memSocket.emit).toHaveBeenCalled();
    });
  });

  describe('routeToModule', () => {
    it('should route to specific module by ID', () => {
      const socket = createMockSocket();
      registry.registerModule('cog-1', ModuleType.COGNITION, socket);

      const message = createMessage(MessageType.COGNITION_REQUEST, ModuleType.CHAT, {
        content: 'test',
      });

      const result = router.routeToModule(message, 'cog-1');

      expect(result.success).toBe(true);
      expect(result.targetModuleId).toBe('cog-1');
      expect(socket.emit).toHaveBeenCalled();
    });

    it('should return error for non-existent module', () => {
      const message = createMessage(MessageType.COGNITION_REQUEST, ModuleType.CHAT, {
        content: 'test',
      });

      const result = router.routeToModule(message, 'non-existent');

      expect(result.success).toBe(false);
      expect(result.error).toContain('not found');
    });

    it('should return error for disconnected module', () => {
      const socket = createMockSocket(false);
      registry.registerModule('cog-1', ModuleType.COGNITION, socket);

      const message = createMessage(MessageType.COGNITION_REQUEST, ModuleType.CHAT, {
        content: 'test',
      });

      const result = router.routeToModule(message, 'cog-1');

      expect(result.success).toBe(false);
      expect(result.error).toContain('not connected');
    });
  });

  describe('latency', () => {
    it('should complete routing within 50ms', async () => {
      const socket = createMockSocket();
      registry.registerModule('cog-1', ModuleType.COGNITION, socket);

      const message = createMessage(
        MessageType.COGNITION_REQUEST,
        ModuleType.CHAT,
        { content: 'test' },
        { target: ModuleType.COGNITION }
      );

      const result = await router.routeMessage(message);

      expect(result.latencyMs).toBeLessThan(50);
    });
  });
});
