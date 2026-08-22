# AIex 本地控制协议

## 目的

桌面 UI、调试工具和未来插件只通过本协议控制 AIex，不直接依赖 LLM、音频、VTS、记忆或安全适配器。服务是唯一组合根和状态所有者。

## 传输与安全

- TCP + UTF-8 JSON Lines：每条请求和响应占一行。
- 只允许绑定 IPv4/IPv6 回环地址；配置非回环地址会被拒绝。
- 每条请求必须携带令牌。令牌从独立文件读取，至少 32 字节，不写入 TOML 或日志。
- 单条消息默认上限 65536 字节；超限连接收到失败响应后关闭。
- `emergency_stop` 会撤销已签发的自动化许可，并尝试打断当前对话。

默认配置：

```toml
[control]
enabled = false
bind = "127.0.0.1:7878"
token_path = "config/control.token"
max_message_bytes = 65536
```

## 请求

请求具有 UUID、令牌和带类型的命令：

```json
{"request_id":"00000000-0000-0000-0000-000000000001","token":"<redacted>","command":{"type":"status"}}
```

支持的命令：

```json
{"type":"submit","text":"你好"}
{"type":"interrupt","reason":"user barge-in"}
{"type":"status"}
{"type":"stage"}
{"type":"persona"}
{"type":"set_persona","profile":{"profile_id":"default","revision":2,"name":"AIex","system_prompt":"","tone":"warm, concise, and curious","taboos":[],"live_mode":"controlled"}}
{"type":"events","after":42,"limit":256}
{"type":"emergency_stop"}
```

`persona` 读取当前角色快照；`set_persona` 经过版本/字段校验后更新 Runtime 系统提示词，并广播 `persona_changed` 事件。活动回合期间切换会失败，避免一半回复使用旧人格、一半回复使用新人格。`submit` 返回 accepted 后异步执行。客户端通过 `status` 获取最新只读快照，通过
`events` 从指定序号之后重放有界事件历史。`limit` 必须位于 1 到 1000；事件带单调递增序号，客户端检测到缺口时必须暂停应用后续事件并重新拉取。

桌面端的新手角色面板使用同一协议：先读取 `persona`，本地编辑草稿，再在确认窗口中发送 `set_persona`。桌面端只在收到 `persona` 快照或 `persona_changed` 事件后更新显示，不会把未确认草稿直接写入服务。开发者可用 `events` 观察角色变更、失败和运行时事件，终端继续保留服务原始日志。
`stage` 返回最近的舞台动作摘要，包含遥测 schema、单调序号、动作类型和受限 detail；它只读，不会触发 OBS 或桌面副作用。

## 响应

成功响应：

```json
{"status":"success","request_id":"00000000-0000-0000-0000-000000000001","payload":{"type":"accepted"}}
```

状态响应的 payload 类型为 `snapshot`，包含当前会话状态、活动轮次、完成/打断/故障计数和最后故障。

失败响应：

```json
{"status":"failure","request_id":null,"error":{"kind":"protocol","message":"invalid control request"}}
```

错误类型与 Rust 领域错误一致：配置、连接、协议、非法状态、安全、不可用和内部错误。客户端不得把 failure 当作 accepted，也不得自动绕过安全错误重试动作。
