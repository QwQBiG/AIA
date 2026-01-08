import * as fc from 'fast-check';
import { serialize, deserialize, validate, createMessage } from './serializer';
import { SystemMessage } from '../types/system';
import { ModuleType, MessageType } from '../types/enums';

/**
 * 生成有效的 UUID v4
 */
const uuidArbitrary = fc.uuid();

/**
 * 生成有效的 ModuleType
 */
const moduleTypeArbitrary = fc.constantFrom(...Object.values(ModuleType));

/**
 * 生成有效的 MessageType
 */
const messageTypeArbitrary = fc.constantFrom(...Object.values(MessageType));

/**
 * 生成有效的 payload 对象
 * 注意：避免生成 -0，因为 JSON.stringify(-0) === "0"，会导致往返测试失败
 */
const payloadArbitrary = fc.dictionary(
  fc.string({ minLength: 1, maxLength: 20 }).filter((s) => /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(s)),
  fc.oneof(
    fc.string(),
    fc.integer(),
    fc.double({ noNaN: true, noDefaultInfinity: true }).map((n) => (Object.is(n, -0) ? 0 : n)),
    fc.boolean(),
    fc.constant(null),
    fc.array(fc.string(), { maxLength: 5 }),
    fc.dictionary(fc.string({ minLength: 1, maxLength: 10 }), fc.string(), { maxKeys: 3 })
  ),
  { maxKeys: 10 }
);

/**
 * 生成有效的 SystemMessage
 */
const systemMessageArbitrary: fc.Arbitrary<SystemMessage> = fc.record({
  id: uuidArbitrary,
  type: messageTypeArbitrary,
  timestamp: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-12-31') }),
  source: moduleTypeArbitrary,
  target: fc.option(moduleTypeArbitrary, { nil: undefined }),
  payload: payloadArbitrary,
  correlationId: fc.option(uuidArbitrary, { nil: undefined }),
});

describe('MessageSerializer Property Tests', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 1: 消息序列化往返一致性**
   * **Validates: Requirements 10.4**
   *
   * For any valid SystemMessage object, serializing to JSON and then
   * deserializing should produce an equivalent object.
   */
  describe('Property 1: 消息序列化往返一致性', () => {
    it('should maintain round-trip consistency for all valid SystemMessages', () => {
      fc.assert(
        fc.property(systemMessageArbitrary, (message) => {
          // Serialize the message
          const json = serialize(message);

          // Deserialize back
          const restored = deserialize(json);

          // Verify all fields match
          expect(restored.id).toBe(message.id);
          expect(restored.type).toBe(message.type);
          expect(restored.timestamp.getTime()).toBe(message.timestamp.getTime());
          expect(restored.source).toBe(message.source);
          expect(restored.target).toBe(message.target);
          expect(restored.payload).toEqual(message.payload);
          expect(restored.correlationId).toBe(message.correlationId);
        }),
        { numRuns: 100 }
      );
    });

    it('should produce valid JSON that can be parsed back', () => {
      fc.assert(
        fc.property(systemMessageArbitrary, (message) => {
          const json = serialize(message);

          // Should be valid JSON
          expect(() => JSON.parse(json)).not.toThrow();

          // Should pass validation
          const validation = validate(json);
          expect(validation.valid).toBe(true);
        }),
        { numRuns: 100 }
      );
    });

    it('should preserve payload structure through serialization', () => {
      fc.assert(
        fc.property(
          moduleTypeArbitrary,
          messageTypeArbitrary,
          payloadArbitrary,
          (source, type, payload) => {
            const message = createMessage(type, source, payload);
            const json = serialize(message);
            const restored = deserialize(json);

            // Deep equality check for payload
            expect(restored.payload).toEqual(payload);
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});


describe('Property 2: 消息结构完整性', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 2: 消息结构完整性**
   * **Validates: Requirements 10.1, 10.2, 10.3**
   *
   * For any serialized SystemMessage, the generated JSON must contain
   * id, type, timestamp, source, and payload fields that conform to the defined Schema.
   */
  it('should always include required fields in serialized output', () => {
    fc.assert(
      fc.property(systemMessageArbitrary, (message) => {
        const json = serialize(message);
        const parsed = JSON.parse(json) as Record<string, unknown>;

        // Check all required fields are present
        expect(parsed).toHaveProperty('id');
        expect(parsed).toHaveProperty('type');
        expect(parsed).toHaveProperty('timestamp');
        expect(parsed).toHaveProperty('source');
        expect(parsed).toHaveProperty('payload');

        // Check field types
        expect(typeof parsed.id).toBe('string');
        expect(typeof parsed.type).toBe('string');
        expect(typeof parsed.timestamp).toBe('string');
        expect(typeof parsed.source).toBe('string');
        expect(typeof parsed.payload).toBe('object');
      }),
      { numRuns: 100 }
    );
  });

  it('should produce valid UUID format for id field', () => {
    fc.assert(
      fc.property(systemMessageArbitrary, (message) => {
        const json = serialize(message);
        const parsed = JSON.parse(json) as Record<string, unknown>;

        // UUID v4 format validation
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        expect(parsed.id).toMatch(uuidRegex);
      }),
      { numRuns: 100 }
    );
  });

  it('should produce valid ISO 8601 timestamp format', () => {
    fc.assert(
      fc.property(systemMessageArbitrary, (message) => {
        const json = serialize(message);
        const parsed = JSON.parse(json) as Record<string, unknown>;

        // ISO 8601 format validation
        const timestamp = parsed.timestamp as string;
        const parsedDate = new Date(timestamp);
        expect(parsedDate.toISOString()).toBe(timestamp);
      }),
      { numRuns: 100 }
    );
  });

  it('should only include valid MessageType values', () => {
    fc.assert(
      fc.property(systemMessageArbitrary, (message) => {
        const json = serialize(message);
        const parsed = JSON.parse(json) as Record<string, unknown>;

        const validTypes = Object.values(MessageType);
        expect(validTypes).toContain(parsed.type);
      }),
      { numRuns: 100 }
    );
  });

  it('should only include valid ModuleType values for source', () => {
    fc.assert(
      fc.property(systemMessageArbitrary, (message) => {
        const json = serialize(message);
        const parsed = JSON.parse(json) as Record<string, unknown>;

        const validModules = Object.values(ModuleType);
        expect(validModules).toContain(parsed.source);
      }),
      { numRuns: 100 }
    );
  });

  it('should pass schema validation for all generated messages', () => {
    fc.assert(
      fc.property(systemMessageArbitrary, (message) => {
        const json = serialize(message);
        const validation = validate(json);

        expect(validation.valid).toBe(true);
        expect(validation.errors).toBeUndefined();
      }),
      { numRuns: 100 }
    );
  });
});


/**
 * 生成无效的 JSON 字符串
 */
const invalidJsonArbitrary = fc.oneof(
  // 完全无效的 JSON
  fc.string().filter((s) => {
    try {
      JSON.parse(s);
      return false;
    } catch {
      return true;
    }
  }),
  // 有效 JSON 但不是对象
  fc.constant('null'),
  fc.constant('123'),
  fc.constant('"string"'),
  fc.constant('[]'),
  fc.constant('true')
);

/**
 * 生成缺少必需字段的消息
 */
const missingFieldMessageArbitrary = fc.oneof(
  // 缺少 id
  fc.record({
    type: messageTypeArbitrary,
    timestamp: fc.date().map((d) => d.toISOString()),
    source: moduleTypeArbitrary,
    payload: fc.constant({}),
  }),
  // 缺少 type
  fc.record({
    id: uuidArbitrary,
    timestamp: fc.date().map((d) => d.toISOString()),
    source: moduleTypeArbitrary,
    payload: fc.constant({}),
  }),
  // 缺少 timestamp
  fc.record({
    id: uuidArbitrary,
    type: messageTypeArbitrary,
    source: moduleTypeArbitrary,
    payload: fc.constant({}),
  }),
  // 缺少 source
  fc.record({
    id: uuidArbitrary,
    type: messageTypeArbitrary,
    timestamp: fc.date().map((d) => d.toISOString()),
    payload: fc.constant({}),
  }),
  // 缺少 payload
  fc.record({
    id: uuidArbitrary,
    type: messageTypeArbitrary,
    timestamp: fc.date().map((d) => d.toISOString()),
    source: moduleTypeArbitrary,
  })
);

/**
 * 生成字段类型错误的消息
 */
const wrongTypeMessageArbitrary = fc.oneof(
  // id 不是 UUID 格式
  fc.record({
    id: fc.string({ minLength: 1, maxLength: 10 }).filter((s) => !/^[0-9a-f-]{36}$/.test(s)),
    type: messageTypeArbitrary,
    timestamp: fc.date().map((d) => d.toISOString()),
    source: moduleTypeArbitrary,
    payload: fc.constant({}),
  }),
  // type 不是有效的 MessageType
  fc.record({
    id: uuidArbitrary,
    type: fc.string({ minLength: 1, maxLength: 20 }).filter((s) => !Object.values(MessageType).includes(s as MessageType)),
    timestamp: fc.date().map((d) => d.toISOString()),
    source: moduleTypeArbitrary,
    payload: fc.constant({}),
  }),
  // source 不是有效的 ModuleType
  fc.record({
    id: uuidArbitrary,
    type: messageTypeArbitrary,
    timestamp: fc.date().map((d) => d.toISOString()),
    source: fc.string({ minLength: 1, maxLength: 20 }).filter((s) => !Object.values(ModuleType).includes(s as ModuleType)),
    payload: fc.constant({}),
  })
);

describe('Property 3: 无效消息拒绝', () => {
  /**
   * **Feature: ai-vtuber-digital-human, Property 3: 无效消息拒绝**
   * **Validates: Requirements 10.5**
   *
   * For any malformed JSON string, the deserialization operation should
   * return a validation error instead of throwing an exception or returning a partial object.
   */
  it('should reject invalid JSON strings with validation error', () => {
    fc.assert(
      fc.property(invalidJsonArbitrary, (invalidJson) => {
        const validation = validate(invalidJson);

        expect(validation.valid).toBe(false);
        expect(validation.errors).toBeDefined();
        expect(validation.errors!.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 }
    );
  });

  it('should reject messages missing required fields', () => {
    fc.assert(
      fc.property(missingFieldMessageArbitrary, (partialMessage) => {
        const json = JSON.stringify(partialMessage);
        const validation = validate(json);

        expect(validation.valid).toBe(false);
        expect(validation.errors).toBeDefined();
      }),
      { numRuns: 100 }
    );
  });

  it('should reject messages with wrong field types', () => {
    fc.assert(
      fc.property(wrongTypeMessageArbitrary, (wrongTypeMessage) => {
        const json = JSON.stringify(wrongTypeMessage);
        const validation = validate(json);

        expect(validation.valid).toBe(false);
        expect(validation.errors).toBeDefined();
      }),
      { numRuns: 100 }
    );
  });

  it('should throw error when deserializing invalid messages', () => {
    fc.assert(
      fc.property(missingFieldMessageArbitrary, (partialMessage) => {
        const json = JSON.stringify(partialMessage);

        expect(() => deserialize(json)).toThrow('Invalid message format');
      }),
      { numRuns: 100 }
    );
  });

  it('should not return partial objects for invalid input', () => {
    fc.assert(
      fc.property(invalidJsonArbitrary, (invalidJson) => {
        // validate should return a proper ValidationResult, not throw
        const validation = validate(invalidJson);

        expect(validation).toHaveProperty('valid');
        expect(validation).toHaveProperty('errors');
        expect(typeof validation.valid).toBe('boolean');
      }),
      { numRuns: 100 }
    );
  });
});
