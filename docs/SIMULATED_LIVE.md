# 模拟直播回放

Phase 3 提供平台无关的直播事件总线和 JSONL 回放器。事件先在边界转换成统一 `EventEnvelope<LiveEvent>`，再经过事件优先级、去重、观众冷却和队列容量策略。

运行示例：

```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 20
```

`--speed 20` 表示按 20 倍时间速度回放。模拟器会打印每个事件的优先级、过滤结果和最终接收数量。

JSONL 录制文件不包含 API Key、控制令牌或用户长期记忆。真实平台连接器只需要把平台字段转换为 `LiveEvent`，不应把平台 SDK 类型带入核心。

事件策略：

- `Moderation` 和 `SystemNotice` 进入安全优先级。
- 礼物/捐赠高于普通聊天。
- 聊天和提及按消息 ID 去重，并受用户/全局冷却限制。
- 队列满时丢弃新事件并返回 `QueueFull`，不会阻塞急停和人工输入。
