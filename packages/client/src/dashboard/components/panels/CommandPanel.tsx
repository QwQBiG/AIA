import React, { useState, useRef, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { MessageType } from '@digital-human/shared';
import styles from '../../styles/panels/CommandPanel.module.css';

/**
 * 命令面板组件
 * 用于发送命令到 Orchestrator
 */
export const CommandPanel: React.FC = () => {
  const { state, dispatch } = useDashboard();
  const [command, setCommand] = useState('');
  const [historyIndex, setHistoryIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  // 聚焦输入框
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim() || !state.sendMessage) return;

    // 发送命令到 Orchestrator
    state.sendMessage({
      type: MessageType.DASHBOARD_COMMAND,
      payload: {
        command: command.trim(),
        timestamp: new Date(),
      },
    });

    // 添加到命令历史
    dispatch({ type: 'ADD_COMMAND', payload: command.trim() });

    // 清空输入
    setCommand('');
    setHistoryIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (state.commandHistory.length > 0) {
        const newIndex = Math.min(
          historyIndex + 1,
          state.commandHistory.length - 1
        );
        setHistoryIndex(newIndex);
        setCommand(
          state.commandHistory[state.commandHistory.length - 1 - newIndex]
        );
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setCommand(
          state.commandHistory[state.commandHistory.length - 1 - newIndex]
        );
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCommand('');
      }
    }
  };

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>命令发送</h3>

      <form onSubmit={handleSubmit} className={styles.form}>
        <input
          ref={inputRef}
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入命令..."
          className={styles.input}
          disabled={!state.isConnected}
        />
        <button
          type="submit"
          className={styles.button}
          disabled={!state.isConnected || !command.trim()}
        >
          发送
        </button>
      </form>

      {!state.isConnected && (
        <div className={styles.warning}>⚠️ 未连接到 Orchestrator</div>
      )}

      <div className={styles.help}>
        <h4>可用命令</h4>
        <ul className={styles.commandList}>
          <li>
            <code>say [text]</code> - 让 AI 说指定内容
          </li>
          <li>
            <code>emotion [type]</code> - 设置表情 (happy/sad/angry/etc)
          </li>
          <li>
            <code>mode [mode]</code> - 切换控制模式 (autonomous/semi/manual)
          </li>
          <li>
            <code>action [name]</code> - 执行游戏动作
          </li>
          <li>
            <code>status</code> - 查看系统状态
          </li>
        </ul>
      </div>

      <div className={styles.history}>
        <h4>命令历史</h4>
        {state.commandHistory.length === 0 ? (
          <div className={styles.empty}>暂无命令历史</div>
        ) : (
          <ul className={styles.historyList}>
            {state.commandHistory
              .slice()
              .reverse()
              .slice(0, 10)
              .map((cmd, index) => (
                <li
                  key={index}
                  className={styles.historyItem}
                  onClick={() => setCommand(cmd)}
                >
                  <code>{cmd}</code>
                </li>
              ))}
          </ul>
        )}
      </div>
    </div>
  );
};
