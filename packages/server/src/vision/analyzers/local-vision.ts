import { VisionProvider } from '@digital-human/shared';
import { CapturedFrame, FrameAnalysis, DetectedObjectInfo } from '../types.js';
import { IVisionAnalyzer, LocalVisionConfig, GAME_ANALYSIS_PROMPT } from './types.js';

/**
 * 本地视觉分析器
 * 支持 LLaVA、MiniGPT-4 等本地视觉模型
 */
export class LocalVisionAnalyzer implements IVisionAnalyzer {
  private config: LocalVisionConfig;
  private provider: VisionProvider;

  constructor(config: LocalVisionConfig) {
    this.config = {
      timeout: 30000,
      ...config,
    };

    this.provider = {
      type: 'local',
      name: 'local-vision',
      model: config.model,
      endpoint: config.endpoint,
    };
  }

  /**
   * 分析帧
   */
  async analyze(frame: CapturedFrame): Promise<FrameAnalysis> {
    const base64Image = frame.data.toString('base64');

    try {
      // 尝试 Ollama 格式
      const response = await this.tryOllamaFormat(base64Image);
      if (response) {
        return response;
      }

      // 尝试通用 OpenAI 兼容格式
      return await this.tryOpenAICompatibleFormat(base64Image, frame.format);
    } catch (error) {
      console.error('Local vision analysis error:', error);
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
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${this.config.endpoint}/api/tags`, {
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      return response.ok;
    } catch {
      // 尝试 OpenAI 兼容端点
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(`${this.config.endpoint}/v1/models`, {
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        return response.ok;
      } catch {
        return false;
      }
    }
  }

  /**
   * 尝试 Ollama 格式
   */
  private async tryOllamaFormat(base64Image: string): Promise<FrameAnalysis | null> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

      const response = await fetch(`${this.config.endpoint}/api/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: this.config.model,
          prompt: GAME_ANALYSIS_PROMPT,
          images: [base64Image],
          stream: false,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        return null;
      }

      const data = (await response.json()) as { response?: string };
      const content = data.response;

      if (!content) {
        return null;
      }

      return this.parseAnalysisResponse(content);
    } catch {
      return null;
    }
  }

  /**
   * 尝试 OpenAI 兼容格式
   */
  private async tryOpenAICompatibleFormat(
    base64Image: string,
    format: string
  ): Promise<FrameAnalysis> {
    const mimeType = format === 'jpeg' ? 'image/jpeg' : 'image/png';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

    const response = await fetch(`${this.config.endpoint}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
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
                },
              },
            ],
          },
        ],
        max_tokens: 1000,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Local vision API error: ${response.status} - ${errorText}`);
    }

    const data = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const content = data.choices?.[0]?.message?.content;

    if (!content) {
      throw new Error('No content in response');
    }

    return this.parseAnalysisResponse(content);
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
