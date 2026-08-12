"""
反射引擎 - 高速游戏动作执行系统

本模块实现了"快速循环"（Fast Loop），以 20Hz 频率运行，
在独立线程中执行模板匹配和动作执行，实现实时游戏交互。

核心特性：
- 20Hz 高频循环（每 50ms 一次迭代）
- 独立线程运行，不阻塞主程序
- ROI 优化：基于上次匹配位置缩小搜索范围
- 资源锁定：与 VLM 动作协调，避免鼠标冲突
- 性能监控：记录循环时间、成功率等指标

支持的动作类型：
- click_repeat: 持续点击（找到目标就点击）
- click_once: 单次点击（点击后停止）
- hover: 悬停（移动鼠标但不点击）
"""

import threading
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReflexStatus:
    """反射引擎状态信息"""
    active: bool
    target_found: bool
    confidence: float
    last_match_coords: Optional[Tuple[int, int]]
    avg_loop_time: float
    actions_per_second: float
    match_success_rate: float
    consecutive_failures: int


class ReflexEngine:
    """
    反射引擎 - 协调快速循环的模板匹配和动作执行
    
    在独立线程中以约 20Hz 频率运行，实现实时游戏交互。
    """
    
    def __init__(self, action_engine, screen_capturer, template_matcher=None, safety_manager=None):
        """
        初始化反射引擎
        
        参数:
            action_engine: ActionEngine 实例
            screen_capturer: ScreenCapturer 实例
            template_matcher: TemplateMatcher 实例（可选）
            safety_manager: SafetyManager 实例（可选）
        """
        self.action_engine = action_engine
        self.screen_capturer = screen_capturer
        self.safety_manager = safety_manager
        
        if template_matcher is None:
            from .template_matcher import TemplateMatcher
            self.template_matcher = TemplateMatcher()
        else:
            self.template_matcher = template_matcher
        
        # 线程管理
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._active = False
        self._lock = threading.Lock()
        self._reflex_lock = threading.Lock()
        
        # 配置
        self._template_path: Optional[str] = None
        self._action_type: Optional[str] = None
        self._region: Optional[Tuple[int, int, int, int]] = None
        
        # 性能指标
        self._loop_times = []
        self._max_loop_times = 100
        self._actions_executed = 0
        self._matches_found = 0
        self._matches_attempted = 0
        self._consecutive_failures = 0
        self._last_match_coords: Optional[Tuple[int, int]] = None
        self._last_confidence = 0.0
        self._start_time = 0.0
        
        # ROI 追踪
        self._last_roi: Optional[Tuple[int, int, int, int]] = None
        self._roi_size = 200
        self._roi_failures = 0
        self._roi_max_failures = 3
        
        logger.info("反射引擎初始化完成")
    
    def start(self, template_path: str, action_type: str, 
              region: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """启动快速循环"""
        if self._active:
            logger.warning("反射引擎已在运行中")
            return False
        
        valid_actions = ["click_repeat", "click_once", "hover"]
        if action_type not in valid_actions:
            logger.error(f"无效的动作类型: {action_type}")
            return False
        
        try:
            if not self.template_matcher.load_template(template_path):
                logger.error(f"模板加载失败: {template_path}")
                return False
        except Exception as e:
            logger.error(f"加载模板时发生错误: {e}")
            return False
        
        self._template_path = template_path
        self._action_type = action_type
        self._region = region
        
        self._stop_event.clear()
        self._active = True
        self._loop_times.clear()
        self._actions_executed = 0
        self._matches_found = 0
        self._matches_attempted = 0
        self._consecutive_failures = 0
        self._last_match_coords = None
        self._last_confidence = 0.0
        self._start_time = time.perf_counter()
        
        self._thread = threading.Thread(target=self._fast_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"反射引擎已启动，模板={template_path}，动作={action_type}")
        return True
    
    def stop(self) -> None:
        """停止快速循环"""
        if not self._active:
            return
        
        logger.info("正在停止反射引擎")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
            if self._thread.is_alive():
                logger.warning("反射引擎线程未能优雅终止")
        
        self._active = False
        logger.info("反射引擎已停止")
    
    def update_template(self, template_path: str) -> bool:
        """运行中更换模板"""
        if not self._active:
            logger.warning("无法更新模板：反射引擎未运行")
            return False
        
        try:
            with self._lock:
                if not self.template_matcher.load_template(template_path):
                    logger.error(f"新模板加载失败: {template_path}")
                    return False
                self._template_path = template_path
                self._last_roi = None
                logger.info(f"模板已更新为: {template_path}")
                return True
        except Exception as e:
            logger.error(f"更新模板时发生错误: {e}")
            return False
    
    def pause_for_vlm_action(self):
        """暂停以执行 VLM 动作"""
        logger.debug("暂停反射引擎以执行 VLM 动作")
        self._reflex_lock.acquire()
    
    def resume_after_vlm_action(self):
        """VLM 动作完成后恢复"""
        logger.debug("VLM 动作完成，恢复反射引擎")
        try:
            self._reflex_lock.release()
        except RuntimeError:
            pass
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态和性能指标"""
        avg_loop_time = sum(self._loop_times) / len(self._loop_times) if self._loop_times else 0.0
        total_time = sum(self._loop_times) if self._loop_times else 1.0
        actions_per_second = self._actions_executed / total_time if total_time > 0 else 0.0
        match_success_rate = (self._matches_found / self._matches_attempted) if self._matches_attempted > 0 else 0.0
        
        return {
            "active": self._active,
            "target_found": self._consecutive_failures < 10,
            "confidence": self._last_confidence,
            "last_match_coords": self._last_match_coords,
            "avg_loop_time": avg_loop_time,
            "actions_per_second": actions_per_second,
            "match_success_rate": match_success_rate,
            "consecutive_failures": self._consecutive_failures
        }
    
    def _fast_loop(self) -> None:
        """主快速循环（约 20Hz）"""
        target_interval = 0.05
        
        while not self._stop_event.is_set():
            loop_start = time.perf_counter()
            
            try:
                if self.safety_manager and self.safety_manager.is_emergency_active():
                    logger.warning("检测到紧急停止，终止快速循环")
                    self._active = False
                    break
                
                try:
                    import numpy as np
                    screenshot = self.screen_capturer.capture()
                    if not isinstance(screenshot, np.ndarray):
                        screenshot = np.array(screenshot)
                except Exception as e:
                    logger.error(f"截图失败: {e}")
                    self._consecutive_failures += 1
                    continue
                
                self._matches_attempted += 1
                search_region = self._get_search_region()
                
                try:
                    match_result = self.template_matcher.find_match(screenshot, search_region)
                    
                    if match_result.found:
                        self._matches_found += 1
                        self._consecutive_failures = 0
                        self._roi_failures = 0
                        self._last_match_coords = (match_result.center_x, match_result.center_y)
                        self._last_confidence = match_result.confidence
                        self._update_roi(match_result.center_x, match_result.center_y)
                        self._execute_action_with_lock(match_result.center_x, match_result.center_y)
                        
                        if self._action_type == "click_once":
                            logger.info("单次点击完成，停止反射引擎")
                            self._stop_event.set()
                            break
                    else:
                        self._consecutive_failures += 1
                        self._last_confidence = match_result.confidence
                        
                        if search_region is not None:
                            self._roi_failures += 1
                            if self._roi_failures >= self._roi_max_failures:
                                logger.debug("ROI 搜索失败，回退到全屏搜索")
                                self._last_roi = None
                                self._roi_failures = 0
                        
                        if self._consecutive_failures == 10:
                            logger.warning("目标丢失：连续 10 次匹配失败")
                            
                except Exception as e:
                    logger.error(f"模板匹配失败: {e}")
                    self._consecutive_failures += 1
                
            except Exception as e:
                logger.error(f"快速循环错误: {e}", exc_info=True)
                self._consecutive_failures += 1
            
            loop_time = time.perf_counter() - loop_start
            self._record_loop_time(loop_time)
            
            sleep_time = max(0, target_interval - loop_time)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.info("快速循环已终止")
    
    def _get_search_region(self) -> Optional[Tuple[int, int, int, int]]:
        """获取搜索区域"""
        if self._region:
            return self._region
        if self._last_roi:
            return self._last_roi
        return None
    
    def _update_roi(self, center_x: int, center_y: int):
        """更新 ROI"""
        half_size = self._roi_size // 2
        x = max(0, center_x - half_size)
        y = max(0, center_y - half_size)
        self._last_roi = (x, y, self._roi_size, self._roi_size)
    
    def _execute_action_with_lock(self, x: int, y: int) -> None:
        """带锁执行动作"""
        if self._reflex_lock.acquire(timeout=1.0):
            try:
                self._execute_action(x, y)
            finally:
                self._reflex_lock.release()
        else:
            logger.debug("无法获取反射锁，跳过本次动作")
    
    def _execute_action(self, x: int, y: int) -> None:
        """执行动作"""
        try:
            if self._action_type in ["click_repeat", "click_once"]:
                import pydirectinput
                pydirectinput.click(x, y)
                self._actions_executed += 1
                logger.debug(f"点击位置 ({x}, {y})")
            elif self._action_type == "hover":
                import pydirectinput
                pydirectinput.moveTo(x, y)
                self._actions_executed += 1
                logger.debug(f"移动到 ({x}, {y})")
        except Exception as e:
            logger.error(f"动作执行失败: {e}")
    
    def _record_loop_time(self, loop_time: float) -> None:
        """记录循环时间"""
        self._loop_times.append(loop_time)
        if len(self._loop_times) > self._max_loop_times:
            self._loop_times.pop(0)
        if loop_time > 0.1:
            logger.warning(f"快速循环迭代超时: {loop_time:.3f}秒")
