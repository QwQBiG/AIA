"""
屏幕捕获器 - 为模板匹配提供屏幕截图功能

本模块提供高效的屏幕捕获功能，支持全屏和区域截图。
截图结果为 OpenCV 兼容的 BGR 格式 numpy 数组。

主要功能：
- 全屏截图
- 指定区域截图
- RGB 到 BGR 颜色空间转换

使用示例：
    capturer = ScreenCapturer()
    screenshot = capturer.capture()  # 全屏截图
    
    # 或者指定区域
    screenshot = capturer.capture(region=(100, 100, 800, 600))
"""

import logging
import numpy as np
from typing import Optional, Tuple
from PIL import ImageGrab

logger = logging.getLogger(__name__)


class ScreenCapturer:
    """
    屏幕截图捕获器
    
    使用 PIL 的 ImageGrab 进行屏幕捕获，并转换为 OpenCV 兼容格式。
    支持设置默认捕获区域，也可以在每次捕获时指定不同区域。
    
    注意事项：
    - Windows 系统上使用 GDI 进行截图
    - 高 DPI 显示器可能需要额外的缩放处理
    - 截图操作会有一定的性能开销，建议控制调用频率
    
    属性:
        region: 默认捕获区域 (x, y, width, height)，None 表示全屏
    """
    
    def __init__(self, region: Optional[Tuple[int, int, int, int]] = None):
        """
        初始化屏幕捕获器
        
        参数:
            region: 默认捕获区域 (x, y, width, height)
                   - x, y: 区域左上角坐标
                   - width, height: 区域宽度和高度
                   - None: 捕获整个屏幕
        """
        self.region = region
        logger.info(f"屏幕捕获器初始化完成，默认区域={region}")
    
    def capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """
        捕获屏幕截图
        
        参数:
            region: 捕获区域 (x, y, width, height)
                   - 如果指定，覆盖默认区域
                   - 如果为 None，使用默认区域或全屏
            
        返回:
            numpy 数组格式的截图（BGR 颜色空间，OpenCV 兼容）
            
        异常:
            Exception: 截图失败时抛出异常
        """
        try:
            # 使用传入的区域或默认区域
            capture_region = region or self.region
            
            # 执行截图
            if capture_region:
                x, y, w, h = capture_region
                # ImageGrab.grab 使用 bbox 格式: (left, top, right, bottom)
                screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            else:
                # 全屏截图
                screenshot = ImageGrab.grab()
            
            # 转换为 numpy 数组
            screenshot_np = np.array(screenshot)
            
            # RGB 转 BGR（OpenCV 使用 BGR 格式）
            # [:, :, ::-1] 反转颜色通道顺序
            screenshot_bgr = screenshot_np[:, :, ::-1].copy()
            
            return screenshot_bgr
            
        except Exception as e:
            logger.error(f"屏幕截图失败: {e}")
            raise
    
    def set_region(self, region: Optional[Tuple[int, int, int, int]]):
        """
        设置默认捕获区域
        
        参数:
            region: 新的默认区域 (x, y, width, height)
                   - None: 恢复为全屏捕获
        """
        self.region = region
        logger.info(f"捕获区域已更新为 {region}")
