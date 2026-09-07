# 开发约定

## Rust 格式

Rust 代码使用 `cargo fmt` 默认格式；独立桌面包通过其 Cargo 清单单独格式化。

## 架构边界

- `ai-ex-domain`：无 I/O 的领域类型与事件。
- `ai-ex-core`：状态机、业务编排和端口定义。
- 适配器分别位于 `ai-ex-ollama`、`ai-ex-deepseek`、`ai-ex-koboldcpp`、`ai-ex-vts`、`ai-ex-audio` 等实际包中。
- `ai-ex-service`：组合根和进程入口。
- `ai-ex-desktop`：独立桌面客户端，通过本地控制协议调用服务，不直接依赖模型、设备或会话运行时。

新功能不得直接耦合 UI、音频设备和网络调用；先定义核心端口，再在适配器实现。

当前分层、数据流和扩展方式见 [架构说明](docs/ARCHITECTURE.md)。`tools/check_architecture.ps1` 同时检查 30 个核心包和独立桌面包；相对路径按脚本位置解析。
