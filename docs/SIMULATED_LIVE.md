# 模拟直播回放

Phase 3 提供平台无关的直播事件总线和 JSONL 回放器。事件先在边界转换成统一 `EventEnvelope<LiveEvent>`，再经过事件优先级、去重、观众冷却和队列容量策略。

运行示例：

```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 20

开发者若要保存可重复的验收结果，可以增加 `--report`：
```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 100 --report target/simulated-live-report.jsonl
```

报告每行记录事件 ID、优先级、过滤结果、响应建议和记忆投影数量；不会调用模型、VTS、键鼠或直播平台。
```

`--speed 20` 表示按 20 倍时间速度回放。模拟器会打印每个事件的优先级、过滤结果、响应建议状态和最终接收数量。

如果希望把回放事件实际写入分类记忆，增加 `--memory`：

```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 20

开发者若要保存可重复的验收结果，可以增加 `--report`：
```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 100 --report target/simulated-live-report.jsonl
```

报告每行记录事件 ID、优先级、过滤结果、响应建议和记忆投影数量；不会调用模型、VTS、键鼠或直播平台。 --memory memory_db/simulated-live.jsonl
```

该模式会通过 `EventBus` 的去重/冷却后再调用 `project_memory`，最终输出 `persisted_memory` 数量。

同一条链路也可以由服务组合根执行，不会初始化模型、VTS 或音频：

```powershell
cargo run -p ai-ex-service -- --config config/ai-ex.example.toml --replay-events config/simulated-live.jsonl
```

服务会使用配置中的 `[memory]` 路径，输出 `input`、`accepted`、`projected_memory` 和 `persisted_memory`，适合在没有任何模型或直播账号时验证完整编排链路。

JSONL 录制文件不包含 API Key、控制令牌或用户长期记忆。真实平台连接器只需要把平台字段转换为 `LiveEvent`，不应把平台 SDK 类型带入核心。

事件进入总线后可以调用 `project_memory` 生成平台无关的记忆投影：观众关系写入 `viewer`，礼物/捐赠和系统事件写入 `live_event`。投影交给 `MemoryStore::remember_projection` 后才会落盘；审核事件和定时器默认不写入记忆。

事件策略：

- `Moderation` 和 `SystemNotice` 进入安全优先级。
- 礼物/捐赠高于普通聊天。
- 聊天和提及按消息 ID 去重，并受用户/全局冷却限制。
- 队列满时丢弃新事件并返回 `QueueFull`，不会阻塞急停和人工输入。
