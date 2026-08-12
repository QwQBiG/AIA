# 工具集目录 (tools/)

## 🛠️ 工具概述
本目录包含 AI VTuber 系统的各种实用工具和脚本，用于系统维护、性能优化、问题诊断和开发辅助。这些工具帮助用户和开发者更好地管理和优化系统。

## 🗂️ 工具分类
```
tools/
├── 🔧 系统诊断工具
│   ├── run_diagnostics.py      # 综合系统诊断
│   ├── check_gpu_status.py     # GPU 状态检查
│   └── validate_config.py      # 配置文件验证
│
├── 📊 性能分析工具
│   ├── measure_performance.py  # 性能测量工具
│   └── system_optimizer.py     # 系统优化工具
│
├── 🎭 VTube Studio 工具
│   ├── check_vts_params.py     # VTS 参数检查
│   └── list_vts_hotkeys.py     # VTS 热键列表
│
└── 📚 README.md                # 工具说明文档
```

## 🔧 系统诊断工具

### run_diagnostics.py
**功能**: 综合系统诊断工具
- 🔍 **全面检查**: 检查所有系统组件状态
- 📊 **生成报告**: 生成详细的诊断报告
- 🚨 **问题识别**: 自动识别常见问题
- 💡 **解决建议**: 提供问题解决建议

**使用方法**:
```bash
# 运行完整诊断
python tools/run_diagnostics.py

# 运行特定模块诊断
python tools/run_diagnostics.py --module llm
python tools/run_diagnostics.py --module vts
python tools/run_diagnostics.py --module audio

# 生成详细报告
python tools/run_diagnostics.py --detailed --output report.html
```

**诊断项目**:
- ✅ **系统环境**: Python 版本、依赖包状态
- ✅ **配置文件**: 配置完整性和有效性
- ✅ **网络连接**: Ollama、VTS、TTS 服务连接
- ✅ **硬件资源**: CPU、内存、GPU 状态
- ✅ **文件系统**: 权限、磁盘空间、缓存状态
- ✅ **模型文件**: AI 模型完整性检查

### check_gpu_status.py
**功能**: GPU 状态检查工具
- 🎮 **GPU 检测**: 检测可用的 GPU 设备
- 📊 **性能监控**: 监控 GPU 使用率和温度
- 💾 **内存分析**: 分析 GPU 内存使用情况
- ⚡ **性能测试**: 测试 GPU 计算性能

**使用方法**:
```bash
# 检查 GPU 状态
python tools/check_gpu_status.py

# 持续监控 GPU
python tools/check_gpu_status.py --monitor --interval 5

# 运行 GPU 性能测试
python tools/check_gpu_status.py --benchmark
```

**输出示例**:
```
GPU 状态报告
=============
GPU 0: NVIDIA GeForce RTX 3080
  - 使用率: 25%
  - 内存使用: 2.1GB / 10GB
  - 温度: 65°C
  - 驱动版本: 472.12

推荐设置:
  - 启用 GPU 加速: 是
  - 最大批处理大小: 32
  - 内存预分配: 4GB
```

### validate_config.py
**功能**: 配置文件验证工具
- ✅ **语法检查**: 验证 JSON 语法正确性
- 🔍 **完整性检查**: 检查必需配置项
- 🎯 **值验证**: 验证配置值的有效性
- 🔧 **自动修复**: 自动修复常见配置问题

**使用方法**:
```bash
# 验证默认配置文件
python tools/validate_config.py

# 验证指定配置文件
python tools/validate_config.py --config custom_config.json

# 自动修复配置问题
python tools/validate_config.py --fix

# 生成配置模板
python tools/validate_config.py --generate-template
```

## 📊 性能分析工具

### measure_performance.py
**功能**: 系统性能测量工具
- ⏱️ **响应时间**: 测量各组件响应时间
- 🔄 **吞吐量**: 测量系统处理能力
- 📈 **性能趋势**: 跟踪性能变化趋势
- 📊 **基准对比**: 与基准性能对比

**使用方法**:
```bash
# 运行性能测试
python tools/measure_performance.py

# 测试特定组件
python tools/measure_performance.py --component llm
python tools/measure_performance.py --component tts
python tools/measure_performance.py --component vts

# 长期性能监控
python tools/measure_performance.py --monitor --duration 3600

# 生成性能报告
python tools/measure_performance.py --report --format html
```

**测试项目**:
- 🤖 **LLM 性能**: 响应时间、令牌生成速度
- 🎤 **TTS 性能**: 音频生成时间、质量评估
- 🎭 **VTS 性能**: 动画响应时间、帧率
- 💾 **内存性能**: 内存使用、垃圾回收
- 🌐 **网络性能**: 网络延迟、带宽使用

### system_optimizer.py
**功能**: 系统优化工具
- ⚡ **性能优化**: 自动优化系统性能
- 🧹 **资源清理**: 清理无用文件和缓存
- ⚙️ **参数调优**: 自动调整最佳参数
- 📊 **优化报告**: 生成优化效果报告

**使用方法**:
```bash
# 运行系统优化
python tools/system_optimizer.py

# 清理系统缓存
python tools/system_optimizer.py --cleanup

# 优化特定组件
python tools/system_optimizer.py --optimize llm
python tools/system_optimizer.py --optimize audio

# 恢复默认设置
python tools/system_optimizer.py --reset
```

**优化项目**:
- 🧠 **内存优化**: 清理内存碎片、优化缓存
- 💾 **存储优化**: 清理临时文件、压缩数据
- 🌐 **网络优化**: 优化连接池、调整超时
- ⚡ **CPU 优化**: 调整线程数、优化算法
- 🎮 **GPU 优化**: 优化显存使用、调整批大小

## 🎭 VTube Studio 工具

### check_vts_params.py
**功能**: VTube Studio 参数检查工具
- 🔍 **参数发现**: 发现可用的模型参数
- 📊 **参数监控**: 实时监控参数值变化
- 🎯 **参数测试**: 测试参数控制效果
- 📝 **参数文档**: 生成参数说明文档

**使用方法**:
```bash
# 检查 VTS 参数
python tools/check_vts_params.py

# 监控参数变化
python tools/check_vts_params.py --monitor

# 测试参数控制
python tools/check_vts_params.py --test MouthOpen

# 导出参数列表
python tools/check_vts_params.py --export params.json
```

**输出示例**:
```
VTube Studio 参数列表
====================
MouthOpen
  - 当前值: 0.0
  - 范围: 0.0 - 1.0
  - 类型: 浮点数
  - 说明: 控制嘴部开合

EyeOpenLeft
  - 当前值: 1.0
  - 范围: 0.0 - 1.0
  - 类型: 浮点数
  - 说明: 控制左眼开合
```

### list_vts_hotkeys.py
**功能**: VTube Studio 热键列表工具
- 🔑 **热键发现**: 发现可用的热键
- 📋 **热键分类**: 按功能分类热键
- 🧪 **热键测试**: 测试热键触发效果
- 📄 **热键导出**: 导出热键配置

**使用方法**:
```bash
# 列出所有热键
python tools/list_vts_hotkeys.py

# 按类型筛选热键
python tools/list_vts_hotkeys.py --type expression
python tools/list_vts_hotkeys.py --type animation

# 测试热键
python tools/list_vts_hotkeys.py --test "Happy Expression"

# 导出热键配置
python tools/list_vts_hotkeys.py --export hotkeys.json
```

## 🚀 工具使用指南

### 1. 系统健康检查
```bash
# 每日健康检查
python tools/run_diagnostics.py --quick

# 每周详细检查
python tools/run_diagnostics.py --detailed --output weekly_report.html

# 问题排查
python tools/run_diagnostics.py --troubleshoot
```

### 2. 性能优化流程
```bash
# 1. 测量当前性能
python tools/measure_performance.py --baseline

# 2. 运行系统优化
python tools/system_optimizer.py

# 3. 验证优化效果
python tools/measure_performance.py --compare
```

### 3. VTube Studio 配置
```bash
# 1. 检查 VTS 连接
python tools/run_diagnostics.py --module vts

# 2. 发现可用参数
python tools/check_vts_params.py --export

# 3. 配置热键映射
python tools/list_vts_hotkeys.py --export
```

## ⚙️ 工具配置

### 配置文件: tools_config.json
```json
{
  "diagnostics": {
    "timeout": 30,
    "detailed_mode": false,
    "auto_fix": false,
    "report_format": "html"
  },
  "performance": {
    "test_duration": 60,
    "sample_interval": 1.0,
    "benchmark_iterations": 10,
    "report_charts": true
  },
  "optimization": {
    "auto_cleanup": true,
    "backup_before_optimize": true,
    "optimization_level": "balanced",
    "preserve_user_settings": true
  }
}
```

### 环境变量
```bash
# 工具配置
export TOOLS_CONFIG_PATH="./tools_config.json"
export TOOLS_OUTPUT_DIR="./tools_output"
export TOOLS_LOG_LEVEL="INFO"

# 诊断配置
export DIAGNOSTIC_TIMEOUT=30
export DIAGNOSTIC_DETAILED=false

# 性能测试配置
export PERF_TEST_DURATION=60
export PERF_SAMPLE_INTERVAL=1.0
```

## 📊 工具输出格式

### 诊断报告格式
```json
{
  "timestamp": "2024-01-24T10:30:00Z",
  "system_info": {
    "os": "Windows 10",
    "python_version": "3.9.7",
    "total_memory": "16GB"
  },
  "test_results": [
    {
      "category": "配置文件",
      "status": "通过",
      "details": "所有配置项有效"
    }
  ],
  "recommendations": [
    "建议升级 GPU 驱动到最新版本"
  ]
}
```

### 性能报告格式
```json
{
  "timestamp": "2024-01-24T10:30:00Z",
  "test_duration": 60,
  "metrics": {
    "llm_response_time": {
      "average": 1.2,
      "min": 0.8,
      "max": 2.1,
      "unit": "seconds"
    },
    "tts_generation_time": {
      "average": 0.5,
      "min": 0.3,
      "max": 0.8,
      "unit": "seconds"
    }
  }
}
```

## 🔧 自定义工具开发

### 工具模板
```python
#!/usr/bin/env python3
"""
自定义工具模板
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from tools.base_tool import BaseTool

class CustomTool(BaseTool):
    """自定义工具类"""
    
    def __init__(self):
        super().__init__()
        self.name = "自定义工具"
        self.description = "工具描述"
    
    def run(self, args):
        """运行工具主逻辑"""
        try:
            # 工具逻辑实现
            self.logger.info("工具开始运行")
            
            # 执行具体任务
            result = self.execute_task(args)
            
            # 输出结果
            self.output_result(result)
            
            return True
            
        except Exception as e:
            self.logger.error(f"工具运行失败: {e}")
            return False
    
    def execute_task(self, args):
        """执行具体任务"""
        # 实现具体功能
        pass
    
    def output_result(self, result):
        """输出结果"""
        print(f"工具执行结果: {result}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="自定义工具")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 设置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)
    
    # 创建并运行工具
    tool = CustomTool()
    success = tool.run(args)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

### 工具基类
```python
class BaseTool:
    """工具基类"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = None
        self.start_time = None
    
    def load_config(self, config_path=None):
        """加载配置文件"""
        try:
            self.config = load_config(config_path or "config.json")
            return True
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            return False
    
    def start_timer(self):
        """开始计时"""
        self.start_time = time.time()
    
    def get_elapsed_time(self):
        """获取经过时间"""
        if self.start_time:
            return time.time() - self.start_time
        return 0
    
    def save_result(self, result, filename):
        """保存结果到文件"""
        try:
            output_dir = Path("tools_output")
            output_dir.mkdir(exist_ok=True)
            
            with open(output_dir / filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"结果已保存到: {output_dir / filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
            return False
```

## 🚨 故障排除

### 常见问题
1. **工具运行失败**
   ```bash
   # 检查 Python 环境
   python --version
   
   # 检查依赖包
   pip list | grep -E "(pytest|requests|websockets)"
   
   # 重新安装依赖
   pip install -r requirements.txt
   ```

2. **权限问题**
   ```bash
   # 检查文件权限
   ls -la tools/
   
   # 添加执行权限
   chmod +x tools/*.py
   ```

3. **配置文件问题**
   ```bash
   # 验证配置文件
   python tools/validate_config.py
   
   # 重新生成配置
   python tools/validate_config.py --generate-template
   ```

### 调试模式
```bash
# 启用详细日志
python tools/run_diagnostics.py --verbose

# 启用调试模式
python tools/measure_performance.py --debug

# 保存调试信息
python tools/system_optimizer.py --debug --log-file debug.log
```

## 📚 相关文档
- [系统配置指南](../docs/setup_guide.md)
- [性能优化指南](../docs/performance_guide.md)
- [故障排除手册](../docs/troubleshooting.md)
- [开发者文档](../docs/developer_guide.md)