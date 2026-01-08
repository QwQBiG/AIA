import { EventLoop, EventPhase, SystemEvent } from './event-loop';
import { MessageRouter } from './message-router';
import { ModuleRegistry } from './module-registry';
import { ModuleType } from '@digital-human/shared';
import { Socket } from 'socket.io';
import { v4 as uuidv4 } from 'uuid';

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

// Helper to create test events
const createTestEvent = (type: SystemEvent['type'] = 'chat'): SystemEvent => ({
  id: uuidv4(),
  type,
  data: { content: 'test message' },
  timestamp: new Date(),
});

describe('EventLoop', () => {
  let registry: ModuleRegistry;
  let router: MessageRouter;
  let eventLoop: EventLoop;

  beforeEach(() => {
    registry = new ModuleRegistry();
    router = new MessageRouter(registry);
    eventLoop = new EventLoop(router, { processInterval: 50 });

    // Register mock modules for all types
    Object.values(ModuleType).forEach((type) => {
      const socket = createMockSocket();
      registry.registerModule(`${type}-1`, type, socket);
    });
  });

  afterEach(() => {
    eventLoop.stopEventLoop();
    registry.clear();
  });

  describe('startEventLoop/stopEventLoop', () => {
    it('should start the event loop', () => {
      eventLoop.startEventLoop();
      expect(eventLoop.getIsRunning()).toBe(true);
    });

    it('should stop the event loop', () => {
      eventLoop.startEventLoop();
      eventLoop.stopEventLoop();
      expect(eventLoop.getIsRunning()).toBe(false);
    });

    it('should not start twice', () => {
      eventLoop.startEventLoop();
      eventLoop.startEventLoop();
      expect(eventLoop.getIsRunning()).toBe(true);
    });

    it('should not stop twice', () => {
      eventLoop.startEventLoop();
      eventLoop.stopEventLoop();
      eventLoop.stopEventLoop();
      expect(eventLoop.getIsRunning()).toBe(false);
    });
  });

  describe('queueEvent', () => {
    it('should add event to queue', () => {
      const event = createTestEvent();
      const result = eventLoop.queueEvent(event);

      expect(result).toBe(true);
      expect(eventLoop.getQueueLength()).toBe(1);
    });

    it('should reject events when queue is full', () => {
      const smallQueueLoop = new EventLoop(router, { maxQueueSize: 2 });

      smallQueueLoop.queueEvent(createTestEvent());
      smallQueueLoop.queueEvent(createTestEvent());
      const result = smallQueueLoop.queueEvent(createTestEvent());

      expect(result).toBe(false);
      expect(smallQueueLoop.getQueueLength()).toBe(2);
    });
  });

  describe('processEvent', () => {
    it('should process event through all phases', async () => {
      const event = createTestEvent();
      const result = await eventLoop.processEvent(event);

      expect(result.success).toBe(true);
      expect(result.eventId).toBe(event.id);
      expect(result.phases).toEqual([
        EventPhase.LISTEN,
        EventPhase.THINK,
        EventPhase.ACT,
        EventPhase.SPEAK,
      ]);
    });

    it('should execute phases in correct order', async () => {
      const event = createTestEvent();
      await eventLoop.processEvent(event);

      const history = eventLoop.getPhaseHistory();
      expect(history).toEqual([
        EventPhase.LISTEN,
        EventPhase.THINK,
        EventPhase.ACT,
        EventPhase.SPEAK,
      ]);
    });

    it('should track duration', async () => {
      const event = createTestEvent();
      const result = await eventLoop.processEvent(event);

      expect(result.duration).toBeGreaterThan(0);
    });
  });

  describe('phase execution', () => {
    it('should update current phase during processing', async () => {
      const event = createTestEvent();

      // Start processing
      const processPromise = eventLoop.processEvent(event);

      // Wait for completion
      await processPromise;

      // After completion, should be at SPEAK phase
      expect(eventLoop.getCurrentPhase()).toBe(EventPhase.SPEAK);
    });

    it('should accumulate phase history across multiple events', async () => {
      await eventLoop.processEvent(createTestEvent());
      await eventLoop.processEvent(createTestEvent());

      const history = eventLoop.getPhaseHistory();
      expect(history.length).toBe(8); // 4 phases × 2 events
    });

    it('should clear phase history', async () => {
      await eventLoop.processEvent(createTestEvent());
      eventLoop.clearPhaseHistory();

      expect(eventLoop.getPhaseHistory()).toEqual([]);
    });
  });

  describe('automatic processing', () => {
    it('should process queued events automatically', async () => {
      const event = createTestEvent();
      eventLoop.queueEvent(event);

      eventLoop.startEventLoop();

      // Wait for processing
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(eventLoop.getQueueLength()).toBe(0);
    });
  });

  describe('event types', () => {
    it('should handle chat events', async () => {
      const event = createTestEvent('chat');
      const result = await eventLoop.processEvent(event);
      expect(result.success).toBe(true);
    });

    it('should handle game_state events', async () => {
      const event = createTestEvent('game_state');
      const result = await eventLoop.processEvent(event);
      expect(result.success).toBe(true);
    });

    it('should handle command events', async () => {
      const event = createTestEvent('command');
      const result = await eventLoop.processEvent(event);
      expect(result.success).toBe(true);
    });

    it('should handle system events', async () => {
      const event = createTestEvent('system');
      const result = await eventLoop.processEvent(event);
      expect(result.success).toBe(true);
    });
  });
});
