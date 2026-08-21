# 人格与记忆配置（Phase 8：分类记忆）

人格位于 `[persona]`，与 `[model]` 分离。更换 DeepSeek、KoboldCpp 或 Ollama 不会改变角色名、语气、禁忌和直播模式；服务会把人格配置编译成会话系统提示词。

```toml
[persona]
name = "AIex"
system_prompt = "你是一个友好的 AI 虚拟主播。"
tone = "warm, concise, and curious"
taboos = ["不要泄露密钥", "不要绕过急停"]
live_mode = "controlled"
```

## 本地记忆分类

`ai-ex-memory` 继续使用本地 JSONL，不会自动把记忆上传到云端。每条新记录包含 `kind` 字段：

| 分类 | 用途 | 默认行为 |
| --- | --- | --- |
| `conversation` | 普通对话上下文 | 运行时自动写入和检索 |
| `viewer` | 观众偏好、称呼和关系 | 由直播事件编排层显式写入 |
| `persona` | 角色长期设定和稳定事实 | 由角色管理流程显式写入 |
| `live_event` | 礼物、关注、直播场次等事件 | 由事件总线适配器显式写入 |

旧版本没有 `kind` 的 JSONL 记录会自动视为 `conversation`，无需迁移文件。

分类记忆由 `MemoryStore` 提供以下管理能力：

- `recall_kind`：只检索指定分类，避免观众信息污染角色设定。
- `count`：查看单类或全部记录数量。
- `export_kind`：导出指定分类到独立 JSONL，便于备份和审查。
- `clear_kind`：清除指定分类并重写原文件，保留其他分类。

这些能力仍然只在 Rust 中间件边界内，不要求模型 Provider 了解存储格式。后续直播事件层会把观众和礼物事件映射到 `viewer` / `live_event`，并继续受权限、冷却和急停策略约束。

自动行为继续由 `SafetyGate` 统一拦截：聊天/语音可以自动，外部发言、礼物动作和游戏输入必须经过权限、审计、冷却和急停。
