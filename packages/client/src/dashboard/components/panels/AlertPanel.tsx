import React from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { ErrorSeverity, RecoveryAction } from '@digital-human/shared';
import styles from '../../styles/panels/AlertPanel.module.css';

/**
 * 告警面板组件
 * 显示系统错误和告警
 */
export const AlertPanel: React.FC = () => {
  const { state, dispatch } = useDashboard();

  const getSeverityIcon = (severity: ErrorSeverity): string => {
    switch (severity) {
      case ErrorSeverity.LOW:
        return 'ℹ️';
      case ErrorSeverity.MEDIUM:
        return '⚠️';
      case ErrorSeverity.HIGH:
        return '🔶';
      case ErrorSeverity.CRITICAL:
        return '🔴';
      default:
        return '❓';
    }
  };

  const getSeverityClass = (severity: ErrorSeverity): string => {
    switch (severity) {
      case ErrorSeverity.LOW:
        return styles.low;
      case ErrorSeverity.MEDIUM:
        return styles.medium;
      case ErrorSeverity.HIGH:
        return styles.high;
      case ErrorSeverity.CRITICAL:
        return styles.critical;
      default:
        return '';
    }
  };

  const getRecoveryText = (action: RecoveryAction | undefined): string => {
    if (!action) return '';
    switch (action) {
      case RecoveryAction.RETRY:
        return '建议: 重试操作';
      case RecoveryAction.FALLBACK:
        return '建议: 使用备用方案';
      case RecoveryAction.RESTART_MODULE:
        return '建议: 重启模块';
      case RecoveryAction.NOTIFY_CREATOR:
        return '建议: 通知创作者';
      case RecoveryAction.SHUTDOWN:
        return '建议: 关闭系统';
      default:
        return '';
    }
  };

  const formatTime = (date: Date): string => {
    const d = new Date(date);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const handleDismiss = (code: string) => {
    dispatch({ type: 'DISMISS_ALERT', payload: code });
  };

  const handleClearAll = () => {
    dispatch({ type: 'CLEAR_ALERTS' });
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>系统告警</h3>
        {state.alerts.length > 0 && (
          <button onClick={handleClearAll} className={styles.clearButton}>
            清除全部
          </button>
        )}
      </div>

      <div className={styles.alertList}>
        {state.alerts.length === 0 ? (
          <div className={styles.empty}>
            <span className={styles.emptyIcon}>✅</span>
            <span>暂无系统告警</span>
          </div>
        ) : (
          state.alerts
            .slice()
            .reverse()
            .map((alert, index) => (
              <div
                key={`${alert.code}-${index}`}
                className={`${styles.alert} ${getSeverityClass(alert.severity)}`}
              >
                <div className={styles.alertHeader}>
                  <span className={styles.severityIcon}>
                    {getSeverityIcon(alert.severity)}
                  </span>
                  <span className={styles.alertCode}>{alert.code}</span>
                  <span className={styles.alertModule}>{alert.module}</span>
                  <span className={styles.alertTime}>
                    {formatTime(alert.timestamp)}
                  </span>
                  <button
                    onClick={() => handleDismiss(alert.code)}
                    className={styles.dismissButton}
                  >
                    ✕
                  </button>
                </div>
                <div className={styles.alertMessage}>{alert.message}</div>
                {alert.recoveryAction && (
                  <div className={styles.recovery}>
                    {getRecoveryText(alert.recoveryAction)}
                  </div>
                )}
                {alert.context && Object.keys(alert.context).length > 0 && (
                  <details className={styles.context}>
                    <summary>详细信息</summary>
                    <pre>{JSON.stringify(alert.context, null, 2)}</pre>
                  </details>
                )}
              </div>
            ))
        )}
      </div>
    </div>
  );
};
