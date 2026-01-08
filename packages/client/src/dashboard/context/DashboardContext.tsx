import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import {
  ModuleStatus,
  SystemError,
  ChatMessage,
  GameState,
  ModuleType,
  HealthStatus,
} from '@digital-human/shared';
import type { SendMessageFn } from '../hooks/useWebSocket';

/**
 * AI 响应接口
 */
export interface AIResponse {
  id: string;
  responseText: string;
  emotion: string;
  timestamp: Date;
}

/**
 * Dashboard 状态接口
 */
export interface DashboardState {
  /** WebSocket 连接状态 */
  isConnected: boolean;
  /** 各模块状态 */
  moduleStatuses: Map<ModuleType, ModuleStatus>;
  /** 聊天消息列表 */
  chatMessages: ChatMessage[];
  /** AI 响应列表 */
  aiResponses: AIResponse[];
  /** 当前游戏状态 */
  gameState: GameState | null;
  /** 系统告警列表 */
  alerts: SystemError[];
  /** 命令历史 */
  commandHistory: string[];
  /** 发送消息函数 */
  sendMessage: SendMessageFn | null;
}

/**
 * Dashboard Action 类型
 */
export type DashboardAction =
  | { type: 'SET_CONNECTED'; payload: boolean }
  | { type: 'SET_SEND_MESSAGE'; payload: SendMessageFn }
  | { type: 'UPDATE_MODULE_STATUS'; payload: ModuleStatus }
  | { type: 'ADD_CHAT_MESSAGE'; payload: ChatMessage }
  | { type: 'ADD_AI_RESPONSE'; payload: AIResponse }
  | { type: 'UPDATE_GAME_STATE'; payload: GameState }
  | { type: 'ADD_ALERT'; payload: SystemError }
  | { type: 'DISMISS_ALERT'; payload: string }
  | { type: 'ADD_COMMAND'; payload: string }
  | { type: 'CLEAR_CHAT_MESSAGES' }
  | { type: 'CLEAR_ALERTS' };

/**
 * 初始状态
 */
const initialState: DashboardState = {
  isConnected: false,
  moduleStatuses: new Map(),
  chatMessages: [],
  aiResponses: [],
  gameState: null,
  alerts: [],
  commandHistory: [],
  sendMessage: null,
};

/**
 * Reducer 函数
 */
function dashboardReducer(
  state: DashboardState,
  action: DashboardAction
): DashboardState {
  switch (action.type) {
    case 'SET_CONNECTED':
      return { ...state, isConnected: action.payload };

    case 'SET_SEND_MESSAGE':
      return { ...state, sendMessage: action.payload };

    case 'UPDATE_MODULE_STATUS': {
      const newStatuses = new Map(state.moduleStatuses);
      newStatuses.set(action.payload.moduleType, action.payload);
      return { ...state, moduleStatuses: newStatuses };
    }

    case 'ADD_CHAT_MESSAGE':
      return {
        ...state,
        chatMessages: [...state.chatMessages.slice(-99), action.payload],
      };

    case 'ADD_AI_RESPONSE':
      return {
        ...state,
        aiResponses: [...state.aiResponses.slice(-49), action.payload],
      };

    case 'UPDATE_GAME_STATE':
      return { ...state, gameState: action.payload };

    case 'ADD_ALERT':
      return {
        ...state,
        alerts: [...state.alerts.slice(-49), action.payload],
      };

    case 'DISMISS_ALERT':
      return {
        ...state,
        alerts: state.alerts.filter((a) => a.code !== action.payload),
      };

    case 'ADD_COMMAND':
      return {
        ...state,
        commandHistory: [...state.commandHistory.slice(-99), action.payload],
      };

    case 'CLEAR_CHAT_MESSAGES':
      return { ...state, chatMessages: [] };

    case 'CLEAR_ALERTS':
      return { ...state, alerts: [] };

    default:
      return state;
  }
}

/**
 * Context 类型
 */
interface DashboardContextType {
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
}

const DashboardContext = createContext<DashboardContextType | undefined>(
  undefined
);

/**
 * Dashboard Provider 组件
 */
export const DashboardProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [state, dispatch] = useReducer(dashboardReducer, initialState);

  return (
    <DashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </DashboardContext.Provider>
  );
};

/**
 * 使用 Dashboard Context 的 Hook
 */
export function useDashboard(): DashboardContextType {
  const context = useContext(DashboardContext);
  if (context === undefined) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}

/**
 * 获取模块健康状态的辅助函数
 */
export function getOverallHealth(
  statuses: Map<ModuleType, ModuleStatus>
): HealthStatus {
  const statusArray = Array.from(statuses.values());
  if (statusArray.length === 0) return 'unhealthy';
  if (statusArray.some((s) => s.health === 'unhealthy')) return 'unhealthy';
  if (statusArray.some((s) => s.health === 'degraded')) return 'degraded';
  return 'healthy';
}
