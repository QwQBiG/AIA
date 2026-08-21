# AIex Protocol v1

`ai-ex-protocol` 是 Provider 与 Rust 核心之间的稳定边界。Provider 可以在 Rust、Python 或 Node 独立进程中实现同一语义；核心只依赖能力声明、健康状态和版本化流事件。

## ModelBackend

- `capabilities()`：声明 text、vision、audio、tool_call、structured_output、reasoning、cancellation。
- `health()`：返回可展示且可审计的组件健康状态。
- `stream(ModelRequest)`：返回 `ModelStreamEvent` 流，不再把纯字符串当作唯一协议。
- `cancel(TurnId)`：取消当前回合；不支持时必须在 capabilities 中声明 false。

`TextDelta`、`ReasoningDelta`、`ToolCall`、`StructuredOutput`、`Usage`、`Finished`、`Failed` 都是独立事件。供应商字段只能放在 Provider 边界或结构化 payload 中。

## EventEnvelope

`EventEnvelope<T>` 提供 `schema_version`、事件/追踪/会话/回合 ID、毫秒时间戳、来源和 payload。非回合事件的 `turn_id` 使用 `null`，模型回合事件填入具体 ID。外部传输使用 JSON；录制与回放必须保留 envelope 原样，便于跨 Provider 重放。

## 兼容迁移

现有 DeepSeek、KoboldCpp、Ollama 仍使用旧的 `LanguageModelPort`，由 `ai_ex_core::LegacyModelBackend` 转换为 v1 流事件。新增 Provider 不需要修改会话状态机；后续 Provider 可直接实现 `ai_ex_protocol::ModelBackend`。

JSON Schema 文件：

- `model-stream.schema.json`
- `event-envelope.schema.json`
