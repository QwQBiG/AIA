import React, { useRef, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import styles from '../../styles/panels/ChatPanel.module.css';

/**
 * 聊天面板组件
 * 显示实时聊天消息流
 */
export const ChatPanel: React.FC = () => {
  const { state } = useDashboard();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.chatMessages]);

  const formatTime = (date: Date): string => {
    const d = new Date(date);
    return d.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getPlatformIcon = (platform: string): string => {
    return platform === 'twitch' ? '🟣' : '🔴';
  };

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>聊天消息</h3>
      <div className={styles.messageList}>
        {state.chatMessages.length === 0 ? (
          <div className={styles.empty}>暂无聊天消息</div>
        ) : (
          state.chatMessages.map((msg) => (
            <div key={msg.id} className={styles.message}>
              <span className={styles.platform}>
                {getPlatformIcon(msg.platform)}
              </span>
              <span className={styles.time}>{formatTime(msg.timestamp)}</span>
              <span className={styles.sender}>
                {msg.sender.displayName}
                {msg.sender.isModerator && (
                  <span className={styles.badge}>🛡️</span>
                )}
                {msg.sender.isSubscriber && (
                  <span className={styles.badge}>⭐</span>
                )}
              </span>
              <span className={styles.content}>{msg.content}</span>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};
