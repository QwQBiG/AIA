"""
调试覆盖层 - AI VTuber 动作目标可视化

本模块提供透明覆盖窗口，用于可视化 AI 的动作目标位置，
帮助用户看到 AI 打算点击或交互的位置。

核心功能：
- 透明全屏覆盖窗口
- 点击穿透（不影响下层窗口操作）
- 目标位置圆圈指示器
- 拖拽路径显示
- 淡出效果

配置选项：
- enabled: 启用/禁用覆盖层
- circle_radius: 目标圆圈半径
- circle_color: 默认颜色
- display_duration: 显示持续时间（秒）
- fade_effect: 启用淡出效果
- use_click_through: 启用点击穿透

使用示例：
    overlay = DebugOverlay({"enabled": True})
    overlay.start_overlay()
    
    # 显示点击目标
    overlay.show_target(960, 540, "click")
    
    # 显示拖拽路径
    overlay.show_drag_path(100, 100, 500, 500)
"""

import tkinter as tk
import threading
import time
import logging
from typing import Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OverlayTarget:
    """
    覆盖层目标数据类
    
    属性:
        x, y: 目标坐标
        action_type: 动作类型
        timestamp: 创建时间戳
        duration: 显示持续时间（秒）
    """
    x: int
    y: int
    action_type: str
    timestamp: datetime
    duration: float = 0.5


class DebugOverlay:
    """
    调试覆盖层 - 透明窗口用于坐标可视化
    
    在屏幕上显示透明覆盖层，标记 AI 的动作目标位置。
    支持点击穿透，不影响下层窗口的操作。
    
    属性:
        enabled: 是否启用
        circle_radius: 圆圈半径
        display_duration: 显示持续时间
    """
    
    def __init__(self, config: dict = None):
        """
        初始化调试覆盖层
        
        参数:
            config: 配置字典，包含：
                - enabled: 是否启用（默认 True）
                - circle_radius: 圆圈半径（默认 15）
                - circle_color: 默认颜色（默认 "red"）
                - circle_width: 圆圈线宽（默认 3）
                - display_duration: 显示时间（默认 0.5 秒）
                - fade_effect: 淡出效果（默认 True）
                - use_click_through: 点击穿透（默认 True）
                - fallback_to_transient: 回退到临时窗口（默认 True）
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # 覆盖层设置
        self.enabled = self.config.get('enabled', True)
        self.circle_radius = self.config.get('circle_radius', 15)
        self.circle_color = self.config.get('circle_color', 'red')
        self.circle_width = self.config.get('circle_width', 3)
        self.display_duration = self.config.get('display_duration', 0.5)
        self.fade_effect = self.config.get('fade_effect', True)
        self.use_click_through = self.config.get('use_click_through', True)
        self.fallback_to_transient = self.config.get('fallback_to_transient', True)
        
        # 窗口和画布
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        self.overlay_thread: Optional[threading.Thread] = None
        self.running = False
        self.click_through_enabled = False
        
        # 活动目标列表
        self.active_targets = []
        self.target_lock = threading.Lock()
        
        # 屏幕尺寸
        self.screen_width = 1920
        self.screen_height = 1080
        
        self.logger.info("调试覆盖层初始化完成")
    
    def start_overlay(self):
        """在独立线程中启动覆盖层窗口"""
        if not self.enabled:
            self.logger.info("调试覆盖层已在配置中禁用")
            return
        
        if self.running:
            self.logger.warning("调试覆盖层已在运行")
            return
        
        self.running = True
        self.overlay_thread = threading.Thread(target=self._run_overlay, daemon=True)
        self.overlay_thread.start()
        
        self.logger.info("调试覆盖层已启动")
    
    def stop_overlay(self):
        """停止覆盖层窗口"""
        if not self.running:
            return
        
        self.running = False
        
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except Exception as e:
                self.logger.error(f"关闭覆盖层窗口时出错: {e}")
        
        if self.overlay_thread and self.overlay_thread.is_alive():
            self.overlay_thread.join(timeout=2.0)
        
        self.logger.info("调试覆盖层已停止")
    
    def _run_overlay(self):
        """运行覆盖层窗口（在独立线程中）"""
        try:
            self.root = tk.Tk()
            self.root.title("AI VTuber 调试覆盖层")
            
            # 获取屏幕尺寸
            self.screen_width = self.root.winfo_screenwidth()
            self.screen_height = self.root.winfo_screenheight()
            
            # 安全起见：先隐藏窗口
            self.root.geometry("1x1+0+0")
            self.root.withdraw()
            self.root.overrideredirect(True)
            
            # 配置透明度
            self.root.wm_attributes("-transparentcolor", "black")
            self.root.configure(bg='black')
            
            # 测试点击穿透
            if self.use_click_through:
                self.root.update_idletasks()
                self.click_through_enabled = self._make_click_through()
                
                if not self.click_through_enabled:
                    self.logger.error("点击穿透配置失败！禁用覆盖层以防止屏幕阻塞")
                    self.root.destroy()
                    self.running = False
                    return
                else:
                    self.logger.info("点击穿透配置成功")
            else:
                self.click_through_enabled = False
                self.logger.warning("点击穿透已禁用，使用临时窗口回退模式")
                if not self.fallback_to_transient:
                    self.logger.error("点击穿透禁用且无回退方案，禁用覆盖层")
                    self.root.destroy()
                    self.running = False
                    return
            
            # 点击穿透成功后才显示全屏窗口
            if self.click_through_enabled:
                self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
                self.root.wm_attributes("-topmost", True)
                self.root.deiconify()
                
                self.canvas = tk.Canvas(
                    self.root,
                    width=self.screen_width,
                    height=self.screen_height,
                    bg='black',
                    highlightthickness=0
                )
                self.canvas.pack()
                
                self.root.after(50, self._update_overlay)
                self.root.mainloop()
            else:
                self.logger.info("使用临时窗口回退模式")
                self.root.after(100, self._fallback_mode_loop)
                self.root.mainloop()
            
        except Exception as e:
            self.logger.error(f"覆盖层窗口错误: {e}")
            if self.root:
                try:
                    self.root.destroy()
                except:
                    pass
        finally:
            self.running = False
    
    def _fallback_mode_loop(self):
        """回退模式循环"""
        if not self.running:
            return
        self.root.after(100, self._fallback_mode_loop)
    
    def _make_click_through(self) -> bool:
        """
        使用 Windows API 配置点击穿透
        
        返回:
            True: 配置成功
            False: 需要回退
        """
        try:
            # 优先使用 pywin32
            try:
                import win32gui
                import win32con
                
                self.root.update_idletasks()
                hwnd = self.root.winfo_id()
                
                if not hwnd or not win32gui.IsWindow(hwnd):
                    self.logger.error("无效的窗口句柄")
                    return False
                
                try:
                    extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                except Exception as e:
                    self.logger.error(f"获取窗口扩展样式失败: {e}")
                    return False
                
                new_style = extended_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                
                try:
                    result = win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                    if result == 0:
                        error = win32gui.GetLastError()
                        if error != 0:
                            self.logger.error(f"SetWindowLong 失败，错误码: {error}")
                            return False
                    
                    verify_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    if (verify_style & win32con.WS_EX_TRANSPARENT) == 0:
                        self.logger.error("点击穿透样式未正确应用")
                        return False
                    
                    self.logger.info("使用 pywin32 配置点击穿透成功")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"设置窗口扩展样式失败: {e}")
                    return False
                
            except ImportError:
                self.logger.debug("pywin32 不可用，尝试 ctypes")
                
                import ctypes
                
                self.root.update_idletasks()
                hwnd = self.root.winfo_id()
                
                if not hwnd:
                    self.logger.error("无效的窗口句柄")
                    return False
                
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x80000
                WS_EX_TRANSPARENT = 0x20
                
                try:
                    extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    if extended_style == 0:
                        error = ctypes.windll.kernel32.GetLastError()
                        self.logger.error(f"GetWindowLongW 失败，错误码: {error}")
                        return False
                    
                    new_style = extended_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                    
                    result = ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    if result == 0:
                        error = ctypes.windll.kernel32.GetLastError()
                        self.logger.error(f"SetWindowLongW 失败，错误码: {error}")
                        return False
                    
                    verify_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    if (verify_style & WS_EX_TRANSPARENT) == 0:
                        self.logger.error("点击穿透样式未正确应用 (ctypes)")
                        return False
                    
                    self.logger.info("使用 ctypes 配置点击穿透成功")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"ctypes 点击穿透配置失败: {e}")
                    return False
                
        except Exception as e:
            self.logger.error(f"配置点击穿透窗口失败: {e}")
            return False
    
    def _show_transient_target(self, x: int, y: int, action_type: str, duration: float):
        """
        回退方案：在目标位置显示小型临时窗口
        
        参数:
            x, y: 目标坐标
            action_type: 动作类型
            duration: 显示时间
        """
        try:
            from .pink_theme import PINK_THEME
            
            transient = tk.Toplevel()
            transient.title("")
            transient.overrideredirect(True)
            transient.attributes("-topmost", True)
            transient.attributes("-alpha", 0.7)
            transient.bind("<FocusIn>", lambda e: self.root.focus_set() if self.root else None)
            
            size = self.circle_radius * 2 + 10
            transient.geometry(f"{size}x{size}+{x-size//2}+{y-size//2}")
            
            canvas = tk.Canvas(
                transient,
                width=size,
                height=size,
                bg=PINK_THEME['bg_darkest'],
                highlightthickness=0
            )
            canvas.pack()
            
            color = self._get_action_color(action_type)
            canvas.create_oval(
                5, 5, size-5, size-5,
                outline=color,
                width=self.circle_width,
                fill=""
            )
            
            def destroy_transient():
                try:
                    if transient.winfo_exists():
                        transient.destroy()
                except:
                    pass
            
            transient.after(int(duration * 1000), destroy_transient)
            self.logger.debug(f"创建临时目标窗口: ({x}, {y})")
            
        except Exception as e:
            self.logger.error(f"创建临时目标窗口失败: {e}")
    
    def _update_overlay(self):
        """更新覆盖层显示（定期调用）"""
        if not self.running or not self.canvas:
            return
        
        try:
            self.canvas.delete("all")
            current_time = datetime.now()
            
            with self.target_lock:
                # 移除过期目标
                self.active_targets = [
                    target for target in self.active_targets
                    if (current_time - target.timestamp).total_seconds() < target.duration
                ]
                
                # 绘制活动目标
                for target in self.active_targets:
                    self._draw_target(target, current_time)
            
            if self.running:
                self.root.after(50, self._update_overlay)
                
        except Exception as e:
            self.logger.error(f"覆盖层更新错误: {e}")
    
    def _draw_target(self, target: OverlayTarget, current_time: datetime):
        """绘制目标指示器"""
        if not self.canvas:
            return
        
        try:
            # 计算淡出效果
            alpha = 1.0
            if self.fade_effect:
                elapsed = (current_time - target.timestamp).total_seconds()
                alpha = max(0.0, 1.0 - (elapsed / target.duration))
            
            color = self._get_action_color(target.action_type)
            
            # 处理拖拽线
            if target.action_type == "drag_line" and hasattr(target, 'x2') and hasattr(target, 'y2'):
                self.canvas.create_line(
                    target.x, target.y,
                    target.x2, target.y2,
                    fill=color,
                    width=self.circle_width,
                    arrow=tk.LAST
                )
                return
            
            # 绘制圆圈
            x, y = target.x, target.y
            radius = self.circle_radius
            
            if 0 <= x <= self.screen_width and 0 <= y <= self.screen_height:
                self.canvas.create_oval(
                    x - radius, y - radius,
                    x + radius, y + radius,
                    outline=color,
                    width=self.circle_width,
                    fill=""
                )
                
                # 添加动作类型标签
                if target.action_type not in ["click", "drag_start", "drag_end"]:
                    self.canvas.create_text(
                        x, y - radius - 10,
                        text=target.action_type.upper(),
                        fill=color,
                        font=("Arial", 8, "bold")
                    )
        
        except Exception as e:
            self.logger.error(f"绘制目标时出错: {e}")
    
    def _get_action_color(self, action_type: str) -> str:
        """获取不同动作类型的颜色"""
        color_map = {
            'click': 'red',
            'drag': 'blue',
            'drag_start': 'blue',
            'drag_end': 'blue',
            'drag_line': 'blue',
            'scroll': 'green',
            'keypress': 'yellow',
            'wait': 'gray'
        }
        return color_map.get(action_type.lower(), 'red')
    
    def show_target(self, x: int, y: int, action_type: str = "click", duration: float = None):
        """
        在指定坐标显示目标指示器
        
        参数:
            x, y: 目标坐标
            action_type: 动作类型
            duration: 显示时间（使用默认值如果为 None）
        """
        if not self.enabled or not self.running:
            return
        
        if duration is None:
            duration = self.display_duration
        
        # 安全检查：如果点击穿透失败，使用临时窗口
        if not self.click_through_enabled or not self.use_click_through:
            self._show_transient_target(x, y, action_type, duration)
            return
        
        if self.canvas is not None:
            target = OverlayTarget(
                x=x,
                y=y,
                action_type=action_type,
                timestamp=datetime.now(),
                duration=duration
            )
            
            with self.target_lock:
                self.active_targets.append(target)
            
            self.logger.debug(f"显示目标: {action_type} 位置 ({x}, {y}) 持续 {duration}秒")
        else:
            self._show_transient_target(x, y, action_type, duration)
    
    def show_drag_path(self, x1: int, y1: int, x2: int, y2: int, duration: float = None):
        """
        显示拖拽路径
        
        参数:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 显示时间
        """
        if not self.enabled or not self.running:
            return
        
        if duration is None:
            duration = self.display_duration
        
        # 显示起点
        self.show_target(x1, y1, "drag_start", duration)
        
        # 显示终点
        self.show_target(x2, y2, "drag_end", duration)
        
        # 显示路径线
        try:
            with self.target_lock:
                line_target = OverlayTarget(
                    x=x1,
                    y=y1,
                    action_type="drag_line",
                    timestamp=datetime.now(),
                    duration=duration
                )
                line_target.x2 = x2
                line_target.y2 = y2
                self.active_targets.append(line_target)
                
        except Exception as e:
            self.logger.error(f"显示拖拽路径时出错: {e}")
    
    def clear_targets(self):
        """清除所有活动目标指示器"""
        with self.target_lock:
            self.active_targets.clear()
        self.logger.debug("所有目标指示器已清除")
    
    def is_running(self) -> bool:
        """检查覆盖层是否正在运行"""
        return self.running
    
    def update_config(self, new_config: dict):
        """更新覆盖层配置"""
        self.config.update(new_config)
        
        self.enabled = self.config.get('enabled', self.enabled)
        self.circle_radius = self.config.get('circle_radius', self.circle_radius)
        self.circle_color = self.config.get('circle_color', self.circle_color)
        self.circle_width = self.config.get('circle_width', self.circle_width)
        self.display_duration = self.config.get('display_duration', self.display_duration)
        self.fade_effect = self.config.get('fade_effect', self.fade_effect)
        self.use_click_through = self.config.get('use_click_through', self.use_click_through)
        self.fallback_to_transient = self.config.get('fallback_to_transient', self.fallback_to_transient)
        
        self.logger.info("调试覆盖层配置已更新")
    
    def cleanup(self):
        """清理覆盖层资源"""
        self.stop_overlay()
        self.logger.info("调试覆盖层清理完成")


def create_debug_overlay(config: dict = None) -> DebugOverlay:
    """
    创建调试覆盖层实例的便捷函数
    
    参数:
        config: 配置字典
        
    返回:
        DebugOverlay 实例
    """
    return DebugOverlay(config)
