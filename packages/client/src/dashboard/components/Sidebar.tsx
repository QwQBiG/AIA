import React from 'react';
import { ModuleType, ModuleStatus, HealthStatus } from '@digital-human/shared';
import styles from '../styles/Sidebar.module.css';

interface SidebarProps {
  moduleStatuses: Map<ModuleType, ModuleStatus>;
}

/**
 * 模块名称映射
 */
const MODULE_NAMES: Record<ModuleType, string> = {
  [ModuleType.COGNITION]: '认知引擎',
  [ModuleType.VISION]: '视觉模块',
  [ModuleType.MEMORY]: '记忆系统',
  [ModuleType.TTS]: '语音合成',
  [ModuleType.CHAT]: '聊天接口',
  [ModuleType.GAME_CONTROLLER]: '游戏控制',
  [ModuleType.AVATAR]: '虚拟形象',
  [ModuleType.DASHBOARD]: '控制面板',
};

/**
 * 所有模块类型列表
 */
const ALL_MODULES: ModuleType[] = [
  ModuleType.COGNITION,
  ModuleType.VISION,
  ModuleType.MEMORY,
  ModuleType.TTS,
  ModuleType.CHAT,
  ModuleType.GAME_CONTROLLER,
  ModuleType.AVATAR,
];

/**
 * 侧边栏组件
 * 显示所有模块的状态
 */
export const Sidebar: React.FC<SidebarProps> = ({ moduleStatuses }) => {
  const getHealthIcon = (health: HealthStatus): string => {
    switch (health) {
      case 'healthy':
        return '🟢';
      case 'degraded':
        return '🟡';
      case 'unhealthy':
        return '🔴';
      default:
        return '⚪';
    }
  };

  const getStatusForModule = (moduleType: ModuleType): ModuleStatus | null => {
    return moduleStatuses.get(moduleType) || null;
  };

  const formatLastHeartbeat = (date: Date | undefined): string => {
    if (!date) return '从未';
    const now = new Date();
    const diff = Math.floor((now.getTime() - new Date(date).getTime()) / 1000);
    if (diff < 60) return `${diff}秒前`;
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    return `${Math.floor(diff / 3600)}小时前`;
  };

  return (
    <aside className={styles.sidebar}>
      <h2 className={styles.title}>模块状态</h2>
      <ul className={styles.moduleList}>
        {ALL_MODULES.map((moduleType) => {
          const status = getStatusForModule(moduleType);
          const health = status?.health || 'unhealthy';
          const isConnected = status?.isConnected || false;

          return (
            <li key={moduleType} className={styles.moduleItem}>
              <div className={styles.moduleHeader}>
                <span className={styles.healthIcon}>{getHealthIcon(health)}</span>
                <span className={styles.moduleName}>
                  {MODULE_NAMES[moduleType]}
                </span>
              </div>
              <div className={styles.moduleDetails}>
                <span
                  className={`${styles.connectionStatus} ${
                    isConnected ? styles.online : styles.offline
                  }`}
                >
                  {isConnected ? '在线' : '离线'}
                </span>
                <span className={styles.lastHeartbeat}>
                  {formatLastHeartbeat(status?.lastHeartbeat)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
};
