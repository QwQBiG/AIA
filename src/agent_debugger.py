"""
Agent Debugger & Visual Calibration Tool

This module provides a visual debugging window for diagnosing AI Vision-Action Agent
decision processes, including real-time screenshot annotation, VLM response logging,
step-by-step debugging, and coordinate calibration tools.
"""

import json
import logging
import time
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, asdict
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw

from .vision_client import AgentCommand


@dataclass
class DebuggerConfig:
    """调试器配置"""
    window_width: int = 1200
    window_height: int = 800
    window_x: int = 100  # 窗口X位置
    window_y: int = 100  # 窗口Y位置
    min_width: int = 800
    min_height: int = 600
    topmost: bool = True
    dpi_scale_factor: float = 1.0
    screenshot_panel_ratio: float = 0.6  # 左侧截图面板占比
    log_max_entries: int = 100
    config_file_path: str = "debugger_config.json"


@dataclass
class TimingMetrics:
    """性能计时指标"""
    screenshot_time: float  # 截图耗时（秒）
    vlm_inference_time: float  # VLM 推理耗时（秒）
    action_execution_time: float  # 动作执行耗时（秒）
    total_cycle_time: float  # 总周期耗时（秒）
    timestamp: datetime


@dataclass
class PendingAction:
    """待确认的动作"""
    command: AgentCommand
    screenshot_b64: str
    timing: TimingMetrics
    created_at: datetime


class AnnotationRenderer:
    """在截图上绘制标注的渲染器"""
    
    @staticmethod
    def draw_target_marker(image: Image.Image, x: int, y: int, 
                          scale_factor: float = 1.0) -> Image.Image:
        """
        绘制绿色靶心标记
        
        Args:
            image: PIL Image 对象
            x, y: 目标坐标（原始屏幕坐标）
            scale_factor: 图像缩放比例
            
        Returns:
            带标注的 PIL Image
        """
        # Create a copy to avoid modifying the original
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        # Scale coordinates
        scaled_x = int(x * scale_factor)
        scaled_y = int(y * scale_factor)
        
        # Draw green crosshair (靶心)
        marker_size = 20
        line_width = 3
        color = "green"
        
        # Horizontal line
        draw.line([
            (scaled_x - marker_size, scaled_y),
            (scaled_x + marker_size, scaled_y)
        ], fill=color, width=line_width)
        
        # Vertical line
        draw.line([
            (scaled_x, scaled_y - marker_size),
            (scaled_x, scaled_y + marker_size)
        ], fill=color, width=line_width)
        
        # Center circle
        circle_radius = 5
        draw.ellipse([
            (scaled_x - circle_radius, scaled_y - circle_radius),
            (scaled_x + circle_radius, scaled_y + circle_radius)
        ], outline=color, width=line_width)
        
        return annotated_image
    
    @staticmethod
    def draw_bounding_box(image: Image.Image, x: int, y: int, 
                         w: int, h: int, scale_factor: float = 1.0) -> Image.Image:
        """
        绘制黄色边界框
        
        Args:
            image: PIL Image 对象
            x, y, w, h: 边界框参数（原始屏幕坐标）
            scale_factor: 图像缩放比例
            
        Returns:
            带标注的 PIL Image
        """
        # Create a copy to avoid modifying the original
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        # Scale coordinates
        scaled_x = int(x * scale_factor)
        scaled_y = int(y * scale_factor)
        scaled_w = int(w * scale_factor)
        scaled_h = int(h * scale_factor)
        
        # Draw yellow rectangle
        color = "yellow"
        line_width = 2
        
        draw.rectangle([
            (scaled_x, scaled_y),
            (scaled_x + scaled_w, scaled_y + scaled_h)
        ], outline=color, width=line_width)
        
        return annotated_image
    
    @staticmethod
    def draw_drift_vector(image: Image.Image, target_x: int, target_y: int,
                         actual_x: int, actual_y: int, scale_factor: float = 1.0) -> Image.Image:
        """
        绘制漂移向量（蓝色十字 + 连线）
        显示 AI 目标位置与实际鼠标位置的差异
        
        Args:
            image: PIL Image 对象
            target_x, target_y: AI 目标坐标
            actual_x, actual_y: 实际鼠标坐标
            scale_factor: 图像缩放比例
            
        Returns:
            带标注的 PIL Image
        """
        # Create a copy to avoid modifying the original
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        # Scale coordinates
        scaled_target_x = int(target_x * scale_factor)
        scaled_target_y = int(target_y * scale_factor)
        scaled_actual_x = int(actual_x * scale_factor)
        scaled_actual_y = int(actual_y * scale_factor)
        
        # Draw blue crosshair at actual position
        marker_size = 15
        line_width = 2
        color = "blue"
        
        # Horizontal line
        draw.line([
            (scaled_actual_x - marker_size, scaled_actual_y),
            (scaled_actual_x + marker_size, scaled_actual_y)
        ], fill=color, width=line_width)
        
        # Vertical line
        draw.line([
            (scaled_actual_x, scaled_actual_y - marker_size),
            (scaled_actual_x, scaled_actual_y + marker_size)
        ], fill=color, width=line_width)
        
        # Draw connecting line from target to actual
        draw.line([
            (scaled_target_x, scaled_target_y),
            (scaled_actual_x, scaled_actual_y)
        ], fill=color, width=line_width)
        
        return annotated_image


class AgentDebugger:
    """Agent 调试窗口主控制器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, parent: Optional[tk.Tk] = None, agent_manager=None):
        """
        初始化调试窗口
        
        Args:
            config: 配置字典，包含窗口设置和 DPI 缩放因子
            parent: 父窗口（主 GUI），如果提供则创建 Toplevel，否则创建独立窗口
            agent_manager: Agent管理器实例，用于调试和控制
        """
        # Initialize logger first
        self.logger = logging.getLogger(__name__)
        
        # Store parent window reference and agent manager
        self.parent = parent
        self.agent_manager = agent_manager
        
        # Load configuration from file first, then override with provided config
        self.config = self._load_config()
        
        if config:
            # Update config with provided values
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        
        # Initialize window components
        self.root: Optional[tk.Toplevel] = None  # Changed to Toplevel
        self.screenshot_canvas: Optional[tk.Canvas] = None
        self.thought_log: Optional[scrolledtext.ScrolledText] = None
        self.control_frame: Optional[tk.Frame] = None
        
        # State management
        self.current_image: Optional[Image.Image] = None
        self.current_command: Optional[AgentCommand] = None
        self.log_entries: List[Dict[str, Any]] = []
        self.last_raw_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None
        
        # Drift vector tracking
        self.drift_vector_data: Optional[Dict[str, int]] = None
        
        # Step mode controller (will be initialized when needed)
        self.step_controller: Optional['StepController'] = None
        self.calibration_tool: Optional['CalibrationTool'] = None
        
        # UI update queue for thread-safe UI updates
        self.ui_update_queue: queue.Queue = queue.Queue()
        self._queue_processor_running = False
        
        # Keep a strong reference to PhotoImage to prevent garbage collection
        self._current_photo: Optional[ImageTk.PhotoImage] = None
        self._canvas_image_id: Optional[int] = None  # Track canvas image item ID
        self._current_pil_image: Optional[Image.Image] = None  # Keep PIL image alive too
    
    def show(self) -> None:
        """显示调试窗口"""
        if self.root is None:
            self._create_window()
        
        self.root.deiconify()
        self.root.lift()
    
    def hide(self) -> None:
        """隐藏调试窗口"""
        if self.root:
            self.root.withdraw()
    
    def _create_window(self) -> None:
        """创建主窗口界面"""
        from .pink_theme import PINK_THEME
        
        # Create Toplevel if parent exists, otherwise create standalone Tk window
        if self.parent:
            self.root = tk.Toplevel(self.parent)
            self.logger.info("Created Toplevel debugger window (child of main GUI)")
        else:
            self.root = tk.Tk()
            self.logger.info("Created standalone debugger window (for testing)")
        
        self.root.title("Agent Debugger")
        
        # Apply pink theme to root window
        self.root.config(bg=PINK_THEME['debugger_bg'])
        
        # Set window size and position from config
        geometry_str = f"{self.config.window_width}x{self.config.window_height}+{self.config.window_x}+{self.config.window_y}"
        self.root.geometry(geometry_str)
        self.root.minsize(self.config.min_width, self.config.min_height)
        
        if self.config.topmost:
            self.root.attributes('-topmost', True)
        
        # Create main paned window with pink theme
        main_paned = tk.PanedWindow(
            self.root, 
            orient=tk.HORIZONTAL,
            bg=PINK_THEME['debugger_bg'],
            sashwidth=5,
            sashrelief=tk.RAISED,
            bd=0
        )
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Screenshot with pink theme
        screenshot_frame = tk.LabelFrame(
            main_paned, 
            text="Screenshot Panel",
            bg=PINK_THEME['debugger_panel'],
            fg=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 10, "bold"),
            bd=2,
            relief=tk.GROOVE,
            labelanchor=tk.N
        )
        screenshot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.screenshot_canvas = tk.Canvas(
            screenshot_frame, 
            bg=PINK_THEME['bg_darkest'],
            highlightthickness=0
        )
        self.screenshot_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Use a Label to display images instead of Canvas - more reliable with PhotoImage
        self.screenshot_label = tk.Label(
            self.screenshot_canvas,
            bg=PINK_THEME['bg_darkest'],
            anchor=tk.CENTER
        )
        self.screenshot_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Right panel - Thought Log with pink theme
        log_frame = tk.LabelFrame(
            main_paned, 
            text="Thought Log",
            bg=PINK_THEME['debugger_panel'],
            fg=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 10, "bold"),
            bd=2,
            relief=tk.GROOVE,
            labelanchor=tk.N
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.thought_log = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=PINK_THEME['log_bg'],
            fg=PINK_THEME['text_primary'],
            insertbackground=PINK_THEME['primary'],
            selectbackground=PINK_THEME['primary'],
            selectforeground=PINK_THEME['text_primary']
        )
        self.thought_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add panels to paned window
        main_paned.add(screenshot_frame, width=int(self.config.window_width * self.config.screenshot_panel_ratio))
        main_paned.add(log_frame, width=int(self.config.window_width * (1 - self.config.screenshot_panel_ratio)))
        
        # Control bar at bottom
        self._create_control_bar()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Start UI update queue processor
        self._start_queue_processor()
    
    def _start_queue_processor(self) -> None:
        """启动UI更新队列处理器"""
        if not self._queue_processor_running and self.root:
            self._queue_processor_running = True
            self._process_ui_queue()
    
    def _process_ui_queue(self) -> None:
        """处理UI更新队列（在主线程中运行）"""
        if not self._queue_processor_running or not self.root:
            return
        
        try:
            # Process all pending UI updates
            while not self.ui_update_queue.empty():
                try:
                    update_func = self.ui_update_queue.get_nowait()
                    if callable(update_func):
                        update_func()
                except queue.Empty:
                    break
                except Exception as e:
                    self.logger.error(f"Error processing UI update: {e}")
        except Exception as e:
            self.logger.error(f"Error in queue processor: {e}")
        
        # Schedule next queue check
        if self.root and self._queue_processor_running:
            self.root.after(50, self._process_ui_queue)
    
    def _create_control_bar(self) -> None:
        """创建底部控制栏"""
        from .pink_theme import PINK_THEME
        from .tooltip import create_tooltip
        
        self.control_frame = tk.Frame(self.root, bg=PINK_THEME['debugger_panel'])
        self.control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Step mode controls
        self.manual_step_button = tk.Button(
            self.control_frame, 
            text="单步执行", 
            command=self._on_manual_step,
            bg=PINK_THEME['button_primary'],
            fg=PINK_THEME['text_primary'],
            activebackground=PINK_THEME['primary_hover'],
            activeforeground=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5
        )
        self.manual_step_button.pack(side=tk.LEFT, padx=5)
        create_tooltip(self.manual_step_button, "manual_step")
        
        # User instruction input
        instruction_label = tk.Label(
            self.control_frame,
            text="💬 指令:",
            bg=PINK_THEME['debugger_panel'],
            fg=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9, "bold")
        )
        instruction_label.pack(side=tk.LEFT, padx=5)
        
        self.user_instruction_var = tk.StringVar(value="点击饼干")
        self.instruction_entry = tk.Entry(
            self.control_frame,
            textvariable=self.user_instruction_var,
            width=20,
            bg=PINK_THEME['input_bg'],
            fg=PINK_THEME['input_text'],
            insertbackground=PINK_THEME['primary'],
            selectbackground=PINK_THEME['primary'],
            selectforeground=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.SUNKEN,
            bd=2
        )
        self.instruction_entry.pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to execute step with instruction
        self.instruction_entry.bind('<Return>', lambda e: self._on_manual_step())
        
        # Separator
        tk.Frame(
            self.control_frame, 
            width=2, 
            bg=PINK_THEME['border'],
            relief=tk.SUNKEN
        ).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.execute_button = tk.Button(
            self.control_frame, 
            text="执行动作", 
            command=self._on_execute,
            state=tk.DISABLED,
            bg=PINK_THEME['button_success'],
            fg=PINK_THEME['text_primary'],
            activebackground=PINK_THEME['primary_hover'],
            activeforeground=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5
        )
        self.execute_button.pack(side=tk.LEFT, padx=5)
        create_tooltip(self.execute_button, "execute")
        
        # Status indicator for pending actions
        self.status_label = tk.Label(
            self.control_frame, 
            text="无待定动作",
            fg=PINK_THEME['text_secondary'],
            bg=PINK_THEME['debugger_panel'],
            font=("Microsoft YaHei", 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Separator
        tk.Frame(
            self.control_frame, 
            width=2, 
            bg=PINK_THEME['border'],
            relief=tk.SUNKEN
        ).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Calibration controls
        test_center_btn = tk.Button(
            self.control_frame, 
            text="测试中心点击", 
            command=self._on_test_center_click,
            bg=PINK_THEME['button_info'],
            fg=PINK_THEME['text_primary'],
            activebackground=PINK_THEME['primary_hover'],
            activeforeground=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5
        )
        test_center_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(test_center_btn, "test_center")
        
        # DPI Scale input
        dpi_label = tk.Label(
            self.control_frame, 
            text="DPI 缩放:",
            bg=PINK_THEME['debugger_panel'],
            fg=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9)
        )
        dpi_label.pack(side=tk.LEFT, padx=5)
        create_tooltip(dpi_label, "dpi_scale")
        
        self.dpi_var = tk.StringVar(value=str(self.config.dpi_scale_factor))
        dpi_entry = tk.Entry(
            self.control_frame, 
            textvariable=self.dpi_var, 
            width=8,
            bg=PINK_THEME['input_bg'],
            fg=PINK_THEME['input_text'],
            insertbackground=PINK_THEME['primary'],
            selectbackground=PINK_THEME['primary'],
            selectforeground=PINK_THEME['text_primary'],
            font=("Consolas", 9),
            relief=tk.SUNKEN,
            bd=2
        )
        dpi_entry.pack(side=tk.LEFT, padx=5)
        
        apply_btn = tk.Button(
            self.control_frame, 
            text="应用", 
            command=self._on_apply_dpi,
            bg=PINK_THEME['button_secondary'],
            fg=PINK_THEME['text_primary'],
            activebackground=PINK_THEME['secondary_hover'],
            activeforeground=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5
        )
        apply_btn.pack(side=tk.LEFT, padx=5)
        
        # Separator
        tk.Frame(
            self.control_frame, 
            width=2, 
            bg=PINK_THEME['border'],
            relief=tk.SUNKEN
        ).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Show Raw button
        show_raw_btn = tk.Button(
            self.control_frame, 
            text="查看原始数据", 
            command=self._on_show_raw,
            bg=PINK_THEME['button_info'],
            fg=PINK_THEME['text_primary'],
            activebackground=PINK_THEME['primary_hover'],
            activeforeground=PINK_THEME['text_primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5
        )
        show_raw_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(show_raw_btn, "show_raw")
        
        # Separator
        tk.Frame(
            self.control_frame, 
            width=2, 
            bg=PINK_THEME['border'],
            relief=tk.SUNKEN
        ).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Topmost toggle
        self.topmost_var = tk.BooleanVar(value=self.config.topmost)
        topmost_check = tk.Checkbutton(
            self.control_frame, 
            text="窗口置顶", 
            variable=self.topmost_var,
            command=self._on_toggle_topmost,
            bg=PINK_THEME['debugger_panel'],
            fg=PINK_THEME['text_primary'],
            selectcolor=PINK_THEME['bg_medium'],
            activebackground=PINK_THEME['debugger_panel'],
            activeforeground=PINK_THEME['primary'],
            font=("Microsoft YaHei", 9),
            relief=tk.FLAT
        )
        topmost_check.pack(side=tk.LEFT, padx=5)
        create_tooltip(topmost_check, "always_on_top")
        
        # Mouse position display
        self.mouse_pos_label = tk.Label(
            self.control_frame, 
            text="当前鼠标: (0, 0)",
            bg=PINK_THEME['debugger_panel'],
            fg=PINK_THEME['text_secondary'],
            font=("Consolas", 9)
        )
        self.mouse_pos_label.pack(side=tk.RIGHT, padx=5)
        
        # Start mouse position tracking
        self._start_mouse_tracking()
    
    def update_drift_vector(self, target_x: int, target_y: int, actual_x: int, actual_y: int) -> None:
        """
        Update drift vector data from ActionEngine
        
        Args:
            target_x, target_y: AI intended target coordinates
            actual_x, actual_y: Actual mouse position after action
        """
        self.drift_vector_data = {
            'target_x': target_x,
            'target_y': target_y,
            'actual_x': actual_x,
            'actual_y': actual_y
        }
        
        # Calculate drift distance for logging
        drift_distance = ((actual_x - target_x) ** 2 + (actual_y - target_y) ** 2) ** 0.5
        
        self.logger.debug(f"Drift vector updated: target({target_x}, {target_y}) -> actual({actual_x}, {actual_y}), distance: {drift_distance:.1f}px")
        
        # Log drift information
        if drift_distance > 5:  # Only log significant drift
            self._log_message(f"DRIFT DETECTED: {drift_distance:.1f}px offset from target", "WARNING")
        
        # Refresh screenshot display to show drift vector
        if self.current_image:
            self._display_image_in_canvas(self.current_image)
    
    def update_screenshot(self, image_b64: str, command: Optional[AgentCommand] = None) -> None:
        """
        更新截图显示并绘制标注
        
        Args:
            image_b64: Base64 编码的截图
            command: 可选的 AgentCommand，用于绘制标注
        """
        # Queue the screenshot update to run in the main thread
        # This is CRITICAL because PhotoImage must be created in the main thread
        def do_update():
            try:
                import base64
                from io import BytesIO
                
                # Decode base64 image
                image_data = base64.b64decode(image_b64)
                image = Image.open(BytesIO(image_data))
                
                # Store current state
                self.current_image = image.copy()  # Make a copy to keep
                self.current_command = command
                
                # Apply annotations if command is provided
                annotated_image = image.copy()
                if command:
                    # Draw target marker for click actions
                    if hasattr(command, 'action') and command.action in ['click', 'drag']:
                        if hasattr(command, 'x') and hasattr(command, 'y'):
                            annotated_image = AnnotationRenderer.draw_target_marker(
                                annotated_image, command.x, command.y, 1.0
                            )
                    
                    # Draw bounding box if available
                    if hasattr(command, 'bounding_box') and command.bounding_box:
                        bbox = command.bounding_box
                        annotated_image = AnnotationRenderer.draw_bounding_box(
                            annotated_image, bbox['x'], bbox['y'], bbox['w'], bbox['h'], 1.0
                        )
                
                # Apply drift vector annotation if available
                if self.drift_vector_data:
                    annotated_image = AnnotationRenderer.draw_drift_vector(
                        annotated_image,
                        self.drift_vector_data['target_x'],
                        self.drift_vector_data['target_y'],
                        self.drift_vector_data['actual_x'],
                        self.drift_vector_data['actual_y'],
                        1.0
                    )
                
                # Display in canvas - NOW running in main thread
                self._display_image_in_canvas(annotated_image)
                
            except Exception as e:
                self.logger.error(f"Failed to update screenshot: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self._log_message(f"Screenshot update error: {e}", "ERROR")
        
        # Queue the update to run in main thread
        self.ui_update_queue.put(do_update)
    
    def _display_image_in_canvas(self, image: Image.Image) -> None:
        """在 Canvas 中显示图像，保持宽高比"""
        if not self.screenshot_canvas or not self.screenshot_label:
            self.logger.warning("Canvas or Label not available")
            return
        
        try:
            import gc
            
            # Temporarily disable garbage collection to prevent PhotoImage from being collected
            gc_was_enabled = gc.isenabled()
            gc.disable()
            
            try:
                # Get canvas dimensions
                canvas_width = self.screenshot_canvas.winfo_width()
                canvas_height = self.screenshot_canvas.winfo_height()
                
                self.logger.debug(f"Canvas dimensions: {canvas_width}x{canvas_height}")
                
                if canvas_width <= 1 or canvas_height <= 1:
                    # Canvas not ready yet, wait a bit and try again
                    self.logger.debug("Canvas not ready, retrying in 100ms")
                    if self.root:
                        # Store image temporarily and retry after canvas is ready
                        self.root.after(100, lambda: self._display_image_in_canvas(image))
                    return
                
                # Calculate scale factor to fit image in canvas while preserving aspect ratio
                image_width, image_height = image.size
                scale_x = canvas_width / image_width
                scale_y = canvas_height / image_height
                scale = min(scale_x, scale_y)
                
                self.logger.debug(f"Image size: {image_width}x{image_height}, scale: {scale:.3f}")
                
                # Apply drift vector annotation with proper scaling if available
                display_image = image.copy()  # Make a copy to avoid modifying original
                if self.drift_vector_data:
                    display_image = AnnotationRenderer.draw_drift_vector(
                        display_image,
                        self.drift_vector_data['target_x'],
                        self.drift_vector_data['target_y'],
                        self.drift_vector_data['actual_x'],
                        self.drift_vector_data['actual_y'],
                        scale  # Use calculated scale factor
                    )
                
                # Resize image
                new_width = int(image_width * scale)
                new_height = int(image_height * scale)
                resized_image = display_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                self.logger.debug(f"Resized to: {new_width}x{new_height}")
                
                # CRITICAL: Keep PIL image alive - Python 3.13 bug workaround
                self._current_pil_image = resized_image
                
                # Create PhotoImage
                new_photo = ImageTk.PhotoImage(resized_image)
                self.logger.debug(f"Created PhotoImage: {new_photo}")
                
                # CRITICAL: Store reference BEFORE using it AND in multiple places
                self._current_photo = new_photo
                
                # Update label - the reference is already saved
                self.screenshot_label.config(image=new_photo)
                # Store another reference directly in the widget
                self.screenshot_label.image = new_photo
                self.screenshot_label._pil_image = resized_image  # Keep PIL image in widget too
                
                # Force update
                self.screenshot_label.update_idletasks()
                
                self.logger.info("Image displayed successfully")
                
            finally:
                # Re-enable garbage collection if it was enabled
                if gc_was_enabled:
                    gc.enable()
            
        except Exception as e:
            self.logger.error(f"Error displaying image in canvas: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_message(f"Failed to display image: {e}", "ERROR")
    
    def update_thought_log(self, vlm_response: Dict[str, Any], timing: Dict[str, float]) -> None:
        """
        更新思维日志
        
        Args:
            vlm_response: VLM 原始 JSON 响应
            timing: 各阶段耗时字典
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format timing information
        timing_info = []
        if 'screenshot_time' in timing:
            timing_info.append(f"Screenshot: {timing['screenshot_time']:.2f}s")
        if 'vlm_inference_time' in timing:
            timing_info.append(f"VLM Inference: {timing['vlm_inference_time']:.2f}s")
        if 'action_execution_time' in timing:
            timing_info.append(f"Action Execution: {timing['action_execution_time']:.2f}s")
        if 'total_cycle_time' in timing:
            timing_info.append(f"Total: {timing['total_cycle_time']:.2f}s")
        
        timing_str = " | ".join(timing_info)
        
        # Format VLM response
        try:
            vlm_json = json.dumps(vlm_response, indent=2, ensure_ascii=False)
        except Exception:
            vlm_json = str(vlm_response)
        
        # Add to log
        log_entry = f"[{timestamp}] {timing_str}\n{vlm_json}\n{'-' * 50}\n"
        
        self._log_message(log_entry)
        
        # Store in history
        self.log_entries.append({
            'timestamp': timestamp,
            'vlm_response': vlm_response,
            'timing': timing
        })
        
        # Limit log entries
        if len(self.log_entries) > self.config.log_max_entries:
            self.log_entries.pop(0)
    
    def _log_message(self, message: str, level: str = "INFO") -> None:
        """向思维日志添加消息"""
        if not self.thought_log:
            return
        
        self.thought_log.insert(tk.END, message + "\n")
        self.thought_log.see(tk.END)
    
    def initialize_step_controller(self, agent_manager, action_engine) -> None:
        """
        初始化单步调试控制器
        
        Args:
            agent_manager: Agent 管理器实例
            action_engine: 动作执行引擎实例
        
        Requirements: 3.1, 3.2 - Step controller initialization for manual debugging
        """
        try:
            # Validate input parameters
            if not agent_manager:
                raise ValueError("agent_manager cannot be None")
            if not action_engine:
                raise ValueError("action_engine cannot be None")
            
            # Initialize StepController with validated parameters
            self.step_controller = StepController(agent_manager, action_engine)
            
            # Initialize CalibrationTool with action_engine
            if not self.calibration_tool:
                self.calibration_tool = CalibrationTool(action_engine)
                self.logger.info("CalibrationTool initialized with ActionEngine")
            
            # Set up drift vector callback in ActionEngine
            if hasattr(action_engine, 'set_debugger_callback'):
                action_engine.set_debugger_callback(self.update_drift_vector)
                self.logger.info("Drift vector callback registered with ActionEngine")
            else:
                self.logger.warning("ActionEngine does not support drift vector callback")
            
            # Update UI state to reflect step controller availability
            self._update_step_ui_state()
            
            # Enable step mode controls
            self.set_step_mode(True)
            
            self.logger.info("StepController initialized successfully with agent_manager and action_engine")
            self._log_message("StepController ready for manual debugging", "INFO")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize StepController: {e}")
            self._log_message(f"StepController initialization failed: {e}", "ERROR")
            
            # Ensure step mode is disabled if initialization fails
            self.set_step_mode(False)
    
    def auto_initialize_step_controller(self, agent_manager, action_engine) -> bool:
        """
        自动初始化 StepController（在 GUI 集成时调用）
        
        Args:
            agent_manager: Agent 管理器实例
            action_engine: 动作执行引擎实例
            
        Returns:
            bool: 初始化是否成功
            
        Requirements: 3.1, 3.2 - Automatic initialization during GUI integration
        """
        try:
            # Check if already initialized
            if self.step_controller is not None:
                self.logger.info("StepController already initialized, skipping auto-initialization")
                # Still set up drift vector callback if not already done
                if hasattr(action_engine, 'set_debugger_callback'):
                    action_engine.set_debugger_callback(self.update_drift_vector)
                return True
            
            # Perform initialization
            self.initialize_step_controller(agent_manager, action_engine)
            
            # Verify initialization was successful
            if self.step_controller is not None:
                self.logger.info("StepController auto-initialization completed successfully")
                return True
            else:
                self.logger.error("StepController auto-initialization failed - controller is None")
                return False
                
        except Exception as e:
            self.logger.error(f"StepController auto-initialization failed: {e}")
            self._log_message(f"Auto-initialization error: {e}", "ERROR")
            return False
    
    def is_step_controller_ready(self) -> bool:
        """
        检查 StepController 是否已准备就绪
        
        Returns:
            bool: StepController 是否可用
        """
        return (self.step_controller is not None and 
                hasattr(self.step_controller, 'agent_manager') and 
                hasattr(self.step_controller, 'action_engine') and
                self.step_controller.agent_manager is not None and
                self.step_controller.action_engine is not None)
    
    def set_step_mode(self, enabled: bool) -> None:
        """启用/禁用单步调试模式"""
        if enabled and not self.is_step_controller_ready():
            self._log_message("StepController not ready - cannot enable step mode", "ERROR")
            return
        
        # Update UI state based on step mode (only if UI exists)
        if hasattr(self, 'manual_step_button') and self.manual_step_button:
            self.manual_step_button.config(state=tk.NORMAL if enabled else tk.DISABLED)
        
        if enabled:
            self._log_message("Step mode enabled - ready for manual debugging")
        else:
            self._log_message("Step mode disabled")
            # Clear any pending actions when disabling
            if self.step_controller:
                self.step_controller.discard_pending()
                # Only update UI if it exists
                if hasattr(self, 'execute_button') and self.execute_button:
                    self._update_step_ui_state()
    
    def get_dpi_scale_factor(self) -> float:
        """获取当前 DPI 缩放因子"""
        return self.config.dpi_scale_factor
    
    def set_dpi_scale_factor(self, factor: float) -> None:
        """设置 DPI 缩放因子"""
        # Validate range
        factor = max(0.5, min(3.0, factor))
        self.config.dpi_scale_factor = factor
        
        # Update UI if available
        if hasattr(self, 'dpi_var'):
            self.dpi_var.set(str(factor))
        
        # Apply to calibration tool if available
        if self.calibration_tool:
            self.calibration_tool.apply_dpi_scale(factor)
    
    def _on_manual_step(self) -> None:
        """处理手动单步按钮点击 - 使用队列的线程安全版本"""
        if not self.step_controller:
            self._log_message("StepController not initialized", "ERROR")
            return
        
        # Get user instruction from input field
        user_instruction = None
        if hasattr(self, 'user_instruction_var'):
            instruction = self.user_instruction_var.get().strip()
            if instruction:
                user_instruction = instruction
                self._log_message(f"💬 User instruction: {instruction}", "INFO")
        
        # Disable manual step button during execution
        if hasattr(self, 'manual_step_button') and self.manual_step_button:
            self.manual_step_button.config(state=tk.DISABLED)
        
        # Run step execution in background thread to avoid blocking UI
        def run_step():
            try:
                # Create new event loop for this thread
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Execute step with user instruction
                    image_b64, command, timing = loop.run_until_complete(
                        self.step_controller.execute_step(user_instruction=user_instruction)
                    )
                    
                    # Queue UI update instead of using after()
                    self.ui_update_queue.put(
                        lambda: self._on_step_completed(image_b64, command, timing)
                    )
                    
                except Exception as e:
                    self.logger.error(f"Step execution failed: {e}")
                    error_msg = str(e)
                    self.ui_update_queue.put(
                        lambda: self._on_step_error(error_msg)
                    )
                finally:
                    loop.close()
                
            except Exception as e:
                self.logger.error(f"Manual step thread failed: {e}")
                # Queue button re-enable
                self.ui_update_queue.put(
                    lambda: self._safe_enable_manual_step_button()
                )
        
        # Start step execution in background thread
        step_thread = threading.Thread(target=run_step, daemon=True)
        step_thread.start()
        
        self._log_message("Manual step initiated...")
    
    def _safe_enable_manual_step_button(self) -> None:
        """Safely re-enable manual step button (called from main thread)"""
        try:
            if hasattr(self, 'manual_step_button') and self.manual_step_button:
                self.manual_step_button.config(state=tk.NORMAL)
        except Exception as e:
            self.logger.error(f"Failed to re-enable manual step button: {e}")
    
    def _on_step_completed(self, image_b64: str, command: AgentCommand, timing: Dict[str, float]) -> None:
        """处理单步执行完成 (在主线程中调用)"""
        try:
            # Update screenshot display
            if image_b64:
                self.update_screenshot(image_b64, command)
            
            # Update thought log
            vlm_response = {
                'thought': command.thought,
                'commentary': command.commentary,
                'action_type': command.action_type,
                'target': command.target,
                'confidence': command.confidence
            }
            self.update_thought_log(vlm_response, timing)
            
            # Update UI state
            self._update_step_ui_state()
            
            # Show pending action info
            if self.step_controller and self.step_controller.has_pending_action:
                pending_info = self.step_controller.get_pending_action_info()
                if pending_info:
                    self._log_message(
                        f"PENDING ACTION: {pending_info['action_type']} at {pending_info['target']} "
                        f"(confidence: {pending_info['confidence']:.2f})"
                    )
            
        except Exception as e:
            self.logger.error(f"Error handling step completion: {e}")
            self._log_message(f"Step completion error: {e}", "ERROR")
        finally:
            # Re-enable manual step button
            self._safe_enable_manual_step_button()
    
    def _on_step_error(self, error_message: str) -> None:
        """处理单步执行错误 (在主线程中调用)"""
        self._log_message(f"Manual step failed: {error_message}", "ERROR")
        self._update_step_ui_state()
        
        # Re-enable manual step button
        self._safe_enable_manual_step_button()
    
    def _on_execute(self) -> None:
        """处理执行按钮点击"""
        if not self.step_controller:
            self._log_message("StepController not initialized", "ERROR")
            return
        
        if not self.step_controller.has_pending_action:
            self._log_message("No pending action to execute", "WARNING")
            return
        
        # Disable execute button during execution
        self.execute_button.config(state=tk.DISABLED)
        
        # Execute action in background thread
        def run_execute():
            try:
                result = self.step_controller.confirm_action()
                
                # Queue UI update instead of using after()
                self.ui_update_queue.put(
                    lambda: self._on_execute_completed(result)
                )
                
            except Exception as e:
                self.logger.error(f"Action execution failed: {e}")
                error_msg = str(e)
                self.ui_update_queue.put(
                    lambda: self._on_execute_error(error_msg)
                )
        
        # Start execution in background thread
        execute_thread = threading.Thread(target=run_execute, daemon=True)
        execute_thread.start()
        
        self._log_message("Executing pending action...")
    
    def _on_execute_completed(self, result) -> None:
        """处理动作执行完成"""
        try:
            if result.success:
                self._log_message(
                    f"Action executed successfully: {result.action_type} "
                    f"(execution time: {result.execution_time:.3f}s)"
                )
            else:
                self._log_message(
                    f"Action execution failed: {result.action_type} - {result.error_message}",
                    "ERROR"
                )
            
            # Update UI state
            self._update_step_ui_state()
            
        except Exception as e:
            self.logger.error(f"Error handling execute completion: {e}")
            self._log_message(f"Execute completion error: {e}", "ERROR")
    
    def _on_execute_error(self, error_message: str) -> None:
        """处理动作执行错误"""
        self._log_message(f"Action execution failed: {error_message}", "ERROR")
        self._update_step_ui_state()
    
    def _update_step_ui_state(self) -> None:
        """更新单步调试UI状态"""
        if not self.step_controller:
            return
        
        # Check if execute_button exists before updating
        if not hasattr(self, 'execute_button') or self.execute_button is None:
            return
        
        # Update execute button state based on pending action
        has_pending = self.step_controller.has_pending_action
        self.execute_button.config(state=tk.NORMAL if has_pending else tk.DISABLED)
        
        # Update status indicator
        if hasattr(self, 'status_label'):
            if has_pending:
                pending_info = self.step_controller.get_pending_action_info()
                if pending_info:
                    status_text = f"待定: {pending_info['action_type']} (置信度: {pending_info['confidence']:.2f})"
                else:
                    status_text = "有待定动作"
            else:
                status_text = "无待定动作"
            
            self.status_label.config(text=status_text)
    
    def _on_test_center_click(self) -> None:
        """处理测试中心点击按钮"""
        if not self.calibration_tool:
            # Initialize calibration tool if not already done
            self.calibration_tool = CalibrationTool()
        
        try:
            center_x, center_y = self.calibration_tool.test_center_click()
            self._log_message(f"Center click test: calculated center at ({center_x}, {center_y})")
            
            # Display coordinates in the log
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            self._log_message(f"Screen dimensions: {screen_width}x{screen_height}")
            self._log_message(f"Expected center: ({screen_width//2}, {screen_height//2})")
            
        except Exception as e:
            self._log_message(f"Center click test failed: {e}", "ERROR")
    
    def _on_apply_dpi(self) -> None:
        """处理 DPI 缩放应用"""
        try:
            factor = float(self.dpi_var.get())
            self.set_dpi_scale_factor(factor)
            self._log_message(f"DPI scale factor set to {factor}")
        except ValueError:
            self._log_message("Invalid DPI scale factor", "ERROR")
    
    def _on_show_raw(self) -> None:
        """处理显示原始响应按钮"""
        self._show_raw_response_window()
    
    def _show_raw_response_window(self) -> None:
        """显示原始响应查看窗口"""
        try:
            from .pink_theme import PINK_THEME
            
            # Create new window
            raw_window = tk.Toplevel(self.root)
            raw_window.title("Raw Response Inspector")
            raw_window.geometry("800x600")
            raw_window.transient(self.root)
            raw_window.config(bg=PINK_THEME['debugger_bg'])
            
            # Make window resizable
            raw_window.resizable(True, True)
            
            # Create notebook for tabs
            notebook = ttk.Notebook(raw_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Prompt tab
            prompt_frame = tk.Frame(notebook, bg=PINK_THEME['debugger_panel'])
            notebook.add(prompt_frame, text="Full Prompt")
            
            prompt_text = scrolledtext.ScrolledText(
                prompt_frame, 
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=PINK_THEME['log_bg'],
                fg=PINK_THEME['text_primary'],
                insertbackground=PINK_THEME['primary'],
                selectbackground=PINK_THEME['primary'],
                selectforeground=PINK_THEME['text_primary']
            )
            prompt_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Validate and display prompt data
            if self.last_raw_prompt:
                try:
                    # Add timestamp and metadata
                    prompt_content = f"=== PROMPT DATA ===\n"
                    prompt_content += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    prompt_content += f"Length: {len(self.last_raw_prompt)} characters\n"
                    prompt_content += f"{'=' * 50}\n\n"
                    prompt_content += self.last_raw_prompt
                    
                    prompt_text.insert(tk.END, prompt_content)
                except Exception as e:
                    prompt_text.insert(tk.END, f"Error displaying prompt data: {e}\n\nRaw data:\n{self.last_raw_prompt}")
            else:
                prompt_text.insert(tk.END, "No prompt data available.\n\nThis could mean:\n- No VLM analysis has been performed yet\n- The VisionClient failed to capture the prompt\n- The debugger was not connected during the last analysis")
            
            prompt_text.config(state=tk.DISABLED)
            
            # Response tab
            response_frame = tk.Frame(notebook, bg=PINK_THEME['debugger_panel'])
            notebook.add(response_frame, text="Raw Response")
            
            response_text = scrolledtext.ScrolledText(
                response_frame, 
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=PINK_THEME['log_bg'],
                fg=PINK_THEME['text_primary'],
                insertbackground=PINK_THEME['primary'],
                selectbackground=PINK_THEME['primary'],
                selectforeground=PINK_THEME['text_primary']
            )
            response_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Validate and display response data
            if self.last_raw_response:
                try:
                    # Add timestamp and metadata
                    response_content = f"=== RESPONSE DATA ===\n"
                    response_content += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    response_content += f"Length: {len(self.last_raw_response)} characters\n"
                    
                    # Try to validate JSON format
                    try:
                        import json
                        json.loads(self.last_raw_response)
                        response_content += f"Format: Valid JSON\n"
                    except json.JSONDecodeError as je:
                        response_content += f"Format: Invalid JSON - {str(je)}\n"
                    except Exception:
                        response_content += f"Format: Unknown\n"
                    
                    response_content += f"{'=' * 50}\n\n"
                    response_content += self.last_raw_response
                    
                    response_text.insert(tk.END, response_content)
                except Exception as e:
                    response_text.insert(tk.END, f"Error displaying response data: {e}\n\nRaw data:\n{self.last_raw_response}")
            else:
                response_text.insert(tk.END, "No response data available.\n\nThis could mean:\n- No VLM analysis has been performed yet\n- The VisionClient failed to capture the response\n- The debugger was not connected during the last analysis")
            
            response_text.config(state=tk.DISABLED)
            
            # Analysis tab for debugging JSON parsing issues
            analysis_frame = tk.Frame(notebook, bg=PINK_THEME['debugger_panel'])
            notebook.add(analysis_frame, text="Analysis")
            
            analysis_text = scrolledtext.ScrolledText(
                analysis_frame, 
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=PINK_THEME['log_bg'],
                fg=PINK_THEME['text_primary'],
                insertbackground=PINK_THEME['primary'],
                selectbackground=PINK_THEME['primary'],
                selectforeground=PINK_THEME['text_primary']
            )
            analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Provide analysis of the data
            analysis_content = f"=== DATA ANALYSIS ===\n"
            analysis_content += f"Analysis performed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Analyze prompt
            if self.last_raw_prompt:
                analysis_content += f"PROMPT ANALYSIS:\n"
                analysis_content += f"- Length: {len(self.last_raw_prompt)} characters\n"
                analysis_content += f"- Lines: {len(self.last_raw_prompt.splitlines())}\n"
                analysis_content += f"- Contains 'JSON': {'Yes' if 'JSON' in self.last_raw_prompt else 'No'}\n"
                analysis_content += f"- Contains 'format': {'Yes' if 'format' in self.last_raw_prompt.lower() else 'No'}\n\n"
            else:
                analysis_content += f"PROMPT ANALYSIS: No data available\n\n"
            
            # Analyze response
            if self.last_raw_response:
                analysis_content += f"RESPONSE ANALYSIS:\n"
                analysis_content += f"- Length: {len(self.last_raw_response)} characters\n"
                analysis_content += f"- Lines: {len(self.last_raw_response.splitlines())}\n"
                
                # Check for common issues
                issues = []
                if not self.last_raw_response.strip().startswith('{'):
                    issues.append("Response doesn't start with '{'")
                if not self.last_raw_response.strip().endswith('}'):
                    issues.append("Response doesn't end with '}'")
                if '```' in self.last_raw_response:
                    issues.append("Response contains code blocks (```)")
                if 'json' in self.last_raw_response.lower() and not self.last_raw_response.strip().startswith('{'):
                    issues.append("Response mentions 'json' but isn't valid JSON")
                
                if issues:
                    analysis_content += f"- Potential Issues: {', '.join(issues)}\n"
                else:
                    analysis_content += f"- Potential Issues: None detected\n"
                
                # Try JSON parsing
                try:
                    import json
                    parsed = json.loads(self.last_raw_response)
                    analysis_content += f"- JSON Parsing: SUCCESS\n"
                    analysis_content += f"- JSON Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}\n"
                except json.JSONDecodeError as je:
                    analysis_content += f"- JSON Parsing: FAILED - {str(je)}\n"
                except Exception as e:
                    analysis_content += f"- JSON Parsing: ERROR - {str(e)}\n"
            else:
                analysis_content += f"RESPONSE ANALYSIS: No data available\n"
            
            analysis_text.insert(tk.END, analysis_content)
            analysis_text.config(state=tk.DISABLED)
            
            # Button frame
            button_frame = tk.Frame(raw_window, bg=PINK_THEME['debugger_panel'])
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # Refresh button to update data
            tk.Button(
                button_frame, 
                text="Refresh", 
                command=lambda: self._refresh_raw_window(raw_window),
                bg=PINK_THEME['button_secondary'],
                fg=PINK_THEME['text_primary'],
                activebackground=PINK_THEME['secondary_hover'],
                activeforeground=PINK_THEME['text_primary'],
                font=("Microsoft YaHei", 9),
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5
            ).pack(side=tk.LEFT, padx=5)
            
            # Close button
            tk.Button(
                button_frame, 
                text="Close", 
                command=raw_window.destroy,
                bg=PINK_THEME['button_danger'],
                fg=PINK_THEME['text_primary'],
                activebackground=PINK_THEME['accent_hover'],
                activeforeground=PINK_THEME['text_primary'],
                font=("Microsoft YaHei", 9),
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5
            ).pack(side=tk.RIGHT, padx=5)
            
            # Copy buttons for each tab
            tk.Button(
                button_frame, 
                text="Copy Prompt", 
                command=lambda: self._copy_to_clipboard(self.last_raw_prompt or "No prompt data"),
                bg=PINK_THEME['button_info'],
                fg=PINK_THEME['text_primary'],
                activebackground=PINK_THEME['primary_hover'],
                activeforeground=PINK_THEME['text_primary'],
                font=("Microsoft YaHei", 9),
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5
            ).pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                button_frame, 
                text="Copy Response", 
                command=lambda: self._copy_to_clipboard(self.last_raw_response or "No response data"),
                bg=PINK_THEME['button_info'],
                fg=PINK_THEME['text_primary'],
                activebackground=PINK_THEME['primary_hover'],
                activeforeground=PINK_THEME['text_primary'],
                font=("Microsoft YaHei", 9),
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5
            ).pack(side=tk.LEFT, padx=5)
            
            self.logger.info("Raw response inspector window opened")
            
        except Exception as e:
            self.logger.error(f"Failed to create raw response window: {e}")
            self._log_message(f"Failed to open raw response window: {e}", "ERROR")
    
    def _refresh_raw_window(self, window: tk.Toplevel) -> None:
        """刷新原始数据窗口"""
        try:
            window.destroy()
            self._show_raw_response_window()
            self._log_message("Raw response window refreshed")
        except Exception as e:
            self.logger.error(f"Failed to refresh raw window: {e}")
            self._log_message(f"Failed to refresh raw window: {e}", "ERROR")
    
    def _copy_to_clipboard(self, text: str) -> None:
        """复制文本到剪贴板"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()  # Required for clipboard to work
            self._log_message("Text copied to clipboard")
        except Exception as e:
            self.logger.error(f"Failed to copy to clipboard: {e}")
            self._log_message(f"Failed to copy to clipboard: {e}", "ERROR")
    
    def update_raw_data(self, prompt: str, response: str) -> None:
        """
        更新原始 Prompt 和响应数据
        
        Args:
            prompt: 发送给 VLM 的完整 Prompt
            response: VLM 返回的原始字符串响应
        """
        try:
            # Validate input data
            if prompt is None:
                self.logger.warning("Received None prompt data")
                prompt = "No prompt data received"
            elif not isinstance(prompt, str):
                self.logger.warning(f"Received non-string prompt data: {type(prompt)}")
                prompt = str(prompt)
            
            if response is None:
                self.logger.warning("Received None response data")
                response = "No response data received"
            elif not isinstance(response, str):
                self.logger.warning(f"Received non-string response data: {type(response)}")
                response = str(response)
            
            # Store the raw data
            self.last_raw_prompt = prompt
            self.last_raw_response = response
            
            # Log data reception for debugging
            self.logger.debug(f"Raw data updated - Prompt: {len(prompt)} chars, Response: {len(response)} chars")
            
            # Validate JSON format of response for early error detection
            if response and response.strip():
                try:
                    import json
                    json.loads(response)
                    self.logger.debug("Response is valid JSON")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Response is not valid JSON: {e}")
                    # Log the first 200 characters for debugging
                    preview = response[:200] + "..." if len(response) > 200 else response
                    self.logger.debug(f"Invalid JSON response preview: {preview}")
                except Exception as e:
                    self.logger.warning(f"Error validating response JSON: {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to update raw data: {e}")
            # Ensure we have some data even if there's an error
            self.last_raw_prompt = f"Error updating prompt: {e}"
            self.last_raw_response = f"Error updating response: {e}"
    
    def _start_mouse_tracking(self) -> None:
        """启动实时鼠标位置追踪"""
        self._mouse_tracking_active = True
        if self.root:
            self._update_mouse_position()
    
    def _update_mouse_position(self) -> None:
        """更新鼠标位置显示"""
        if not getattr(self, '_mouse_tracking_active', False):
            return
        
        try:
            import pyautogui
            x, y = pyautogui.position()
            if hasattr(self, 'mouse_pos_label') and self.mouse_pos_label:
                self.mouse_pos_label.config(text=f"当前鼠标: ({x}, {y})")
        except Exception as e:
            if hasattr(self, 'mouse_pos_label') and self.mouse_pos_label:
                self.mouse_pos_label.config(text="当前鼠标: (错误)")
        
        # Schedule next update in 100ms if still active and window exists
        if self.root and getattr(self, '_mouse_tracking_active', False):
            self.root.after(100, self._update_mouse_position)
    
    def _on_toggle_topmost(self) -> None:
        """处理置顶切换"""
        if self.root:
            topmost = self.topmost_var.get()
            self.root.attributes('-topmost', topmost)
            self.config.topmost = topmost
            
            # Log the change
            status = "enabled" if topmost else "disabled"
            self._log_message(f"Always on top {status}")
            self.logger.info(f"Window topmost attribute {status}")
            
            # Save config immediately to persist the change
            self._save_config()
    
    def _on_closing(self) -> None:
        """处理窗口关闭事件"""
        self.logger.info("Debugger window closing, performing cleanup...")
        
        # Save current window position and size before closing
        if self.root:
            # Get current window geometry
            geometry = self.root.geometry()  # Returns "widthxheight+x+y"
            try:
                # Parse geometry string
                size_part, pos_part = geometry.split('+', 1)
                width, height = map(int, size_part.split('x'))
                
                # Handle negative positions (multi-monitor setups)
                if '+' in pos_part:
                    x, y = map(int, pos_part.split('+'))
                else:
                    # Handle negative coordinates
                    parts = pos_part.replace('-', '+-').split('+')
                    x = int(parts[0]) if parts[0] else 0
                    y = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                
                # Update config with current values
                self.config.window_width = width
                self.config.window_height = height
                self.config.window_x = x
                self.config.window_y = y
                
                self.logger.info(f"Saving window geometry: {width}x{height} at ({x}, {y})")
                
            except Exception as e:
                self.logger.warning(f"Failed to parse window geometry '{geometry}': {e}")
        
        # Perform cleanup
        self._cleanup_resources()
        
        # Save configuration
        self._save_config()
        
        # Destroy window
        if self.root:
            self.root.destroy()
            self.root = None
        
        self.logger.info("Debugger window closed successfully")
    
    def clear_drift_vector(self) -> None:
        """Clear drift vector data"""
        self.drift_vector_data = None
        self.logger.debug("Drift vector data cleared")
    
    def _cleanup_resources(self) -> None:
        """清理资源和停止后台任务"""
        try:
            # Stop queue processor
            self._queue_processor_running = False
            
            # Stop mouse tracking if running
            if hasattr(self, '_mouse_tracking_active'):
                self._mouse_tracking_active = False
            
            # Clear pending actions in step controller
            if self.step_controller:
                self.step_controller.discard_pending()
                self.logger.info("Cleared pending actions from StepController")
            
            # Clear drift vector data
            self.clear_drift_vector()
            
            # Clear PhotoImage reference
            self._current_photo = None
            
            # Clear image references to free memory
            if self.current_image:
                self.current_image = None
            
            # Clear log entries to free memory
            self.log_entries.clear()
            
            # Clear raw data references
            self.last_raw_prompt = None
            self.last_raw_response = None
            
            # Clear UI update queue
            while not self.ui_update_queue.empty():
                try:
                    self.ui_update_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.logger.info("Resource cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during resource cleanup: {e}")
    
    def close(self) -> None:
        """
        公共方法：优雅关闭调试窗口
        可以被主应用调用来关闭调试器
        """
        if self.root:
            # Trigger the normal closing process
            self._on_closing()
        else:
            self.logger.info("Debugger window already closed")
    
    def on_main_app_closing(self) -> None:
        """
        处理主应用关闭事件
        当主应用即将关闭时调用此方法进行清理
        
        Requirements: 5.4 - Listen for main application close events
        """
        self.logger.info("Main application closing, shutting down debugger...")
        
        try:
            # Perform immediate cleanup without waiting for window events
            self._cleanup_resources()
            
            # Save configuration
            self._save_config()
            
            # Force close the window if it exists
            if self.root:
                try:
                    self.root.quit()  # Exit the mainloop
                    self.root.destroy()  # Destroy the window
                    self.root = None
                except Exception as e:
                    self.logger.error(f"Error force-closing debugger window: {e}")
            
            self.logger.info("Debugger shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during main app shutdown cleanup: {e}")
    
    def is_open(self) -> bool:
        """检查调试窗口是否打开"""
        return self.root is not None and self.root.winfo_exists()
    
    def _save_config(self) -> None:
        """保存配置到文件"""
        try:
            config_dict = asdict(self.config)
            with open(self.config.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
    
    def _load_config(self, config_path: Optional[str] = None) -> DebuggerConfig:
        """从文件加载配置"""
        # Use provided path, or current config path, or default
        if config_path is None:
            if hasattr(self, 'config') and self.config and hasattr(self.config, 'config_file_path'):
                config_path = self.config.config_file_path
            else:
                config_path = DebuggerConfig().config_file_path
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
                loaded_config = DebuggerConfig(**config_dict)
                if hasattr(self, 'logger'):
                    self.logger.info(f"Loaded config from {config_path}")
                return loaded_config
        except FileNotFoundError:
            if hasattr(self, 'logger'):
                self.logger.info("No config file found, using default configuration")
            return DebuggerConfig()
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to load config: {e}, using defaults")
            return DebuggerConfig()


class StepController:
    """单步调试模式控制器"""
    
    def __init__(self, agent_manager, action_engine):
        """
        初始化单步控制器
        
        Args:
            agent_manager: Agent 管理器实例
            action_engine: 动作执行引擎实例
        """
        self.agent_manager = agent_manager
        self.action_engine = action_engine
        self.logger = logging.getLogger(__name__)
        
        # Pending action state
        self.pending_action: Optional[PendingAction] = None
        self._step_lock = threading.Lock()
        
        self.logger.info("StepController initialized")
    
    async def execute_step(self, user_instruction: Optional[str] = None) -> Tuple[str, AgentCommand, Dict[str, float]]:
        """
        执行单步：截图 -> 分析 -> 返回结果（不执行动作）
        
        Args:
            user_instruction: 用户指令（可选）
        
        Returns:
            (image_b64, command, timing) 元组
        
        Requirements: 3.1, 3.2 - Single step execution with timing
        """
        with self._step_lock:
            # Clear any existing pending action
            self.pending_action = None
            
            timing = {}
            
            try:
                # 1. Capture screenshot with timing
                screenshot_start = time.time()
                image_b64 = await self.agent_manager.vision_client.capture_screen()
                timing['screenshot_time'] = time.time() - screenshot_start
                
                # 2. Analyze scene with VLM with timing (with user instruction)
                vlm_start = time.time()
                action_history = self.action_engine.get_action_history() if hasattr(self.action_engine, 'get_action_history') else []
                command, image_dimensions = await self.agent_manager.vision_client.analyze_scene(
                    image_b64, 
                    context="testing - click on any buttons or interactive elements you see",
                    action_history=action_history,
                    user_instruction=user_instruction  # Pass user instruction
                )
                timing['vlm_inference_time'] = time.time() - vlm_start
                
                # 3. Create pending action (DO NOT EXECUTE)
                timing_metrics = TimingMetrics(
                    screenshot_time=timing['screenshot_time'],
                    vlm_inference_time=timing['vlm_inference_time'],
                    action_execution_time=0.0,  # Not executed yet
                    total_cycle_time=timing['screenshot_time'] + timing['vlm_inference_time'],
                    timestamp=datetime.now()
                )
                
                self.pending_action = PendingAction(
                    command=command,
                    screenshot_b64=image_b64,
                    timing=timing_metrics,
                    created_at=datetime.now()
                )
                
                self.logger.info(f"Step executed: {command.action_type} at {command.target} (confidence: {command.confidence:.2f})")
                self.logger.debug(f"Timing: screenshot={timing['screenshot_time']:.3f}s, vlm={timing['vlm_inference_time']:.3f}s")
                
                return image_b64, command, timing
                
            except Exception as e:
                self.logger.error(f"Step execution failed: {e}")
                
                # Create fallback command
                fallback_command = AgentCommand(
                    thought=f"Step execution failed: {str(e)}",
                    commentary="I encountered an error during analysis.",
                    action_type="wait",
                    target=None,
                    key=None,
                    confidence=0.0,
                    timestamp=datetime.now()
                )
                
                # Return error state
                error_timing = {
                    'screenshot_time': timing.get('screenshot_time', 0.0),
                    'vlm_inference_time': timing.get('vlm_inference_time', 0.0),
                    'error': str(e)
                }
                
                return "", fallback_command, error_timing
    
    def confirm_action(self) -> 'ActionResult':
        """
        确认并执行待定动作
        
        Returns:
            动作执行结果
        
        Requirements: 3.3 - Action confirmation and execution
        """
        with self._step_lock:
            if not self.pending_action:
                from .action_engine import ActionResult
                return ActionResult(
                    success=False,
                    action_type="none",
                    target=None,
                    error_message="No pending action to execute",
                    execution_time=0.0,
                    timestamp=datetime.now()
                )
            
            try:
                # Execute the pending action
                action_start = time.time()
                result = self.action_engine.execute_command(self.pending_action.command)
                action_time = time.time() - action_start
                
                # Update timing metrics
                self.pending_action.timing.action_execution_time = action_time
                self.pending_action.timing.total_cycle_time += action_time
                
                self.logger.info(f"Action confirmed and executed: {result.action_type} - {'Success' if result.success else 'Failed'}")
                
                # Clear pending action
                self.pending_action = None
                
                return result
                
            except Exception as e:
                self.logger.error(f"Action confirmation failed: {e}")
                
                from .action_engine import ActionResult
                result = ActionResult(
                    success=False,
                    action_type=self.pending_action.command.action_type,
                    target=self.pending_action.command.target,
                    error_message=str(e),
                    execution_time=0.0,
                    timestamp=datetime.now()
                )
                
                # Clear pending action even on failure
                self.pending_action = None
                
                return result
    
    def discard_pending(self) -> None:
        """
        丢弃待定动作
        
        Requirements: 3.4 - Pending action discard
        """
        with self._step_lock:
            if self.pending_action:
                self.logger.info(f"Discarded pending action: {self.pending_action.command.action_type}")
                self.pending_action = None
            else:
                self.logger.debug("No pending action to discard")
    
    @property
    def has_pending_action(self) -> bool:
        """
        是否有待定动作
        
        Requirements: 3.5, 3.6 - Pending action state tracking
        """
        return self.pending_action is not None
    
    def get_pending_action_info(self) -> Optional[Dict[str, Any]]:
        """获取待定动作信息用于UI显示"""
        if not self.pending_action:
            return None
        
        return {
            'action_type': self.pending_action.command.action_type,
            'target': self.pending_action.command.target,
            'confidence': self.pending_action.command.confidence,
            'thought': self.pending_action.command.thought,
            'commentary': self.pending_action.command.commentary,
            'created_at': self.pending_action.created_at.strftime("%H:%M:%S"),
            'timing': {
                'screenshot_time': self.pending_action.timing.screenshot_time,
                'vlm_inference_time': self.pending_action.timing.vlm_inference_time,
                'total_time': self.pending_action.timing.total_cycle_time
            }
        }


class CalibrationTool:
    """DPI 缩放校准工具"""
    
    def __init__(self, action_engine=None):
        """
        初始化校准工具
        
        Args:
            action_engine: 动作执行引擎实例
        """
        self.action_engine = action_engine
        self.logger = logging.getLogger(__name__)
    
    def test_center_click(self) -> Tuple[int, int]:
        """
        测试点击屏幕中心
        
        Returns:
            (calculated_x, calculated_y) 计算的中心坐标
        """
        try:
            # Get screen dimensions
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            
            # Calculate center coordinates
            center_x = screen_width // 2
            center_y = screen_height // 2
            
            self.logger.info(f"Screen center calculated: ({center_x}, {center_y}) on {screen_width}x{screen_height}")
            
            # If action engine is available, move mouse to center
            if self.action_engine:
                try:
                    # Create a mock command for center click
                    from .vision_client import AgentCommand
                    from datetime import datetime
                    
                    center_command = AgentCommand(
                        thought="Testing center click calibration",
                        commentary="Moving to screen center for calibration",
                        action_type="click",
                        target=(0.5, 0.5),  # Center as percentage
                        key=None,
                        confidence=1.0,
                        timestamp=datetime.now()
                    )
                    
                    # Execute the center click
                    result = self.action_engine.execute_command(center_command)
                    
                    if result.success:
                        self.logger.info(f"Center click test successful at ({center_x}, {center_y})")
                    else:
                        self.logger.warning(f"Center click test failed: {result.error_message}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to execute center click: {e}")
            else:
                self.logger.info("No action engine available, only calculated center coordinates")
            
            return center_x, center_y
            
        except Exception as e:
            self.logger.error(f"Center click calculation failed: {e}")
            # Return default center for common resolution
            return 960, 540
    
    def apply_dpi_scale(self, factor: float) -> None:
        """
        应用 DPI 缩放因子到 ActionEngine
        
        Args:
            factor: DPI 缩放因子 (例如 1.0, 1.25, 1.5)
        """
        if self.action_engine and hasattr(self.action_engine, 'set_dpi_scale_factor'):
            self.action_engine.set_dpi_scale_factor(factor)
            self.logger.info(f"Applied DPI scale factor {factor} to ActionEngine")
        else:
            self.logger.warning("No ActionEngine available or DPI scaling not supported")
    
    def save_calibration(self) -> None:
        """保存校准设置到配置文件"""
        try:
            if self.action_engine:
                dpi_factor = self.action_engine.get_dpi_scale_factor()
                
                # Save to debugger config file
                config_data = {
                    'dpi_scale_factor': dpi_factor,
                    'last_calibration': datetime.now().isoformat()
                }
                
                import json
                with open('debugger_calibration.json', 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Calibration saved: DPI factor {dpi_factor}")
            else:
                self.logger.warning("No ActionEngine available for calibration save")
                
        except Exception as e:
            self.logger.error(f"Failed to save calibration: {e}")
    
    def load_calibration(self) -> float:
        """从配置文件加载校准设置"""
        try:
            import json
            with open('debugger_calibration.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            dpi_factor = config_data.get('dpi_scale_factor', 1.0)
            
            # Apply to action engine if available
            if self.action_engine:
                self.apply_dpi_scale(dpi_factor)
            
            self.logger.info(f"Calibration loaded: DPI factor {dpi_factor}")
            return dpi_factor
            
        except FileNotFoundError:
            self.logger.info("No calibration file found, using default DPI factor 1.0")
            return 1.0
        except Exception as e:
            self.logger.error(f"Failed to load calibration: {e}")
            return 1.0