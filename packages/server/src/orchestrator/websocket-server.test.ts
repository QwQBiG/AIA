import { WebSocketServer } from './websocket-server';
import { io as ioClient, Socket as ClientSocket } from 'socket.io-client';
import { SocketEvents } from './types';

describe('WebSocketServer', () => {
  let server: WebSocketServer;
  let clientSocket: ClientSocket;
  const TEST_PORT = 3001;

  beforeEach(async () => {
    server = new WebSocketServer({ port: TEST_PORT, heartbeatInterval: 1000 });
    await server.start();
  });

  afterEach(async () => {
    if (clientSocket?.connected) {
      clientSocket.disconnect();
    }
    await server.stop();
  });

  const connectClient = (): Promise<ClientSocket> => {
    return new Promise((resolve) => {
      const client = ioClient(`http://localhost:${TEST_PORT}`, {
        transports: ['websocket'],
      });
      client.on('connect', () => resolve(client));
    });
  };

  describe('start/stop', () => {
    it('should start the server', () => {
      expect(server.getIsRunning()).toBe(true);
    });

    it('should stop the server', async () => {
      await server.stop();
      expect(server.getIsRunning()).toBe(false);
    });

    it('should not start twice', async () => {
      await server.start();
      expect(server.getIsRunning()).toBe(true);
    });

    it('should not stop twice', async () => {
      await server.stop();
      await server.stop();
      expect(server.getIsRunning()).toBe(false);
    });
  });

  describe('connection', () => {
    it('should accept client connections', async () => {
      clientSocket = await connectClient();
      expect(clientSocket.connected).toBe(true);
    });

    it('should track connected sockets', async () => {
      clientSocket = await connectClient();
      const sockets = server.getConnectedSockets();
      expect(sockets.length).toBe(1);
      expect(sockets[0]).toBe(clientSocket.id);
    });

    it('should handle client disconnect', async () => {
      clientSocket = await connectClient();
      expect(server.getConnectedSockets().length).toBe(1);

      clientSocket.disconnect();
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(server.getConnectedSockets().length).toBe(0);
    });
  });

  describe('messaging', () => {
    it('should send message to specific socket', async () => {
      clientSocket = await connectClient();

      const receivedPromise = new Promise<unknown>((resolve) => {
        clientSocket.on('test-event', resolve);
      });

      server.sendTo(clientSocket.id!, 'test-event', { data: 'test' });

      const received = await receivedPromise;
      expect(received).toEqual({ data: 'test' });
    });

    it('should broadcast message to all sockets', async () => {
      clientSocket = await connectClient();

      const receivedPromise = new Promise<unknown>((resolve) => {
        clientSocket.on('broadcast-event', resolve);
      });

      server.broadcast('broadcast-event', { message: 'hello' });

      const received = await receivedPromise;
      expect(received).toEqual({ message: 'hello' });
    });
  });

  describe('heartbeat', () => {
    it('should emit heartbeat events', async () => {
      clientSocket = await connectClient();

      const heartbeatPromise = new Promise<unknown>((resolve) => {
        clientSocket.on(SocketEvents.MODULE_HEARTBEAT, resolve);
      });

      const heartbeat = (await heartbeatPromise) as { timestamp: string };
      expect(heartbeat).toHaveProperty('timestamp');
      expect(new Date(heartbeat.timestamp)).toBeInstanceOf(Date);
    });
  });

  describe('configuration', () => {
    it('should use default config when not provided', () => {
      const defaultServer = new WebSocketServer();
      const config = defaultServer.getConfig();
      expect(config.port).toBe(3000);
      expect(config.heartbeatInterval).toBe(5000);
      expect(config.heartbeatTimeout).toBe(15000);
      expect(config.cors).toBe(true);
    });

    it('should merge custom config with defaults', () => {
      const config = server.getConfig();
      expect(config.port).toBe(TEST_PORT);
      expect(config.heartbeatInterval).toBe(1000);
    });
  });

  describe('onConnection', () => {
    it('should call handler when client connects', async () => {
      const connectionHandler = jest.fn();
      server.onConnection(connectionHandler);

      clientSocket = await connectClient();
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(connectionHandler).toHaveBeenCalled();
    });
  });
});
