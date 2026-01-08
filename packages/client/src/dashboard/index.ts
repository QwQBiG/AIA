// Dashboard module exports
export { App } from './App';
export { DashboardProvider, useDashboard } from './context/DashboardContext';
export type { DashboardState, DashboardAction, AIResponse } from './context/DashboardContext';
export { useWebSocket } from './hooks/useWebSocket';
export type { SendMessageFn } from './hooks/useWebSocket';
