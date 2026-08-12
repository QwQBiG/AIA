# 🎭 AI VTuber 智能控制中心 - 完整安装配置指南

本指南将帮助您安装和配置 AI VTuber 智能控制中心，包括语音克隆、表情控制、智能内存系统和 Agent 模式等完整功能。

## 📖 目录

1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
3. [核心服务配置](#核心服务配置)
4. [功能模块设置](#功能模块设置)
5. [GUI界面说明](#gui界面说明)
6. [测试验证](#测试验证)
7. [故障排除](#故障排除)
8. [性能优化](#性能优化)
9. [高级配置](#高级配置)

## 🖥️ 系统要求

### 最低配置
- **操作系统**: Windows 10/11 (64位)
- **CPU**: Intel i5-8400 / AMD Ryzen 5 2600 或同等性能
- **内存**: 8GB RAM (推荐 16GB)
- **存储**: 10GB 可用空间 (SSD 推荐)
- **Python**: 3.9-3.11 (推荐 3.11)

### 推荐配置
- **CPU**: Intel i7-10700K / AMD Ryzen 7 3700X 或更高
- **内存**: 16GB+ RAM (32GB 用于大型语音模型)
- **GPU**: NVIDIA GTX 1060 / RTX 2060 或更高 (GPT-SoVITS)
- **存储**: SSD 20GB+ 可用空间

### 必需软件
- **Python 3.9-3.11**
- **Ollama** (LLM 服务)
- **VTube Studio** (Live2D 动画)

### 可选组件
- **GPT-SoVITS** (高质量语音克隆)
- **专业音频设备** (全双工模式)

## 🚀 安装步骤

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd ai-vtuber-system

# 创建虚拟环境 (推荐)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -r requirements.txt
```

### 2. 验证安装

```bash
# 检查 Python 版本
python --version

# 验证基础安装
python main.py --help

# 运行系统诊断
python tools/run_diagnostics.py
```

## 🔧 核心服务配置

### Ollama 设置

```bash
# 1. 安装 Ollama
# 从 https://ollama.ai 下载并安装

# 2. 启动服务
ollama serve

# 3. 下载模型 (新终端)
ollama pull llama3

# 4. 验证连接
curl http://localhost:11434/api/tags
```

### VTube Studio 配置

1. **安装 VTube Studio**
   - 从 Steam 或官网下载安装
   - 加载您的 Live2D 模型

2. **启用 API 访问**
   - 设置 → 通用 → 允许外部应用控制
   - 记录端口号 (默认: 8001)

3. **配置表情热键**
   ```
   F1: 开心表情
   F2: 惊讶表情
   F3: 生气表情
   F4: 悲伤表情
   F5: 中性表情
   ```

### GPT-SoVITS 设置 (可选)

#### Docker 方式 (推荐)
```bash
# 拉取镜像
docker pull breakstring/gpt-sovits:latest

# 运行容器
docker run -d -p 9880:9880 --name gpt-sovits breakstring/gpt-sovits:latest
```

#### 手动安装
```bash
# 克隆项目
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS

# 安装依赖
pip install -r requirements.txt

# 启动 WebUI
python webui.py
```

## 🎯 功能模块设置

### 智能内存系统

系统已内置 ChromaDB 驱动的智能内存系统：

```bash
# 初始化内存系统
python scripts/setup_memory_system.py

# 验证内存配置
python scripts/validate_memory_config.py

# 创建内存备份
python scripts/migrate_memory_database.py --backup
```

### Agent 模式配置

Agent 模式提供视觉分析和自动操作能力：

1. **确保权限设置**
   - Windows: 允许应用控制其他应用
   - 调整 DPI 缩放设置

2. **校准坐标系统**
   - 使用 Agent Debugger 测试中心点击
   - 调整 DPI 缩放因子

### 全双工对话模式

支持实时语音识别和打断：

1. **音频设备要求**
   - 推荐使用耳机避免回音
   - 确保麦克风权限

2. **硬件兼容性检查**
   - 系统会自动检测音频设备
   - 显示兼容性警告和建议

## 🖥️ GUI界面说明

### 改进的界面特点

系统提供两种 GUI 界面：

#### 改进版界面 (推荐)
```bash
# 切换到改进界面
python switch_gui.py improved
```

**特点**:
- 🎯 **5个主要标签页**: 基础功能、性能优化、高级功能、Agent模式、系统管理
- 💡 **完整工具提示**: 鼠标悬停查看详细说明
- 🎨 **现代化设计**: 深色主题，粉色强调色
- ⚡ **响应式布局**: 适配不同屏幕尺寸

#### 原始界面
```bash
# 切换回原始界面
python switch_gui.py original
```

### 界面布局说明

#### 1. 🎯 基础功能
- **语音合成设置**: GPT-SoVITS 开关
- **表情控制设置**: 情感智能、Live2D 控制
- **用户体验设置**: 字幕显示、全双工模式

#### 2. ⚡ 性能优化
- **响应速度优化**: 流式响应、分句处理、激进分句
- **交互体验优化**: 用户打断、音频缓存
- **系统优化**: 预热加载、文本清洗

#### 3. 🔬 高级功能
- **智能内存系统**: 内存管理器、统计、备份
- **音频系统设置**: 设备配置、测试、诊断
- **AI模型管理**: 模型管理、状态监控、优化

#### 4. 🤖 Agent模式
- **Agent控制中心**: 启动/停止、状态监控
- **运行参数**: 循环间隔、冷却时间
- **调试工具**: Debugger、性能监控、日志

#### 5. 🔧 系统管理
- **系统信息**: 版本信息、功能状态、连接状态
- **系统诊断**: 健康检查、网络测试、性能统计

## ✅ 测试验证

### 1. 基础功能测试

```bash
# 启动系统
python main.py

# 在GUI中测试：
# 1. 输入消息并发送
# 2. 验证 LLM 响应
# 3. 检查音频播放
# 4. 观察表情变化
```

### 2. 情感智能测试

测试不同情感的消息：
- **开心**: "我今天心情特别好！"
- **悲伤**: "我感到很沮丧..."
- **生气**: "这太让人生气了！"
- **惊讶**: "哇，真是太神奇了！"

验证：
- ✅ 触发正确的表情
- ✅ 语音匹配情感 (GPT-SoVITS)
- ✅ 时序同步正确

### 3. 系统诊断

```bash
# 运行完整诊断
python tools/run_diagnostics.py

# 检查特定组件
python tools/validate_config.py --test-ollama
python tools/validate_config.py --test-sovits
python tools/validate_config.py --test-vts
```

### 4. 性能测试

```bash
# 性能基准测试
python tools/measure_performance.py

# 查看性能报告
cat tools/performance_report.md
```

## 🔧 故障排除

### 常见问题

#### 应用启动失败

**症状**: Python 错误，NumPy 警告

**解决方案**:
```bash
# 更新 NumPy 和 OpenCV
pip install numpy==2.1.3 opencv-python==4.13.0.90

# 检查 Python 版本兼容性
python --version  # 应该是 3.9-3.11
```

#### 服务连接失败

**症状**: GUI 显示服务未连接

**解决方案**:
1. **Ollama 连接问题**:
   ```bash
   # 检查 Ollama 状态
   ollama list
   curl http://localhost:11434/api/tags
   
   # 重启 Ollama
   ollama serve
   ```

2. **VTube Studio 连接问题**:
   - 确保 VTube Studio 运行
   - 检查 API 设置已启用
   - 重新认证 API 连接

3. **GPT-SoVITS 连接问题**:
   ```bash
   # 检查服务状态
   curl http://localhost:9880/
   
   # 重启服务
   docker restart gpt-sovits
   ```

#### 音频播放问题

**症状**: 无音频输出或音频异常

**解决方案**:
1. **检查音频设备**:
   - 使用 GUI 中的音频设置
   - 运行音频诊断工具

2. **测试 Edge-TTS**:
   ```bash
   edge-tts --text "测试" --voice zh-CN-XiaoxiaoNeural --write-media test.mp3
   ```

3. **检查音频权限**:
   - Windows: 确保应用有音频权限
   - 检查音频设备驱动

#### Agent 模式问题

**症状**: 坐标不准确或操作失败

**解决方案**:
1. **使用 Agent Debugger**:
   - 打开调试器测试坐标
   - 调整 DPI 缩放因子
   - 验证点击精度

2. **检查权限设置**:
   - Windows UAC 设置
   - 应用控制权限

### 性能问题

#### 响应速度慢

**解决方案**:
1. **启用性能优化**:
   - 流式响应
   - 分句处理
   - 激进分句模式

2. **系统优化**:
   - 启用预热加载
   - 使用音频缓存
   - 调整超时设置

#### 内存使用过高

**解决方案**:
1. **监控内存使用**:
   - 使用系统诊断工具
   - 定期清理内存数据

2. **优化配置**:
   - 使用较小的 LLM 模型
   - 禁用不需要的功能
   - 定期重启服务

## ⚡ 性能优化

### 推荐配置

#### 实时流媒体优化
```json
{
  "performance": {
    "enable_streaming": true,
    "enable_sentence_chunking": true,
    "enable_interruption": true,
    "warmup_enabled": true
  },
  "ux": {
    "aggressive_split": true,
    "enable_cache": true,
    "remove_emoji": true
  }
}
```

#### 高质量语音优化
```json
{
  "enable_voice_cloning": true,
  "sovits_timeout": 15.0,
  "fallback_to_edge_tts": false
}
```

#### 低资源系统优化
```json
{
  "enable_voice_cloning": false,
  "enable_expression_control": true,
  "log_level": "ERROR"
}
```

### 监控和调优

1. **使用性能统计**:
   - GUI 中查看性能指标
   - 分析响应时间趋势

2. **系统监控**:
   ```bash
   # Windows
   tasklist /fi "imagename eq python.exe"
   
   # 性能计数器
   python tools/measure_performance.py
   ```

3. **日志分析**:
   ```bash
   # 查看性能日志
   tail -f logs/performance_*.log
   
   # 分析错误模式
   grep -i error logs/ai_vtuber.log
   ```

## 🔬 高级配置

### 自定义系统提示词

修改 AI 角色个性：

```python
# 在 src/llm_client.py 中自定义
SYSTEM_PROMPT = """
你是一个名叫小艾的 AI VTuber。你聪明、友善，充满好奇心。

响应格式要求：
{
  "emotion": "neutral, happy, angry, sad, surprised 中的一个",
  "text": "你的自然对话内容"
}
"""
```

### 多语音模型配置

为不同情感配置不同声音：

```json
{
  "voice_models": {
    "happy": "http://localhost:9880/model1",
    "sad": "http://localhost:9881/model2",
    "default": "http://localhost:9880"
  }
}
```

### 复杂表情控制

使用组合热键：

```json
{
  "emotion_hotkey_map": {
    "neutral": "F5",
    "happy": "Ctrl+F1",
    "very_happy": "Shift+F1",
    "angry": "Ctrl+F2",
    "very_angry": "Shift+F2"
  }
}
```

### 外部服务集成

配置 Webhook 或 API 集成：

```json
{
  "webhooks": {
    "on_emotion_change": "http://localhost:3000/emotion",
    "on_speech_start": "http://localhost:3000/speech"
  }
}
```

## 📞 获取帮助

### 支持资源

- **配置示例**: `config_examples/`
- **验证工具**: `tools/`
- **日志文件**: `logs/`
- **文档**: `docs/`
- **用户指南**: `docs/ai_vtuber_user_guide_zh.md`

### 常见日志消息

- **INFO**: 正常操作信息
- **WARNING**: 非关键问题，系统继续运行
- **ERROR**: 组件故障，启用备用方案
- **SUCCESS**: 操作成功完成
- **SYSTEM**: 重要系统事件

### 调试技巧

1. **启用详细日志**:
   ```json
   {
     "log_level": "DEBUG"
   }
   ```

2. **使用诊断工具**:
   ```bash
   python tools/run_diagnostics.py
   ```

3. **分步测试**:
   - 单独测试每个组件
   - 逐步启用功能
   - 监控系统资源

记住定期更新系统和依赖项以获得最佳性能和最新功能！

---

*本指南涵盖了 AI VTuber 智能控制中心的完整安装和配置过程。如需更多帮助，请查看用户指南或使用系统内置的诊断工具。*

## Prerequisites

Before starting, ensure you have:

- **Python 3.8+** installed
- **Ollama** running with a compatible model
- **VTube Studio** installed and running
- **Live2D model** loaded in VTube Studio
- **Basic understanding** of JSON configuration files

### Optional Components
- **GPT-SoVITS** for voice cloning (recommended)
- **Audio output device** for TTS playback
- **Microphone** for voice input (if using voice input features)

## System Requirements

### Minimum Requirements
- **CPU**: Intel i5-8400 / AMD Ryzen 5 2600 or equivalent
- **RAM**: 8GB (16GB recommended with GPT-SoVITS)
- **Storage**: 2GB free space (10GB+ for GPT-SoVITS models)
- **OS**: Windows 10/11, macOS 10.15+, or Linux Ubuntu 18.04+

### Recommended Requirements
- **CPU**: Intel i7-10700K / AMD Ryzen 7 3700X or better
- **RAM**: 16GB+ (32GB for large voice models)
- **GPU**: NVIDIA GTX 1060 / RTX 2060 or better (for GPT-SoVITS)
- **Storage**: SSD with 20GB+ free space

## Installation Steps

### 1. Clone and Setup Base System

```bash
# Clone the repository
git clone <repository-url>
cd ai-vtuber-system

# Install Python dependencies
pip install -r requirements.txt

# Verify base installation
python main.py --help
```

### 2. Configure Ollama

```bash
# Start Ollama service
ollama serve

# Pull a compatible model (in another terminal)
ollama pull llama3

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 3. Setup VTube Studio

1. **Install VTube Studio** from Steam or official website
2. **Load your Live2D model**
3. **Enable API access**:
   - Go to Settings → General
   - Enable "Allow external applications to control VTube Studio"
   - Note the port number (default: 8001)

## GPT-SoVITS Setup

GPT-SoVITS provides high-quality voice cloning capabilities.

### Installation

#### Option 1: Docker (Recommended)
```bash
# Pull GPT-SoVITS Docker image
docker pull breakstring/gpt-sovits:latest

# Run GPT-SoVITS container
docker run -d -p 9880:9880 --name gpt-sovits breakstring/gpt-sovits:latest
```

#### Option 2: Manual Installation
```bash
# Clone GPT-SoVITS repository
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS

# Install dependencies
pip install -r requirements.txt

# Download pre-trained models
python download_models.py

# Start the web interface
python webui.py
```

### Configuration

1. **Access GPT-SoVITS WebUI** at `http://localhost:9880`
2. **Upload reference audio** (3-10 seconds of target voice)
3. **Enter reference text** (what the reference audio says)
4. **Test synthesis** with sample text
5. **Verify API endpoint** is accessible at `http://localhost:9880`

### Voice Model Training (Optional)

For best results, train a custom voice model:

1. **Prepare training data**:
   - 10-30 minutes of clean audio
   - Corresponding text transcriptions
   - Consistent audio quality and speaker

2. **Train the model**:
   - Use GPT-SoVITS training interface
   - Follow the training guide in GPT-SoVITS documentation
   - Training takes 2-6 hours depending on data size

3. **Load trained model**:
   - Load your trained model in the WebUI
   - Test with various text samples
   - Adjust parameters for optimal quality

## VTube Studio Configuration

### Setting Up Hotkeys

1. **Open VTube Studio**
2. **Go to Settings → Hotkeys**
3. **Create hotkeys for expressions**:
   - F1: Happy expression
   - F2: Surprised expression  
   - F3: Angry expression
   - F4: Sad expression
   - F5: Neutral expression

4. **Test hotkeys manually** to ensure they work

### Expression Setup

1. **Load your Live2D model**
2. **Configure expressions**:
   - Ensure each emotion has a distinct expression
   - Test expression transitions
   - Adjust expression parameters if needed

3. **Note available hotkeys**:
   ```bash
   # Use the hotkey discovery tool
   python tools/list_vts_hotkeys.py
   ```

### API Token Setup

1. **First run will prompt for API access**
2. **Allow the connection** in VTube Studio
3. **Token will be saved** to `token.json`
4. **Verify connection**:
   ```bash
   python tools/validate_config.py
   ```

## System Configuration

### 1. Choose Configuration Template

Select a configuration template from `config_examples/`:

```bash
# For full features
cp config_examples/emotional_intelligence_config.json config.json

# For voice cloning only
cp config_examples/voice_cloning_only_config.json config.json

# For expressions only  
cp config_examples/expression_only_config.json config.json
```

### 2. Update Configuration

Edit `config.json` with your specific settings:

```json
{
  "ollama_url": "http://localhost:11434",
  "ollama_model": "llama3",
  "tts_voice": "zh-CN-XiaoxiaoNeural",
  "vts_port": 8001,
  "enable_emotional_intelligence": true,
  "enable_voice_cloning": true,
  "enable_expression_control": true,
  "sovits_url": "http://127.0.0.1:9880",
  "emotion_hotkey_map": {
    "neutral": "F5",
    "happy": "F1", 
    "angry": "F3",
    "sad": "F4",
    "surprised": "F2"
  }
}
```

### 3. Validate Configuration

```bash
# Validate your configuration
python tools/validate_config.py config.json

# Test individual components
python tools/validate_config.py --test-ollama
python tools/validate_config.py --test-sovits
python tools/validate_config.py --test-vts
```

## Testing Your Setup

### 1. Basic Functionality Test

```bash
# Start the system
python main.py

# Test basic conversation
# Type a message and verify:
# - LLM responds appropriately
# - Audio is generated and played
# - VTube Studio model animates
```

### 2. Emotional Intelligence Test

Test emotional responses:

1. **Happy message**: "I'm so excited about this!"
2. **Sad message**: "I'm feeling really down today."
3. **Angry message**: "This is so frustrating!"
4. **Surprised message**: "Wow, I can't believe it!"

Verify:
- ✅ Appropriate expressions are triggered
- ✅ Voice matches the emotion (if using GPT-SoVITS)
- ✅ Timing is synchronized

### 3. Fallback Testing

Test fallback mechanisms:

1. **Stop GPT-SoVITS** and verify Edge-TTS fallback
2. **Disconnect VTube Studio** and verify audio continues
3. **Use invalid hotkeys** and verify graceful handling

## Troubleshooting

### Common Issues

#### GPT-SoVITS Not Working

**Symptoms**: Audio falls back to Edge-TTS immediately

**Solutions**:
1. **Check GPT-SoVITS is running**:
   ```bash
   curl http://localhost:9880/
   ```

2. **Verify model is loaded** in GPT-SoVITS WebUI

3. **Check firewall settings** - ensure port 9880 is accessible

4. **Review logs** for connection errors:
   ```bash
   tail -f logs/ai_vtuber.log | grep -i sovits
   ```

5. **Test API directly**:
   ```bash
   curl "http://localhost:9880?text=测试&text_language=zh"
   ```

#### Expressions Not Triggering

**Symptoms**: Audio plays but no expression changes

**Solutions**:
1. **Verify VTube Studio connection**:
   ```bash
   python tools/validate_config.py --test-vts
   ```

2. **Check hotkey mappings**:
   ```bash
   python tools/list_vts_hotkeys.py
   ```

3. **Test hotkeys manually** in VTube Studio

4. **Verify model has expressions** for mapped hotkeys

5. **Check API permissions** in VTube Studio settings

#### Ollama Connection Issues

**Symptoms**: No LLM responses generated

**Solutions**:
1. **Verify Ollama is running**:
   ```bash
   ollama list
   curl http://localhost:11434/api/tags
   ```

2. **Check model is available**:
   ```bash
   ollama show llama3
   ```

3. **Test model directly**:
   ```bash
   ollama run llama3 "Hello, how are you?"
   ```

4. **Review Ollama logs** for errors

#### Audio Playback Issues

**Symptoms**: No audio output or distorted audio

**Solutions**:
1. **Check audio device** settings
2. **Verify Edge-TTS** is working:
   ```bash
   edge-tts --text "测试" --voice zh-CN-XiaoxiaoNeural --write-media test.mp3
   ```

3. **Check audio file permissions** in temp directory
4. **Try different TTS voice** in configuration
5. **Verify audio codecs** are installed

### Performance Issues

#### Slow Response Times

**Symptoms**: Long delays between input and response

**Solutions**:
1. **Reduce timeouts** in configuration:
   ```json
   {
     "sovits_timeout": 5.0,
     "expression_timeout": 0.3
   }
   ```

2. **Use performance-optimized config**:
   ```bash
   cp config_examples/performance_optimized_config.json config.json
   ```

3. **Check system resources** (CPU, RAM, GPU usage)

4. **Optimize Ollama model** or use smaller model

5. **Disable features** if not needed:
   ```json
   {
     "enable_voice_cloning": false,
     "enable_expression_control": false
   }
   ```

#### High Memory Usage

**Symptoms**: System becomes slow or crashes

**Solutions**:
1. **Monitor memory usage**:
   ```bash
   # Linux/macOS
   top -p $(pgrep -f "python main.py")
   
   # Windows
   tasklist /fi "imagename eq python.exe"
   ```

2. **Use smaller Ollama model**:
   ```json
   {
     "ollama_model": "llama3:8b"
   }
   ```

3. **Reduce GPT-SoVITS model size** or disable voice cloning

4. **Clear temp audio files** regularly

5. **Restart services** periodically for long-running sessions

### Configuration Issues

#### Invalid Configuration

**Symptoms**: System fails to start or behaves unexpectedly

**Solutions**:
1. **Validate configuration**:
   ```bash
   python tools/validate_config.py config.json
   ```

2. **Check JSON syntax**:
   ```bash
   python -m json.tool config.json
   ```

3. **Compare with working examples**:
   ```bash
   diff config.json config_examples/emotional_intelligence_config.json
   ```

4. **Reset to default**:
   ```bash
   cp config_examples/basic_config.json config.json
   ```

#### Hotkey Mapping Issues

**Symptoms**: Wrong expressions triggered or no expressions

**Solutions**:
1. **List available hotkeys**:
   ```bash
   python tools/list_vts_hotkeys.py
   ```

2. **Test hotkeys manually** in VTube Studio

3. **Update emotion_hotkey_map** with correct hotkey names

4. **Use model-specific config**:
   ```bash
   cp config_examples/live2d_model_configs/vroid_studio_model.json config.json
   ```

## Performance Tuning

### Optimization Strategies

#### For Real-time Streaming

```json
{
  "log_level": "WARNING",
  "sovits_timeout": 5.0,
  "expression_timeout": 0.3,
  "enable_emotional_intelligence": true,
  "enable_voice_cloning": true,
  "enable_expression_control": true
}
```

#### For High-Quality Voice

```json
{
  "sovits_timeout": 15.0,
  "expression_timeout": 0.8,
  "fallback_to_edge_tts": false
}
```

#### For Low-Resource Systems

```json
{
  "enable_voice_cloning": false,
  "enable_expression_control": true,
  "log_level": "ERROR",
  "expression_timeout": 0.5
}
```

### Monitoring Performance

1. **Enable detailed logging**:
   ```json
   {
     "log_level": "DEBUG"
   }
   ```

2. **Monitor response times** in logs

3. **Track memory usage** over time

4. **Profile bottlenecks** using Python profiling tools

## Advanced Configuration

### Custom System Prompts

Modify the LLM system prompt for different character personalities:

```python
# In src/llm_client.py, customize the system prompt
SYSTEM_PROMPT = """
你是一个名叫娜娜的 VTuber。你活泼、可爱，有点傲娇。

响应格式：你必须使用以下模式以严格的 JSON 格式响应：
{
  "emotion": "neutral, happy, angry, sad, surprised 中的一个",
  "text": "你的口语响应内容"
}

不要在 JSON 对象外输出任何文本。
"""
```

### Multiple Voice Models

Configure different voices for different emotions:

```json
{
  "voice_models": {
    "happy": "http://localhost:9880/model1",
    "sad": "http://localhost:9881/model2",
    "default": "http://localhost:9880"
  }
}
```

### Advanced Expression Control

Use complex hotkey combinations:

```json
{
  "emotion_hotkey_map": {
    "neutral": "F5",
    "happy": "Ctrl+F1",
    "very_happy": "Shift+F1",
    "angry": "Ctrl+F2",
    "very_angry": "Shift+F2"
  }
}
```

### Integration with External Services

Configure webhooks or API integrations:

```json
{
  "webhooks": {
    "on_emotion_change": "http://localhost:3000/emotion",
    "on_speech_start": "http://localhost:3000/speech"
  }
}
```

## Getting Help

If you continue to experience issues:

1. **Check the logs** in `logs/ai_vtuber.log`
2. **Review configuration** with validation tool
3. **Test components individually** using tools
4. **Consult the troubleshooting section** above
5. **Check for updates** to the system and dependencies

### Support Resources

- **Configuration Examples**: `config_examples/`
- **Validation Tools**: `tools/`
- **Log Files**: `logs/`
- **Documentation**: `docs/`

### Common Log Messages

**INFO messages**: Normal operation
**WARNING messages**: Non-critical issues, system continues
**ERROR messages**: Component failures, fallbacks activated
**DEBUG messages**: Detailed operation info (enable with `"log_level": "DEBUG"`)

Remember to regularly update your system and dependencies for the best performance and latest features!