import { useEffect, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useDashboard } from '../context/DashboardContext';
import {
  ModuleType,
  MessageType,
  SystemMessage,
  ModuleStatus,
  SystemError,
} from '@digital-human/shared';
import { v4 as uuidv4 } from 'uuid';

const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:8080';

/**
 * WebSocket 连接 Hook
 * 管理与 Orchestrator 的 WebSocket 连接
 */
export function useWebSocket() {
  const socketRef = useRef<Socket | null>(null);
  const { dispatch, state } = useDashboard();

  // 发送消息到 Orchestrator
  const sendMessage = useCallback((message: Omit<SystemMessage, 'id' | 'timestamp' | 'source'>) => {
    if (socketRef.current?.connected) {
      const fullMessage: SystemMessage = {
        ...message,
        id: uuidv4(),
        timestamp: new Date(),
        source: ModuleType.DASHBOARD,
      };
      socketRef.current.emit('message', fullMessage);
      return fullMessage;
    }
    return null;
  }, []);

  useEffect(() => {
    // 创建 Socket.IO 连接
    const socket = io(ORCHESTRATOR_URL, {
      transports: ['websocket'],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    socketRef.current = socket;

    // 连接成功
    socket.on('connect', () => {
      dispatch({ type: 'SET_CONNECTED', payload: true });
      
      // 注册 Dashboard 模块
      const registerMessage: SystemMessage = {
        id: uuidv4(),
        type: MessageType.MODULE_REGISTER,
        timestamp: new Date(),
        source: ModuleType.DASHBOARD,
        payload: {
          moduleType: ModuleType.DASHBOARD,
          capabilities: ['monitor', 'command', 'override'],
        },
      };
      socket.emit('message', registerMessage);
    });

    // 连接断开
    socket.on('disconnect', () => {
      dispatch({ type: 'SET_CONNECTED', payload: false });
    });

    // 连接错误
    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      dispatch({ type: 'SET_CONNECTED', payload: false });
    });

    // 接收消息
    socket.on('message', (message: SystemMessage) => {
      handleMessage(message, dispatch);
    });

    // 清理
    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [dispatch]);

  // 将 sendMessage 存储到 context 中
  useEffect(() => {
    dispatch({ type: 'SET_SEND_MESSAGE', payload: sendMessage });
  }, [sendMessage, dispatch]);

  return { sendMessage, isConnected: state.isConnected };
}

/**
 * 处理接收到的消息
 */
function handleMessage(
  message: SystemMessage,
  dispatch: React.Dispatch<DashboardAction>
) {
  switch (message.type) {
    case MessageType.MODULE_STATUS:
      dispatch({
        type: 'UPDATE_MODULE_STATUS',
        payload: message.payload as ModuleStatus,
      });
      break;

    case MessageType.CHAT_MESSAGE:
      dispatch({
        type: 'ADD_CHAT_MESSAGE',
        payload: message.payload,
      });
      break;

    case MessageType.COGNITION_RESPONSE:
      dispatch({
        type: 'ADD_AI_RESPONSE',
        payload: message.payload,
      });
      break;

    case MessageType.GAME_STATE:
      dispatch({
        type: 'UPDATE_GAME_STATE',
        payload: message.payload,
      });
      break;

    case MessageType.SYSTEM_ALERT:
      dispatch({
        type: 'ADD_ALERT',
        payload: message.payload as SystemError,
      });
      break;

    default:
      // 其他消息类型可以在这里处理
      break;
  }
}

// 导出类型供 context 使用
export type SendMessageFn = (
  message: Omit<SystemMessage, 'id' | 'timestamp' | 'source'>
) => SystemMessage | null;

type DashboardAction =
  | { type: 'SET_CONNECTED'; payload: boolean }
  | { type: 'SET_SEND_MESSAGE'; payload: SendMessageFn }
  | { type: 'UPDATE_MODULE_STATUS'; payload: ModuleStatus }
  | { type: 'ADD_CHAT_MESSAGE'; payload: unknown }
  | { type: 'ADD_AI_RESPONSE'; payload: unknown }
  | { type: 'UPDATE_GAME_STATE'; payload: unknown }
  | { type: 'ADD_ALERT'; payload: SystemError };
