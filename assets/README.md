# 资源文件目录 (assets/)

## 📁 目录概述
本目录包含 AI VTuber 系统运行所需的所有静态资源文件，包括音频缓存、模型文件、游戏模板、图标资源等。

## 🗂️ 目录结构
```
assets/
├── 🎵 audio_config.json    # 音频设备配置文件
├── 💾 cache/              # 音频缓存目录
│   ├── *.mp3             # 缓存的音频文件
│   ├── *.wav             # 参考音频文件
│   └── GPT-SoVITS_README.md # GPT-SoVITS 说明文档
├── 🎮 games/              # 游戏相关资源
│   ├── cookie-clicker/   # Cookie Clicker 游戏模板
│   └── README.md         # 游戏资源说明
├── 🖼️ icons/              # 图标资源目录
├── 📸 images/             # 图片资源目录
├── 🤖 models/             # AI 模型文件
│   ├── silero_vad.jit    # Silero VAD 模型
│   └── README.md         # 模型说明文档
└── 📂 temp/               # 临时文件目录
```

## 🎵 音频系统资源

### audio_config.json
**功能**: 音频设备配置文件
- 🎤 **输入设备配置**: 麦克风设备选择和参数
- 🔊 **输出设备配置**: 扬声器设备选择和参数
- 🎚️ **音量设置**: 输入输出音量控制
- ⚙️ **高级参数**: 采样率、缓冲区大小等

**配置示例**:
```json
{
  "input_device": {
    "device_id": null,
    "sample_rate": 16000,
    "channels": 1,
    "volume": 0.8
  },
  "output_device": {
    "device_id": null,
    "sample_rate": 44100,
    "channels": 2,
    "volume": 0.7
  }
}
```

### cache/ 目录
**功能**: 音频文件缓存系统
- 🎵 **TTS 缓存**: 缓存生成的语音文件，提高响应速度
- 🎤 **参考音频**: GPT-SoVITS 语音克隆参考音频
- 🔄 **自动清理**: 定期清理过期缓存文件
- 📊 **缓存统计**: 跟踪缓存使用情况

**缓存文件类型**:
- `*.mp3`: 压缩音频文件，用于快速播放
- `*.wav`: 无损音频文件，用于高质量播放
- `reference_audio.wav`: GPT-SoVITS 参考音频

## 🎮 游戏资源系统

### games/ 目录
**功能**: 游戏自动化相关资源
- 🍪 **Cookie Clicker**: 自动点击游戏模板和配置
- 🎯 **模板匹配**: 游戏界面元素识别模板
- ⚙️ **游戏配置**: 自动化策略和参数设置
- 📊 **游戏数据**: 游戏状态和进度记录

### cookie-clicker/ 子目录
**功能**: Cookie Clicker 游戏自动化
- 🖼️ **templates/**: 界面元素识别模板
  - `big-cookie.png`: 大饼干按钮模板
  - `cursor-upgrade.png`: 光标升级按钮模板
  - `grandma-upgrade.png`: 奶奶升级按钮模板
- ⚙️ **profile.json**: 游戏配置文件

**配置示例**:
```json
{
  "game_name": "Cookie Clicker",
  "auto_click_enabled": true,
  "upgrade_strategy": "balanced",
  "click_interval": 0.1,
  "upgrade_threshold": 1000
}
```

## 🤖 AI 模型资源

### models/ 目录
**功能**: AI 模型文件存储
- 🎤 **语音检测模型**: Silero VAD 模型文件
- 🧠 **嵌入模型**: 文本嵌入模型缓存
- 📝 **语言模型**: 本地语言模型文件
- 🔄 **模型管理**: 自动下载和更新模型

### silero_vad.jit
**功能**: Silero 语音活动检测模型
- 🎯 **语音检测**: 实时检测语音活动
- 🔇 **静音检测**: 识别静音段落
- ⚡ **高性能**: 优化的 JIT 编译模型
- 🎚️ **可调参数**: 支持敏感度调节

**使用方式**:
```python
import torch

# 加载 VAD 模型
vad_model = torch.jit.load('assets/models/silero_vad.jit')

# 检测语音活动
speech_prob = vad_model(audio_chunk, sample_rate)
```

## 🖼️ 视觉资源系统

### icons/ 目录
**功能**: 应用程序图标资源
- 🖥️ **应用图标**: 主程序窗口图标
- 🎭 **状态图标**: 系统状态指示图标
- 🔘 **按钮图标**: 界面按钮装饰图标
- 🎨 **主题图标**: 不同主题的图标变体

### images/ 目录
**功能**: 图片资源存储
- 🖼️ **界面背景**: GUI 背景图片
- 📊 **图表图片**: 统计图表和可视化
- 🎭 **虚拟形象**: VTuber 形象相关图片
- 📸 **截图缓存**: 屏幕截图临时存储

## 📂 临时文件系统

### temp/ 目录
**功能**: 临时文件存储
- 🔄 **临时音频**: 处理中的音频文件
- 📸 **临时图片**: 处理中的图片文件
- 📝 **临时数据**: 中间处理数据
- 🧹 **自动清理**: 定期清理临时文件

**清理策略**:
- 启动时清理超过 24 小时的文件
- 内存不足时优先清理临时文件
- 手动清理命令支持

## 🛠️ 资源管理

### 缓存管理
```python
from src.cache_manager import CacheManager

# 创建缓存管理器
cache_manager = CacheManager("assets/cache")

# 清理过期缓存
cache_manager.cleanup_expired(hours=24)

# 获取缓存统计
stats = cache_manager.get_cache_stats()
```

### 模型管理
```python
from src.model_manager import ModelManager

# 创建模型管理器
model_manager = ModelManager("assets/models")

# 检查模型更新
model_manager.check_for_updates()

# 下载缺失模型
model_manager.download_missing_models()
```

### 资源优化
```python
from src.resource_optimizer import ResourceOptimizer

# 创建资源优化器
optimizer = ResourceOptimizer("assets/")

# 压缩图片资源
optimizer.compress_images()

# 清理重复文件
optimizer.remove_duplicates()
```

## 📊 存储空间管理

### 空间使用统计
- **cache/**: 通常占用 100-500MB
- **models/**: 通常占用 50-200MB
- **games/**: 通常占用 < 10MB
- **temp/**: 动态变化，建议 < 100MB

### 空间优化建议
1. **定期清理缓存**: 每周清理一次过期缓存
2. **压缩音频文件**: 使用 MP3 格式减少存储
3. **清理临时文件**: 每日清理临时目录
4. **监控磁盘空间**: 设置空间不足警告

## 🔧 配置和维护

### 资源配置文件
```json
{
  "cache": {
    "max_size_mb": 500,
    "cleanup_interval_hours": 24,
    "compression_enabled": true
  },
  "models": {
    "auto_download": true,
    "update_check_interval": 168,
    "fallback_enabled": true
  },
  "temp": {
    "max_age_hours": 24,
    "max_size_mb": 100,
    "auto_cleanup": true
  }
}
```

### 维护脚本
```bash
# 清理所有缓存
python tools/cleanup_cache.py

# 检查资源完整性
python tools/check_resources.py

# 优化资源存储
python tools/optimize_resources.py
```

## 🚨 故障排除

### 常见问题
1. **缓存文件损坏**
   - 删除损坏的缓存文件
   - 重新生成音频缓存
   - 检查磁盘空间

2. **模型文件缺失**
   - 重新下载模型文件
   - 检查网络连接
   - 使用备用模型

3. **临时文件过多**
   - 手动清理临时目录
   - 检查清理脚本
   - 调整清理策略

### 恢复操作
```python
# 重置资源目录
from src.resource_manager import ResourceManager
resource_manager = ResourceManager()
resource_manager.reset_resources()

# 重新下载必需资源
resource_manager.download_essential_resources()
```

## 📚 相关文档
- [系统配置指南](../docs/setup_guide.md)
- [音频配置说明](./cache/GPT-SoVITS_README.md)
- [游戏自动化指南](./games/README.md)
- [模型管理文档](./models/README.md)