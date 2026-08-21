# 人格与记忆配置（Phase 5 基础）

人格位于 `[persona]`，与 `[model]` 分离。更换 DeepSeek、KoboldCpp 或 Ollama 不会改变角色名、语气、禁忌和直播模式；服务会把人格配置编译成会话系统提示词。

```toml
[persona]
name = "AIex"
system_prompt = "你是一个友好的 AI 虚拟主播。"
tone = "warm, concise, and curious"
taboos = ["不要泄露密钥", "不要绕过急停"]
live_mode = "controlled"
```

记忆仍然默认本地 JSONL 保存，云端模型不会自动上传记忆文件。当前短期对话记忆由 `ai-ex-memory` 管理；观众记忆、角色长期记忆和直播事件记忆会在下一步以相同本地格式分层接入，并提供按类别导出、清理、禁用和回滚。

自动行为继续由 `SafetyGate` 统一拦截：聊天/语音可以自动，外部发言、礼物动作和游戏输入必须经过权限、审计、冷却和急停。
