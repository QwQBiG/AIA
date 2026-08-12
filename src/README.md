# 源代码目录 (src/)

## 📁 目录概述
本目录包含 AI VTuber 系统的所有核心源代码模块，采用模块化设计，每个文件负责特定功能。

## 🏗️ 架构设计
```
src/
├── 🎮 核心系统
│   ├── main.py              # 主程序入口
│   ├── config.py            # 配置管理系统
│   ├── system_workflow.py   # 系统工作流控制器
│   └── error_handler.py     # 全局错误处理器
│
├── 🖥️ 用户界面
│   ├── gui_controller.py    # 主界面控制器
│   ├── subtitle_window.py   # 字幕窗口
│   ├── pink_theme.py        # 粉色主题配置
│   └── tooltip.py           # 工具提示系统
│
├── 🤖 AI 核心
│   ├── llm_client.py        # 基础 LLM 客户端
│   ├── enhanced_llm_client.py # 增强 LLM 客户端
│   └── memory_core/         # 记忆核心系统
│
├── 🎤 语音系统
│   ├── tts_pipeline.py      # TTS 管道
│   ├── tts_player.py        # TTS 播放器
│   ├── text_cleaner.py      # 文本清理器
│   └── full_duplex_engine/  # 全双工对话引擎
│
├── 🎭 虚拟形象
│   ├── vts_client.py        # VTube Studio 客户端
│   └── stream_processor.py  # 流处理器
│
├── 🎯 智能代理
│   ├── agent_manager.py     # 代理管理器
│   ├── action_engine.py     # 动作执行引擎
│   ├── vision_client.py     # 视觉客户端
│   ├── safety_manager.py    # 安全管理器
│   └── reflex_engine.py     # 反射引擎
│
└── 🛠️ 工具模块
    ├── performance_monitor.py # 性能监控
    ├── warmup_manager.py     # 预热管理器
    ├── health_check.py       # 健康检查
    └── network_config.py     # 网络配置
```

## 🔧 核心模块详解

### 系统控制层
- **main.py**: 应用程序主入口，负责系统初始化和生命周期管理
- **config.py**: 统一配置管理，支持动态配置加载和验证
- **system_workflow.py**: 核心工作流控制器，协调各模块间的交互
- **error_handler.py**: 全局异常处理和错误恢复机制

### 用户界面层
- **gui_controller.py**: 主界面控制器，提供完整的用户交互界面
- **subtitle_window.py**: 实时字幕显示窗口，支持多种显示模式
- **pink_theme.py**: 统一的粉色主题配置，提供一致的视觉体验
- **tooltip.py**: 智能工具提示系统，提供上下文帮助

### AI 智能层
- **llm_client.py**: 基础大语言模型客户端，支持 Ollama 接口
- **enhanced_llm_client.py**: 增强版 LLM 客户端，集成记忆和上下文管理
- **memory_core/**: 记忆核心系统，提供长期记忆和知识检索

### 语音处理层
- **tts_pipeline.py**: TTS 处理管道，支持多种语音合成引擎
- **tts_player.py**: 音频播放器，负责音频文件的播放和管理
- **text_cleaner.py**: 智能文本清理器，优化 TTS 输入质量
- **full_duplex_engine/**: 全双工对话引擎，支持实时语音交互

### 虚拟形象层
- **vts_client.py**: VTube Studio 集成客户端，控制虚拟形象动画
- **stream_processor.py**: 流媒体处理器，优化实时性能

### 智能代理层
- **agent_manager.py**: 智能代理管理器，协调自动化任务
- **action_engine.py**: 动作执行引擎，处理用户界面操作
- **vision_client.py**: 计算机视觉客户端，提供屏幕理解能力
- **safety_manager.py**: 安全管理器，提供紧急停止和安全保护
- **reflex_engine.py**: 反射引擎，实现快速响应机制

### 工具支持层
- **performance_monitor.py**: 系统性能监控，实时跟踪资源使用
- **warmup_manager.py**: 系统预热管理器，减少首次响应延迟
- **health_check.py**: 健康检查工具，监控系统状态
- **network_config.py**: 网络配置管理，优化网络连接

## 🚀 快速开始

### 1. 导入核心模块
```python
from src.config import SystemConfig, load_config
from src.gui_controller import ImprovedGUIController
from src.system_workflow import SystemWorkflow
```

### 2. 初始化系统
```python
# 加载配置
config = load_config("config.json")

# 创建GUI控制器
gui = ImprovedGUIController(config)
gui.setup_ui()

# 启动系统
gui.run()
```

## 📋 开发规范

### 代码风格
- 使用中文注释，简洁明了
- 遵循 PEP 8 编码规范
- 类名使用 PascalCase
- 函数名使用 snake_case
- 常量使用 UPPER_CASE

### 错误处理
- 所有公共方法必须包含异常处理
- 使用 logging 模块记录错误信息
- 提供有意义的错误消息

### 性能优化
- 使用异步编程处理 I/O 操作
- 实现资源池化和缓存机制
- 避免阻塞主线程

## 🔍 调试指南

### 日志系统
- 日志文件位置: `logs/ai_vtuber.log`
- 代理活动日志: `logs/agent_activity.log`
- 全双工引擎日志: `logs/full_duplex_engine_*.log`

### 常见问题
1. **连接问题**: 检查 Ollama 和 VTube Studio 是否运行
2. **性能问题**: 查看性能监控日志，调整配置参数
3. **内存问题**: 使用内存管理器清理缓存

## 🧪 测试
- 单元测试位于 `tests/` 目录
- 运行测试: `python -m pytest tests/`
- 集成测试: `python test_critical_fixes.py`

## 📚 相关文档
- [配置指南](../docs/setup_guide.md)
- [用户手册](../docs/ai_vtuber_user_guide_zh.md)
- [全双工引擎文档](../docs/full_duplex_user_guide.md)