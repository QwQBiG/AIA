# 全双工对话引擎 (full_duplex_engine/)

## 🎙️ 系统概述
全双工对话引擎是 AI VTuber 系统的实时语音交互核心，支持同时进行语音输入和输出，实现自然流畅的对话体验。系统采用模块化设计，支持语音识别、智能打断、延迟优化等高级功能。

## 🏗️ 架构设计
```
full_duplex_engine/
├── duplex_manager.py          # 全双工管理器 - 核心控制器
├── streaming_ears.py          # 流式语音识别 - 实时听取
├── audio_device_manager.py    # 音频设备管理 - 硬件控制
├── text_processor.py          # 文本处理器 - 语言理解
├── configuration_manager.py   # 配置管理器 - 设置持久化
├── latency_optimizer.py       # 延迟优化器 - 性能提升
├── system_health_monitor.py   # 系统健康监控 - 状态跟踪
├── performance_monitor.py     # 性能监控器 - 指标收集
├── threading_optimizer.py     # 线程优化器 - 并发管理
├── whisper_asr.py            # Whisper ASR - 语音识别
├── diagnostic_tools.py        # 诊断工具 - 问题排查
├── error_handler.py          # 错误处理器 - 异常管理
└── logging_config.py         # 日志配置 - 调试支持
```

## 🔧 核心组件详解

### DuplexManager (duplex_manager.py)
**功能**: 全双工对话的核心控制器
- 🎯 **流量控制**: 协调输入输出流，避免冲突
- 🔄 **状态管理**: 跟踪对话状态（听取、思考、回应）
- ⚡ **智能打断**: 检测用户打断并优雅处理
- 🎚️ **音量控制**: 动态调整输入输出音量
- 📊 **性能监控**: 实时监控系统性能指标

**核心方法**:
```python
# 启动全双工模式
await duplex_manager.start_duplex_mode()

# 处理用户语音检测
duplex_manager.on_user_speech_detected(confidence=0.9)

# 处理 AI 开始说话
duplex_manager.on_ai_speech_start()

# 优雅停止
await duplex_manager.stop_duplex_mode()
```

### StreamingEars (streaming_ears.py)
**功能**: 实时流式语音识别系统
- 🎤 **实时识别**: 持续监听和识别语音
- 📝 **流式输出**: 实时输出部分识别结果
- 🔍 **语音检测**: 智能检测语音开始和结束
- 🎯 **句子分割**: 自动识别句子边界
- 🔧 **噪音过滤**: 过滤背景噪音和干扰

**使用示例**:
```python
# 初始化流式识别
streaming_ears = StreamingEars(audio_device_manager)

# 设置回调函数
streaming_ears.set_callbacks(
    on_speech_start=handle_speech_start,
    on_partial_text=handle_partial_text,
    on_sentence_complete=handle_sentence_complete,
    on_speech_end=handle_speech_end
)

# 开始监听
await streaming_ears.start_streaming()
```

### AudioDeviceManager (audio_device_manager.py)
**功能**: 音频硬件设备管理
- 🎧 **设备检测**: 自动检测可用音频设备
- ⚙️ **设备配置**: 配置最佳音频参数
- 🔊 **音量控制**: 动态调整输入输出音量
- 📊 **设备监控**: 监控设备状态和性能
- 🔄 **热插拔支持**: 支持设备动态插拔

**设备管理**:
```python
# 获取可用设备
devices = audio_device_manager.get_available_devices()

# 设置输入设备
audio_device_manager.set_input_device(device_id)

# 设置输出设备
audio_device_manager.set_output_device(device_id)

# 调整音量
audio_device_manager.set_input_volume(0.8)
```

### TextProcessor (text_processor.py)
**功能**: 智能文本处理和理解
- ✂️ **句子分割**: 智能识别句子边界
- 🧹 **文本清理**: 清理识别错误和噪音
- 🎯 **意图识别**: 理解用户意图和情感
- 🔄 **上下文管理**: 维护对话上下文
- 📝 **文本规范化**: 标准化文本格式

**文本处理流程**:
```python
# 处理部分文本
processed = text_processor.process_partial_text(partial_text)

# 检测句子完成
is_complete = text_processor.is_sentence_complete(text)

# 清理最终文本
final_text = text_processor.clean_final_text(raw_text)
```

### ConfigurationManager (configuration_manager.py)
**功能**: 全双工引擎配置管理
- 💾 **配置持久化**: 保存用户配置到文件
- 🔄 **动态更新**: 运行时更新配置
- ✅ **配置验证**: 验证配置有效性
- 🎛️ **参数调优**: 自动优化性能参数
- 📊 **配置统计**: 跟踪配置使用情况

## 🚀 快速开始

### 1. 基础初始化
```python
from src.full_duplex_engine import (
    DuplexManager, StreamingEars, AudioDeviceManager,
    TextProcessor, ConfigurationManager
)

# 初始化组件
config_manager = ConfigurationManager()
audio_manager = AudioDeviceManager()
text_processor = TextProcessor()
streaming_ears = StreamingEars(audio_manager)
duplex_manager = DuplexManager()

# 连接组件
duplex_manager.set_streaming_ears(streaming_ears)
duplex_manager.set_text_processor(text_processor)
```

### 2. 启动全双工模式
```python
# 设置回调函数
def on_user_speech(text):
    print(f"用户说: {text}")
    # 处理用户输入...

def on_ai_response(text):
    print(f"AI回应: {text}")
    # 播放AI响应...

# 启动系统
await duplex_manager.start_duplex_mode()
```

### 3. 处理对话流程
```python
# 用户开始说话
duplex_manager.on_user_speech_detected(confidence=0.9)

# 接收部分识别结果
duplex_manager.on_partial_transcription("你好，我想...")

# 句子完成
duplex_manager.on_sentence_complete("你好，我想问一个问题。")

# AI开始回应
duplex_manager.on_ai_speech_start()

# 用户打断
duplex_manager.on_user_interruption()
```

## ⚙️ 配置参数

### 音频配置
```json
{
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "input_device": null,
    "output_device": null,
    "input_volume": 0.8,
    "output_volume": 0.7
  }
}
```

### 语音识别配置
```json
{
  "speech_recognition": {
    "model": "whisper-base",
    "language": "zh",
    "vad_threshold": 0.5,
    "silence_timeout": 2.0,
    "partial_results": true,
    "continuous_mode": true
  }
}
```

### 全双工配置
```json
{
  "duplex": {
    "interruption_enabled": true,
    "interruption_threshold": 0.7,
    "response_delay": 0.5,
    "overlap_handling": "graceful",
    "priority_mode": "user_first"
  }
}
```

## 🎯 高级功能

### 智能打断处理
```python
# 配置打断策略
duplex_manager.configure_interruption(
    enabled=True,
    threshold=0.7,
    grace_period=0.5,
    strategy="graceful"  # 或 "immediate"
)

# 处理打断事件
def handle_interruption(context):
    if context.confidence > 0.8:
        # 立即停止AI说话
        duplex_manager.stop_ai_speech()
    else:
        # 等待确认
        duplex_manager.wait_for_confirmation()
```

### 延迟优化
```python
from src.full_duplex_engine.latency_optimizer import get_latency_optimizer

# 获取延迟优化器
optimizer = get_latency_optimizer()

# 注册组件
optimizer.register_components(
    streaming_ears=streaming_ears,
    duplex_manager=duplex_manager,
    text_processor=text_processor
)

# 开始优化
optimizer.start_optimization(interval=10.0)
```

### 性能监控
```python
from src.full_duplex_engine.performance_monitor import PerformanceMonitor

# 创建性能监控器
monitor = PerformanceMonitor()

# 开始监控
monitor.start_monitoring()

# 获取性能报告
report = monitor.get_performance_report()
print(f"平均延迟: {report.average_latency}ms")
print(f"CPU使用率: {report.cpu_usage}%")
```

## 🔍 调试和诊断

### 诊断工具
```python
from src.full_duplex_engine.diagnostic_tools import DiagnosticTools

# 创建诊断工具
diagnostics = DiagnosticTools()

# 运行系统诊断
results = diagnostics.run_full_diagnostic()

# 检查音频设备
audio_status = diagnostics.check_audio_devices()

# 测试语音识别
recognition_test = diagnostics.test_speech_recognition()
```

### 日志配置
```python
from src.full_duplex_engine.logging_config import setup_logging

# 设置详细日志
setup_logging(
    level="DEBUG",
    file_path="logs/full_duplex_engine.log",
    console_output=True
)
```

## 📊 性能指标

### 关键指标
- **端到端延迟**: < 500ms
- **语音识别准确率**: > 95%
- **打断响应时间**: < 200ms
- **CPU使用率**: < 30%
- **内存使用**: < 512MB

### 监控面板
```python
# 获取实时指标
metrics = duplex_manager.get_real_time_metrics()
print(f"当前延迟: {metrics.current_latency}ms")
print(f"识别准确率: {metrics.recognition_accuracy}%")
print(f"打断次数: {metrics.interruption_count}")
```

## 🛠️ 故障排除

### 常见问题
1. **音频设备未找到**
   ```python
   # 刷新设备列表
   audio_manager.refresh_devices()
   
   # 使用默认设备
   audio_manager.use_default_devices()
   ```

2. **语音识别延迟高**
   ```python
   # 优化识别参数
   streaming_ears.optimize_for_latency()
   
   # 调整缓冲区大小
   streaming_ears.set_buffer_size(512)
   ```

3. **打断功能不工作**
   ```python
   # 检查打断配置
   status = duplex_manager.check_interruption_status()
   
   # 重新校准阈值
   duplex_manager.calibrate_interruption_threshold()
   ```

### 错误恢复
```python
# 自动错误恢复
duplex_manager.enable_auto_recovery(
    max_retries=3,
    recovery_delay=1.0,
    fallback_mode=True
)

# 手动重置系统
await duplex_manager.reset_system()
```

## 📚 相关文档
- [用户指南](../../docs/full_duplex_user_guide.md)
- [API参考](./api_reference.md)
- [性能调优指南](./performance_tuning.md)
- [故障排除手册](./troubleshooting.md)