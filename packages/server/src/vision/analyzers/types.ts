import { VisionProvider } from '@digital-human/shared';
import { CapturedFrame, FrameAnalysis } from '../types.js';

/**
 * 视觉分析提供者接口
 */
export interface IVisionAnalyzer {
  /** 分析帧 */
  analyze(frame: CapturedFrame): Promise<FrameAnalysis>;
  /** 获取提供者信息 */
  getProviderInfo(): VisionProvider;
  /** 是否可用 */
  isAvailable(): Promise<boolean>;
}

/**
 * OpenAI Vision 配置
 */
export interface OpenAIVisionConfig {
  apiKey: string;
  model: string;
  maxTokens?: number;
  detail?: 'low' | 'high' | 'auto';
}

/**
 * 本地视觉模型配置
 */
export interface LocalVisionConfig {
  endpoint: string;
  model: string;
  timeout?: number;
}

/**
 * 视觉分析提示词
 */
export const GAME_ANALYSIS_PROMPT = `Analyze this game screenshot and extract the following information in JSON format:
{
  "playerPosition": { "x": number, "y": number } or null,
  "health": number (0-100) or null,
  "inventory": ["item1", "item2", ...] or [],
  "environment": "description of the current game environment",
  "detectedObjects": [
    {
      "type": "enemy|item|npc|obstacle|ui",
      "name": "object name",
      "boundingBox": { "x": number, "y": number, "width": number, "height": number } or null,
      "confidence": number (0-1)
    }
  ]
}

Focus on:
1. Player character position and status
2. Health/HP indicators
3. Inventory or equipped items
4. Enemies, NPCs, or interactive objects
5. Environmental context (indoor/outdoor, terrain, etc.)

Return ONLY valid JSON, no additional text.`;
