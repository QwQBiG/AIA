import { VisionProvider } from '@digital-human/shared';
import { IVisionAnalyzer, OpenAIVisionConfig, LocalVisionConfig } from './types.js';
import { OpenAIVisionAnalyzer } from './openai-vision.js';
import { LocalVisionAnalyzer } from './local-vision.js';

/**
 * 视觉分析器工厂配置
 */
export interface VisionFactoryConfig {
  openai?: OpenAIVisionConfig;
  local?: LocalVisionConfig;
  defaultProvider?: 'cloud' | 'local';
}

/**
 * 视觉分析器工厂
 * 创建和管理视觉分析提供者
 */
export class VisionAnalyzerFactory {
  private config: VisionFactoryConfig;
  private analyzers: Map<string, IVisionAnalyzer> = new Map();

  constructor(config: VisionFactoryConfig) {
    this.config = config;
    this.initializeAnalyzers();
  }

  /**
   * 初始化分析器
   */
  private initializeAnalyzers(): void {
    if (this.config.openai) {
      const openaiAnalyzer = new OpenAIVisionAnalyzer(this.config.openai);
      this.analyzers.set('openai-vision', openaiAnalyzer);
    }

    if (this.config.local) {
      const localAnalyzer = new LocalVisionAnalyzer(this.config.local);
      this.analyzers.set('local-vision', localAnalyzer);
    }
  }

  /**
   * 获取分析器
   */
  getAnalyzer(provider: VisionProvider): IVisionAnalyzer | null {
    return this.analyzers.get(provider.name) || null;
  }

  /**
   * 获取默认分析器
   */
  getDefaultAnalyzer(): IVisionAnalyzer | null {
    const defaultType = this.config.defaultProvider || 'cloud';

    if (defaultType === 'cloud' && this.analyzers.has('openai-vision')) {
      return this.analyzers.get('openai-vision')!;
    }

    if (defaultType === 'local' && this.analyzers.has('local-vision')) {
      return this.analyzers.get('local-vision')!;
    }

    // 返回任何可用的分析器
    const firstAnalyzer = this.analyzers.values().next().value;
    return firstAnalyzer || null;
  }

  /**
   * 获取所有可用的提供者
   */
  getAvailableProviders(): VisionProvider[] {
    return Array.from(this.analyzers.values()).map((analyzer) => analyzer.getProviderInfo());
  }

  /**
   * 检查提供者是否可用
   */
  async checkProviderAvailability(providerName: string): Promise<boolean> {
    const analyzer = this.analyzers.get(providerName);
    if (!analyzer) {
      return false;
    }
    return analyzer.isAvailable();
  }

  /**
   * 获取第一个可用的分析器
   */
  async getFirstAvailableAnalyzer(): Promise<IVisionAnalyzer | null> {
    for (const analyzer of this.analyzers.values()) {
      if (await analyzer.isAvailable()) {
        return analyzer;
      }
    }
    return null;
  }

  /**
   * 创建 OpenAI Vision 分析器
   */
  static createOpenAIAnalyzer(apiKey: string, model: string = 'gpt-4-vision-preview'): IVisionAnalyzer {
    return new OpenAIVisionAnalyzer({
      apiKey,
      model,
    });
  }

  /**
   * 创建本地视觉分析器
   */
  static createLocalAnalyzer(endpoint: string, model: string = 'llava'): IVisionAnalyzer {
    return new LocalVisionAnalyzer({
      endpoint,
      model,
    });
  }
}
