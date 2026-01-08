import React, { useRef, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import styles from '../../styles/panels/AIResponsePanel.module.css';

/**
 * AI 响应面板组件
 * 显示 AI 生成的响应
 */
export const AIResponsePanel: React.FC = () => {
  const { state } = useDashboard();
  const responsesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新响应
  useEffect(() => {
    responsesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.aiResponses]);

  const formatTime = (date: Date): string => {
    const d = new Date(date);
    return d.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getEmotionIcon = (emotion: string): string => {
    const emotionIcons: Record<string, string> = {
      neutral: '😐',
      happy: '😊',
      sad: '😢',
      surprised: '😮',
      angry: '😠',
      thinking: '🤔',
    };
    return emotionIcons[emotion] || '😐';
  };

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>AI 响应</h3>
      <div className={styles.responseList}>
        {state.aiResponses.length === 0 ? (
          <div className={styles.empty}>暂无 AI 响应</div>
        ) : (
          state.aiResponses.map((response) => (
            <div key={response.id} className={styles.response}>
              <div className={styles.header}>
                <span className={styles.emotion}>
                  {getEmotionIcon(response.emotion)}
                </span>
                <span className={styles.time}>
                  {formatTime(response.timestamp)}
                </span>
              </div>
              <div className={styles.text}>{response.responseText}</div>
            </div>
          ))
        )}
        <div ref={responsesEndRef} />
      </div>
    </div>
  );
};
