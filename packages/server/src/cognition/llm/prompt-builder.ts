/**
 * Prompt Builder
 * 提示词构建工具
 */

import {
  CognitionInput,
  CognitionOutput,
  EmotionType,
  GameAction,
} from '@digital-human/shared';
import { OpenAIChatMessage, AnthropicMessage } from './types';

/**
 * 构建 OpenAI 格式的消息列表
 */
export function buildPromptMessages(input: CognitionInput): OpenAIChatMessage[] {
  const messages: OpenAIChatMessage[] = [];

  // 系统提示词
  messages.push({
    role: 'system',
    content: input.systemPrompt,
  });

  // 添加记忆上下文
  if (input.memories.length > 0) {
    const memoryContext = input.memories
      .map((m) => `[${m.timestamp.toISOString()}] ${m.content}`)
      .join('\n');
    
    messages.push({
      role: 'system',
      content: `相关记忆上下文:\n${memoryContext}`,
    });
  }

  // 添加游戏状态
  if (input.gameState) {
    const gameContext = formatGameState(input.gameState);
    messages.push({
      role: 'system',
      content: `当前游戏状态:\n${gameContext}`,
    });
  }

  // 添加用户消息
  if (input.chatMessage) {
    messages.push({
      role: 'user',
      content: `[${input.chatMessage.sender.displayName}]: ${input.chatMessage.content}`,
    });
  }

  // 添加响应格式指令
  messages.push({
    role: 'system',
    content: getResponseFormatInstruction(),
  });

  return messages;
}

/**
 * 构建 Anthropic 格式的消息
 */
export function buildAnthropicMessages(input: CognitionInput): {
  systemPrompt: string;
  messages: AnthropicMessage[];
} {
  let systemPrompt = input.systemPrompt;

  // 添加记忆上下文到系统提示
  if (input.memories.length > 0) {
    const memoryContext = input.memories
      .map((m) => `[${m.timestamp.toISOString()}] ${m.content}`)
      .join('\n');
    systemPrompt += `\n\n相关记忆上下文:\n${memoryContext}`;
  }

  // 添加游戏状态到系统提示
  if (input.gameState) {
    const gameContext = formatGameState(input.gameState);
    systemPrompt += `\n\n当前游戏状态:\n${gameContext}`;
  }

  // 添加响应格式指令
  systemPrompt += `\n\n${getResponseFormatInstruction()}`;

  const messages: AnthropicMessage[] = [];

  // 添加用户消息
  if (input.chatMessage) {
    messages.push({
      role: 'user',
      content: `[${input.chatMessage.sender.displayName}]: ${input.chatMessage.content}`,
    });
  } else {
    // 如果没有聊天消息，添加一个默认的触发消息
    messages.push({
      role: 'user',
      content: '请根据当前状态做出响应。',
    });
  }

  return { systemPrompt, messages };
}

/**
 * 构建 Ollama/KoboldCPP 格式的提示词
 */
export function buildOllamaPrompt(input: CognitionInput): string {
  let prompt = `### System:\n${input.systemPrompt}\n\n`;

  // 添加记忆上下文
  if (input.memories.length > 0) {
    const memoryContext = input.memories
      .map((m) => `[${m.timestamp.toISOString()}] ${m.content}`)
      .join('\n');
    prompt += `### 相关记忆:\n${memoryContext}\n\n`;
  }

  // 添加游戏状态
  if (input.gameState) {
    const gameContext = formatGameState(input.gameState);
    prompt += `### 游戏状态:\n${gameContext}\n\n`;
  }

  // 添加响应格式指令
  prompt += `### 响应格式:\n${getResponseFormatInstruction()}\n\n`;

  // 添加用户消息
  if (input.chatMessage) {
    prompt += `### User:\n[${input.chatMessage.sender.displayName}]: ${input.chatMessage.content}\n\n`;
  }

  prompt += '### Assistant:\n';

  return prompt;
}

/**
 * 格式化游戏状态
 */
function formatGameState(gameState: CognitionInput['gameState']): string {
  if (!gameState) return '';

  const parts: string[] = [];
  const analysis = gameState.analysis;

  if (analysis.playerPosition) {
    parts.push(`玩家位置: (${analysis.playerPosition.x}, ${analysis.playerPosition.y})`);
  }
  if (analysis.health !== undefined) {
    parts.push(`生命值: ${analysis.health}`);
  }
  if (analysis.inventory && analysis.inventory.length > 0) {
    parts.push(`物品栏: ${analysis.inventory.join(', ')}`);
  }
  if (analysis.environment) {
    parts.push(`环境: ${analysis.environment}`);
  }
  if (analysis.detectedObjects && analysis.detectedObjects.length > 0) {
    const objects = analysis.detectedObjects
      .map((o) => `${o.name}(${Math.round(o.confidence * 100)}%)`)
      .join(', ');
    parts.push(`检测到的对象: ${objects}`);
  }

  return parts.join('\n');
}

/**
 * 获取响应格式指令
 */
function getResponseFormatInstruction(): string {
  return `请以 JSON 格式响应，包含以下字段:
{
  "responseText": "你的回复文本",
  "emotion": "neutral|happy|sad|surprised|angry|thinking",
  "gameActions": [{"name": "动作名称", "inputs": [], "description": "动作描述"}],
  "shouldSpeak": true
}

注意:
- responseText: 必填，你要说的话
- emotion: 必填，当前情绪状态
- gameActions: 可选，如果需要执行游戏动作
- shouldSpeak: 必填，是否需要语音输出`;
}

/**
 * 解析 AI 响应
 */
export function parseAIResponse(content: string): CognitionOutput {
  // 默认响应
  const defaultResponse: CognitionOutput = {
    responseText: content,
    emotion: 'neutral' as EmotionType,
    shouldSpeak: true,
  };

  try {
    // 尝试提取 JSON
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return defaultResponse;
    }

    const parsed = JSON.parse(jsonMatch[0]);

    // 验证并提取字段
    const response: CognitionOutput = {
      responseText: typeof parsed.responseText === 'string' 
        ? parsed.responseText 
        : content,
      emotion: isValidEmotion(parsed.emotion) 
        ? parsed.emotion 
        : 'neutral',
      shouldSpeak: typeof parsed.shouldSpeak === 'boolean' 
        ? parsed.shouldSpeak 
        : true,
    };

    // 解析游戏动作
    if (Array.isArray(parsed.gameActions)) {
      response.gameActions = parsed.gameActions
        .filter(isValidGameAction)
        .map((action: GameAction) => ({
          name: action.name,
          inputs: action.inputs || [],
          description: action.description || '',
        }));
    }

    return response;
  } catch {
    // JSON 解析失败，返回原始文本作为响应
    return defaultResponse;
  }
}

/**
 * 验证情绪类型
 */
function isValidEmotion(emotion: unknown): emotion is EmotionType {
  const validEmotions: EmotionType[] = [
    'neutral', 'happy', 'sad', 'surprised', 'angry', 'thinking'
  ];
  return typeof emotion === 'string' && validEmotions.includes(emotion as EmotionType);
}

/**
 * 验证游戏动作
 */
function isValidGameAction(action: unknown): action is GameAction {
  if (typeof action !== 'object' || action === null) {
    return false;
  }
  const a = action as Record<string, unknown>;
  return typeof a.name === 'string' && a.name.length > 0;
}
