import React, { useEffect, useState } from 'react';
import { SystemError, ErrorSeverity } from '@digital-human/shared';
import styles from '../styles/Toast.module.css';

interface ToastProps {
  error: SystemError;
  onDismiss: () => void;
  duration?: number;
}

/**
 * Toast 通知组件
 * 显示系统错误告警
 */
export const Toast: React.FC<ToastProps> = ({
  error,
  onDismiss,
  duration = 5000,
}) => {
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    // 自动关闭（除了 CRITICAL 级别）
    if (error.severity !== ErrorSeverity.CRITICAL) {
      const timer = setTimeout(() => {
        handleDismiss();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [error.severity, duration]);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(onDismiss, 300); // 等待退出动画完成
  };

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

  return (
    <div
      className={`${styles.toast} ${getSeverityClass(error.severity)} ${
        isExiting ? styles.exiting : ''
      }`}
    >
      <div className={styles.icon}>{getSeverityIcon(error.severity)}</div>
      <div className={styles.content}>
        <div className={styles.header}>
          <span className={styles.code}>{error.code}</span>
          <span className={styles.module}>{error.module}</span>
        </div>
        <div className={styles.message}>{error.message}</div>
      </div>
      <button onClick={handleDismiss} className={styles.closeButton}>
        ✕
      </button>
    </div>
  );
};

interface ToastContainerProps {
  errors: SystemError[];
  onDismiss: (code: string) => void;
}

/**
 * Toast 容器组件
 * 管理多个 Toast 通知的显示
 */
export const ToastContainer: React.FC<ToastContainerProps> = ({
  errors,
  onDismiss,
}) => {
  // 只显示最近的 5 个告警
  const visibleErrors = errors.slice(-5);

  return (
    <div className={styles.container}>
      {visibleErrors.map((error, index) => (
        <Toast
          key={`${error.code}-${index}`}
          error={error}
          onDismiss={() => onDismiss(error.code)}
        />
      ))}
    </div>
  );
};
