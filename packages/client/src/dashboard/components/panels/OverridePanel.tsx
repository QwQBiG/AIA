import React, { useState } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { MessageType, ControlMode } from '@digital-human/shared';
import styles from '../../styles/panels/OverridePanel.module.css';

/**
 * 覆盖功能面板组件
 * 用于覆盖 AI 决策、注入自定义响应、切换游戏控制模式
 */
export const OverridePanel: React.FC = () => {
  const { state } = useDashboard();
  const [customResponse, setCustomResponse] = useState('');
  const [selectedEmotion, setSelectedEmotion] = useState('neutral');
  const [controlMode, setControlMode] = useState<ControlMode>('autonomous');

  const emotions = [
    { value: 'neutral', label: '😐 中性', icon: '😐' },
    { value: 'happy', label: '😊 开心', icon: '😊' },
    { value: 'sad', label: '😢 悲伤', icon: '😢' },
    { value: 'surprised', label: '😮 惊讶', icon: '😮' },
    { value: 'angry', label: '😠 生气', icon: '😠' },
    { value: 'thinking', label: '🤔 思考', icon: '🤔' },
  ];

  const controlModes: { value: ControlMode; label: string; description: string }[] = [
    {
      value: 'autonomous',
      label: '自主模式',
      description: 'AI 完全自主控制游戏',
    },
    {
      value: 'semi-autonomous',
      label: '半自主模式',
      description: 'AI 控制，创作者可随时覆盖',
    },
    {
      value: 'manual',
      label: '手动模式',
      description: '创作者完全手动控制',
    },
  ];

  const handleInjectResponse = () => {
    if (!customResponse.trim() || !state.sendMessage) return;

    state.sendMessage({
      type: MessageType.DASHBOARD_OVERRIDE,
      payload: {
        action: 'inject_response',
        response: {
          text: customResponse.trim(),
          emotion: selectedEmotion,
          shouldSpeak: true,
        },
      },
    });

    setCustomResponse('');
  };

  const handleOverrideDecision = (decision: string) => {
    if (!state.sendMessage) return;

    state.sendMessage({
      type: MessageType.DASHBOARD_OVERRIDE,
      payload: {
        action: 'override_decision',
        decision,
      },
    });
  };

  const handleModeChange = (mode: ControlMode) => {
    if (!state.sendMessage) return;

    setControlMode(mode);
    state.sendMessage({
      type: MessageType.DASHBOARD_OVERRIDE,
      payload: {
        action: 'change_mode',
        mode,
      },
    });
  };

  const handleStopSpeaking = () => {
    if (!state.sendMessage) return;

    state.sendMessage({
      type: MessageType.DASHBOARD_OVERRIDE,
      payload: {
        action: 'stop_speaking',
      },
    });
  };

  const handlePauseAI = () => {
    if (!state.sendMessage) return;

    state.sendMessage({
      type: MessageType.DASHBOARD_OVERRIDE,
      payload: {
        action: 'pause_ai',
      },
    });
  };

  const handleResumeAI = () => {
    if (!state.sendMessage) return;

    state.sendMessage({
      type: MessageType.DASHBOARD_OVERRIDE,
      payload: {
        action: 'resume_ai',
      },
    });
  };

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>覆盖控制</h3>

      {!state.isConnected && (
        <div className={styles.warning}>⚠️ 未连接到 Orchestrator</div>
      )}

      {/* 自定义响应注入 */}
      <section className={styles.section}>
        <h4>注入自定义响应</h4>
        <p className={styles.description}>
          直接让 AI 说出指定内容，覆盖当前的 AI 响应
        </p>

        <div className={styles.emotionSelector}>
          <label>表情:</label>
          <div className={styles.emotionButtons}>
            {emotions.map((emotion) => (
              <button
                key={emotion.value}
                className={`${styles.emotionButton} ${
                  selectedEmotion === emotion.value ? styles.selected : ''
                }`}
                onClick={() => setSelectedEmotion(emotion.value)}
                title={emotion.label}
              >
                {emotion.icon}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.inputGroup}>
          <textarea
            value={customResponse}
            onChange={(e) => setCustomResponse(e.target.value)}
            placeholder="输入要让 AI 说的内容..."
            className={styles.textarea}
            rows={3}
            disabled={!state.isConnected}
          />
          <button
            onClick={handleInjectResponse}
            className={styles.primaryButton}
            disabled={!state.isConnected || !customResponse.trim()}
          >
            注入响应
          </button>
        </div>
      </section>

      {/* 游戏控制模式 */}
      <section className={styles.section}>
        <h4>游戏控制模式</h4>
        <p className={styles.description}>切换 AI 对游戏的控制程度</p>

        <div className={styles.modeSelector}>
          {controlModes.map((mode) => (
            <button
              key={mode.value}
              className={`${styles.modeButton} ${
                controlMode === mode.value ? styles.selected : ''
              }`}
              onClick={() => handleModeChange(mode.value)}
              disabled={!state.isConnected}
            >
              <span className={styles.modeLabel}>{mode.label}</span>
              <span className={styles.modeDescription}>{mode.description}</span>
            </button>
          ))}
        </div>
      </section>

      {/* 快速操作 */}
      <section className={styles.section}>
        <h4>快速操作</h4>
        <p className={styles.description}>常用的覆盖操作</p>

        <div className={styles.quickActions}>
          <button
            onClick={handleStopSpeaking}
            className={styles.actionButton}
            disabled={!state.isConnected}
          >
            🔇 停止说话
          </button>
          <button
            onClick={handlePauseAI}
            className={styles.actionButton}
            disabled={!state.isConnected}
          >
            ⏸️ 暂停 AI
          </button>
          <button
            onClick={handleResumeAI}
            className={styles.actionButton}
            disabled={!state.isConnected}
          >
            ▶️ 恢复 AI
          </button>
          <button
            onClick={() => handleOverrideDecision('skip_response')}
            className={styles.actionButton}
            disabled={!state.isConnected}
          >
            ⏭️ 跳过响应
          </button>
        </div>
      </section>

      {/* AI 决策覆盖 */}
      <section className={styles.section}>
        <h4>AI 决策覆盖</h4>
        <p className={styles.description}>覆盖 AI 的下一个决策</p>

        <div className={styles.decisionButtons}>
          <button
            onClick={() => handleOverrideDecision('approve')}
            className={`${styles.decisionButton} ${styles.approve}`}
            disabled={!state.isConnected}
          >
            ✓ 批准决策
          </button>
          <button
            onClick={() => handleOverrideDecision('reject')}
            className={`${styles.decisionButton} ${styles.reject}`}
            disabled={!state.isConnected}
          >
            ✗ 拒绝决策
          </button>
          <button
            onClick={() => handleOverrideDecision('modify')}
            className={`${styles.decisionButton} ${styles.modify}`}
            disabled={!state.isConnected}
          >
            ✎ 修改决策
          </button>
        </div>
      </section>
    </div>
  );
};
