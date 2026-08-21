# 插件协议（Phase 6）

`ai-ex-plugin` 固定本地插件的最小边界：JSON-RPC 2.0 over stdio，一行一个请求或响应。插件通过 `PluginManifest` 声明版本、能力、健康状态和配置 schema；插件崩溃只影响自身进程。

核心请求示例：

```json
{"jsonrpc":"2.0","id":1,"method":"health","params":{}}
```

插件不得直接访问核心内存、控制令牌或任意桌面输入。VTS、TTS、OBS、视觉和游戏适配器都应在该边界上实现；游戏插件默认只返回观察结果，动作必须经过能力白名单、人工确认和急停。

远程 Provider 可以复用相同 JSON 结构，通过 HTTP/SSE 或 WebSocket 传输；MCP 只作为可选工具/资源发现层，不改变 AIex 核心协议。
## 舞台动作协议

ai-ex-stage 提供平台无关的 StageAction、StageCapability 和 StageExecutor。VTS、TTS、字幕、OBS 场景和热键都先转换为动作，再由具体适配器执行。DryRunStage 会校验并记录动作，不产生外部副作用，可用于录制回放和桌面端联调。

`ai-ex-stage-obs` 提供 `ObsDryRunStage`：它只接受字幕、场景和热键动作，记录版本化 JSONL，并在急停时清空待执行动作但保留停止记录。真实 OBS WebSocket 连接器以后只需复用 StageExecutor，不会把 OBS SDK 或网络状态带入核心。

动作默认受到长度、数值范围、队列容量和急停边界约束；真实适配器不得绕过这些校验。

`ObsWebSocketStage` 是真实 OBS v5 连接器：启动时完成 Hello/Identify/Identified 握手，可选读取密码环境变量，并把字幕、场景和热键转换为 OBS request。它只在 `obs.enabled = true` 时建立连接；连接失败不会拖垮模型和本地 dry-run。
`StageRouter` 按 `StageCapability` 把动作分发给所有匹配的执行器，并把 `Stop`/急停广播到全部执行器；新增 VTS、音频或 OBS 实现不需要修改会话状态机。

Runtime 通过 `ai-ex-core` 的 `StageOutput` 将 `SpeechPort` 与 `AvatarPort` 桥接到 `StageRouter`。因此会话状态机只面向语音和化身抽象，具体的 VTS、音频、字幕或 OBS Provider 仍留在舞台适配器边界。

当路由器声明 `Subtitle` 能力时，`StageSpeechPort` 会为每个完整句子生成受限时长字幕动作；没有字幕执行器时，语音路径保持兼容。

## 视觉与游戏自动化边界

`ai-ex-automation` 的 `AutomationCoordinator` 是所有视觉观察和游戏动作的安全入口；它固定执行“校验动作 → 持久审计 → SafetyGate 授权 → Permit 复核 → 适配器执行”的顺序。`DryRunAutomationPort` 实现同一接口但不触碰真实桌面：动作只进入有界队列，`CaptureScreen` 返回确定性的 RGBA 帧，Permit 能力不匹配或急停都会被再次拒绝。

视觉插件只应返回 `ScreenFrame` 或结构化观察，游戏插件只应提交白名单内的 `AutomationAction`。真实键鼠、进程启动和截图实现必须位于独立进程或明确的原生适配器边界，默认配置保持 dry-run。