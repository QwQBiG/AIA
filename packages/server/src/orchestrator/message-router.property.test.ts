import * as fc from 'fast-check';
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

// Arbitraries
const moduleTypeArbitrary = fc.constantFrom(...Object.values(ModuleType));
const messageTypeArbitrary = fc.constantFrom(...Object.values(MessageType));
const payloadArbitrary = fc.dictionary(
  fc.string({ minLength: 1, maxLength: 10 }),
  fc.oneof(fc.string(), fc.integer(), fc.boolean()),
  { maxKeys: 5 }
);

/**
 * **Feature: ai-vtuber-digital-human, Property 14: 消息路由正确性**
 * **Validates: Requirements 8.1**
 *
 * For any SystemMessage with a target module, the Orchestrator should
 * route the message to the correct target module within 50ms.
 */
describe('Property 14: 消息路由正确性', () => {
  let registry: ModuleRegistry;
  let router: MessageRouter;

  beforeEach(() => {
    registry = new ModuleRegistry();
    router = new MessageRouter(registry);
  });

  afterEach(() => {
    registry.clear();
  });

  it('should route messages to correct target module type', async () => {
    await fc.assert(
      fc.asyncProperty(
        moduleTypeArbitrary,
        moduleTypeArbitrary,
        messageTypeArbitrary,
        payloadArbitrary,
        async (sourceType, targetType, msgType, payload) => {
          // Register a module of the target type
          const socket = createMockSocket();
          const moduleId = `${targetType}-test`;
          registry.registerModule(moduleId, targetType, socket);

          // Create and route message
          const message = createMessage(msgType, sourceType, payload, { target: targetType });
          const result = await router.routeMessage(message);

          // Verify routing
          expect(result.success).toBe(true);
          expect(result.targetModuleId).toBe(moduleId);
          expect(socket.emit).toHaveBeenCalled();

          // Cleanup
          registry.unregisterModule(moduleId);
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should complete routing within 50ms latency requirement', async () => {
    await fc.assert(
      fc.asyncProperty(
        moduleTypeArbitrary,
        messageTypeArbitrary,
        payloadArbitrary,
        async (targetType, msgType, payload) => {
          // Register target module
          const socket = createMockSocket();
          const moduleId = `${targetType}-test`;
          registry.registerModule(moduleId, targetType, socket);

          // Create and route message
          const message = createMessage(msgType, ModuleType.DASHBOARD, payload, {
            target: targetType,
          });
          const result = await router.routeMessage(message);

          // Verify latency
          expect(result.latencyMs).toBeLessThan(50);

          // Cleanup
          registry.unregisterModule(moduleId);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should fail gracefully when target module type not registered', async () => {
    await fc.assert(
      fc.asyncProperty(
        moduleTypeArbitrary,
        moduleTypeArbitrary,
        messageTypeArbitrary,
        payloadArbitrary,
        async (sourceType, targetType, msgType, payload) => {
          // Don't register any modules - registry is empty

          const message = createMessage(msgType, sourceType, payload, { target: targetType });
          const result = await router.routeMessage(message);

          // Should fail gracefully
          expect(result.success).toBe(false);
          expect(result.error).toBeDefined();
          expect(result.error).toContain('No modules of type');
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should broadcast to all modules of specified types', () => {
    fc.assert(
      fc.property(
        fc.array(moduleTypeArbitrary, { minLength: 1, maxLength: 5 }),
        messageTypeArbitrary,
        payloadArbitrary,
        (targetTypes, msgType, payload) => {
          // Register one module per target type
          const uniqueTypes = [...new Set(targetTypes)];
          const sockets: Socket[] = [];

          uniqueTypes.forEach((type, index) => {
            const socket = createMockSocket();
            sockets.push(socket);
            registry.registerModule(`${type}-${index}`, type, socket);
          });

          // Broadcast message
          const message = createMessage(msgType, ModuleType.DASHBOARD, payload);
          const results = router.broadcast(message, uniqueTypes);

          // Verify all targets received message
          expect(results.length).toBe(uniqueTypes.length);
          expect(results.every((r) => r.success)).toBe(true);

          // Verify each socket received emit
          sockets.forEach((socket) => {
            expect(socket.emit).toHaveBeenCalled();
          });

          // Cleanup
          registry.clear();
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should prefer healthy modules over unhealthy ones', async () => {
    await fc.assert(
      fc.asyncProperty(moduleTypeArbitrary, messageTypeArbitrary, async (targetType, msgType) => {
        // Register unhealthy module first
        const unhealthySocket = createMockSocket();
        registry.registerModule(`${targetType}-unhealthy`, targetType, unhealthySocket);
        const unhealthyModule = registry.getModule(`${targetType}-unhealthy`);
        if (unhealthyModule) {
          unhealthyModule.health = 'unhealthy';
        }

        // Register healthy module second
        const healthySocket = createMockSocket();
        registry.registerModule(`${targetType}-healthy`, targetType, healthySocket);

        // Route message
        const message = createMessage(msgType, ModuleType.DASHBOARD, {}, { target: targetType });
        const result = await router.routeMessage(message);

        // Should route to healthy module
        expect(result.success).toBe(true);
        expect(result.targetModuleId).toBe(`${targetType}-healthy`);
        expect(healthySocket.emit).toHaveBeenCalled();

        // Cleanup
        registry.clear();
      }),
      { numRuns: 50 }
    );
  });
});
