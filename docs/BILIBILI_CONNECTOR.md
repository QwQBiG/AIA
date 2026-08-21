# Bilibili 连接器（Phase 4）

`ai-ex-bilibili` 只负责 WebSocket 连接、握手、数据包边界解析、平台消息映射和断线重连；输出统一的 `LiveEventEnvelope`，不把 Bilibili 字段带进核心状态机。

当前连接器：

- 默认连接 `wss://broadcastlv.chat.bilibili.com:443/sub`，房间号由 `BilibiliSettings` 提供。
- 支持 `DANMU_MSG`、`SEND_GIFT`、`INTERACT_WORD`（关注）、`SUPER_CHAT_MESSAGE`、开播/下播通知的边界映射。
- 读取 Cookie 只通过显式环境变量名配置；不把 Cookie 写入配置文件或日志。
- 连接中断后按 `reconnect_delay_ms` 重连；平台输入异常只返回连接器错误。
- WebSocket 数据包采用大端长度/操作码解析；版本 2 的 zlib 压缩包会在边界解压并递归解析内部数据包，版本 3 Brotli 在未启用编解码器时明确报错，避免把未解压数据误当作 JSON。模拟连接器和 JSONL 回放始终可用。

无真实账号时运行完整模拟路径：

```powershell
cargo run -p ai-ex-simulator -- --input config/simulated-live.jsonl --speed 20
```

真实连接器的账号权限、Cookie 生命周期和平台协议属于部署边界；生产接入前应为 zlib/Brotli 压缩包版本、嵌套包、重复消息、限流和断线场景补充录制契约测试。
## 服务端接入（可视化向导或配置文件）

桌面首次设置窗口可以勾选“接收 Bilibili 直播事件”，填写房间号和 Cookie 环境变量名。向导只保存环境变量名，不保存 Cookie 内容；默认仍为关闭状态。

开发者或部署脚本可以在本机配置中启用：

~~~toml
[bilibili]
enabled = true
room_id = 123456
endpoint = "wss://broadcastlv.chat.bilibili.com:443/sub"
cookie_env = "BILIBILI_COOKIE"
reconnect_delay_ms = 2000
auto_react = false
reaction_cooldown_ms = 5000
~~~

然后启动服务：

~~~powershell
$env:BILIBILI_COOKIE = "你的 Cookie"
cargo run -p ai-ex-service -- --config "config/ai-ex.local.toml"
~~~

连接器在服务后台运行，收到的弹幕、关注、礼物和醒目留言先经过统一事件总线，再投影到 memory.path。默认 auto_react = false，只在桌面开发者日志和终端显示“建议反应”；开启后也只调用现有 Runtime 生成角色语音/表情反应，不会向 Bilibili 自动发言。reaction_cooldown_ms 用于限制自动反应频率，急停状态会阻止新反应。连接器断线或平台不可用时，核心对话和桌面控制不会被拖垮；真实账号网络连接需要在目标机器上单独验证。
