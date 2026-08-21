# AIex 模型后端操作手册

AIex 的模型层由统一的 \`LanguageModelPort\` 驱动，服务组合根按配置选择后端。三种后端可以并存：

| 后端 | 连接方式 | 当前用途 |
| --- | --- | --- |
| DeepSeek | 官方 OpenAI 兼容 API，SSE 流式 | 现在优先测试 |
| KoboldCpp | 本机 HTTP/SSE | 本地模型测试 |
| Ollama | 本机 HTTP/NDJSON | 保留给其他用户 |

## DeepSeek V4

官方 API 地址是 \`https://api.deepseek.com\`，当前 V4 API 型号为 \`deepseek-v4-flash\` 和 \`deepseek-v4-pro\`。默认测试配置使用 Flash 的非 thinking 模式，速度和成本更适合先验收链路。

先在当前 PowerShell 会话设置密钥：

\`$env:DEEPSEEK_API_KEY = "sk-你的密钥"\`

密钥不会写入 TOML、Git 或日志。使用仓库配置进行健康检查和一次对话：

\`\`\`powershell
cargo run -p ai-ex-service -- --config "config/ai-ex.deepseek.toml" --check
cargo run -p ai-ex-service -- --config "config/ai-ex.deepseek.toml" --prompt "你好，请用一句话确认 DeepSeek 已接入。"
\`\`\`

切换 Pro 或 thinking 模式，修改 \`config/ai-ex.deepseek.toml\`：

\`\`\`toml
model = "deepseek-v4-pro"
thinking = true
reasoning_effort = "high"
\`\`\`

\`reasoning_content\` 只用于内部推理，不会进入角色台词、TTS 或字幕；服务只转发 \`delta.content\`。

## KoboldCpp

启动 KoboldCpp，并确认它监听 \`http://127.0.0.1:5001\`。然后执行：

\`\`\`powershell
cargo run -p ai-ex-service -- --config "config/ai-ex.koboldcpp.toml" --check
cargo run -p ai-ex-service -- --config "config/ai-ex.koboldcpp.toml" --prompt "你好，请用一句话确认 KoboldCpp 已接入。"
\`\`\`

如果 KoboldCpp 使用其他端口，只修改配置中的 \`koboldcpp.base_url\`。服务使用 \`/api/v1/model\` 做健康检查，使用 \`/api/v1/generate\` 做 SSE 流式生成。

## Ollama 兼容

Ollama 适配仍然保留。使用原来的 \`model.backend = "ollama"\` 和 \`[ollama]\` 配置即可；没有安装 Ollama 不会影响 DeepSeek 或 KoboldCpp 配置的解析和构建。只要选择 Ollama，\`--check\` 才会检查 Ollama。

## 排错顺序

1. 先运行 \`--check\`，确认是配置错误、密钥错误还是外部服务未启动。
2. DeepSeek 返回 HTTP 401/403 时，检查当前 PowerShell 会话的 \`DEEPSEEK_API_KEY\`。
3. DeepSeek 返回 HTTP 404 时，检查 \`base_url\` 是否为 \`https://api.deepseek.com\`，不要把 \`/chat/completions\` 写进配置。
4. KoboldCpp unavailable 时，确认端口、模型已加载，并在浏览器或 \`Invoke-WebRequest\` 中确认服务可达。
5. 流式响应只显示文本增量；thinking 的内部内容不显示是设计行为。

官方参考：

- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/api/list-models
