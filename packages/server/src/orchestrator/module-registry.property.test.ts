import * as fc from 'fast-check';
import { ModuleRegistry } from './module-registry';
import { ModuleType } from '@digital-human/shared';
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
const moduleIdArbitrary = fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0);
const moduleTypeArbitrary = fc.constantFrom(...Object.values(ModuleType));

/**
 * **Feature: ai-vtuber-digital-human, Property 13: 模块注册和状态追踪**
 * **Validates: Requirements 8.2**
 *
 * For any module that connects to the Orchestrator, the system should
 * correctly register and track its health status.
 */
describe('Property 13: 模块注册和状态追踪', () => {
  let registry: ModuleRegistry;

  beforeEach(() => {
    registry = new ModuleRegistry({ heartbeatInterval: 100, heartbeatTimeout: 300 });
  });

  afterEach(() => {
    registry.stopHealthCheck();
    registry.clear();
  });

  it('should correctly register any valid module', () => {
    fc.assert(
      fc.property(moduleIdArbitrary, moduleTypeArbitrary, (moduleId, moduleType) => {
        const socket = createMockSocket();
        registry.registerModule(moduleId, moduleType, socket);

        // Module should be registered
        expect(registry.hasModule(moduleId)).toBe(true);

        // Module status should be retrievable
        const status = registry.getModuleStatus(moduleId);
        expect(status).not.toBeNull();
        expect(status?.moduleId).toBe(moduleId);
        expect(status?.moduleType).toBe(moduleType);
        expect(status?.health).toBe('healthy');

        // Cleanup for next iteration
        registry.unregisterModule(moduleId);
      }),
      { numRuns: 100 }
    );
  });

  it('should track module count correctly after registrations', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(moduleIdArbitrary, moduleTypeArbitrary), { minLength: 1, maxLength: 20 }),
        (modules) => {
          // Filter to unique module IDs
          const uniqueModules = modules.filter(
            (m, i, arr) => arr.findIndex((x) => x[0] === m[0]) === i
          );

          uniqueModules.forEach(([moduleId, moduleType]) => {
            const socket = createMockSocket();
            registry.registerModule(moduleId, moduleType, socket);
          });

          expect(registry.getModuleCount()).toBe(uniqueModules.length);

          // Cleanup
          registry.clear();
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should correctly unregister modules', () => {
    fc.assert(
      fc.property(moduleIdArbitrary, moduleTypeArbitrary, (moduleId, moduleType) => {
        const socket = createMockSocket();
        registry.registerModule(moduleId, moduleType, socket);

        // Unregister
        const result = registry.unregisterModule(moduleId);

        expect(result).toBe(true);
        expect(registry.hasModule(moduleId)).toBe(false);
        expect(registry.getModuleStatus(moduleId)).toBeNull();
      }),
      { numRuns: 100 }
    );
  });

  it('should correctly track modules by type', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(moduleIdArbitrary, moduleTypeArbitrary), { minLength: 1, maxLength: 10 }),
        (modules) => {
          // Filter to unique module IDs
          const uniqueModules = modules.filter(
            (m, i, arr) => arr.findIndex((x) => x[0] === m[0]) === i
          );

          uniqueModules.forEach(([moduleId, moduleType]) => {
            const socket = createMockSocket();
            registry.registerModule(moduleId, moduleType, socket);
          });

          // Count modules by type
          const expectedCounts = new Map<ModuleType, number>();
          uniqueModules.forEach(([, moduleType]) => {
            expectedCounts.set(moduleType, (expectedCounts.get(moduleType) || 0) + 1);
          });

          // Verify counts match
          expectedCounts.forEach((count, type) => {
            const modulesOfType = registry.getModulesByType(type);
            expect(modulesOfType.length).toBe(count);
          });

          // Cleanup
          registry.clear();
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should update heartbeat and maintain healthy status', () => {
    fc.assert(
      fc.property(moduleIdArbitrary, moduleTypeArbitrary, (moduleId, moduleType) => {
        const socket = createMockSocket();
        registry.registerModule(moduleId, moduleType, socket);

        // Update heartbeat
        const result = registry.updateHeartbeat(moduleId);

        expect(result).toBe(true);

        const status = registry.getModuleStatus(moduleId);
        expect(status?.health).toBe('healthy');

        // Cleanup
        registry.unregisterModule(moduleId);
      }),
      { numRuns: 100 }
    );
  });

  it('should return all registered modules in getAllModuleStatus', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(moduleIdArbitrary, moduleTypeArbitrary), { minLength: 1, maxLength: 10 }),
        (modules) => {
          // Filter to unique module IDs
          const uniqueModules = modules.filter(
            (m, i, arr) => arr.findIndex((x) => x[0] === m[0]) === i
          );

          uniqueModules.forEach(([moduleId, moduleType]) => {
            const socket = createMockSocket();
            registry.registerModule(moduleId, moduleType, socket);
          });

          const allStatuses = registry.getAllModuleStatus();

          expect(allStatuses.length).toBe(uniqueModules.length);

          // All registered modules should be in the status list
          uniqueModules.forEach(([moduleId]) => {
            const found = allStatuses.find((s) => s.moduleId === moduleId);
            expect(found).toBeDefined();
          });

          // Cleanup
          registry.clear();
        }
      ),
      { numRuns: 50 }
    );
  });
});
