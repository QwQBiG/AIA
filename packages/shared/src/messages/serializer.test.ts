import { serialize, deserialize, validate, createMessage, isValidMessage } from './serializer.js';
import { SystemMessage } from '../types/system.js';
import { ModuleType, MessageType } from '../types/enums.js';

describe('MessageSerializer', () => {
  const validMessage: SystemMessage = {
    id: '550e8400-e29b-41d4-a716-446655440000',
    type: MessageType.CHAT_MESSAGE,
    timestamp: new Date('2024-01-15T10:30:00.000Z'),
    source: ModuleType.CHAT,
    payload: { content: 'Hello, world!' },
  };

  describe('serialize', () => {
    it('should serialize a valid SystemMessage to JSON string', () => {
      const json = serialize(validMessage);
      const parsed = JSON.parse(json);

      expect(parsed.id).toBe(validMessage.id);
      expect(parsed.type).toBe(validMessage.type);
      expect(parsed.timestamp).toBe('2024-01-15T10:30:00.000Z');
      expect(parsed.source).toBe(validMessage.source);
      expect(parsed.payload).toEqual(validMessage.payload);
    });

    it('should include optional target field when present', () => {
      const messageWithTarget: SystemMessage = {
        ...validMessage,
        target: ModuleType.COGNITION,
      };

      const json = serialize(messageWithTarget);
      const parsed = JSON.parse(json);

      expect(parsed.target).toBe(ModuleType.COGNITION);
    });

    it('should include optional correlationId when present', () => {
      const messageWithCorrelation: SystemMessage = {
        ...validMessage,
        correlationId: '660e8400-e29b-41d4-a716-446655440001',
      };

      const json = serialize(messageWithCorrelation);
      const parsed = JSON.parse(json);

      expect(parsed.correlationId).toBe('660e8400-e29b-41d4-a716-446655440001');
    });
  });

  describe('deserialize', () => {
    it('should deserialize a valid JSON string to SystemMessage', () => {
      const json = serialize(validMessage);
      const deserialized = deserialize(json);

      expect(deserialized.id).toBe(validMessage.id);
      expect(deserialized.type).toBe(validMessage.type);
      expect(deserialized.timestamp.toISOString()).toBe(validMessage.timestamp.toISOString());
      expect(deserialized.source).toBe(validMessage.source);
      expect(deserialized.payload).toEqual(validMessage.payload);
    });

    it('should throw error for invalid JSON', () => {
      expect(() => deserialize('not valid json')).toThrow('Invalid message format');
    });

    it('should throw error for missing required fields', () => {
      const invalidJson = JSON.stringify({ id: '123' });
      expect(() => deserialize(invalidJson)).toThrow('Invalid message format');
    });
  });

  describe('validate', () => {
    it('should return valid: true for valid message', () => {
      const json = serialize(validMessage);
      const result = validate(json);

      expect(result.valid).toBe(true);
      expect(result.errors).toBeUndefined();
    });

    it('should return valid: false for invalid JSON', () => {
      const result = validate('not valid json');

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid JSON format');
    });

    it('should return valid: false for missing required fields', () => {
      const invalidJson = JSON.stringify({
        id: '550e8400-e29b-41d4-a716-446655440000',
        type: MessageType.CHAT_MESSAGE,
      });
      const result = validate(invalidJson);

      expect(result.valid).toBe(false);
      expect(result.errors).toBeDefined();
      expect(result.errors!.length).toBeGreaterThan(0);
    });

    it('should return valid: false for invalid UUID format', () => {
      const invalidJson = JSON.stringify({
        id: 'not-a-uuid',
        type: MessageType.CHAT_MESSAGE,
        timestamp: '2024-01-15T10:30:00.000Z',
        source: ModuleType.CHAT,
        payload: {},
      });
      const result = validate(invalidJson);

      expect(result.valid).toBe(false);
    });

    it('should return valid: false for invalid message type', () => {
      const invalidJson = JSON.stringify({
        id: '550e8400-e29b-41d4-a716-446655440000',
        type: 'invalid.type',
        timestamp: '2024-01-15T10:30:00.000Z',
        source: ModuleType.CHAT,
        payload: {},
      });
      const result = validate(invalidJson);

      expect(result.valid).toBe(false);
    });
  });

  describe('createMessage', () => {
    it('should create a valid SystemMessage with required fields', () => {
      const message = createMessage(MessageType.CHAT_MESSAGE, ModuleType.CHAT, {
        content: 'test',
      });

      expect(message.id).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
      );
      expect(message.type).toBe(MessageType.CHAT_MESSAGE);
      expect(message.source).toBe(ModuleType.CHAT);
      expect(message.payload).toEqual({ content: 'test' });
      expect(message.timestamp).toBeInstanceOf(Date);
    });

    it('should include optional target when provided', () => {
      const message = createMessage(MessageType.COGNITION_REQUEST, ModuleType.CHAT, {}, {
        target: ModuleType.COGNITION,
      });

      expect(message.target).toBe(ModuleType.COGNITION);
    });

    it('should include optional correlationId when provided', () => {
      const correlationId = '550e8400-e29b-41d4-a716-446655440000';
      const message = createMessage(MessageType.COGNITION_RESPONSE, ModuleType.COGNITION, {}, {
        correlationId,
      });

      expect(message.correlationId).toBe(correlationId);
    });
  });

  describe('isValidMessage', () => {
    it('should return true for valid SystemMessage', () => {
      expect(isValidMessage(validMessage)).toBe(true);
    });

    it('should return false for null', () => {
      expect(isValidMessage(null)).toBe(false);
    });

    it('should return false for non-object', () => {
      expect(isValidMessage('string')).toBe(false);
      expect(isValidMessage(123)).toBe(false);
    });

    it('should return false for object missing required fields', () => {
      expect(isValidMessage({ id: '123' })).toBe(false);
    });
  });

  describe('round-trip consistency', () => {
    it('should maintain data integrity through serialize/deserialize cycle', () => {
      const original = createMessage(
        MessageType.GAME_STATE,
        ModuleType.VISION,
        { health: 100, position: { x: 10, y: 20 } },
        { target: ModuleType.COGNITION, correlationId: '550e8400-e29b-41d4-a716-446655440000' }
      );

      const json = serialize(original);
      const restored = deserialize(json);

      expect(restored.id).toBe(original.id);
      expect(restored.type).toBe(original.type);
      expect(restored.timestamp.getTime()).toBe(original.timestamp.getTime());
      expect(restored.source).toBe(original.source);
      expect(restored.target).toBe(original.target);
      expect(restored.payload).toEqual(original.payload);
      expect(restored.correlationId).toBe(original.correlationId);
    });
  });
});
