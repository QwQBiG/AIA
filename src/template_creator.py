"""
模板创建器 - 交互式模板创建工具

本模块提供用户界面功能，允许用户通过鼠标拖拽选择屏幕区域
来创建模板图片，用于后续的模板匹配。

工作流程：
1. 调用 start_selection() 开始选择模式
2. 用户拖拽鼠标选择区域
3. 调用 on_mouse_drag() 更新选择区域
4. 调用 confirm_selection() 保存模板
5. 或调用 cancel_selection() 取消操作

使用示例：
    creator = TemplateCreator(debug_overlay, game_knowledge)
    
    # 开始选择
    screenshot = screen_capturer.capture()
    creator.start_selection(screenshot)
    
    # 用户拖拽后更新区域
    creator.on_mouse_drag(100, 100, 200, 200)
    
    # 确认并保存
    path = creator.confirm_selection("cookie-clicker", "cookie")
"""

import cv2
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TemplateCreator:
    """
    交互式模板创建器
    
    提供用户界面功能，允许用户从截图中选择区域并保存为模板。
    选择的区域必须在 20x20 到 200x200 像素范围内。
    
    属性:
        debug_overlay: 调试覆盖层实例，用于视觉反馈
        game_knowledge: 游戏知识库实例，用于保存模板
    """
    
    def __init__(self, debug_overlay, game_knowledge):
        """
        初始化模板创建器
        
        参数:
            debug_overlay: DebugOverlay 实例，用于显示选择框
            game_knowledge: GameKnowledge 实例，用于保存模板
        """
        self.debug_overlay = debug_overlay
        self.game_knowledge = game_knowledge
        
        # 选择状态
        self._selection_active = False                          # 是否处于选择模式
        self._screenshot: Optional[np.ndarray] = None           # 当前截图
        self._start_pos: Optional[Tuple[int, int]] = None       # 拖拽起始位置
        self._end_pos: Optional[Tuple[int, int]] = None         # 拖拽结束位置
        self._selection_rect: Optional[Tuple[int, int, int, int]] = None  # 选择区域
        
        logger.info("模板创建器初始化完成")
    
    def start_selection(self, screenshot: np.ndarray) -> None:
        """
        开始模板选择模式
        
        参数:
            screenshot: 当前屏幕截图，用户将从中选择区域
        """
        if self._selection_active:
            logger.warning("选择模式已激活")
            return
        
        self._selection_active = True
        self._screenshot = screenshot.copy()
        self._start_pos = None
        self._end_pos = None
        self._selection_rect = None
        
        logger.info("模板选择模式已启动")
    
    def on_mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        """
        处理鼠标拖拽事件，更新选择区域
        
        参数:
            start_x: 拖拽起始 X 坐标
            start_y: 拖拽起始 Y 坐标
            end_x: 拖拽结束 X 坐标
            end_y: 拖拽结束 Y 坐标
        """
        if not self._selection_active:
            logger.warning("选择模式未激活")
            return
        
        self._start_pos = (start_x, start_y)
        self._end_pos = (end_x, end_y)
        
        # 计算矩形区域（确保宽高为正值）
        x = min(start_x, end_x)
        y = min(start_y, end_y)
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)
        
        self._selection_rect = (x, y, width, height)
        
        logger.debug(f"选择区域已更新: {self._selection_rect}")
    
    def confirm_selection(self, game_name: str, template_name: str) -> str:
        """
        确认选择并保存模板
        
        参数:
            game_name: 游戏标识符，用于确定保存位置
            template_name: 模板名称（不含扩展名）
            
        返回:
            保存的模板文件路径
            
        异常:
            ValueError: 选择无效或尺寸超出范围
        """
        if not self._selection_active:
            raise ValueError("没有激活的选择")
        
        if self._selection_rect is None or self._screenshot is None:
            raise ValueError("未定义选择区域")
        
        x, y, width, height = self._selection_rect
        
        # 验证尺寸范围
        if width < 20 or height < 20:
            raise ValueError(f"模板太小: {width}x{height} (最小 20x20)")
        
        if width > 200 or height > 200:
            raise ValueError(f"模板太大: {width}x{height} (最大 200x200)")
        
        # 裁剪选择区域
        cropped = self._screenshot[y:y+height, x:x+width]
        
        # 保存模板
        template_path = self.game_knowledge.save_template(game_name, template_name, cropped)
        
        # 重置选择状态
        self._selection_active = False
        self._screenshot = None
        self._start_pos = None
        self._end_pos = None
        self._selection_rect = None
        
        logger.info(f"模板已保存: {template_path}")
        return template_path
    
    def cancel_selection(self) -> None:
        """取消模板创建，返回正常模式"""
        if not self._selection_active:
            return
        
        self._selection_active = False
        self._screenshot = None
        self._start_pos = None
        self._end_pos = None
        self._selection_rect = None
        
        logger.info("模板选择已取消")
    
    def get_selection_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """
        获取当前选择区域
        
        返回:
            (x, y, width, height) 或 None（如果没有选择）
        """
        return self._selection_rect
    
    def is_active(self) -> bool:
        """检查选择模式是否激活"""
        return self._selection_active
    
    def get_preview(self) -> Optional[np.ndarray]:
        """
        获取选择区域的预览图片
        
        返回:
            裁剪后的图片（numpy 数组）
            None: 没有有效选择
        """
        if not self._selection_active or self._selection_rect is None or self._screenshot is None:
            return None
        
        x, y, width, height = self._selection_rect
        
        # 验证边界
        if width <= 0 or height <= 0:
            return None
        
        if x < 0 or y < 0 or x + width > self._screenshot.shape[1] or y + height > self._screenshot.shape[0]:
            return None
        
        return self._screenshot[y:y+height, x:x+width]
