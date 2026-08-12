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
{"type":"events","after":42,"limit":256}
{"type":"emergency_stop"}
```

`submit` 返回 accepted 后异步执行。客户端通过 `status` 获取最新只读快照，通过
`events` 从指定序号之后重放有界事件历史。`limit` 必须位于 1 到 1000；事件带单调递增序号，客户端检测到缺口时必须暂停应用后续事件并重新拉取。

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
