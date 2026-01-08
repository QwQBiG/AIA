import React from 'react';
import { useDashboard } from '../../context/DashboardContext';
import styles from '../../styles/panels/GameStatePanel.module.css';

/**
 * 游戏状态面板组件
 * 显示当前游戏状态信息
 */
export const GameStatePanel: React.FC = () => {
  const { state } = useDashboard();
  const gameState = state.gameState;

  const formatTime = (date: Date): string => {
    const d = new Date(date);
    return d.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  if (!gameState) {
    return (
      <div className={styles.panel}>
        <h3 className={styles.title}>游戏状态</h3>
        <div className={styles.empty}>暂无游戏状态数据</div>
      </div>
    );
  }

  const { analysis } = gameState;

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>游戏状态</h3>
      <div className={styles.content}>
        <div className={styles.timestamp}>
          更新时间: {formatTime(gameState.timestamp)}
          {gameState.significantChange && (
            <span className={styles.changeIndicator}>🔄 状态变化</span>
          )}
        </div>

        <div className={styles.section}>
          <h4>玩家信息</h4>
          <div className={styles.info}>
            {analysis.playerPosition && (
              <div className={styles.item}>
                <span className={styles.label}>位置:</span>
                <span className={styles.value}>
                  ({analysis.playerPosition.x}, {analysis.playerPosition.y})
                </span>
              </div>
            )}
            {analysis.health !== undefined && (
              <div className={styles.item}>
                <span className={styles.label}>血量:</span>
                <span className={styles.value}>
                  <div className={styles.healthBar}>
                    <div
                      className={styles.healthFill}
                      style={{ width: `${analysis.health}%` }}
                    />
                  </div>
                  {analysis.health}%
                </span>
              </div>
            )}
          </div>
        </div>

        {analysis.inventory && analysis.inventory.length > 0 && (
          <div className={styles.section}>
            <h4>物品栏</h4>
            <div className={styles.inventory}>
              {analysis.inventory.map((item, index) => (
                <span key={index} className={styles.inventoryItem}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className={styles.section}>
          <h4>环境</h4>
          <div className={styles.environment}>{analysis.environment}</div>
        </div>

        {analysis.detectedObjects.length > 0 && (
          <div className={styles.section}>
            <h4>检测到的对象 ({analysis.detectedObjects.length})</h4>
            <div className={styles.objects}>
              {analysis.detectedObjects.slice(0, 5).map((obj, index) => (
                <div key={index} className={styles.object}>
                  <span className={styles.objectName}>{obj.name}</span>
                  <span className={styles.objectType}>{obj.type}</span>
                  <span className={styles.confidence}>
                    {Math.round(obj.confidence * 100)}%
                  </span>
                </div>
              ))}
              {analysis.detectedObjects.length > 5 && (
                <div className={styles.more}>
                  +{analysis.detectedObjects.length - 5} 更多
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
