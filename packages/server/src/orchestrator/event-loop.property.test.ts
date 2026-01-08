import * as fc from 'fast-check';
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

// Arbitraries
const eventTypeArbitrary = fc.constantFrom<SystemEvent['type']>('chat', 'game_state', 'command', 'system');
const eventDataArbitrary = fc.dictionary(
  fc.string({ minLength: 1, maxLength: 10 }),
  fc.oneof(fc.string(), fc.integer(), fc.boolean()),
  { maxKeys: 5 }
);

const systemEventArbitrary: fc.Arbitrary<SystemEvent> = fc.record({
  id: fc.uuid(),
  type: eventTypeArbitrary,
  data: eventDataArbitrary,
  timestamp: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-12-31') }),
});

/**
 * **Feature: ai-vtuber-digital-human, Property 15: 事件循环顺序**
 * **Validates: Requirements 8.4**
 *
 * For any processed event, the Orchestrator should execute phases
 * in the order: Listen → Think → Act → Speak.
 */
describe('Property 15: 事件循环顺序', () => {
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

  it('should always execute phases in Listen → Think → Act → Speak order', async () => {
    await fc.assert(
      fc.asyncProperty(systemEventArbitrary, async (event) => {
        eventLoop.clearPhaseHistory();

        const result = await eventLoop.processEvent(event);

        // Verify success
        expect(result.success).toBe(true);

        // Verify phase order
        expect(result.phases).toEqual([
          EventPhase.LISTEN,
          EventPhase.THINK,
          EventPhase.ACT,
          EventPhase.SPEAK,
        ]);

        // Verify history matches
        const history = eventLoop.getPhaseHistory();
        expect(history).toEqual([
          EventPhase.LISTEN,
          EventPhase.THINK,
          EventPhase.ACT,
          EventPhase.SPEAK,
        ]);
      }),
      { numRuns: 100 }
    );
  });

  it('should maintain phase order across multiple sequential events', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(systemEventArbitrary, { minLength: 2, maxLength: 5 }),
        async (events) => {
          eventLoop.clearPhaseHistory();

          // Process all events
          for (const event of events) {
            const result = await eventLoop.processEvent(event);
            expect(result.success).toBe(true);
          }

          // Verify history shows correct pattern
          const history = eventLoop.getPhaseHistory();
          const expectedLength = events.length * 4;
          expect(history.length).toBe(expectedLength);

          // Each group of 4 should be in correct order
          for (let i = 0; i < events.length; i++) {
            const offset = i * 4;
            expect(history[offset]).toBe(EventPhase.LISTEN);
            expect(history[offset + 1]).toBe(EventPhase.THINK);
            expect(history[offset + 2]).toBe(EventPhase.ACT);
            expect(history[offset + 3]).toBe(EventPhase.SPEAK);
          }
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should complete all four phases for any event type', async () => {
    await fc.assert(
      fc.asyncProperty(eventTypeArbitrary, eventDataArbitrary, async (eventType, data) => {
        eventLoop.clearPhaseHistory();

        const event: SystemEvent = {
          id: uuidv4(),
          type: eventType,
          data,
          timestamp: new Date(),
        };

        const result = await eventLoop.processEvent(event);

        // All four phases should be completed
        expect(result.phases.length).toBe(4);
        expect(result.phases).toContain(EventPhase.LISTEN);
        expect(result.phases).toContain(EventPhase.THINK);
        expect(result.phases).toContain(EventPhase.ACT);
        expect(result.phases).toContain(EventPhase.SPEAK);
      }),
      { numRuns: 100 }
    );
  });

  it('should never skip phases', async () => {
    await fc.assert(
      fc.asyncProperty(systemEventArbitrary, async (event) => {
        eventLoop.clearPhaseHistory();

        const result = await eventLoop.processEvent(event);

        // No phase should be missing
        const allPhases = [EventPhase.LISTEN, EventPhase.THINK, EventPhase.ACT, EventPhase.SPEAK];

        allPhases.forEach((phase) => {
          expect(result.phases).toContain(phase);
        });

        // No duplicate phases in single event processing
        const uniquePhases = new Set(result.phases);
        expect(uniquePhases.size).toBe(4);
      }),
      { numRuns: 100 }
    );
  });

  it('should return event ID in result', async () => {
    await fc.assert(
      fc.asyncProperty(systemEventArbitrary, async (event) => {
        const result = await eventLoop.processEvent(event);

        expect(result.eventId).toBe(event.id);
      }),
      { numRuns: 100 }
    );
  });

  it('should track positive duration for all events', async () => {
    await fc.assert(
      fc.asyncProperty(systemEventArbitrary, async (event) => {
        const result = await eventLoop.processEvent(event);

        expect(result.duration).toBeGreaterThan(0);
      }),
      { numRuns: 100 }
    );
  });
});
