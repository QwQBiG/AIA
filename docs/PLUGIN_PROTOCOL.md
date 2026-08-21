# 插件协议（Phase 6）

`ai-ex-plugin` 固定本地插件的最小边界：JSON-RPC 2.0 over stdio，一行一个请求或响应。插件通过 `PluginManifest` 声明版本、能力、健康状态和配置 schema；插件崩溃只影响自身进程。

核心请求示例：

```json
{"jsonrpc":"2.0","id":1,"method":"health","params":{}}
```

插件不得直接访问核心内存、控制令牌或任意桌面输入。VTS、TTS、OBS、视觉和游戏适配器都应在该边界上实现；游戏插件默认只返回观察结果，动作必须经过能力白名单、人工确认和急停。

远程 Provider 可以复用相同 JSON 结构，通过 HTTP/SSE 或 WebSocket 传输；MCP 只作为可选工具/资源发现层，不改变 AIex 核心协议。
