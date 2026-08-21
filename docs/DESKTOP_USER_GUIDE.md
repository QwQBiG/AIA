# AIex 桌面端快速使用

Phase 1 的桌面端只通过本地 control 协议连接 `ai-ex-service`，不会直接持有模型、VTS 或音频对象。默认样例使用 DeepSeek；没有 Ollama 也可以运行。

## 初始化控制令牌

在仓库根目录执行：

```powershell
pwsh -NoProfile -File tools/create_control_token.ps1
```

令牌文件 `config/control.token` 只存在于本机，不要提交到 Git。需要轮换时显式使用 `-Force`。

## 配置 API Key

```powershell
$env:DEEPSEEK_API_KEY = "sk-你的密钥"
```

也可以复制 `config/ai-ex.desktop.example.toml` 后修改模型或地址。配置中的 `token_path`、`bind` 和桌面端参数必须一致。

## 启动服务和桌面端

先启动服务：

```powershell
cargo run -p ai-ex-service -- --config config/ai-ex.desktop.example.toml
```

再打开另一个终端启动桌面端：

```powershell
cargo run --manifest-path "crates/ai-ex-desktop/Cargo.toml" -- --config config/ai-ex.desktop.example.toml
```

桌面端提供连接状态、模型/VTS/TTS 等组件健康快照、对话流、事件回放、打断和急停。事件序号出现缺口时，服务重连会重新同步状态。

## 启动前检查

服务可先执行离线配置和组件检查：

```powershell
cargo run -p ai-ex-service -- --config config/ai-ex.desktop.example.toml --check
```

DeepSeek 未配置时会明确报告 `DEEPSEEK_API_KEY` 缺失；VTS、TTS 和记忆在样例中默认关闭，因此不要求安装这些外部服务。
