import React from 'react';
import { useDashboard, getOverallHealth } from '../context/DashboardContext';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MainContent } from './MainContent';
import { ToastContainer } from './Toast';
import styles from '../styles/Layout.module.css';

/**
 * Dashboard 布局组件
 * 包含头部、侧边栏、主内容区域和 Toast 通知
 */
export const Layout: React.FC = () => {
  const { state, dispatch } = useDashboard();
  const overallHealth = getOverallHealth(state.moduleStatuses);

  const handleDismissAlert = (code: string) => {
    dispatch({ type: 'DISMISS_ALERT', payload: code });
  };

  return (
    <div className={styles.layout}>
      <Header
        isConnected={state.isConnected}
        overallHealth={overallHealth}
        alertCount={state.alerts.length}
      />
      <div className={styles.container}>
        <Sidebar moduleStatuses={state.moduleStatuses} />
        <MainContent />
      </div>
      <ToastContainer errors={state.alerts} onDismiss={handleDismissAlert} />
    </div>
  );
};
