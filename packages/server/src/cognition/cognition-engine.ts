/**
 * Cognition Engine
 * 认知引擎 - 基于 LLM 的思考和决策核心
 */

import {
  LLMProvider,
  CognitionInput,
  CognitionOutput,
  PersonalityConfig,
  Memory,
} from '@digital-human/shared';
import { ICognitionEngine, LLMFactoryConfig } from './types';
import { ILLMService } from './llm/types';
import { createLLMService, getDefaultLLMProvider, getAvailableLLMProviders } from './llm/llm-factory';

/**
 * 认知引擎配置
 */
export interface CognitionEngineConfig {
  /** LLM 工厂配置 */
  llmConfig: LLMFactoryConfig;
  /** 初始 LLM 提供者（可选） */
  initialProvider?: LLMProvider;
  /** 初始人格配置（可选） */
  initialPersonality?: PersonalityConfig;
  /** 响应超时时间（毫秒，默认 30000） */
  responseTimeout?: number;
  /** 最大上下文记忆数量（默认 50） */
  maxContextMemories?: number;
}

/**
 * 默认人格配置
 */
const DEFAULT_PERSONALITY: PersonalityConfig = {
  name: 'AI VTuber',
  description: '一个友好、有趣的 AI 虚拟主播',
  speakingStyle: '活泼、亲切、偶尔调皮',
  traits: ['友好', '幽默', '好奇', '热情'],
};

/**
 * 认知引擎类
 */
export class CognitionEngine implements ICognitionEngine {
  private llmService: ILLMService;
  private config: Required<CognitionEngineConfig>;
  private personality: PersonalityConfig;
  private messageQueue: CognitionInput[] = [];
  private isProcessing: boolean = false;
  private isDegraded: boolean = false;

  constructor(config: CognitionEngineConfig) {
    this.config = {
      llmConfig: config.llmConfig,
      initialProvider: config.initialProvider || getDefaultLLMProvider(),
      initialPersonality: config.initialPersonality || DEFAULT_PERSONALITY,
      responseTimeout: config.responseTimeout || 30000,
      maxContextMemories: config.maxContextMemories || 50,
    };

    this.personality = this.config.initialPersonality;
    this.llmService = createLLMService(this.config.initialProvider, this.config.llmConfig);
  }

  /**
   * 生成响应
   * 集成 Memory_System 获取上下文，确保响应在 3 秒内生成
   */
  async generateResponse(input: CognitionInput): Promise<CognitionOutput> {
    // 限制记忆数量
    const limitedInput: CognitionInput = {
      ...input,
      memories: this.limitMemories(input.memories),
      systemPrompt: input.systemPrompt || this.buildSystemPrompt(),
    };

    // 使用超时控制
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`Response generation timed out after ${this.config.responseTimeout}ms`));
      }, this.config.responseTimeout);
    });

    try {
      const response = await Promise.race([
        this.llmService.generateResponse(limitedInput),
        timeoutPromise,
      ]);

      // 如果之前是降级状态，现在恢复了
      if (this.isDegraded) {
        this.isDegraded = false;
      }

      return response;
    } catch (error) {
      // 尝试降级到本地 LLM
      return this.handleGenerationError(error, limitedInput);
    }
  }

  /**
   * 设置 LLM 提供者
   */
  setProvider(provider: LLMProvider): void {
    this.llmService = createLLMService(provider, this.config.llmConfig);
    this.isDegraded = false;
  }

  /**
   * 获取可用的提供者列表
   */
  getAvailableProviders(): LLMProvider[] {
    return getAvailableLLMProviders(this.config.llmConfig);
  }

  /**
   * 设置人格配置
   */
  setPersonality(personality: PersonalityConfig): void {
    this.personality = personality;
  }

  /**
   * 获取当前人格配置
   */
  getPersonality(): PersonalityConfig | null {
    return this.personality;
  }

  /**
   * 获取当前 LLM 提供者
   */
  getCurrentProvider(): LLMProvider {
    return this.llmService.getProvider();
  }

  /**
   * 检查当前服务是否可用
   */
  async isServiceAvailable(): Promise<boolean> {
    return this.llmService.isAvailable();
  }

  /**
   * 检查是否处于降级状态
   */
  isInDegradedMode(): boolean {
    return this.isDegraded;
  }

  /**
   * 将消息加入队列（用于 API 不可用时）
   */
  queueMessage(input: CognitionInput): void {
    this.messageQueue.push(input);
  }

  /**
   * 获取队列中的消息数量
   */
  getQueueLength(): number {
    return this.messageQueue.length;
  }

  /**
   * 处理队列中的消息
   */
  async processQueue(): Promise<CognitionOutput[]> {
    if (this.isProcessing || this.messageQueue.length === 0) {
      return [];
    }

    this.isProcessing = true;
    const results: CognitionOutput[] = [];

    try {
      while (this.messageQueue.length > 0) {
        const input = this.messageQueue.shift()!;
        const response = await this.generateResponse(input);
        results.push(response);
      }
    } finally {
      this.isProcessing = false;
    }

    return results;
  }

  /**
   * 限制记忆数量
   */
  private limitMemories(memories: Memory[]): Memory[] {
    if (memories.length <= this.config.maxContextMemories) {
      return memories;
    }
    // 保留最近的记忆
    return memories.slice(-this.config.maxContextMemories);
  }

  /**
   * 构建系统提示词
   */
  private buildSystemPrompt(): string {
    const { name, description, speakingStyle, backstory, traits } = this.personality;

    let prompt = `你是 ${name}，${description}。\n`;
    prompt += `你的说话风格是：${speakingStyle}。\n`;
    
    if (traits.length > 0) {
      prompt += `你的性格特点：${traits.join('、')}。\n`;
    }
    
    if (backstory) {
      prompt += `背景故事：${backstory}\n`;
    }

    prompt += `\n请保持角色一致性，用自然、有趣的方式与观众互动。`;

    return prompt;
  }

  /**
   * 处理生成错误，尝试降级
   */
  private async handleGenerationError(
    error: unknown,
    input: CognitionInput
  ): Promise<CognitionOutput> {
    const currentProvider = this.llmService.getProvider();
    
    // 如果当前是云端提供者，尝试降级到本地
    if (currentProvider.type === 'cloud' && !this.isDegraded) {
      console.warn(`Cloud LLM failed, attempting fallback to local LLM:`, error);
      
      try {
        // 尝试使用 Ollama
        const localProvider: LLMProvider = {
          type: 'local',
          name: 'ollama',
          model: process.env.OLLAMA_MODEL || 'llama3.2',
          endpoint: this.config.llmConfig.ollamaEndpoint || 'http://localhost:11434',
        };

        const localService = createLLMService(localProvider, this.config.llmConfig);
        
        // 检查本地服务是否可用
        if (await localService.isAvailable()) {
          this.llmService = localService;
          this.isDegraded = true;
          
          // 重试生成
          return this.llmService.generateResponse(input);
        }
      } catch (fallbackError) {
        console.error('Fallback to local LLM also failed:', fallbackError);
      }
    }

    // 如果降级也失败，将消息加入队列并返回默认响应
    this.queueMessage(input);
    
    return {
      responseText: '抱歉，我现在有点忙，稍后再回复你哦~',
      emotion: 'thinking',
      shouldSpeak: false,
    };
  }
}
