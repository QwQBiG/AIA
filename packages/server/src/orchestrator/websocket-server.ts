import { Server as HttpServer, createServer } from 'http';
import { Server, Socket } from 'socket.io';
import { OrchestratorConfig, DEFAULT_CONFIG, SocketEvents } from './types';

/**
 * WebSocket 服务器类
 * 负责管理 Socket.IO 连接和基础通信
 */
export class WebSocketServer {
  private httpServer: HttpServer;
  private io: Server;
  private config: OrchestratorConfig;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isRunning = false;

  constructor(config: Partial<OrchestratorConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.httpServer = createServer();
    this.io = new Server(this.httpServer, {
      cors: this.config.cors
        ? {
            origin: '*',
            methods: ['GET', 'POST'],
          }
        : undefined,
      pingInterval: this.config.heartbeatInterval,
      pingTimeout: this.config.heartbeatTimeout,
    });
  }

  /**
   * 启动 WebSocket 服务器
   */
  async start(): Promise<void> {
    if (this.isRunning) {
      return;
    }

    return new Promise((resolve, reject) => {
      try {
        this.httpServer.listen(this.config.port, () => {
          this.isRunning = true;
          this.setupHeartbeat();
          resolve();
        });
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 停止 WebSocket 服务器
   */
  async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    return new Promise((resolve) => {
      this.io.close(() => {
        this.httpServer.close(() => {
          this.isRunning = false;
          resolve();
        });
      });
    });
  }

  /**
   * 获取 Socket.IO 服务器实例
   */
  getIO(): Server {
    return this.io;
  }

  /**
   * 获取服务器运行状态
   */
  getIsRunning(): boolean {
    return this.isRunning;
  }

  /**
   * 获取配置
   */
  getConfig(): OrchestratorConfig {
    return { ...this.config };
  }

  /**
   * 注册连接事件处理器
   */
  onConnection(handler: (socket: Socket) => void): void {
    this.io.on(SocketEvents.CONNECTION, handler);
  }

  /**
   * 向指定 socket 发送消息
   */
  sendTo(socketId: string, event: string, data: unknown): void {
    this.io.to(socketId).emit(event, data);
  }

  /**
   * 广播消息给所有连接
   */
  broadcast(event: string, data: unknown): void {
    this.io.emit(event, data);
  }

  /**
   * 获取所有已连接的 socket ID
   */
  getConnectedSockets(): string[] {
    return Array.from(this.io.sockets.sockets.keys());
  }

  /**
   * 设置心跳检测
   */
  private setupHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.io.emit(SocketEvents.MODULE_HEARTBEAT, { timestamp: new Date().toISOString() });
    }, this.config.heartbeatInterval);
  }
}
