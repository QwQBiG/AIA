"""
模板匹配器 - 基于 OpenCV 的视觉目标检测模块

本模块提供模板匹配功能，使用 OpenCV 的 cv2.matchTemplate 方法
在屏幕截图中定位视觉目标。

主要功能：
- 加载和验证模板图片
- 在截图中搜索模板位置
- 返回匹配结果（置信度、坐标、边界框）

使用示例：
    matcher = TemplateMatcher(confidence_threshold=0.7)
    matcher.load_template("assets/games/cookie-clicker/templates/cookie.png")
    result = matcher.find_match(screenshot)
    if result.found:
        print(f"找到目标，位置: ({result.center_x}, {result.center_y})")
"""

import cv2
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
import logging
from pathlib import Path
import time

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """
    模板匹配操作的结果数据类
    
    属性:
        found: 是否找到匹配目标
        confidence: 匹配置信度 (0.0-1.0)
        center_x: 匹配区域中心点 X 坐标
        center_y: 匹配区域中心点 Y 坐标
        bounding_box: 边界框 (x, y, width, height)
        timestamp: 匹配操作的时间戳
    """
    found: bool
    confidence: float
    center_x: int
    center_y: int
    bounding_box: Tuple[int, int, int, int]  # (x, y, width, height)
    timestamp: float


class TemplateMatcher:
    """
    基于 OpenCV 的模板匹配器
    
    使用 cv2.matchTemplate 配合归一化相关系数方法 (TM_CCOEFF_NORMED)
    在截图中查找模板，支持可配置的置信度阈值。
    
    工作原理：
    1. 将模板和搜索图像都转换为灰度图（加速匹配）
    2. 使用滑动窗口在搜索图像上移动模板
    3. 计算每个位置的相关系数
    4. 找到最大相关系数的位置作为匹配结果
    
    属性:
        confidence_threshold: 最小置信度阈值，低于此值视为未匹配
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        初始化模板匹配器
        
        参数:
            confidence_threshold: 最小置信度阈值 (0.0-1.0)，默认 0.7
                                 值越高要求匹配越精确，但可能漏检
                                 值越低容易误检，但召回率更高
        
        异常:
            ValueError: 置信度阈值不在 0.0-1.0 范围内
        """
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("置信度阈值必须在 0.0 到 1.0 之间")
        
        self.confidence_threshold = confidence_threshold
        
        # 模板相关属性
        self._template: Optional[np.ndarray] = None  # 灰度模板图像
        self._template_path: Optional[str] = None    # 模板文件路径
        self._template_width: int = 0                # 模板宽度
        self._template_height: int = 0               # 模板高度
        
        logger.info(f"模板匹配器初始化完成，置信度阈值={confidence_threshold}")
    
    def load_template(self, image_path: str) -> bool:
        """
        加载并验证模板图片
        
        模板图片要求：
        - 格式：PNG（推荐）或其他 OpenCV 支持的格式
        - 尺寸：20x20 到 200x200 像素之间
        - 内容：清晰的目标特征，避免过多背景
        
        参数:
            image_path: 模板图片文件路径
            
        返回:
            True: 加载成功
            False: 加载失败（文件不存在、格式错误、尺寸不合规）
        """
        try:
            # 检查文件是否存在
            path = Path(image_path)
            if not path.exists():
                logger.error(f"模板文件不存在: {image_path}")
                return False
            
            # 加载图片
            template = cv2.imread(str(path))
            if template is None:
                logger.error(f"无法加载模板图片（可能格式不支持）: {image_path}")
                return False
            
            # 验证尺寸（20-200 像素范围）
            height, width = template.shape[:2]
            if not (20 <= width <= 200 and 20 <= height <= 200):
                logger.error(f"模板尺寸 {width}x{height} 超出有效范围 (20-200)")
                return False
            
            # 转换为灰度图以加速匹配
            self._template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            self._template_path = image_path
            self._template_height, self._template_width = self._template.shape
            
            logger.info(f"模板加载成功: {image_path} ({width}x{height})")
            return True
            
        except Exception as e:
            logger.error(f"加载模板时发生错误: {e}", exc_info=True)
            return False
    
    def find_match(self, screenshot: np.ndarray, 
                   region: Optional[Tuple[int, int, int, int]] = None) -> MatchResult:
        """
        在截图中查找模板
        
        搜索流程：
        1. 提取搜索区域（如果指定）
        2. 转换为灰度图
        3. 执行模板匹配
        4. 检查最大置信度是否超过阈值
        5. 计算匹配位置的绝对坐标
        
        参数:
            screenshot: 屏幕截图，numpy 数组格式（BGR 颜色空间）
            region: 可选的搜索区域 (x, y, width, height)
                   指定后只在该区域内搜索，可提升性能
            
        返回:
            MatchResult: 包含匹配结果的数据对象
                - found=True: 找到匹配，其他字段有效
                - found=False: 未找到匹配，坐标字段为 0
        """
        timestamp = time.time()
        
        # 检查模板是否已加载
        if self._template is None:
            logger.warning("未加载模板，请先调用 load_template()")
            return MatchResult(
                found=False,
                confidence=0.0,
                center_x=0,
                center_y=0,
                bounding_box=(0, 0, 0, 0),
                timestamp=timestamp
            )
        
        try:
            # 提取搜索区域（如果指定）
            search_image = screenshot
            offset_x, offset_y = 0, 0
            
            if region is not None:
                x, y, w, h = region
                search_image = screenshot[y:y+h, x:x+w]
                offset_x, offset_y = x, y
            
            # 转换为灰度图
            if len(search_image.shape) == 3:
                search_gray = cv2.cvtColor(search_image, cv2.COLOR_BGR2GRAY)
            else:
                search_gray = search_image
            
            # 检查模板是否大于搜索区域
            if (self._template_height > search_gray.shape[0] or 
                self._template_width > search_gray.shape[1]):
                logger.warning("模板尺寸大于搜索区域，无法匹配")
                return MatchResult(
                    found=False,
                    confidence=0.0,
                    center_x=0,
                    center_y=0,
                    bounding_box=(0, 0, 0, 0),
                    timestamp=timestamp
                )
            
            # 执行模板匹配（使用归一化相关系数方法）
            # TM_CCOEFF_NORMED: 值域 [-1, 1]，1 表示完美匹配
            result = cv2.matchTemplate(search_gray, self._template, cv2.TM_CCOEFF_NORMED)
            
            # 获取最大匹配值和位置
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 检查置信度是否达到阈值
            if max_val < self.confidence_threshold:
                return MatchResult(
                    found=False,
                    confidence=max_val,
                    center_x=0,
                    center_y=0,
                    bounding_box=(0, 0, 0, 0),
                    timestamp=timestamp
                )
            
            # 计算绝对坐标（考虑区域偏移）
            top_left_x = max_loc[0] + offset_x
            top_left_y = max_loc[1] + offset_y
            center_x = top_left_x + self._template_width // 2
            center_y = top_left_y + self._template_height // 2
            
            return MatchResult(
                found=True,
                confidence=max_val,
                center_x=center_x,
                center_y=center_y,
                bounding_box=(top_left_x, top_left_y, self._template_width, self._template_height),
                timestamp=timestamp
            )
            
        except cv2.error as e:
            logger.error(f"OpenCV 模板匹配错误: {e}")
            return MatchResult(
                found=False,
                confidence=0.0,
                center_x=0,
                center_y=0,
                bounding_box=(0, 0, 0, 0),
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"模板匹配过程中发生错误: {e}", exc_info=True)
            return MatchResult(
                found=False,
                confidence=0.0,
                center_x=0,
                center_y=0,
                bounding_box=(0, 0, 0, 0),
                timestamp=timestamp
            )
