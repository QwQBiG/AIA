# AIex 桌面端快速使用

AIex 提供两种入口：普通用户使用可视化首次设置向导；开发者可以继续使用命令行、配置文件和终端日志。桌面端只通过本地 control 协议连接 `ai-ex-service`，不会直接持有模型、VTS 或音频对象。

| 使用方式 | 入口 | 能看到什么 |
| --- | --- | --- |
| 普通用户 | 直接启动桌面端 | 向导、连接状态、对话、模型/VTS/TTS 健康、急停 |
| 开发者 | 点击右上角“开发者诊断”（可选 `--developer` 默认展开） | 桌面事件日志、控制协议错误、服务完整 stdout/stderr |

## 小白模式：一条命令完成初始化

在仓库根目录执行：

```powershell
cargo run --manifest-path "crates/ai-ex-desktop/Cargo.toml"
```

当配置文件或控制令牌不存在时，AIex 会自动打开“首次设置”窗口：

1. 选择 DeepSeek、KoboldCpp 或 Ollama。
2. 确认模型地址和模型名称。
3. DeepSeek 粘贴 API Key（密钥只在本次进程中使用，不写入配置文件），或提前设置 `DEEPSEEK_API_KEY`。
4. 可选勾选 Bilibili 直播事件，填写房间号和 Cookie 环境变量名（只填变量名，不粘贴 Cookie）。
5. 填写角色名称，点击“保存并进入 AIex”。
6. 点击“检查连接”可提前检查地址和本地服务端口；HTTP 本地服务会读取状态码，HTTPS 云服务先检查网络端口，完整 API 鉴权由服务启动时再次验证。

向导会自动创建 `config/ai-ex.local.toml` 和 `config/control.token`。
连通性检查不会保存 API Key；向导生成的配置只保存环境变量名，密钥仍通过当前进程或环境变量传递。勾选“保存后自动启动服务”时，桌面端会优先启动旁边的 `ai-ex-service.exe`；开发环境没有该文件时，会自动回退到 `cargo run -p ai-ex-service`。服务日志会继续显示在启动桌面的同一个终端中。

## 普通用户界面

主窗口会显示连接状态、模型/VTS/TTS 健康状态（实时刷新）、对话流、事件回放、打断和急停。
Provider 健康详情会区分鉴权失败、接口地址不存在、请求受限、服务端故障、超时和无法连接；看到这些文字时，优先按提示检查 API Key、模型地址、模型进程或网络。
如果服务提供标准模型清单，健康状态还会检查配置模型：Ollama 会提示是否需要 `ollama pull`，DeepSeek 会提示模型名称或账户权限问题；非标准兼容服务会显示“未能验证模型”，不会直接假装模型可用。服务重启后桌面端会自动重连；检测到事件序号缺口时会请求状态重同步。
连接保持后，桌面端每约 2 秒同步事件，并每约 2 秒刷新一次组件健康状态；模型服务在桌面启动后才启动或停止时，健康面板也会更新。急停状态优先保留，不会因为重连显示“假连接”。
Bilibili 事件会在开发者日志中显示“已接受”和“反应建议”。向导生成的配置默认不自动反应；需要高级测试时再手动设置 `bilibili.response_mode = "automatic"`（旧配置也可用 `auto_react = true`），并保留急停和冷却限制。
角色设置面板位于新手控制台下方：可编辑档案 ID、版本、名称、语气、系统提示词、禁忌和直播模式。点击“预览并请求确认”后会进入人工确认队列，确认窗口展示档案版本；只有确认后才发送 `set_persona`，服务拒绝或活动回合冲突时不会替换当前角色。外部命令行切换会通过事件流同步回桌面端。
开发者诊断会记录角色草稿、确认、应用结果、版本变化和失败原因；需要原始细节时，同时查看启动服务的终端输出。

## 开发者模式：可视化日志 + 终端原始日志

需要分析控制协议或排查问题时执行：

```powershell
cargo run --manifest-path "crates/ai-ex-desktop/Cargo.toml" -- --developer
```

桌面默认先显示新手控制台：连接状态、组件就绪数、对话输入、打断和急停都不需要命令行。点击右上角“开发者诊断”即可展开桌面端收到的连接变化、健康快照、事件数量、控制命令和失败信息；启动终端仍保留 `ai-ex-service` 的完整 stdout/stderr。`--developer` 只用于让诊断面板启动时自动展开，两者结合可以同时满足“看得懂”和“查得深”。

Developer stage replay is available with --replay-stage PATH; the service validates version, sequence, and action capability before printing replay logs.
示例回放文件位于 `config_examples/stage-replay.jsonl`，可执行：

```powershell
cargo run -p ai-ex-service -- --config config/ai-ex.example.toml --replay-stage config_examples/stage-replay.jsonl
```

开发者诊断下的“舞台/OBS 动作遥测”面板会显示服务最近的舞台动作摘要（schema、序号、类型和受限 detail），包括语音、字幕、口型、表情、Stop 等；它是只读观察，不会因为查看而触发 OBS。

视觉/游戏 dry-run 回放：

```powershell
cargo run -p ai-ex-service -- --config config/ai-ex.example.toml --replay-automation config_examples/automation-replay.jsonl
```

该命令只记录动作并生成确定性屏幕帧，不会移动真实鼠标或启动进程；每个动作仍会写入 `logs/automation-audit.jsonl`。

也可以显式指定配置：

```powershell
cargo run --manifest-path "crates/ai-ex-desktop/Cargo.toml" -- --config config/ai-ex.local.toml --developer
```

## 高级命令行流程

需要完全控制进程和配置时，仍可手动执行：

```powershell
pwsh -NoProfile -File tools/create_control_token.ps1
$env:DEEPSEEK_API_KEY = "sk-你的密钥"
cargo run -p ai-ex-service -- --config config/ai-ex.desktop.example.toml
cargo run --manifest-path "crates/ai-ex-desktop/Cargo.toml" -- --config config/ai-ex.desktop.example.toml
```

也可以复制 `config/ai-ex.desktop.example.toml` 后修改模型或地址。配置中的 `token_path`、`bind` 和桌面端参数必须一致。令牌文件只存在于本机，不要提交到 Git；需要轮换时显式使用 `-Force`。

## 启动前检查

服务可先执行离线配置和组件检查：

```powershell
cargo run -p ai-ex-service -- --config config/ai-ex.desktop.example.toml --check
```

DeepSeek 未配置时会明确报告 `DEEPSEEK_API_KEY` 缺失；VTS、TTS 和记忆在样例中默认关闭，因此不要求安装这些外部服务。
