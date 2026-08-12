"""
GPU 状态检查工具
检查 CUDA、PyTorch GPU 支持和 Ollama GPU 使用情况
"""

import subprocess
import sys

def check_nvidia_smi():
    """检查 NVIDIA GPU 状态"""
    print("=" * 50)
    print("1. NVIDIA GPU 状态 (nvidia-smi)")
    print("=" * 50)
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("❌ nvidia-smi 执行失败")
            print(result.stderr)
    except FileNotFoundError:
        print("❌ nvidia-smi 未找到 - 可能没有安装 NVIDIA 驱动")
    except Exception as e:
        print(f"❌ 错误: {e}")

def check_pytorch_cuda():
    """检查 PyTorch CUDA 支持"""
    print("\n" + "=" * 50)
    print("2. PyTorch CUDA 支持")
    print("=" * 50)
    try:
        import torch
        print(f"PyTorch 版本: {torch.__version__}")
        print(f"CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA 版本: {torch.version.cuda}")
            print(f"GPU 数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
                props = torch.cuda.get_device_properties(i)
                print(f"    显存: {props.total_memory / 1024**3:.1f} GB")
        else:
            print("❌ PyTorch 未检测到 CUDA")
            print("   可能原因:")
            print("   - 安装的是 CPU 版本的 PyTorch")
            print("   - CUDA 驱动版本不兼容")
            print("   建议: pip install torch --index-url https://download.pytorch.org/whl/cu121")
    except ImportError:
        print("❌ PyTorch 未安装")
    except Exception as e:
        print(f"❌ 错误: {e}")

def check_ollama_gpu():
    """检查 Ollama GPU 使用情况"""
    print("\n" + "=" * 50)
    print("3. Ollama GPU 配置")
    print("=" * 50)
    try:
        import requests
        # 获取 Ollama 版本和状态
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✓ Ollama 服务运行中")
            print(f"已加载模型: {[m['name'] for m in data.get('models', [])]}")
            
            # 检查模型详情
            for model in data.get('models', []):
                model_name = model['name']
                detail_resp = requests.post(
                    "http://localhost:11434/api/show",
                    json={"name": model_name},
                    timeout=10
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                    params = detail.get('details', {})
                    print(f"\n模型 {model_name}:")
                    print(f"  参数量: {params.get('parameter_size', 'N/A')}")
                    print(f"  量化: {params.get('quantization_level', 'N/A')}")
        else:
            print("❌ 无法连接 Ollama")
    except requests.exceptions.ConnectionError:
        print("❌ Ollama 服务未运行")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    print("\n提示: Ollama 默认会自动使用 GPU (如果可用)")
    print("检查 GPU 使用: 运行模型时观察 nvidia-smi 的 GPU 利用率")

def check_sovits_performance():
    """GPT-SoVITS 性能建议"""
    print("\n" + "=" * 50)
    print("4. GPT-SoVITS 性能优化建议")
    print("=" * 50)
    print("""
GPT-SoVITS 生成时间 15-18秒 偏长，正常 GPU 加速应该在 2-5秒。

可能原因:
1. 未使用 GPU 加速
   - 检查 GPT-SoVITS 启动日志是否显示 CUDA
   - 确保 PyTorch 是 CUDA 版本

2. 模型未预热
   - 第一次推理会较慢（加载模型到 GPU）
   - 后续推理应该更快

3. 参考音频过长
   - 参考音频越长，处理时间越长
   - 建议使用 3-10 秒的参考音频

4. 文本过长
   - 长文本会增加生成时间
   - 可以考虑分句生成

优化建议:
- 确保 GPT-SoVITS 使用 GPU: 启动时应显示 "Using CUDA"
- 使用较短的参考音频 (3-5秒最佳)
- 考虑使用流式生成 API (如果支持)
""")

def main():
    print("AI VTuber 系统 GPU 诊断工具")
    print("=" * 50)
    
    check_nvidia_smi()
    check_pytorch_cuda()
    check_ollama_gpu()
    check_sovits_performance()
    
    print("\n" + "=" * 50)
    print("诊断完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
