import React, { useState } from 'react';
import { ChatPanel } from './panels/ChatPanel';
import { AIResponsePanel } from './panels/AIResponsePanel';
import { GameStatePanel } from './panels/GameStatePanel';
import { CommandPanel } from './panels/CommandPanel';
import { AlertPanel } from './panels/AlertPanel';
import { OverridePanel } from './panels/OverridePanel';
import styles from '../styles/MainContent.module.css';

type TabType = 'activity' | 'command' | 'override' | 'alerts';

/**
 * 主内容区域组件
 * 包含活动监控、命令发送、覆盖控制和告警面板
 */
export const MainContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('activity');

  return (
    <main className={styles.main}>
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'activity' ? styles.active : ''}`}
          onClick={() => setActiveTab('activity')}
        >
          活动监控
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'command' ? styles.active : ''}`}
          onClick={() => setActiveTab('command')}
        >
          命令发送
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'override' ? styles.active : ''}`}
          onClick={() => setActiveTab('override')}
        >
          覆盖控制
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'alerts' ? styles.active : ''}`}
          onClick={() => setActiveTab('alerts')}
        >
          系统告警
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === 'activity' && (
          <div className={styles.activityGrid}>
            <div className={styles.chatSection}>
              <ChatPanel />
            </div>
            <div className={styles.aiSection}>
              <AIResponsePanel />
            </div>
            <div className={styles.gameSection}>
              <GameStatePanel />
            </div>
          </div>
        )}

        {activeTab === 'command' && <CommandPanel />}

        {activeTab === 'override' && <OverridePanel />}

        {activeTab === 'alerts' && <AlertPanel />}
      </div>
    </main>
  );
};
