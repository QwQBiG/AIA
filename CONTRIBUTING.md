# 开发约定

## Rust 格式

本项目新增 Rust 代码使用 Allman 大括号风格：控制语句、函数、`impl`、`match` 分支和结构体均将左花括号放在独立行。例如：

```rust
if is_ready()
{
    start();
}
else
{
    recover();
}
```

不要在未确认该规则保持不变前运行会自动改变花括号位置的格式化命令。

## 架构边界

- `ai-ex-domain`：无 I/O 的领域类型与事件。
- `ai-ex-core`：状态机、业务编排和端口定义。
- `ai-ex-adapters`：Ollama、VTube Studio、音频和平台适配器。
- `ai-ex-service`：组合根和进程入口。

新功能不得直接耦合 UI、音频设备和网络调用；先定义核心端口，再在适配器实现。

