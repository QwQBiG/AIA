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

运行时上下文不会把所有分类无边界地塞给模型：默认上下文只检索 `conversation`、`persona` 和 `viewer`，排除 `live_event` 原始记录；每次仍受 `memory_recall_limit` 上限约束。这样可以保留观众关系，又避免直播事件日志无限扩大上下文。需要审计或回放时，再通过分类 API 单独检索 `live_event`。`MemoryPort::recall_for_context` 是核心的可替换边界，未来可接向量检索或远程记忆而不修改 Runtime。

分类记忆由 `MemoryStore` 提供以下管理能力：

- `recall_kind`：只检索指定分类，避免观众信息污染角色设定。
- `count`：查看单类或全部记录数量。
- `export_kind`：导出指定分类到独立 JSONL，便于备份和审查。
- `clear_kind`：清除指定分类并重写原文件，保留其他分类。

平台无关事件总线提供 `project_memory` 投影：聊天/关注/订阅进入 `viewer`，礼物/付费支持同时产生观众关系和 `live_event` 记录，游戏观察和系统通知进入 `live_event`；审核事件和定时器默认不写入记忆。服务层可以把投影交给 `MemoryStore::remember_projection`，模型 Provider 不需要了解事件或存储格式。所有自动响应仍继续受权限、冷却和急停策略约束。

自动行为继续由 `SafetyGate` 统一拦截：聊天/语音可以自动，外部发言、礼物动作和游戏输入必须经过权限、审计、冷却和急停。
