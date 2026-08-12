"""
网络配置管理模块
Network Configuration Management Module
"""

import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class NetworkConfig:
    """网络配置管理器"""
    
    def __init__(self):
        self.proxy_enabled = False
        self.proxy_address = "http://127.0.0.1:10808"
        self.timeout = 30
        
    def set_proxy(self, enabled: bool, address: str = None):
        """设置代理配置"""
        self.proxy_enabled = enabled
        if address:
            self.proxy_address = address
            
        if enabled and self.proxy_address:
            os.environ['HTTP_PROXY'] = self.proxy_address
            os.environ['HTTPS_PROXY'] = self.proxy_address
            os.environ['http_proxy'] = self.proxy_address
            os.environ['https_proxy'] = self.proxy_address
            logger.info(f"代理已启用: {self.proxy_address}")
        else:
            # 清除代理设置
            for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
                if key in os.environ:
                    del os.environ[key]
            logger.info("代理已禁用")
    
    def set_timeout(self, timeout: int):
        """设置网络超时"""
        self.timeout = timeout
        os.environ['REQUESTS_TIMEOUT'] = str(timeout)
        os.environ['HTTPX_TIMEOUT'] = str(timeout)
        os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = str(timeout)
        logger.info(f"网络超时设置为: {timeout}秒")
    
    def configure_offline_mode(self):
        """配置离线模式"""
        # 强制HuggingFace离线模式
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_DATASETS_OFFLINE'] = '1'
        
        # 禁用网络检查
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
        os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
        
        # 设置缓存目录
        cache_dir = os.path.join(os.getcwd(), "models", "huggingface")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ['HF_HOME'] = cache_dir
        os.environ['TRANSFORMERS_CACHE'] = cache_dir
        os.environ['HF_DATASETS_CACHE'] = cache_dir
        
        # 设置网络超时为极短时间，强制使用本地缓存
        os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '1'
        os.environ['REQUESTS_TIMEOUT'] = '1'
        os.environ['HTTPX_TIMEOUT'] = '1'
        
        logger.info("HuggingFace强制离线模式已配置")
        logger.info(f"缓存目录: {cache_dir}")
    
    def apply_performance_optimizations(self):
        """应用性能优化设置"""
        try:
            # 强制离线模式
            self.configure_offline_mode()
            
            # 设置Python优化
            os.environ['PYTHONUNBUFFERED'] = '1'
            os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
            
            # 禁用不必要的警告
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            
            # 设置音频优化
            os.environ['SDL_AUDIODRIVER'] = 'directsound'  # Windows优化
            
            logger.info("性能优化设置已应用")
            return True
        except Exception as e:
            logger.error(f"应用性能优化失败: {e}")
            return False
    
    def apply_settings(self, proxy_enabled: bool, proxy_address: str, timeout: int):
        """应用所有网络设置"""
        try:
            self.set_proxy(proxy_enabled, proxy_address)
            self.set_timeout(timeout)
            self.apply_performance_optimizations()  # 包含离线模式配置
            return True
        except Exception as e:
            logger.error(f"应用网络设置失败: {e}")
            return False

# 全局网络配置实例
network_config = NetworkConfig()

# 自动应用性能优化设置
try:
    network_config.apply_performance_optimizations()
    logger.info("启动时自动应用了性能优化设置")
except Exception as e:
    logger.warning(f"启动时应用性能优化失败: {e}")