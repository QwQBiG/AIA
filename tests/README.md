# 测试套件目录 (tests/)

## 🧪 测试概述
本目录包含 AI VTuber 系统的完整测试套件，采用多层次测试策略，确保系统的稳定性、可靠性和性能。测试覆盖单元测试、集成测试、性能测试和端到端测试。

## 🏗️ 测试架构
```
tests/
├── 🔧 单元测试
│   ├── test_config.py              # 配置系统测试
│   ├── test_llm_client.py          # LLM 客户端测试
│   ├── test_enhanced_llm_client.py # 增强 LLM 客户端测试
│   ├── test_tts_pipeline.py        # TTS 管道测试
│   ├── test_tts_player.py          # TTS 播放器测试
│   ├── test_vts_client.py          # VTS 客户端测试
│   ├── test_text_cleaner.py        # 文本清理器测试
│   └── test_error_handler.py       # 错误处理器测试
│
├── 🎭 界面测试
│   ├── test_gui_controller.py      # GUI 控制器测试
│   └── test_subtitle_window.py     # 字幕窗口测试
│
├── 🧠 记忆系统测试
│   ├── test_memory_core_setup.py   # 记忆核心设置测试
│   ├── test_data_models.py         # 数据模型测试
│   └── test_entity_extractor.py    # 实体提取器测试
│
├── 🎙️ 全双工引擎测试
│   └── test_full_duplex_engine.py  # 全双工引擎测试
│
├── 🤖 智能代理测试
│   ├── test_agent_manager.py       # 代理管理器测试
│   ├── test_action_engine.py       # 动作引擎测试
│   ├── test_vision_client.py       # 视觉客户端测试
│   ├── test_safety_manager.py      # 安全管理器测试
│   └── test_resource_monitor.py    # 资源监控测试
│
├── 🎮 游戏系统测试
│   ├── test_game_knowledge.py      # 游戏知识测试
│   └── test_template_matcher.py    # 模板匹配测试
│
├── 🔗 集成测试
│   ├── test_integration.py         # 系统集成测试
│   ├── test_agent_integration.py   # 代理集成测试
│   └── test_lipsync_integration.py # 唇同步集成测试
│
└── 🎯 流处理测试
    └── test_stream_processor.py    # 流处理器测试
```

## 🔧 测试框架和工具

### 主要测试框架
- **pytest**: 主要测试框架，支持参数化和插件
- **unittest.mock**: 模拟对象和依赖注入
- **hypothesis**: 基于属性的测试和模糊测试
- **asyncio**: 异步代码测试支持
- **pytest-asyncio**: 异步测试插件

### 测试工具
- **coverage**: 代码覆盖率分析
- **pytest-benchmark**: 性能基准测试
- **pytest-xdist**: 并行测试执行
- **pytest-html**: HTML 测试报告生成

## 🚀 快速开始

### 运行所有测试
```bash
# 运行完整测试套件
python -m pytest tests/

# 运行测试并生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html

# 并行运行测试（加速）
python -m pytest tests/ -n auto
```

### 运行特定测试
```bash
# 运行单个测试文件
python -m pytest tests/test_config.py

# 运行特定测试类
python -m pytest tests/test_llm_client.py::TestLLMClient

# 运行特定测试方法
python -m pytest tests/test_config.py::TestSystemConfig::test_load_config
```

### 运行集成测试
```bash
# 运行关键修复测试
python test_critical_fixes.py

# 运行流式响应测试
python test_streaming_fix.py

# 运行热键功能测试
python test_hotkeys.py
```

## 📋 测试分类详解

### 🔧 单元测试
**目标**: 测试单个组件的功能正确性

#### test_config.py
**测试范围**: 配置系统功能
- ✅ 配置文件加载和保存
- ✅ 配置验证和默认值
- ✅ 配置更新和合并
- ✅ 错误配置处理

```python
def test_load_valid_config():
    """测试加载有效配置文件"""
    config = load_config("config.json")
    assert config.ollama_url == "http://localhost:11434"
    assert config.log_level == "INFO"

def test_invalid_config_handling():
    """测试无效配置处理"""
    with pytest.raises(ConfigValidationError):
        load_config("invalid_config.json")
```

#### test_llm_client.py
**测试范围**: LLM 客户端功能
- ✅ 连接建立和断开
- ✅ 消息发送和接收
- ✅ 错误处理和重试
- ✅ 流式响应处理

#### test_tts_pipeline.py
**测试范围**: TTS 管道功能
- ✅ 文本到语音转换
- ✅ 音频文件生成
- ✅ 缓存机制
- ✅ 多引擎支持

### 🎭 界面测试
**目标**: 测试用户界面组件

#### test_gui_controller.py
**测试范围**: GUI 控制器功能
- ✅ 界面初始化
- ✅ 事件处理
- ✅ 状态更新
- ✅ 热键绑定

### 🧠 记忆系统测试
**目标**: 测试记忆和知识管理

#### test_memory_core_setup.py
**测试范围**: 记忆核心设置
- ✅ 数据库初始化
- ✅ 嵌入模型加载
- ✅ 数据存储和检索
- ✅ 备份和恢复

### 🎙️ 全双工引擎测试
**目标**: 测试实时语音交互

#### test_full_duplex_engine.py
**测试范围**: 全双工引擎功能
- ✅ 音频设备管理
- ✅ 实时语音识别
- ✅ 智能打断处理
- ✅ 延迟优化

### 🤖 智能代理测试
**目标**: 测试自动化代理功能

#### test_agent_manager.py
**测试范围**: 代理管理器功能
- ✅ 代理生命周期管理
- ✅ 任务调度和执行
- ✅ 错误恢复机制
- ✅ 性能监控

#### test_safety_manager.py
**测试范围**: 安全管理器功能
- ✅ 紧急停止机制
- ✅ 热键监听
- ✅ 安全状态管理
- ✅ 回调系统

### 🔗 集成测试
**目标**: 测试组件间协作

#### test_integration.py
**测试范围**: 系统集成测试
- ✅ 端到端对话流程
- ✅ 多组件协作
- ✅ 数据流完整性
- ✅ 错误传播处理

## 🎯 测试策略

### 测试金字塔
```
        🔺 E2E 测试 (10%)
       /              \
      /   集成测试 (20%)  \
     /                    \
    /    单元测试 (70%)      \
   /_________________________\
```

### 测试优先级
1. **P0 - 关键功能**: 核心对话流程、安全机制
2. **P1 - 重要功能**: 界面交互、音频处理
3. **P2 - 辅助功能**: 统计分析、调试工具

### 测试覆盖率目标
- **整体覆盖率**: > 80%
- **核心模块**: > 90%
- **关键路径**: 100%

## 🔍 测试数据管理

### 测试数据结构
```
tests/
├── fixtures/           # 测试固定数据
│   ├── config/        # 测试配置文件
│   ├── audio/         # 测试音频文件
│   ├── images/        # 测试图片文件
│   └── responses/     # 模拟响应数据
└── mocks/             # 模拟对象定义
    ├── mock_llm.py    # 模拟 LLM 客户端
    ├── mock_tts.py    # 模拟 TTS 引擎
    └── mock_vts.py    # 模拟 VTS 客户端
```

### 测试数据生成
```python
# 生成测试配置
@pytest.fixture
def test_config():
    return SystemConfig(
        ollama_url="http://localhost:11434",
        ollama_model="test-model",
        log_level="DEBUG"
    )

# 生成测试音频
@pytest.fixture
def test_audio():
    return generate_test_audio(duration=1.0, sample_rate=16000)
```

## 🚨 测试环境配置

### 环境变量
```bash
# 设置测试环境
export TESTING=true
export LOG_LEVEL=DEBUG
export DISABLE_EXTERNAL_SERVICES=true

# 设置测试数据库
export TEST_DB_PATH="./test_memory_db"
export TEST_CACHE_PATH="./test_cache"
```

### 依赖服务模拟
```python
# 模拟 Ollama 服务
@pytest.fixture
def mock_ollama_server():
    with mock_server("http://localhost:11434") as server:
        server.add_response("/api/generate", {"response": "测试响应"})
        yield server

# 模拟 VTube Studio
@pytest.fixture
def mock_vts_server():
    with mock_websocket_server("ws://localhost:8001") as server:
        yield server
```

## 📊 性能测试

### 基准测试
```python
def test_llm_response_time(benchmark):
    """测试 LLM 响应时间"""
    llm_client = LLMClient()
    
    def generate_response():
        return llm_client.generate("测试输入")
    
    result = benchmark(generate_response)
    assert result is not None

def test_tts_generation_speed(benchmark):
    """测试 TTS 生成速度"""
    tts_pipeline = TTSPipeline()
    
    def generate_audio():
        return tts_pipeline.generate("测试文本")
    
    result = benchmark(generate_audio)
    assert len(result) > 0
```

### 负载测试
```python
@pytest.mark.parametrize("concurrent_requests", [1, 5, 10, 20])
def test_concurrent_llm_requests(concurrent_requests):
    """测试并发 LLM 请求处理"""
    llm_client = LLMClient()
    
    async def make_request():
        return await llm_client.generate_async("测试输入")
    
    # 并发执行请求
    tasks = [make_request() for _ in range(concurrent_requests)]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == concurrent_requests
    assert all(result is not None for result in results)
```

## 🔧 持续集成

### GitHub Actions 配置
```yaml
name: 测试套件
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: 设置 Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: 安装依赖
      run: pip install -r requirements.txt
    - name: 运行测试
      run: pytest tests/ --cov=src --cov-report=xml
    - name: 上传覆盖率报告
      uses: codecov/codecov-action@v1
```

### 测试报告
- **HTML 报告**: `htmlcov/index.html`
- **XML 报告**: `coverage.xml`
- **JSON 报告**: `coverage.json`

## 🛠️ 调试测试

### 调试单个测试
```bash
# 详细输出模式
python -m pytest tests/test_config.py -v -s

# 调试模式（进入 pdb）
python -m pytest tests/test_config.py --pdb

# 只运行失败的测试
python -m pytest tests/ --lf
```

### 测试日志
```python
import logging

def test_with_logging(caplog):
    """测试日志输出"""
    with caplog.at_level(logging.INFO):
        # 执行测试代码
        pass
    
    assert "预期日志消息" in caplog.text
```

## 📚 测试最佳实践

### 测试命名规范
- 测试文件: `test_<module_name>.py`
- 测试类: `Test<ClassName>`
- 测试方法: `test_<功能描述>`

### 测试结构
```python
def test_function_name():
    """测试描述"""
    # Arrange - 准备测试数据
    input_data = "测试输入"
    expected_output = "预期输出"
    
    # Act - 执行被测试的功能
    actual_output = function_under_test(input_data)
    
    # Assert - 验证结果
    assert actual_output == expected_output
```

### 异步测试
```python
@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await async_function()
    assert result is not None
```

## 🚨 故障排除

### 常见测试问题
1. **测试环境不一致**
   - 使用 Docker 容器化测试环境
   - 固定依赖版本
   - 清理测试数据

2. **异步测试失败**
   - 检查事件循环配置
   - 使用适当的异步测试装饰器
   - 处理超时问题

3. **模拟对象问题**
   - 验证模拟对象配置
   - 检查调用次数和参数
   - 重置模拟状态

### 测试维护
```bash
# 更新测试快照
python -m pytest tests/ --update-snapshots

# 清理测试缓存
python -m pytest --cache-clear

# 重新生成测试数据
python tools/generate_test_data.py
```

## 📚 相关文档
- [开发指南](../docs/development_guide.md)
- [代码规范](../docs/coding_standards.md)
- [CI/CD 配置](../.github/workflows/test.yml)
- [性能基准](./benchmarks/README.md)