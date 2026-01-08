/**
 * AI VTuber Digital Human - Main Entry Point
 * 系统主入口文件 - 集成所有模块到 Orchestrator
 *
 * Requirements: 8.1, 8.3, 8.4
 */

import { Socket } from 'socket.io';
import { v4 as uuidv4 } from 'uuid';
import { ModuleType, MessageType, createMessage, deserialize } from '@digital-human/shared';

// Orchestrator 组件
import { WebSocketServer } from './orchestrator/websocket-server.js';
import { ModuleRegistry } from './orchestrator/module-registry.js';
import { MessageRouter } from './orchestrator/message-router.js';
import { EventLoop, SystemEvent } from './orchestrator/event-loop.js';
import { SocketEvents } from './orchestrator/types.js';

// 模块
import { CognitionEngine, CognitionEngineConfig } from './cognition/cognition-engine.js';
import { MemorySystem, MemorySystemConfig } from './memory/memory-system.js';
import { ChatInterfaceManager } from './chat/chat-interface.js';
import { TTSEngine } from './tts/tts-engine.js';
import { VisionModule, VisionModuleConfig } from './vision/vision-module.js';
import { GameController } from './game-controller/game-controller.js';

/**
 * 系统配置接口
 */
export interface DigitalHumanConfig {
  /** WebSocket 服务器端口 */
  port: number;
  /** 是否启用 CORS */
  cors: boolean;
  /** 认知引擎配置 */
  cognition: CognitionEngineConfig;
  /** 记忆系统配置 */
  memory: MemorySystemConfig;
  /** 视觉模块配置 */
  vision: VisionModuleConfig;
  /** TTS 配置 */
  tts?: {
    elevenLabsApiKey?: string;
    azureApiKey?: string;
    azureRegion?: string;
    vitsEndpoint?: string;
    gptSovitsEndpoint?: string;
  };
  /** 聊天配置 */
  chat?: {
    twitchUsername?: string;
  };
}

/**
 * 从环境变量创建默认配置
 */
export function createConfigFromEnv(): DigitalHumanConfig {
  return {
    port: parseInt(process.env.ORCHESTRATOR_PORT || '3001', 10),
    cors: process.env.CORS_ENABLED !== 'false',
    cognition: {
      llmConfig: {
        openaiApiKey: process.env.OPENAI_API_KEY,
        anthropicApiKey: process.env.ANTHROPIC_API_KEY,
        ollamaEndpoint: process.env.OLLAMA_ENDPOINT || 'http://localhost:11434',
        koboldEndpoint: process.env.KOBOLDCPP_ENDPOINT,
      },
    },
    memory: {
      database: {
        host: process.env.POSTGRES_HOST || 'localhost',
        port: parseInt(process.env.POSTGRES_PORT || '5432', 10),
        database: process.env.POSTGRES_DB || 'digital_human',
        user: process.env.POSTGRES_USER || 'postgres',
        password: process.env.POSTGRES_PASSWORD || '',
      },
      embedding: {
        openaiApiKey: process.env.OPENAI_API_KEY,
        localEndpoint: process.env.EMBEDDING_ENDPOINT,
      },
      useDatabaseFallback: true,
    },
    vision: {
      analyzerConfig: {
        openai: process.env.OPENAI_API_KEY ? {
          apiKey: process.env.OPENAI_API_KEY,
          model: 'gpt-4-vision-preview',
        } : undefined,
        local: process.env.VISION_ENDPOINT ? {
          endpoint: process.env.VISION_ENDPOINT,
          model: 'llava',
        } : undefined,
      },
    },
    tts: {
      elevenLabsApiKey: process.env.ELEVENLABS_API_KEY,
      azureApiKey: process.env.AZURE_TTS_API_KEY,
      azureRegion: process.env.AZURE_TTS_REGION,
      vitsEndpoint: process.env.VITS_ENDPOINT,
      gptSovitsEndpoint: process.env.GPT_SOVITS_ENDPOINT,
    },
    chat: {
      twitchUsername: process.env.TWITCH_USERNAME,
    },
  };
}


/**
 * Digital Human 系统主类
 * 集成所有模块并管理系统生命周期
 */
export class DigitalHumanSystem {
  private config: DigitalHumanConfig;

  // Orchestrator 组件
  private wsServer: WebSocketServer;
  private registry: ModuleRegistry;
  private router: MessageRouter;
  private eventLoop: EventLoop;

  // 模块实例
  private cognitionEngine: CognitionEngine | null = null;
  private memorySystem: MemorySystem | null = null;
  private chatManager: ChatInterfaceManager | null = null;
  private ttsEngine: TTSEngine | null = null;
  private visionModule: VisionModule | null = null;
  private gameController: GameController | null = null;

  private isRunning = false;

  constructor(config: DigitalHumanConfig) {
    this.config = config;

    // 初始化 Orchestrator 组件
    this.wsServer = new WebSocketServer({
      port: config.port,
      cors: config.cors,
    });
    this.registry = new ModuleRegistry();
    this.router = new MessageRouter(this.registry);
    this.eventLoop = new EventLoop(this.router);
  }

  /**
   * 启动系统
   */
  async start(): Promise<void> {
    if (this.isRunning) {
      console.log('[DigitalHuman] System is already running');
      return;
    }

    console.log('[DigitalHuman] Starting system...');

    try {
      // 1. 启动 WebSocket 服务器
      await this.wsServer.start();
      console.log(`[DigitalHuman] WebSocket server started on port ${this.config.port}`);

      // 2. 设置连接处理
      this.setupConnectionHandlers();

      // 3. 初始化模块
      await this.initializeModules();

      // 4. 启动健康检查
      this.registry.startHealthCheck((moduleId, module) => {
        console.warn(`[DigitalHuman] Module ${moduleId} (${module.moduleType}) is unhealthy`);
        this.handleUnhealthyModule(moduleId, module.moduleType);
      });

      // 5. 启动事件循环
      this.eventLoop.startEventLoop();
      console.log('[DigitalHuman] Event loop started');

      this.isRunning = true;
      console.log('[DigitalHuman] System started successfully');
    } catch (error) {
      console.error('[DigitalHuman] Failed to start system:', error);
      await this.stop();
      throw error;
    }
  }

  /**
   * 停止系统
   */
  async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    console.log('[DigitalHuman] Stopping system...');

    // 停止事件循环
    this.eventLoop.stopEventLoop();

    // 停止健康检查
    this.registry.stopHealthCheck();

    // 关闭模块
    await this.shutdownModules();

    // 停止 WebSocket 服务器
    await this.wsServer.stop();

    this.isRunning = false;
    console.log('[DigitalHuman] System stopped');
  }

  /**
   * 获取系统状态
   */
  getStatus(): {
    isRunning: boolean;
    modules: ReturnType<ModuleRegistry['getAllModuleStatus']>;
    eventQueueLength: number;
  } {
    return {
      isRunning: this.isRunning,
      modules: this.registry.getAllModuleStatus(),
      eventQueueLength: this.eventLoop.getQueueLength(),
    };
  }

  /**
   * 设置连接处理器
   */
  private setupConnectionHandlers(): void {
    this.wsServer.onConnection((socket: Socket) => {
      console.log(`[DigitalHuman] New connection: ${socket.id}`);

      // 处理模块注册
      socket.on(SocketEvents.MODULE_REGISTER, (data: { moduleId: string; moduleType: ModuleType }) => {
        try {
          this.registry.registerModule(data.moduleId, data.moduleType, socket);
          console.log(`[DigitalHuman] Module registered: ${data.moduleId} (${data.moduleType})`);

          // 发送注册确认
          socket.emit(SocketEvents.MODULE_STATUS, {
            status: 'registered',
            moduleId: data.moduleId,
          });
        } catch (error) {
          console.error(`[DigitalHuman] Failed to register module:`, error);
          socket.emit(SocketEvents.MODULE_STATUS, {
            status: 'error',
            error: (error as Error).message,
          });
        }
      });

      // 处理心跳
      socket.on(SocketEvents.MODULE_HEARTBEAT, (data: { moduleId: string }) => {
        this.registry.updateHeartbeat(data.moduleId);
      });

      // 处理消息
      socket.on(SocketEvents.MESSAGE, async (data: string) => {
        try {
          const message = deserialize(data);

          // 如果是聊天消息或游戏状态，加入事件队列
          if (message.type === MessageType.CHAT_MESSAGE || message.type === MessageType.GAME_STATE) {
            const event: SystemEvent = {
              id: uuidv4(),
              type: message.type === MessageType.CHAT_MESSAGE ? 'chat' : 'game_state',
              data: message.payload,
              timestamp: new Date(),
            };
            this.eventLoop.queueEvent(event);
          } else {
            // 其他消息直接路由
            await this.router.routeMessage(message);
          }
        } catch (error) {
          console.error('[DigitalHuman] Failed to process message:', error);
        }
      });

      // 处理断开连接
      socket.on('disconnect', () => {
        // 查找并注销该 socket 对应的模块
        const modules = this.registry.getAllModuleStatus();
        for (const module of modules) {
          const registeredModule = this.registry.getModule(module.moduleId);
          if (registeredModule?.socket.id === socket.id) {
            this.registry.unregisterModule(module.moduleId);
            console.log(`[DigitalHuman] Module disconnected: ${module.moduleId}`);
          }
        }
      });
    });
  }


  /**
   * 初始化所有模块
   */
  private async initializeModules(): Promise<void> {
    console.log('[DigitalHuman] Initializing modules...');

    // 初始化记忆系统
    try {
      this.memorySystem = new MemorySystem(this.config.memory);
      await this.memorySystem.initialize();
      console.log('[DigitalHuman] Memory system initialized');
    } catch (error) {
      console.warn('[DigitalHuman] Memory system initialization failed, using fallback:', error);
    }

    // 初始化认知引擎
    try {
      this.cognitionEngine = new CognitionEngine(this.config.cognition);
      console.log('[DigitalHuman] Cognition engine initialized');
    } catch (error) {
      console.error('[DigitalHuman] Cognition engine initialization failed:', error);
    }

    // 初始化 TTS 引擎
    try {
      this.ttsEngine = new TTSEngine(this.config.tts);
      await this.ttsEngine.initialize();
      console.log('[DigitalHuman] TTS engine initialized');
    } catch (error) {
      console.warn('[DigitalHuman] TTS engine initialization failed:', error);
    }

    // 初始化视觉模块
    try {
      this.visionModule = new VisionModule(this.config.vision);
      console.log('[DigitalHuman] Vision module initialized');
    } catch (error) {
      console.warn('[DigitalHuman] Vision module initialization failed:', error);
    }

    // 初始化游戏控制器
    try {
      this.gameController = new GameController();
      console.log('[DigitalHuman] Game controller initialized');
    } catch (error) {
      console.warn('[DigitalHuman] Game controller initialization failed:', error);
    }

    // 初始化聊天管理器
    try {
      this.chatManager = new ChatInterfaceManager(this.config.chat);
      this.setupChatForwarding();
      console.log('[DigitalHuman] Chat manager initialized');
    } catch (error) {
      console.warn('[DigitalHuman] Chat manager initialization failed:', error);
    }
  }


  /**
   * 设置聊天消息转发
   */
  private setupChatForwarding(): void {
    if (!this.chatManager) return;

    this.chatManager.setMessageForwarder(async (message) => {
      // 将聊天消息加入事件队列
      const event: SystemEvent = {
        id: uuidv4(),
        type: 'chat',
        data: message.payload,
        timestamp: new Date(),
      };
      this.eventLoop.queueEvent(event);
    });
  }

  /**
   * 关闭所有模块
   */
  private async shutdownModules(): Promise<void> {
    console.log('[DigitalHuman] Shutting down modules...');

    if (this.chatManager) {
      await this.chatManager.stop();
    }

    if (this.visionModule) {
      this.visionModule.destroy();
    }

    if (this.memorySystem) {
      await this.memorySystem.close();
    }

    console.log('[DigitalHuman] Modules shut down');
  }

  /**
   * 处理不健康的模块
   */
  private handleUnhealthyModule(moduleId: string, moduleType: ModuleType): void {
    // 发送系统告警
    const alertMessage = createMessage(
      MessageType.SYSTEM_ALERT,
      ModuleType.DASHBOARD,
      {
        severity: 'high',
        message: `Module ${moduleId} (${moduleType}) is unhealthy`,
        timestamp: new Date().toISOString(),
      }
    );

    // 广播给所有 Dashboard
    this.router.broadcast(alertMessage, [ModuleType.DASHBOARD]);
  }

  // 模块访问器
  getCognitionEngine(): CognitionEngine | null { return this.cognitionEngine; }
  getMemorySystem(): MemorySystem | null { return this.memorySystem; }
  getChatManager(): ChatInterfaceManager | null { return this.chatManager; }
  getTTSEngine(): TTSEngine | null { return this.ttsEngine; }
  getVisionModule(): VisionModule | null { return this.visionModule; }
  getGameController(): GameController | null { return this.gameController; }
  getRouter(): MessageRouter { return this.router; }
  getRegistry(): ModuleRegistry { return this.registry; }
}


/**
 * 主函数 - 启动系统
 */
async function main(): Promise<void> {
  console.log('='.repeat(50));
  console.log('AI VTuber Digital Human System');
  console.log('='.repeat(50));

  // 从环境变量创建配置
  const config = createConfigFromEnv();

  // 创建系统实例
  const system = new DigitalHumanSystem(config);

  // 处理进程信号
  const shutdown = async () => {
    console.log('\n[Main] Received shutdown signal');
    await system.stop();
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  // 启动系统
  try {
    await system.start();
    console.log('\n[Main] System is ready');
    console.log(`[Main] WebSocket server: ws://localhost:${config.port}`);
    console.log('[Main] Press Ctrl+C to stop\n');
  } catch (error) {
    console.error('[Main] Failed to start system:', error);
    process.exit(1);
  }
}

// 如果直接运行此文件，启动系统
if (require.main === module) {
  main().catch(console.error);
}

export { main };
