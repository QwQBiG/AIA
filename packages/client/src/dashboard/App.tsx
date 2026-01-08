import React from 'react';
import { DashboardProvider } from './context/DashboardContext';
import { Layout } from './components/Layout';
import { useWebSocket } from './hooks/useWebSocket';

/**
 * Dashboard 应用根组件
 * 提供 WebSocket 连接和全局状态管理
 */
export const App: React.FC = () => {
  return (
    <DashboardProvider>
      <DashboardApp />
    </DashboardProvider>
  );
};

const DashboardApp: React.FC = () => {
  // 初始化 WebSocket 连接
  useWebSocket();

  return <Layout />;
};
