# Bilibili 连接器（Phase 4）

`ai-ex-bilibili` 只负责 WebSocket 连接、握手、数据包边界解析、平台消息映射和断线重连；输出统一的 `LiveEventEnvelope`，不把 Bilibili 字段带进核心状态机。

当前连接器：

- 默认连接 `wss://broadcastlv.chat.bilibili.com:443/sub`，房间号由 `BilibiliSettings` 提供。
- 支持 `DANMU_MSG`、`SEND_GIFT`、`INTERACT_WORD`（关注）、`SUPER_CHAT_MESSAGE`、开播/下播通知的边界映射。
- 读取 Cookie 只通过显式环境变量名配置；不把 Cookie 写入配置文件或日志。
- 连接中断后按 `reconnect_delay_ms` 重连；平台输入异常只返回连接器错误。
- WebSocket 数据包采用大端长度/操作码解析；压缩版本在边界明确报错，避免把未解压数据误当作 JSON。模拟连接器和 JSONL 回放始终可用。

无真实账号时运行完整模拟路径：

```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 20
```

真实连接器的账号权限、Cookie 生命周期和平台协议属于部署边界；生产接入前应为压缩包版本、重复消息、限流和断线场景补充录制契约测试。
