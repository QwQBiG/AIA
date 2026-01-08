import { VisionProvider } from '@digital-human/shared';
import { CapturedFrame, FrameAnalysis, DetectedObjectInfo } from '../types.js';
import { IVisionAnalyzer, OpenAIVisionConfig, GAME_ANALYSIS_PROMPT } from './types.js';

/**
 * OpenAI Vision 分析器
 * 使用 OpenAI GPT-4 Vision API 进行游戏画面分析
 */
export class OpenAIVisionAnalyzer implements IVisionAnalyzer {
  private config: OpenAIVisionConfig;
  private provider: VisionProvider;

  constructor(config: OpenAIVisionConfig) {
    this.config = {
      maxTokens: 1000,
      detail: 'auto',
      ...config,
    };

    this.provider = {
      type: 'cloud',
      name: 'openai-vision',
      model: config.model,
      endpoint: 'https://api.openai.com/v1/chat/completions',
    };
  }

  /**
   * 分析帧
   */
  async analyze(frame: CapturedFrame): Promise<FrameAnalysis> {
    const base64Image = frame.data.toString('base64');
    const mimeType = frame.format === 'jpeg' ? 'image/jpeg' : 'image/png';

    try {
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify({
          model: this.config.model,
          messages: [
            {
              role: 'user',
              content: [
                {
                  type: 'text',
                  text: GAME_ANALYSIS_PROMPT,
                },
                {
                  type: 'image_url',
                  image_url: {
                    url: `data:${mimeType};base64,${base64Image}`,
                    detail: this.config.detail,
                  },
                },
              ],
            },
          ],
          max_tokens: this.config.maxTokens,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenAI API error: ${response.status} - ${errorText}`);
      }

      const data = (await response.json()) as {
        choices?: Array<{ message?: { content?: string } }>;
      };
      const content = data.choices?.[0]?.message?.content;

      if (!content) {
        throw new Error('No content in OpenAI response');
      }

      return this.parseAnalysisResponse(content);
    } catch (error) {
      console.error('OpenAI Vision analysis error:', error);
      return this.getDefaultAnalysis();
    }
  }

  /**
   * 获取提供者信息
   */
  getProviderInfo(): VisionProvider {
    return this.provider;
  }

  /**
   * 检查是否可用
   */
  async isAvailable(): Promise<boolean> {
    if (!this.config.apiKey) {
      return false;
    }

    try {
      const response = await fetch('https://api.openai.com/v1/models', {
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * 解析分析响应
   */
  private parseAnalysisResponse(content: string): FrameAnalysis {
    try {
      // 尝试提取 JSON
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('No JSON found in response');
      }

      const parsed = JSON.parse(jsonMatch[0]);

      return {
        playerPosition: parsed.playerPosition || undefined,
        health: typeof parsed.health === 'number' ? parsed.health : undefined,
        inventory: Array.isArray(parsed.inventory) ? parsed.inventory : [],
        environment: parsed.environment || 'Unknown environment',
        detectedObjects: this.parseDetectedObjects(parsed.detectedObjects),
        rawResponse: content,
      };
    } catch (error) {
      console.error('Failed to parse analysis response:', error);
      return this.getDefaultAnalysis(content);
    }
  }

  /**
   * 解析检测到的对象
   */
  private parseDetectedObjects(objects: unknown): DetectedObjectInfo[] {
    if (!Array.isArray(objects)) {
      return [];
    }

    return objects
      .filter((obj): obj is Record<string, unknown> => typeof obj === 'object' && obj !== null)
      .map((obj) => ({
        type: String(obj.type || 'unknown'),
        name: String(obj.name || 'Unknown'),
        boundingBox: this.parseBoundingBox(obj.boundingBox),
        confidence: typeof obj.confidence === 'number' ? obj.confidence : 0.5,
      }));
  }

  /**
   * 解析边界框
   */
  private parseBoundingBox(
    box: unknown
  ): { x: number; y: number; width: number; height: number } | undefined {
    if (!box || typeof box !== 'object') {
      return undefined;
    }

    const b = box as Record<string, unknown>;
    if (
      typeof b.x === 'number' &&
      typeof b.y === 'number' &&
      typeof b.width === 'number' &&
      typeof b.height === 'number'
    ) {
      return {
        x: b.x,
        y: b.y,
        width: b.width,
        height: b.height,
      };
    }

    return undefined;
  }

  /**
   * 获取默认分析结果
   */
  private getDefaultAnalysis(rawResponse?: string): FrameAnalysis {
    return {
      environment: 'Unable to analyze frame',
      detectedObjects: [],
      rawResponse,
    };
  }
}
