# 开发约定

## Rust 格式

Rust 代码使用 `cargo fmt` 默认格式；独立桌面包通过其 Cargo 清单单独格式化。

## 架构边界

- `ai-ex-domain`：无 I/O 的领域类型与事件。
- `ai-ex-core`：状态机、业务编排和端口定义。
- `ai-ex-adapters`：Ollama、VTube Studio、音频和平台适配器。
- `ai-ex-service`：组合根和进程入口。

新功能不得直接耦合 UI、音频设备和网络调用；先定义核心端口，再在适配器实现。
