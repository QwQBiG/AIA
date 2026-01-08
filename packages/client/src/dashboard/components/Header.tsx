import React from 'react';
import { HealthStatus } from '@digital-human/shared';
import styles from '../styles/Header.module.css';

interface HeaderProps {
  isConnected: boolean;
  overallHealth: HealthStatus;
  alertCount: number;
}

/**
 * Dashboard 头部组件
 * 显示连接状态、系统健康状态和告警数量
 */
export const Header: React.FC<HeaderProps> = ({
  isConnected,
  overallHealth,
  alertCount,
}) => {
  const getHealthColor = (health: HealthStatus): string => {
    switch (health) {
      case 'healthy':
        return styles.healthy;
      case 'degraded':
        return styles.degraded;
      case 'unhealthy':
        return styles.unhealthy;
      default:
        return styles.unhealthy;
    }
  };

  const getHealthText = (health: HealthStatus): string => {
    switch (health) {
      case 'healthy':
        return '正常';
      case 'degraded':
        return '降级';
      case 'unhealthy':
        return '异常';
      default:
        return '未知';
    }
  };

  return (
    <header className={styles.header}>
      <div className={styles.logo}>
        <h1>AI VTuber 控制面板</h1>
      </div>

      <div className={styles.status}>
        <div className={styles.statusItem}>
          <span className={styles.label}>连接状态:</span>
          <span
            className={`${styles.indicator} ${
              isConnected ? styles.connected : styles.disconnected
            }`}
          >
            {isConnected ? '已连接' : '未连接'}
          </span>
        </div>

        <div className={styles.statusItem}>
          <span className={styles.label}>系统状态:</span>
          <span className={`${styles.indicator} ${getHealthColor(overallHealth)}`}>
            {getHealthText(overallHealth)}
          </span>
        </div>

        {alertCount > 0 && (
          <div className={styles.alertBadge}>
            <span className={styles.alertIcon}>⚠️</span>
            <span className={styles.alertCount}>{alertCount}</span>
          </div>
        )}
      </div>
    </header>
  );
};
