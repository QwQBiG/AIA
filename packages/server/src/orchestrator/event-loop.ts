import { ModuleType, MessageType, SystemMessage, createMessage } from '@digital-human/shared';
import { MessageRouter } from './message-router';

/**
 * 事件循环阶段
 */
export enum EventPhase {
  LISTEN = 'listen',
  THINK = 'think',
  ACT = 'act',
  SPEAK = 'speak',
}

/**
 * 系统事件接口
 */
export interface SystemEvent {
  id: string;
  type: 'chat' | 'game_state' | 'command' | 'system';
  data: unknown;
  timestamp: Date;
}

/**
 * 事件处理结果
 */
export interface EventProcessResult {
  eventId: string;
  phases: EventPhase[];
  success: boolean;
  error?: string;
  duration: number;
}

/**
 * 事件循环配置
 */
export interface EventLoopConfig {
  /** 处理间隔（毫秒） */
  processInterval: number;
  /** 最大队列大小 */
  maxQueueSize: number;
}

const DEFAULT_CONFIG: EventLoopConfig = {
  processInterval: 100,
  maxQueueSize: 1000,
};

/**
 * 事件循环
 * 实现 Listen → Think → Act → Speak 的核心处理流程
 */
export class EventLoop {
  private router: MessageRouter;
  private config: EventLoopConfig;
  private eventQueue: SystemEvent[] = [];
  private isRunning = false;
  private processTimer: NodeJS.Timeout | null = null;
  private currentPhase: EventPhase = EventPhase.LISTEN;
  private phaseHistory: EventPhase[] = [];

  constructor(router: MessageRouter, config: Partial<EventLoopConfig> = {}) {
    this.router = router;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * 启动事件循环
   */
  startEventLoop(): void {
    if (this.isRunning) {
      return;
    }

    this.isRunning = true;
    this.processTimer = setInterval(() => {
      this.processNextEvent().catch(console.error);
    }, this.config.processInterval);
  }

  /**
   * 停止事件循环
   */
  stopEventLoop(): void {
    if (!this.isRunning) {
      return;
    }

    this.isRunning = false;
    if (this.processTimer) {
      clearInterval(this.processTimer);
      this.processTimer = null;
    }
  }

  /**
   * 获取运行状态
   */
  getIsRunning(): boolean {
    return this.isRunning;
  }

  /**
   * 获取当前阶段
   */
  getCurrentPhase(): EventPhase {
    return this.currentPhase;
  }

  /**
   * 获取阶段历史
   */
  getPhaseHistory(): EventPhase[] {
    return [...this.phaseHistory];
  }

  /**
   * 添加事件到队列
   */
  queueEvent(event: SystemEvent): boolean {
    if (this.eventQueue.length >= this.config.maxQueueSize) {
      return false;
    }

    this.eventQueue.push(event);
    return true;
  }

  /**
   * 获取队列长度
   */
  getQueueLength(): number {
    return this.eventQueue.length;
  }

  /**
   * 处理单个事件
   * 按照 Listen → Think → Act → Speak 顺序执行
   */
  async processEvent(event: SystemEvent): Promise<EventProcessResult> {
    const startTime = performance.now();
    const phases: EventPhase[] = [];

    try {
      // Phase 1: Listen - 接收和解析事件
      this.currentPhase = EventPhase.LISTEN;
      phases.push(EventPhase.LISTEN);
      this.phaseHistory.push(EventPhase.LISTEN);
      await this.executeListenPhase(event);

      // Phase 2: Think - 发送到认知引擎处理
      this.currentPhase = EventPhase.THINK;
      phases.push(EventPhase.THINK);
      this.phaseHistory.push(EventPhase.THINK);
      const thinkResult = await this.executeThinkPhase(event);

      // Phase 3: Act - 执行游戏动作（如果有）
      this.currentPhase = EventPhase.ACT;
      phases.push(EventPhase.ACT);
      this.phaseHistory.push(EventPhase.ACT);
      await this.executeActPhase(thinkResult);

      // Phase 4: Speak - 语音合成和输出
      this.currentPhase = EventPhase.SPEAK;
      phases.push(EventPhase.SPEAK);
      this.phaseHistory.push(EventPhase.SPEAK);
      await this.executeSpeakPhase(thinkResult);

      return {
        eventId: event.id,
        phases,
        success: true,
        duration: performance.now() - startTime,
      };
    } catch (error) {
      return {
        eventId: event.id,
        phases,
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        duration: performance.now() - startTime,
      };
    }
  }

  /**
   * 处理队列中的下一个事件
   */
  private async processNextEvent(): Promise<void> {
    if (this.eventQueue.length === 0) {
      return;
    }

    const event = this.eventQueue.shift();
    if (event) {
      await this.processEvent(event);
    }
  }

  /**
   * Listen 阶段 - 接收和解析事件
   */
  private async executeListenPhase(event: SystemEvent): Promise<void> {
    // 将事件存储到记忆系统
    const memoryMessage = createMessage(
      MessageType.MEMORY_QUERY,
      ModuleType.DASHBOARD,
      {
        action: 'store',
        content: event.data,
        type: event.type,
        timestamp: event.timestamp,
      },
      { target: ModuleType.MEMORY }
    );

    await this.router.routeMessage(memoryMessage);
  }

  /**
   * Think 阶段 - 发送到认知引擎
   */
  private async executeThinkPhase(event: SystemEvent): Promise<unknown> {
    const cognitionMessage = createMessage(
      MessageType.COGNITION_REQUEST,
      ModuleType.DASHBOARD,
      {
        event: event.data,
        eventType: event.type,
      },
      { target: ModuleType.COGNITION }
    );

    await this.router.routeMessage(cognitionMessage);

    // 返回模拟的认知结果（实际实现中会等待响应）
    return {
      responseText: '',
      emotion: 'neutral',
      gameActions: [],
      shouldSpeak: false,
    };
  }

  /**
   * Act 阶段 - 执行游戏动作
   */
  private async executeActPhase(thinkResult: unknown): Promise<void> {
    const result = thinkResult as { gameActions?: unknown[] };

    if (result.gameActions && result.gameActions.length > 0) {
      const actionMessage = createMessage(
        MessageType.GAME_ACTION,
        ModuleType.DASHBOARD,
        { actions: result.gameActions },
        { target: ModuleType.GAME_CONTROLLER }
      );

      await this.router.routeMessage(actionMessage);
    }
  }

  /**
   * Speak 阶段 - 语音合成
   */
  private async executeSpeakPhase(thinkResult: unknown): Promise<void> {
    const result = thinkResult as { responseText?: string; shouldSpeak?: boolean; emotion?: string };

    if (result.shouldSpeak && result.responseText) {
      // 发送 TTS 请求
      const ttsMessage = createMessage(
        MessageType.TTS_REQUEST,
        ModuleType.DASHBOARD,
        { text: result.responseText },
        { target: ModuleType.TTS }
      );

      await this.router.routeMessage(ttsMessage);

      // 发送表情更新
      const expressionMessage = createMessage(
        MessageType.AVATAR_EXPRESSION,
        ModuleType.DASHBOARD,
        { emotion: result.emotion || 'neutral' },
        { target: ModuleType.AVATAR }
      );

      await this.router.routeMessage(expressionMessage);
    }
  }

  /**
   * 清除阶段历史
   */
  clearPhaseHistory(): void {
    this.phaseHistory = [];
  }
}
