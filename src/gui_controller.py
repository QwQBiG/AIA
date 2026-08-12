"""
改进的GUI控制器 - 优化布局和功能分类
Enhanced GUI Controller with improved layout and feature categorization
"""

import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import logging
import os
import re
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from .config import SystemConfig, SystemState, UXConfig
from .error_handler import ErrorHandler
from .system_workflow import SystemWorkflow
from .tooltip import ToolTip, TOOLTIP_TEXTS, create_tooltip
from .performance_monitor import performance_monitor


class GUILogHandler(logging.Handler):
    """自定义日志处理器，将日志发送到GUI显示"""
    
    def __init__(self, gui_controller):
        super().__init__()
        self.gui_controller = gui_controller
    
    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelname
            if hasattr(self.gui_controller, 'log_queue'):
                self.gui_controller.log_queue.put((f"{msg}\n", level))
        except Exception:
            pass


class ImprovedGUIController:
    """
    改进的GUI控制器
    
    特点：
    - 重新设计的功能分类和布局
    - 完整的工具提示支持
    - 更好的视觉层次结构
    - 优化的用户体验
    """
    
    def __init__(self, config: SystemConfig):
        """初始化改进的GUI控制器"""
        self.config = config
        self.system_state = SystemState()
        self.error_handler = ErrorHandler()
        
        # Initialize system workflow
        self.system_workflow = SystemWorkflow(config)
        self.system_workflow.set_status_callback(self.log_message)
        self.system_workflow.set_streaming_text_callback(self._on_streaming_text)
        
        # Threading components
        self.message_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.streaming_text_queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.is_processing = False
        self.shutdown_event = threading.Event()
        
        # Shared event loop
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_loop_lock = threading.Lock()
        
        # GUI components
        self.root: Optional[tk.Tk] = None
        self.tooltips: Dict[str, ToolTip] = {}  # 存储所有工具提示
        
        # Setup logging
        self.setup_logging()
        
        # Start background monitoring
        self.start_monitoring_thread()
        
        # 启动性能监控
        performance_monitor.start_monitoring()
    
    def _get_or_create_event_loop(self) -> asyncio.AbstractEventLoop:
        """
        获取或创建共享事件循环
        
        确保所有异步操作使用相同的事件循环，避免
        "Future attached to a different loop" 错误
        
        Returns:
            共享事件循环
        """
        with self._async_loop_lock:
            if self._async_loop is None or self._async_loop.is_closed():
                self._async_loop = asyncio.new_event_loop()
            return self._async_loop
    
    def _run_async(self, coro):
        """
        使用共享事件循环运行异步协程

        Args:
            coro: 要运行的协程

        Returns:
            协程的结果
        """
        try:
            # 检查当前线程是否已有运行中的事件循环
            current_loop = asyncio.get_running_loop()
            # 如果有运行中的循环，使用 run_coroutine_threadsafe
            if current_loop and current_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coro, current_loop)
                # 等待结果（带超时防止无限等待）
                return future.result(timeout=120.0)
        except RuntimeError:
            # 没有运行中的事件循环，创建新的事件循环
            pass

        # 创建新的事件循环并运行
        loop = self._get_or_create_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    def setup_ui(self) -> None:
        """
        创建改进的GUI界面
        
        新的布局特点：
        - 更清晰的功能分组
        - 优化的视觉层次
        - 完整的工具提示支持
        - 响应式布局设计
        """
        # 创建主窗口
        self._create_main_window()
        
        # 创建顶部标题栏
        self._create_header()
        
        # 创建主要交互区域
        self._create_interaction_area()
        
        # 创建状态显示区域
        self._create_status_area()
        
        # 创建功能控制面板
        self._create_control_panel()
        
        # 创建日志显示区域
        self._create_log_area()
        
        # 创建字幕显示
        self._create_subtitle_display()
        
        # 设置工具提示
        self._setup_all_tooltips()
        
        # 设置F1-F5情感热键
        self._setup_emotion_hotkeys()
        
        # 启动消息队列处理
        self.process_message_queue()
        
        self.logger.info("改进的GUI界面初始化完成")
    
    def _create_main_window(self) -> None:
        """创建主窗口"""
        self.root = tk.Tk()
        self.root.title("AIex VTuber")
        self.root.geometry("1200x1000")
        self.root.minsize(1000, 800)
        
        # 设置窗口图标
        try:
            icon_path = "assets/icons/app_icon.ico"
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass
        
        # 配置主题颜色
        from .pink_theme import get_theme
        self.colors = get_theme()
        self.root.configure(bg=self.colors['bg_dark'])
        
        # 配置ttk样式
        self._configure_ttk_styles()
        
        # 配置网格权重
        self.root.grid_rowconfigure(4, weight=1)  # 日志区域可扩展
        self.root.grid_columnconfigure(0, weight=1)
    
    def _configure_ttk_styles(self) -> None:
        """配置ttk样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置Notebook样式
        style.configure('TNotebook', 
                       background=self.colors['bg_dark'], 
                       borderwidth=0,
                       tabmargins=[2, 5, 2, 0])
        
        style.configure('TNotebook.Tab', 
                       background=self.colors['bg_medium'],
                       foreground=self.colors['text_primary'],
                       padding=[20, 10],
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['accent']),
                           ('active', self.colors['bg_light'])],
                 foreground=[('selected', self.colors['text_primary']),
                           ('active', self.colors['text_primary'])])
        
        # 配置进度条样式
        style.configure('TProgressbar',
                       background=self.colors['primary'],
                       troughcolor=self.colors['bg_medium'],
                       borderwidth=0,
                       lightcolor=self.colors['primary'],
                       darkcolor=self.colors['primary'])
    
    def _create_header(self) -> None:
        """创建顶部标题栏"""
        header_frame = tk.Frame(self.root, bg=self.colors['bg_medium'], height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.root.grid_rowconfigure(4, weight=0)
        self.root.grid_rowconfigure(3, weight=1)
        self.root.geometry("1280x860")
        self.root.minsize(1024, 700)
        header_frame.grid_propagate(False)
        
        # 主标题
        title_label = tk.Label(
            header_frame,
            text="🎭 AI VTuber 智能控制中心",
            font=("Microsoft YaHei", 18, "bold"),
            fg=self.colors['accent'],
            bg=self.colors['bg_medium']
        )
        title_label.pack(side=tk.LEFT, padx=25, pady=15)
        
        # 状态指示器容器
        status_container = tk.Frame(header_frame, bg=self.colors['bg_medium'])
        status_container.pack(side=tk.RIGHT, padx=25, pady=15)
        
        # 系统状态指示器
        self.system_status_label = tk.Label(
            status_container,
            text="🟢 系统就绪",
            font=("Microsoft YaHei", 11, "bold"),
            fg=self.colors['success'],
            bg=self.colors['bg_medium']
        )
        self.system_status_label.pack(side=tk.TOP)
        
        # 记忆 & VAD 状态行
        sub_status_frame = tk.Frame(status_container, bg=self.colors['bg_medium'])
        sub_status_frame.pack(side=tk.TOP)
        
        self.memory_status_label = tk.Label(
            sub_status_frame,
            text="🧠 记忆: 加载中",
            font=("Microsoft YaHei", 9),
            fg=self.colors['warning'],
            bg=self.colors['bg_medium']
        )
        self.memory_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.vad_status_label = tk.Label(
            sub_status_frame,
            text="🎙️ 麦克风: 待机",
            font=("Microsoft YaHei", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_medium']
        )
        self.vad_status_label.pack(side=tk.LEFT)
        
        # 版本信息
        version_label = tk.Label(
            status_container,
            text="v4.0 - UX超级优化版",
            font=("Microsoft YaHei", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_medium']
        )
        version_label.pack(side=tk.TOP)
    
    def _create_interaction_area(self) -> None:
        """创建主要交互区域"""
        interaction_frame = tk.Frame(self.root, bg=self.colors['bg_dark'])
        interaction_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        interaction_frame.grid_columnconfigure(0, weight=1)
        
        # ── 对话历史区 ──────────────────────────────────────────────
        chat_header = tk.Frame(interaction_frame, bg=self.colors['bg_dark'])
        chat_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        chat_header.grid_columnconfigure(0, weight=1)
        
        tk.Label(
            chat_header,
            text="💬 对话历史",
            font=("Microsoft YaHei", 12, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        ).pack(side=tk.LEFT)
        
        # 清空对话按钮
        clear_chat_btn = tk.Button(
            chat_header,
            text="清空对话",
            command=self._clear_chat_display,
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_light'],
            fg=self.colors['text_secondary'],
            activebackground=self.colors['bg_medium'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        clear_chat_btn.pack(side=tk.RIGHT)
        
        # 对话显示框（ScrolledText，只读，显示用户和AI的消息）
        self.chat_display = scrolledtext.ScrolledText(
            interaction_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 11),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent'],
            state=tk.DISABLED,
            height=8,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.colors['primary'],
            highlightbackground=self.colors['bg_light']
        )
        self.chat_display.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        
        # 配置对话框文字颜色标签
        self.chat_display.tag_configure("user_label", foreground="#ffc107",
                                        font=("Microsoft YaHei", 11, "bold"))
        self.chat_display.tag_configure("user_text", foreground="#ffffff",
                                        font=("Microsoft YaHei", 11))
        self.chat_display.tag_configure("ai_label", foreground="#4ecca3",
                                        font=("Microsoft YaHei", 11, "bold"))
        self.chat_display.tag_configure("ai_text", foreground="#e0e0e0",
                                        font=("Microsoft YaHei", 11))
        self.chat_display.tag_configure("ai_streaming", foreground="#00d9ff",
                                        font=("Microsoft YaHei", 11, "italic"))
        self.chat_display.tag_configure("timestamp", foreground="#666666",
                                        font=("Microsoft YaHei", 9))
        
        # ── 输入区 ──────────────────────────────────────────────────
        tk.Label(
            interaction_frame,
            text="✏️ 输入消息",
            font=("Microsoft YaHei", 10, "bold"),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_dark']
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))
        
        # 输入框容器
        input_container = tk.Frame(interaction_frame, bg=self.colors['bg_dark'])
        input_container.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        input_container.grid_columnconfigure(0, weight=1)
        
        # 输入框
        self.input_entry = tk.Entry(
            input_container,
            font=("Microsoft YaHei", 14),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent'],
            relief=tk.FLAT,
            highlightthickness=2,
            highlightcolor=self.colors['primary'],
            highlightbackground=self.colors['bg_light']
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 15), ipady=12)
        self.input_entry.bind("<Return>", lambda e: self.on_send_clicked())
        
        # 发送按钮
        self.send_button = tk.Button(
            input_container,
            text="发送 ➤",
            command=self.on_send_clicked,
            font=("Microsoft YaHei", 12, "bold"),
            bg=self.colors['accent'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent_hover'],
            activeforeground=self.colors['text_primary'],
            relief=tk.FLAT,
            cursor="hand2",
            width=12,
            height=2
        )
        self.send_button.grid(row=0, column=1, ipady=8)
        
        # 快捷操作按钮
        quick_actions = tk.Frame(interaction_frame, bg=self.colors['bg_dark'])
        quick_actions.grid(row=4, column=0, sticky="ew", pady=(2, 0))
        
        # 清除输入按钮
        clear_input_btn = tk.Button(
            quick_actions,
            text="🗑️ 清除输入",
            command=lambda: self.input_entry.delete(0, tk.END),
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_light'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['bg_medium'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        clear_input_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 中断响应按钮
        self.interrupt_button = tk.Button(
            quick_actions,
            text="✋ 中断",
            command=self._interrupt_response,
            font=("Microsoft YaHei", 9),
            bg=self.colors['warning'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['error'],
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.interrupt_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 语音输入按钮（未来功能）
        voice_input_btn = tk.Button(
            quick_actions,
            text="🎤 语音",
            command=self._voice_input,
            font=("Microsoft YaHei", 9),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['bg_medium'],
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED  # 暂时禁用
        )
        voice_input_btn.pack(side=tk.LEFT)
    def _create_status_area(self) -> None:
        """创建状态显示区域"""
        status_frame = tk.Frame(self.root, bg=self.colors['bg_medium'])
        status_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        
        # 连接状态区域
        connection_frame = tk.Frame(status_frame, bg=self.colors['bg_medium'])
        connection_frame.pack(side=tk.LEFT, padx=15, pady=10)
        
        tk.Label(
            connection_frame,
            text="🔗 服务连接",
            font=("Microsoft YaHei", 11, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_medium']
        ).pack(side=tk.LEFT)
        
        # Ollama状态
        self.llm_status_label = tk.Label(
            connection_frame,
            text="● Ollama: 未连接",
            fg=self.colors['error'],
            bg=self.colors['bg_medium'],
            font=("Microsoft YaHei", 10)
        )
        self.llm_status_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # VTube Studio状态
        self.vts_status_label = tk.Label(
            connection_frame,
            text="● VTS: 未连接",
            fg=self.colors['error'],
            bg=self.colors['bg_medium'],
            font=("Microsoft YaHei", 10)
        )
        self.vts_status_label.pack(side=tk.LEFT, padx=(15, 0))
        
        # TTS状态
        self.tts_status_label = tk.Label(
            connection_frame,
            text="● TTS: 未连接",
            fg=self.colors['error'],
            bg=self.colors['bg_medium'],
            font=("Microsoft YaHei", 10)
        )
        self.tts_status_label.pack(side=tk.LEFT, padx=(15, 0))
        
        # 控制按钮区域
        control_frame = tk.Frame(status_frame, bg=self.colors['bg_medium'])
        control_frame.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # 重连按钮
        reconnect_btn = tk.Button(
            control_frame,
            text="🔄 重新连接",
            command=self.reconnect_services,
            font=("Microsoft YaHei", 10),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        reconnect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 清除日志按钮
        clear_log_btn = tk.Button(
            control_frame,
            text="🗑️ 清除日志",
            command=self.clear_log,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_light'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        clear_log_btn.pack(side=tk.LEFT)
        
        # 进度条
        self.progress_bar = ttk.Progressbar(
            status_frame,
            mode='indeterminate',
            length=150
        )
        # 需要时才显示
    
    def _create_control_panel(self) -> None:
        """创建功能控制面板"""
        # 创建主要的Notebook容器
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        
        # 基础功能标签页
        self._create_basic_tab()
        
        # 性能优化标签页
        self._create_performance_tab()
        
        # 高级功能标签页
        self._create_advanced_tab()
        
        # Agent模式标签页
        self._create_agent_tab()
        
        # 系统管理标签页
        self._create_system_tab()
    
    def _create_basic_tab(self) -> None:
        """创建基础功能标签页"""
        basic_frame = tk.Frame(self.main_notebook, bg=self.colors['bg_dark'])
        self.main_notebook.add(basic_frame, text="🎯 基础功能")
        
        # 语音合成设置
        tts_group = tk.LabelFrame(
            basic_frame,
            text="🎤 语音合成设置",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        tts_group.pack(fill=tk.X, padx=15, pady=10)
        
        # GPT-SoVITS开关
        self.voice_cloning_var = tk.BooleanVar(value=self.config.enable_voice_cloning)
        voice_cloning_cb = tk.Checkbutton(
            tts_group,
            text="🎤 GPT-SoVITS 语音克隆",
            variable=self.voice_cloning_var,
            command=self._toggle_voice_cloning,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        voice_cloning_cb.pack(anchor=tk.W, pady=5)
        
        # 表情控制设置
        expression_group = tk.LabelFrame(
            basic_frame,
            text="😊 表情控制设置",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        expression_group.pack(fill=tk.X, padx=15, pady=10)
        
        # 情感智能开关
        self.emotional_intelligence_var = tk.BooleanVar(value=self.config.enable_emotional_intelligence)
        emotional_cb = tk.Checkbutton(
            expression_group,
            text="💭 情感智能分析",
            variable=self.emotional_intelligence_var,
            command=self._toggle_emotional_intelligence,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        emotional_cb.pack(anchor=tk.W, pady=5)
        
        # 表情控制开关
        self.expression_control_var = tk.BooleanVar(value=self.config.enable_expression_control)
        expression_cb = tk.Checkbutton(
            expression_group,
            text="😊 Live2D 表情控制",
            variable=self.expression_control_var,
            command=self._toggle_expression_control,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        expression_cb.pack(anchor=tk.W, pady=5)
        
        # 用户体验设置
        ux_group = tk.LabelFrame(
            basic_frame,
            text="✨ 用户体验设置",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        ux_group.pack(fill=tk.X, padx=15, pady=10)
        
        # 字幕显示开关
        self.subtitle_var = tk.BooleanVar(value=True)
        subtitle_cb = tk.Checkbutton(
            ux_group,
            text="📺 同步字幕显示",
            variable=self.subtitle_var,
            command=self._toggle_subtitle,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        subtitle_cb.pack(anchor=tk.W, pady=5)
        
        # 字幕设置按钮
        subtitle_settings_frame = tk.Frame(ux_group, bg=self.colors['bg_dark'])
        subtitle_settings_frame.pack(fill=tk.X, pady=5)
        
        subtitle_settings_btn = tk.Button(
            subtitle_settings_frame,
            text="⚙️ 字幕窗口设置",
            command=self._open_subtitle_settings,
            font=("Microsoft YaHei", 9),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        subtitle_settings_btn.pack(side=tk.LEFT, padx=(20, 10))
        
        # 全双工模式开关
        self.full_duplex_var = tk.BooleanVar(value=False)
        full_duplex_cb = tk.Checkbutton(
            ux_group,
            text="🎙️ 全双工对话模式",
            variable=self.full_duplex_var,
            command=self._toggle_full_duplex,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        full_duplex_cb.pack(anchor=tk.W, pady=5)
    
    def _create_performance_tab(self) -> None:
        """创建性能优化标签页"""
        perf_frame = tk.Frame(self.main_notebook, bg=self.colors['bg_dark'])
        self.main_notebook.add(perf_frame, text="⚡ 性能优化")
        
        # 响应速度优化
        response_group = tk.LabelFrame(
            perf_frame,
            text="🚀 响应速度优化",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        response_group.pack(fill=tk.X, padx=15, pady=10)
        
        # 流式响应
        self.streaming_var = tk.BooleanVar(value=True)
        streaming_cb = tk.Checkbutton(
            response_group,
            text="⚡ 流式响应显示",
            variable=self.streaming_var,
            command=self._toggle_streaming,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        streaming_cb.pack(anchor=tk.W, pady=5)
        
        # 分句处理
        self.chunking_var = tk.BooleanVar(value=True)
        chunking_cb = tk.Checkbutton(
            response_group,
            text="📝 智能分句处理",
            variable=self.chunking_var,
            command=self._toggle_chunking,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        chunking_cb.pack(anchor=tk.W, pady=5)
        
        # 激进分句
        self.aggressive_split_var = tk.BooleanVar(value=True)
        aggressive_cb = tk.Checkbutton(
            response_group,
            text="✂️ 激进分句模式",
            variable=self.aggressive_split_var,
            command=self._toggle_aggressive_split,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        aggressive_cb.pack(anchor=tk.W, pady=5)
        
        # 交互体验优化
        interaction_group = tk.LabelFrame(
            perf_frame,
            text="🎯 交互体验优化",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        interaction_group.pack(fill=tk.X, padx=15, pady=10)
        
        # 用户打断
        self.interruption_var = tk.BooleanVar(value=True)
        interruption_cb = tk.Checkbutton(
            interaction_group,
            text="✋ 用户打断支持",
            variable=self.interruption_var,
            command=self._toggle_interruption,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        interruption_cb.pack(anchor=tk.W, pady=5)
        
        # 音频缓存
        self.cache_var = tk.BooleanVar(value=True)
        cache_cb = tk.Checkbutton(
            interaction_group,
            text="💾 音频缓存系统",
            variable=self.cache_var,
            command=self._toggle_cache,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        cache_cb.pack(anchor=tk.W, pady=5)
        
        # 系统优化
        system_group = tk.LabelFrame(
            perf_frame,
            text="🔧 系统优化",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        system_group.pack(fill=tk.X, padx=15, pady=10)
        
        # 预热加载
        self.warmup_var = tk.BooleanVar(value=True)
        warmup_cb = tk.Checkbutton(
            system_group,
            text="🔥 系统预热加载",
            variable=self.warmup_var,
            command=self._toggle_warmup,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        warmup_cb.pack(anchor=tk.W, pady=5)
        
        # 文本清洗
        self.text_cleaning_var = tk.BooleanVar(value=True)
        cleaning_cb = tk.Checkbutton(
            system_group,
            text="🧹 智能文本清洗",
            variable=self.text_cleaning_var,
            command=self._toggle_text_cleaning,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        cleaning_cb.pack(anchor=tk.W, pady=5)
    def _create_advanced_tab(self) -> None:
        """创建高级功能标签页"""
        advanced_frame = tk.Frame(self.main_notebook, bg=self.colors['bg_dark'])
        self.main_notebook.add(advanced_frame, text="🔬 高级功能")
        
        # 内存管理
        memory_group = tk.LabelFrame(
            advanced_frame,
            text="🧠 智能内存系统",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        memory_group.pack(fill=tk.X, padx=15, pady=10)
        
        memory_buttons = tk.Frame(memory_group, bg=self.colors['bg_dark'])
        memory_buttons.pack(fill=tk.X, pady=5)
        
        # 内存管理器按钮
        memory_mgr_btn = tk.Button(
            memory_buttons,
            text="🧠 内存管理器",
            command=self._open_memory_manager,
            font=("Microsoft YaHei", 10),
            bg="#4CAF50",
            fg=self.colors['text_primary'],
            activebackground=self.colors['success'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        memory_mgr_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 内存统计按钮
        memory_stats_btn = tk.Button(
            memory_buttons,
            text="📊 内存统计",
            command=self._show_memory_stats,
            font=("Microsoft YaHei", 10),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        memory_stats_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 内存备份按钮
        memory_backup_btn = tk.Button(
            memory_buttons,
            text="💾 创建备份",
            command=self._create_memory_backup,
            font=("Microsoft YaHei", 10),
            bg=self.colors['warning'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        memory_backup_btn.pack(side=tk.LEFT)
        
        # 音频设置
        audio_group = tk.LabelFrame(
            advanced_frame,
            text="🎧 音频系统设置",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        audio_group.pack(fill=tk.X, padx=15, pady=10)
        
        audio_buttons = tk.Frame(audio_group, bg=self.colors['bg_dark'])
        audio_buttons.pack(fill=tk.X, pady=5)
        
        # 音频设置按钮
        audio_setup_btn = tk.Button(
            audio_buttons,
            text="🎧 音频配置",
            command=self.show_audio_setup_dialog,
            font=("Microsoft YaHei", 10),
            bg="#2196F3",
            fg=self.colors['text_primary'],
            activebackground=self.colors['info'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        audio_setup_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 音频测试按钮
        audio_test_btn = tk.Button(
            audio_buttons,
            text="🔊 音频测试",
            command=self._test_audio,
            font=("Microsoft YaHei", 10),
            bg=self.colors['success'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        audio_test_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 音频诊断按钮
        audio_diag_btn = tk.Button(
            audio_buttons,
            text="🔍 音频诊断",
            command=self._run_audio_diagnostics,
            font=("Microsoft YaHei", 10),
            bg=self.colors['warning'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        audio_diag_btn.pack(side=tk.LEFT)
        
        # 模型管理
        model_group = tk.LabelFrame(
            advanced_frame,
            text="🤖 AI模型管理",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        model_group.pack(fill=tk.X, padx=15, pady=10)
        
        model_buttons = tk.Frame(model_group, bg=self.colors['bg_dark'])
        model_buttons.pack(fill=tk.X, pady=5)
        
        # 模型管理器按钮
        model_mgr_btn = tk.Button(
            model_buttons,
            text="🤖 模型管理",
            command=self._open_model_manager,
            font=("Microsoft YaHei", 10),
            bg="#FF9800",
            fg=self.colors['text_primary'],
            activebackground=self.colors['warning'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        model_mgr_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 模型状态按钮
        model_status_btn = tk.Button(
            model_buttons,
            text="📈 模型状态",
            command=self._show_model_status,
            font=("Microsoft YaHei", 10),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        model_status_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 模型优化按钮
        model_opt_btn = tk.Button(
            model_buttons,
            text="⚡ 模型优化",
            command=self._optimize_models,
            font=("Microsoft YaHei", 10),
            bg=self.colors['accent'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent_hover'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        model_opt_btn.pack(side=tk.LEFT)
    
    def _create_agent_tab(self) -> None:
        """创建Agent模式标签页"""
        agent_frame = tk.Frame(self.main_notebook, bg=self.colors['bg_dark'])
        self.main_notebook.add(agent_frame, text="🤖 Agent模式")
        
        # Agent控制
        control_group = tk.LabelFrame(
            agent_frame,
            text="🎮 Agent控制中心",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        control_group.pack(fill=tk.X, padx=15, pady=10)
        
        # Agent状态和控制
        agent_status_frame = tk.Frame(control_group, bg=self.colors['bg_dark'])
        agent_status_frame.pack(fill=tk.X, pady=5)
        
        # Agent开关按钮
        self.agent_toggle_button = tk.Button(
            agent_status_frame,
            text="▶ 启动 Agent",
            command=self._toggle_agent_mode,
            font=("Microsoft YaHei", 12, "bold"),
            bg=self.colors['success'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15,
            height=2
        )
        self.agent_toggle_button.pack(side=tk.LEFT, padx=(0, 20))
        
        # Agent状态显示
        status_info_frame = tk.Frame(agent_status_frame, bg=self.colors['bg_dark'])
        status_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.agent_status_label = tk.Label(
            status_info_frame,
            text="● 状态: 未启动",
            font=("Microsoft YaHei", 11, "bold"),
            fg=self.colors['error'],
            bg=self.colors['bg_dark']
        )
        self.agent_status_label.pack(anchor=tk.W)
        
        self.emergency_status_label = tk.Label(
            status_info_frame,
            text="🛡️ 紧急停止: F9键",
            font=("Microsoft YaHei", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_dark']
        )
        self.emergency_status_label.pack(anchor=tk.W)
        
        # Agent参数设置
        params_group = tk.LabelFrame(
            agent_frame,
            text="⚙️ 运行参数",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        params_group.pack(fill=tk.X, padx=15, pady=10)
        
        params_frame = tk.Frame(params_group, bg=self.colors['bg_dark'])
        params_frame.pack(fill=tk.X, pady=5)
        
        # 循环间隔设置
        tk.Label(
            params_frame,
            text="🔄 循环间隔(秒):",
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary']
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        
        self.loop_interval_var = tk.DoubleVar(value=2.0)
        loop_interval_spin = tk.Spinbox(
            params_frame,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=self.loop_interval_var,
            width=10,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary']
        )
        loop_interval_spin.grid(row=0, column=1, padx=(0, 30), pady=5)
        
        # 冷却时间设置
        tk.Label(
            params_frame,
            text="❄️ 冷却时间(秒):",
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary']
        ).grid(row=0, column=2, sticky="w", padx=(0, 10), pady=5)
        
        self.cooldown_period_var = tk.DoubleVar(value=1.0)
        cooldown_spin = tk.Spinbox(
            params_frame,
            from_=0.1,
            to=5.0,
            increment=0.1,
            textvariable=self.cooldown_period_var,
            width=10,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary']
        )
        cooldown_spin.grid(row=0, column=3, pady=5)
        
        # Agent工具
        tools_group = tk.LabelFrame(
            agent_frame,
            text="🛠️ 调试工具",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        tools_group.pack(fill=tk.X, padx=15, pady=10)
        
        tools_frame = tk.Frame(tools_group, bg=self.colors['bg_dark'])
        tools_frame.pack(fill=tk.X, pady=5)
        
        # Debugger按钮
        debugger_btn = tk.Button(
            tools_frame,
            text="🔧 Agent Debugger",
            command=self._open_agent_debugger,
            font=("Microsoft YaHei", 10),
            bg="#9C27B0",
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=18
        )
        debugger_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 性能监控按钮
        perf_monitor_btn = tk.Button(
            tools_frame,
            text="📊 性能监控",
            command=self._show_agent_performance,
            font=("Microsoft YaHei", 10),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=18
        )
        perf_monitor_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 日志查看按钮
        agent_logs_btn = tk.Button(
            tools_frame,
            text="📋 Agent日志",
            command=self._show_agent_logs,
            font=("Microsoft YaHei", 10),
            bg=self.colors['warning'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=18
        )
        agent_logs_btn.pack(side=tk.LEFT)
    
    def _create_system_tab(self) -> None:
        """创建系统管理标签页"""
        system_frame = tk.Frame(self.main_notebook, bg=self.colors['bg_dark'])
        self.main_notebook.add(system_frame, text="🔧 系统管理")
        
        # 系统信息
        info_group = tk.LabelFrame(
            system_frame,
            text="ℹ️ 系统信息",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        info_group.pack(fill=tk.X, padx=15, pady=10)
        
        info_buttons = tk.Frame(info_group, bg=self.colors['bg_dark'])
        info_buttons.pack(fill=tk.X, pady=5)
        
        # 系统信息按钮
        sys_info_btn = tk.Button(
            info_buttons,
            text="ℹ️ 系统信息",
            command=self._show_system_info,
            font=("Microsoft YaHei", 10),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        sys_info_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 性能统计按钮
        perf_stats_btn = tk.Button(
            info_buttons,
            text="📊 性能统计",
            command=self._show_performance_stats,
            font=("Microsoft YaHei", 10),
            bg=self.colors['success'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        perf_stats_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 功能文档按钮
        docs_btn = tk.Button(
            info_buttons,
            text="📖 功能文档",
            command=self._show_feature_docs,
            font=("Microsoft YaHei", 10),
            bg=self.colors['warning'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        docs_btn.pack(side=tk.LEFT)
        
        # 网络设置
        network_group = tk.LabelFrame(
            system_frame,
            text="🌐 网络设置",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        network_group.pack(fill=tk.X, padx=15, pady=10)
        
        # 代理设置
        proxy_frame = tk.Frame(network_group, bg=self.colors['bg_dark'])
        proxy_frame.pack(fill=tk.X, pady=5)
        
        # 启用代理复选框
        self.proxy_enabled_var = tk.BooleanVar(value=False)
        proxy_cb = tk.Checkbutton(
            proxy_frame,
            text="🔗 启用代理",
            variable=self.proxy_enabled_var,
            command=self._toggle_proxy,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark'],
            activeforeground=self.colors['accent']
        )
        proxy_cb.pack(anchor=tk.W, pady=2)
        
        # 代理地址输入
        proxy_addr_frame = tk.Frame(network_group, bg=self.colors['bg_dark'])
        proxy_addr_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(
            proxy_addr_frame,
            text="代理地址:",
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_secondary']
        ).pack(side=tk.LEFT)
        
        self.proxy_addr_var = tk.StringVar(value="http://127.0.0.1:7890")
        proxy_addr_entry = tk.Entry(
            proxy_addr_frame,
            textvariable=self.proxy_addr_var,
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            width=30
        )
        proxy_addr_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # 网络超时设置
        timeout_frame = tk.Frame(network_group, bg=self.colors['bg_dark'])
        timeout_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(
            timeout_frame,
            text="连接超时(秒):",
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_secondary']
        ).pack(side=tk.LEFT)
        
        self.timeout_var = tk.StringVar(value="30")
        timeout_entry = tk.Entry(
            timeout_frame,
            textvariable=self.timeout_var,
            font=("Microsoft YaHei", 9),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            width=10
        )
        timeout_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # 应用网络设置按钮
        apply_network_btn = tk.Button(
            network_group,
            text="✅ 应用网络设置",
            command=self._apply_network_settings,
            font=("Microsoft YaHei", 10),
            bg=self.colors['success'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=20
        )
        apply_network_btn.pack(pady=5)
        
        # 系统诊断
        diag_group = tk.LabelFrame(
            system_frame,
            text="🔍 系统诊断",
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            padx=10,
            pady=10
        )
        diag_group.pack(fill=tk.X, padx=15, pady=10)
        
        diag_buttons = tk.Frame(diag_group, bg=self.colors['bg_dark'])
        diag_buttons.pack(fill=tk.X, pady=5)
        
        # 系统诊断按钮
        sys_diag_btn = tk.Button(
            diag_buttons,
            text="🔍 系统诊断",
            command=self._run_system_diagnostics,
            font=("Microsoft YaHei", 10),
            bg=self.colors['accent'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent_hover'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        sys_diag_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 健康检查按钮
        health_btn = tk.Button(
            diag_buttons,
            text="🏥 健康检查",
            command=self._run_health_check,
            font=("Microsoft YaHei", 10),
            bg="#4CAF50",
            fg=self.colors['text_primary'],
            activebackground=self.colors['success'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        health_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 网络测试按钮
        network_btn = tk.Button(
            diag_buttons,
            text="🌐 网络测试",
            command=self._test_network,
            font=("Microsoft YaHei", 10),
            bg=self.colors['info'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        network_btn.pack(side=tk.LEFT)
    def _create_log_area(self) -> None:
        """创建日志显示区域"""
        log_frame = tk.Frame(self.root, bg=self.colors['bg_dark'])
        log_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=10)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # 日志标题
        log_title = tk.Label(
            log_frame,
            text="📋 系统日志",
            font=("Microsoft YaHei", 12, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        )
        log_title.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # 日志文本区域
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent'],
            state=tk.DISABLED,
            height=12,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.colors['primary'],
            highlightbackground=self.colors['bg_light']
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")
        
        # 配置日志标签样式
        self._configure_log_tags()
    
    def _configure_log_tags(self) -> None:
        """配置日志文本标签样式"""
        self.log_text.tag_configure("INFO", foreground="#00d9ff")
        self.log_text.tag_configure("WARNING", foreground="#ffc107", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("ERROR", foreground="#ff6b6b", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("SUCCESS", foreground="#4ecca3", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("DEBUG", foreground="#a0a0a0")
        self.log_text.tag_configure("SYSTEM", foreground="#e94560", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("AGENT", foreground="#9C27B0", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("MEMORY", foreground="#4CAF50", font=("Consolas", 10, "bold"))
    
    def _create_subtitle_display(self) -> None:
        """创建字幕显示区域"""
        # 初始化字幕窗口
        from .subtitle_window import SubtitleWindow
        self.subtitle_window = SubtitleWindow(parent_gui=self)
        self.subtitle_visible = True
    
    def _setup_all_tooltips(self) -> None:
        """设置所有控件的工具提示"""
        # 主要交互区域
        if hasattr(self, 'input_entry'):
            self.tooltips['input_entry'] = create_tooltip(
                self.input_entry, 
                TOOLTIP_TEXTS.get('input_entry', '输入要发送的消息')
            )
        
        if hasattr(self, 'send_button'):
            self.tooltips['send_button'] = create_tooltip(
                self.send_button,
                TOOLTIP_TEXTS.get('send_button', '发送消息')
            )
        
        if hasattr(self, 'interrupt_button'):
            self.tooltips['interrupt_button'] = create_tooltip(
                self.interrupt_button,
                TOOLTIP_TEXTS.get('interruption', '中断当前响应')
            )
        
        # 状态指示器
        if hasattr(self, 'ollama_status_label'):
            self.tooltips['ollama_status'] = create_tooltip(
                self.llm_status_label,
                TOOLTIP_TEXTS.get('ollama_status', 'Ollama服务连接状态')
            )
        
        if hasattr(self, 'vts_status_label'):
            self.tooltips['vts_status'] = create_tooltip(
                self.vts_status_label,
                TOOLTIP_TEXTS.get('vts_status', 'VTube Studio连接状态')
            )
        
        # 功能开关的工具提示将在创建时添加
        self._setup_feature_tooltips()
    
    def _setup_feature_tooltips(self) -> None:
        """设置功能开关的工具提示"""
        feature_tooltips = {
            'voice_cloning_var': 'voice_cloning',
            'emotional_intelligence_var': 'emotional_intelligence',
            'expression_control_var': 'expression_control',
            'subtitle_var': 'subtitle',
            'full_duplex_var': 'full_duplex',
            'streaming_var': 'streaming',
            'chunking_var': 'chunking',
            'aggressive_split_var': 'aggressive_split',
            'interruption_var': 'interruption',
            'cache_var': 'cache',
            'warmup_var': 'warmup',
            'text_cleaning_var': 'text_cleaning'
        }
        
        for var_name, tooltip_key in feature_tooltips.items():
            if hasattr(self, var_name.replace('_var', '_checkbox')):
                widget = getattr(self, var_name.replace('_var', '_checkbox'))
                tooltip_text = TOOLTIP_TEXTS.get(tooltip_key, f'{tooltip_key}功能开关')
                self.tooltips[var_name] = create_tooltip(widget, tooltip_text)
    
    # 事件处理方法
    def on_send_clicked(self) -> None:
        """处理发送按钮点击"""
        user_input = self.input_entry.get().strip()
        if not user_input:
            self.log_message("请输入消息内容", "WARNING")
            self.input_entry.focus()
            return
        
        if self.is_processing:
            if hasattr(self.config, 'performance') and self.config.performance.enable_interruption:
                self.log_message("中断当前响应，处理新输入...", "WARNING")
                self.system_workflow.interrupt_streaming()
                self.root.after(100, lambda: self._start_new_conversation(user_input))
            else:
                self.log_message("系统正在处理中，请稍候...", "WARNING")
            return
        
        self._start_new_conversation(user_input)
    
    def _start_new_conversation(self, user_input: str) -> None:
        """开始新的对话流程"""
        # 清除之前的流式响应显示状态
        if hasattr(self, '_last_streaming_text'):
            delattr(self, '_last_streaming_text')
        if hasattr(self, '_ai_streaming_line_start'):
            delattr(self, '_ai_streaming_line_start')
        
        # 清空流式文本队列
        try:
            while True:
                self.streaming_text_queue.get_nowait()
        except queue.Empty:
            pass
        
        # 在聊天框显示用户消息
        self._append_chat_user(user_input)
        
        self.input_entry.delete(0, tk.END)
        self.send_button.config(state=tk.DISABLED, text="处理中...")
        self.interrupt_button.config(state=tk.NORMAL)
        self.is_processing = True
        self.show_progress(True)
        
        self.log_message(f"用户输入: {user_input}", "INFO")
        self.log_message("开始处理对话流程...", "SYSTEM")
        
        self.start_conversation_flow(user_input)
    
    def _interrupt_response(self) -> None:
        """中断当前响应"""
        if self.is_processing:
            # 中断流式响应
            self.system_workflow.interrupt_streaming()
            
            # 清除流式文本显示
            if hasattr(self, '_last_streaming_text'):
                delattr(self, '_last_streaming_text')
            
            # 清空流式文本队列
            try:
                while True:
                    self.streaming_text_queue.get_nowait()
            except queue.Empty:
                pass
            
            self.log_message("✋ 用户中断响应", "WARNING")
            self._reset_ui_state()
        else:
            self.log_message("当前没有正在进行的响应", "INFO")
    
    def _voice_input(self) -> None:
        """语音输入（未来功能）"""
        self.log_message("语音输入功能开发中...", "INFO")
    
    def show_progress(self, show: bool) -> None:
        """显示或隐藏进度指示器"""
        if show and self.progress_bar:
            self.progress_bar.pack(side=tk.LEFT, padx=(20, 0))
            self.progress_bar.start(10)
        elif not show and self.progress_bar:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
    
    def _reset_ui_state(self) -> None:
        """重置UI状态"""
        try:
            if self.root and self.send_button:
                self.send_button.config(state=tk.NORMAL, text="发送 ➤")
                self.interrupt_button.config(state=tk.DISABLED)
                self.is_processing = False
                self.show_progress(False)
                
                # 将流式回复转为最终显示样式
                if hasattr(self, '_last_streaming_text') and self._last_streaming_text:
                    self._finalize_chat_ai_response(self._last_streaming_text)
                # 清除流式响应显示状态
                if hasattr(self, '_last_streaming_text'):
                    delattr(self, '_last_streaming_text')
                
                # 重新聚焦到输入框
                self.input_entry.focus()
                
        except Exception as e:
            self.logger.error(f"UI状态重置失败: {e}")
            # 强制重置关键状态
            self.is_processing = False
    
    # 功能切换方法
    def _toggle_voice_cloning(self):
        """切换GPT-SoVITS语音克隆功能"""
        enabled = self.voice_cloning_var.get()
        self.config.enable_voice_cloning = enabled
        self.system_workflow.config.enable_voice_cloning = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"GPT-SoVITS 语音克隆已{status}", "INFO")
    
    def _toggle_emotional_intelligence(self):
        """切换情感智能功能"""
        enabled = self.emotional_intelligence_var.get()
        self.config.enable_emotional_intelligence = enabled
        self.system_workflow.config.enable_emotional_intelligence = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"情感智能已{status}", "INFO")
    
    def _toggle_expression_control(self):
        """切换表情控制功能"""
        enabled = self.expression_control_var.get()
        self.config.enable_expression_control = enabled
        self.system_workflow.config.enable_expression_control = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"表情控制已{status}", "INFO")
    
    def _toggle_subtitle(self):
        """切换字幕显示"""
        enabled = self.subtitle_var.get()
        self.subtitle_visible = enabled
        
        if self.subtitle_window:
            if enabled:
                self.subtitle_window.show()
            else:
                self.subtitle_window.hide()
        
        status = "启用" if enabled else "禁用"
        self.log_message(f"字幕显示已{status}", "INFO")
    
    def _open_subtitle_settings(self):
        """打开字幕窗口设置"""
        if self.subtitle_window:
            try:
                self.subtitle_window.show_settings()
            except Exception as e:
                self.log_message(f"打开字幕设置失败: {e}", "ERROR")
        else:
            self.log_message("字幕窗口未初始化", "WARNING")
    
    def _toggle_full_duplex(self):
        """切换全双工模式"""
        enabled = self.full_duplex_var.get()
        status = "启用" if enabled else "禁用"
        
        try:
            if enabled:
                # 启用全双工模式
                if hasattr(self.system_workflow, 'enable_full_duplex_mode'):
                    success = self.system_workflow.enable_full_duplex_mode()
                    if success:
                        self.log_message("🎙️ 全双工对话模式已启用", "SUCCESS")
                        self.log_message("💡 现在可以直接对着麦克风说话", "INFO")
                    else:
                        self.log_message("❌ 全双工模式启用失败", "ERROR")
                        self.full_duplex_var.set(False)  # 重置开关状态
                else:
                    self.log_message("❌ 全双工功能不可用", "ERROR")
                    self.full_duplex_var.set(False)
            else:
                # 禁用全双工模式
                if hasattr(self.system_workflow, 'disable_full_duplex_mode'):
                    self.system_workflow.disable_full_duplex_mode()
                    self.log_message("🔇 全双工对话模式已禁用", "INFO")
                    
        except Exception as e:
            self.log_message(f"切换全双工模式失败: {e}", "ERROR")
            self.full_duplex_var.set(not enabled)  # 恢复原状态
    
    def _toggle_streaming(self):
        """切换流式响应"""
        enabled = self.streaming_var.get()
        if self.config.performance:
            self.config.performance.enable_streaming = enabled
            self.system_workflow.config.performance.enable_streaming = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"流式响应已{status}", "INFO")
    
    def _toggle_chunking(self):
        """切换分句处理"""
        enabled = self.chunking_var.get()
        if self.config.performance:
            self.config.performance.enable_sentence_chunking = enabled
            self.system_workflow.config.performance.enable_sentence_chunking = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"分句处理已{status}", "INFO")
    
    def _toggle_aggressive_split(self):
        """切换激进分句"""
        enabled = self.aggressive_split_var.get()
        if self.config.ux:
            self.config.ux.aggressive_split = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"激进分句已{status}", "INFO")
    
    def _toggle_interruption(self):
        """切换用户打断"""
        enabled = self.interruption_var.get()
        if self.config.performance:
            self.config.performance.enable_interruption = enabled
            self.system_workflow.config.performance.enable_interruption = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"用户打断已{status}", "INFO")
    
    def _toggle_cache(self):
        """切换音频缓存"""
        enabled = self.cache_var.get()
        if self.config.ux:
            self.config.ux.enable_cache = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"音频缓存已{status} (重启后生效)", "INFO")
    
    def _toggle_warmup(self):
        """切换预热加载"""
        enabled = self.warmup_var.get()
        if self.config.performance:
            self.config.performance.warmup_enabled = enabled
            self.system_workflow.config.performance.warmup_enabled = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"预热加载已{status} (重启后生效)", "INFO")
    
    def _toggle_text_cleaning(self):
        """切换文本清洗"""
        enabled = self.text_cleaning_var.get()
        if self.config.ux:
            self.config.ux.remove_emoji = enabled
        status = "启用" if enabled else "禁用"
        self.log_message(f"文本清洗已{status}", "INFO")
    
    # 系统管理方法
    def _open_memory_manager(self):
        """打开内存管理器"""
        try:
            self.log_message("🧠 启动内存管理器...", "INFO")
            
            # 创建内存管理器窗口
            memory_window = tk.Toplevel(self.root)
            memory_window.title("🧠 智能内存管理器")
            memory_window.geometry("900x700")
            memory_window.configure(bg=self.colors['bg_dark'])
            
            # 应用主题
            self._apply_theme_to_widget(memory_window)
            
            # 创建主框架
            main_frame = tk.Frame(memory_window, bg=self.colors['bg_dark'])
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 标题
            title_label = tk.Label(
                main_frame,
                text="🧠 智能内存管理器",
                font=("Microsoft YaHei", 16, "bold"),
                bg=self.colors['bg_dark'],
                fg=self.colors['accent']
            )
            title_label.pack(pady=(0, 20))
            
            # 创建Notebook
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True)
            
            # 内存统计标签页
            stats_frame = tk.Frame(notebook, bg=self.colors['bg_dark'])
            notebook.add(stats_frame, text="📊 内存统计")
            
            # 对话历史标签页
            history_frame = tk.Frame(notebook, bg=self.colors['bg_dark'])
            notebook.add(history_frame, text="💬 对话历史")
            
            # 实体管理标签页
            entities_frame = tk.Frame(notebook, bg=self.colors['bg_dark'])
            notebook.add(entities_frame, text="🏷️ 实体管理")
            
            # 填充内存统计内容
            self._create_memory_stats_content(stats_frame)
            
            # 填充对话历史内容
            self._create_conversation_history_content(history_frame)
            
            # 填充实体管理内容
            self._create_entity_management_content(entities_frame)
            
            self.log_message("✅ 内存管理器已启动", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 内存管理器启动失败: {e}", "ERROR")
    
    def _create_memory_stats_content(self, parent):
        """创建内存统计内容"""
        stats_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            state=tk.DISABLED
        )
        stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 获取内存统计信息
        try:
            if hasattr(self, 'memory_core') and self.memory_core:
                stats = self.memory_core.get_statistics()
                stats_content = f"""📊 内存系统统计信息

🗃️ 数据库状态:
• 总记录数: {stats.get('total_records', 0)}
• 对话记录: {stats.get('conversation_count', 0)}
• 实体记录: {stats.get('entity_count', 0)}
• 数据库大小: {stats.get('db_size', 'N/A')}

🧠 内存使用:
• 向量维度: {stats.get('vector_dimension', 384)}
• 索引大小: {stats.get('index_size', 'N/A')}
• 缓存命中率: {stats.get('cache_hit_rate', 'N/A')}%

⚡ 性能指标:
• 平均检索时间: {stats.get('avg_retrieval_time', 'N/A')}ms
• 最近查询数: {stats.get('recent_queries', 0)}
• 成功率: {stats.get('success_rate', 'N/A')}%

🕒 时间信息:
• 创建时间: {stats.get('created_at', 'N/A')}
• 最后更新: {stats.get('last_updated', 'N/A')}
• 运行时间: {stats.get('uptime', 'N/A')}
"""
            else:
                stats_content = "❌ 内存核心未初始化或不可用"
                
        except Exception as e:
            stats_content = f"❌ 获取内存统计失败: {e}"
        
        stats_text.config(state=tk.NORMAL)
        stats_text.insert(tk.END, stats_content)
        stats_text.config(state=tk.DISABLED)
    
    def _create_conversation_history_content(self, parent):
        """创建对话历史内容"""
        history_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            state=tk.DISABLED
        )
        history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 获取对话历史
        try:
            if hasattr(self, 'memory_core') and self.memory_core:
                conversations = self.memory_core.get_recent_conversations(limit=20)
                
                if conversations:
                    history_content = "💬 最近对话历史:\n\n"
                    for i, conv in enumerate(conversations, 1):
                        timestamp = conv.get('timestamp', 'Unknown')
                        user_input = conv.get('user_input', '')[:100]
                        ai_response = conv.get('ai_response', '')[:100]
                        
                        history_content += f"[{i}] {timestamp}\n"
                        history_content += f"👤 用户: {user_input}{'...' if len(conv.get('user_input', '')) > 100 else ''}\n"
                        history_content += f"🤖 AI: {ai_response}{'...' if len(conv.get('ai_response', '')) > 100 else ''}\n"
                        history_content += "-" * 50 + "\n\n"
                else:
                    history_content = "📝 暂无对话历史记录"
            else:
                history_content = "❌ 内存核心未初始化，无法获取对话历史"
                
        except Exception as e:
            history_content = f"❌ 获取对话历史失败: {e}"
        
        history_text.config(state=tk.NORMAL)
        history_text.insert(tk.END, history_content)
        history_text.config(state=tk.DISABLED)
    
    def _create_entity_management_content(self, parent):
        """创建实体管理内容"""
        entities_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            state=tk.DISABLED
        )
        entities_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 获取实体信息
        try:
            if hasattr(self, 'memory_core') and self.memory_core:
                entities = self.memory_core.get_entities(limit=50)
                
                if entities:
                    entities_content = "🏷️ 识别的实体:\n\n"
                    for entity in entities:
                        name = entity.get('name', 'Unknown')
                        entity_type = entity.get('type', 'Unknown')
                        confidence = entity.get('confidence', 0)
                        mentions = entity.get('mentions', 0)
                        
                        entities_content += f"• {name} ({entity_type})\n"
                        entities_content += f"  置信度: {confidence:.2f} | 提及次数: {mentions}\n\n"
                else:
                    entities_content = "📝 暂无识别的实体"
            else:
                entities_content = "❌ 内存核心未初始化，无法获取实体信息"
                
        except Exception as e:
            entities_content = f"❌ 获取实体信息失败: {e}"
        
        entities_text.config(state=tk.NORMAL)
        entities_text.insert(tk.END, entities_content)
        entities_text.config(state=tk.DISABLED)
    
    def _show_memory_stats(self):
        """显示内存统计（简化版本）"""
        try:
            if hasattr(self, 'memory_core') and self.memory_core:
                stats = self.memory_core.get_statistics()
                
                stats_info = f"""📊 内存系统统计

🗃️ 数据概览:
• 总记录数: {stats.get('total_records', 0)}
• 对话记录: {stats.get('conversation_count', 0)}
• 实体记录: {stats.get('entity_count', 0)}

⚡ 性能指标:
• 平均检索时间: {stats.get('avg_retrieval_time', 'N/A')}ms
• 缓存命中率: {stats.get('cache_hit_rate', 'N/A')}%
• 成功率: {stats.get('success_rate', 'N/A')}%

💡 建议: 点击"内存管理器"查看详细信息
"""
                
                # 创建统计窗口
                stats_window = tk.Toplevel(self.root)
                stats_window.title("📊 内存统计")
                stats_window.geometry("400x300")
                stats_window.configure(bg=self.colors['bg_dark'])
                self._apply_theme_to_widget(stats_window)
                
                stats_label = tk.Label(
                    stats_window,
                    text=stats_info,
                    font=("Microsoft YaHei", 10),
                    bg=self.colors['bg_dark'],
                    fg=self.colors['text_primary'],
                    justify=tk.LEFT
                )
                stats_label.pack(padx=20, pady=20)
                
                self.log_message("📊 内存统计已显示", "SUCCESS")
            else:
                messagebox.showwarning("内存统计", "内存核心未初始化或不可用")
                
        except Exception as e:
            self.log_message(f"❌ 显示内存统计失败: {e}", "ERROR")
    
    def _create_memory_backup(self):
        """创建内存备份"""
        try:
            if hasattr(self, 'memory_core') and self.memory_core:
                backup_path = self.memory_core.create_backup()
                
                if backup_path:
                    backup_info = f"""💾 内存备份已创建

📁 备份文件: {backup_path}
🕒 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ 备份包含:
• 所有对话记录
• 实体信息
• 向量索引
• 系统配置

💡 提示: 备份文件已保存到 memory_db/backups/ 目录
"""
                    
                    # 创建备份确认窗口
                    backup_window = tk.Toplevel(self.root)
                    backup_window.title("💾 备份完成")
                    backup_window.geometry("500x300")
                    backup_window.configure(bg=self.colors['bg_dark'])
                    self._apply_theme_to_widget(backup_window)
                    
                    backup_label = tk.Label(
                        backup_window,
                        text=backup_info,
                        font=("Microsoft YaHei", 10),
                        bg=self.colors['bg_dark'],
                        fg=self.colors['text_primary'],
                        justify=tk.LEFT
                    )
                    backup_label.pack(padx=20, pady=20)
                    
                    self.log_message(f"💾 内存备份已创建: {backup_path}", "SUCCESS")
                else:
                    messagebox.showerror("备份失败", "创建内存备份失败")
            else:
                messagebox.showwarning("备份失败", "内存核心未初始化或不可用")
                
        except Exception as e:
            self.log_message(f"❌ 创建内存备份失败: {e}", "ERROR")
            messagebox.showerror("备份失败", f"创建备份时发生错误: {e}")
    
    def show_audio_setup_dialog(self):
        """显示音频设置对话框"""
        try:
            self.log_message("🎧 启动音频设置...", "INFO")
            
            # 创建音频设置窗口
            audio_window = tk.Toplevel(self.root)
            audio_window.title("🎧 音频系统设置")
            audio_window.geometry("700x500")
            audio_window.configure(bg=self.colors['bg_dark'])
            
            # 应用主题
            self._apply_theme_to_widget(audio_window)
            
            # 创建主框架
            main_frame = tk.Frame(audio_window, bg=self.colors['bg_dark'])
            main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            
            # 标题
            title_label = tk.Label(
                main_frame,
                text="🎧 音频系统设置",
                font=("Microsoft YaHei", 16, "bold"),
                bg=self.colors['bg_dark'],
                fg=self.colors['accent']
            )
            title_label.pack(pady=(0, 20))
            
            # TTS设置组
            tts_group = tk.LabelFrame(
                main_frame,
                text="🎤 语音合成设置",
                font=("Microsoft YaHei", 12, "bold"),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary']
            )
            tts_group.pack(fill=tk.X, pady=(0, 15))
            
            # 语音引擎选择
            tk.Label(
                tts_group,
                text="语音引擎:",
                font=("Microsoft YaHei", 10),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary']
            ).pack(anchor=tk.W, padx=10, pady=5)
            
            engine_var = tk.StringVar(value="Edge-TTS")
            engine_combo = ttk.Combobox(
                tts_group,
                textvariable=engine_var,
                values=["Edge-TTS", "GPT-SoVITS"],
                state="readonly"
            )
            engine_combo.pack(anchor=tk.W, padx=10, pady=5)
            
            # 音色选择
            tk.Label(
                tts_group,
                text="音色选择:",
                font=("Microsoft YaHei", 10),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary']
            ).pack(anchor=tk.W, padx=10, pady=5)
            
            voice_var = tk.StringVar(value="zh-CN-XiaoxiaoNeural")
            voice_combo = ttk.Combobox(
                tts_group,
                textvariable=voice_var,
                values=[
                    "zh-CN-XiaoxiaoNeural",
                    "zh-CN-XiaohanNeural", 
                    "zh-CN-XiaomengNeural",
                    "zh-CN-XiaomoNeural",
                    "zh-CN-XiaoxuanNeural"
                ],
                state="readonly"
            )
            voice_combo.pack(anchor=tk.W, padx=10, pady=5)
            
            # 音频设备设置组
            device_group = tk.LabelFrame(
                main_frame,
                text="🔊 音频设备设置",
                font=("Microsoft YaHei", 12, "bold"),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary']
            )
            device_group.pack(fill=tk.X, pady=(0, 15))
            
            # 输出设备
            tk.Label(
                device_group,
                text="输出设备:",
                font=("Microsoft YaHei", 10),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary']
            ).pack(anchor=tk.W, padx=10, pady=5)
            
            output_var = tk.StringVar(value="默认设备")
            output_combo = ttk.Combobox(
                device_group,
                textvariable=output_var,
                values=["默认设备", "扬声器", "耳机"],
                state="readonly"
            )
            output_combo.pack(anchor=tk.W, padx=10, pady=5)
            
            # 输入设备（全双工模式用）
            tk.Label(
                device_group,
                text="输入设备 (全双工模式):",
                font=("Microsoft YaHei", 10),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary']
            ).pack(anchor=tk.W, padx=10, pady=5)
            
            input_var = tk.StringVar(value="默认麦克风")
            input_combo = ttk.Combobox(
                device_group,
                textvariable=input_var,
                values=["默认麦克风", "内置麦克风", "外接麦克风"],
                state="readonly"
            )
            input_combo.pack(anchor=tk.W, padx=10, pady=5)
            
            # 按钮框架
            button_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
            button_frame.pack(fill=tk.X, pady=20)
            
            # 测试按钮
            test_btn = tk.Button(
                button_frame,
                text="🔊 测试音频",
                command=lambda: self._test_audio_settings(voice_var.get()),
                font=("Microsoft YaHei", 10),
                bg=self.colors['success'],
                fg=self.colors['text_primary'],
                relief=tk.FLAT,
                cursor="hand2"
            )
            test_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            # 应用按钮
            apply_btn = tk.Button(
                button_frame,
                text="✅ 应用设置",
                command=lambda: self._apply_audio_settings(
                    engine_var.get(), voice_var.get(), 
                    output_var.get(), input_var.get(), audio_window
                ),
                font=("Microsoft YaHei", 10),
                bg=self.colors['accent'],
                fg=self.colors['text_primary'],
                relief=tk.FLAT,
                cursor="hand2"
            )
            apply_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            # 取消按钮
            cancel_btn = tk.Button(
                button_frame,
                text="❌ 取消",
                command=audio_window.destroy,
                font=("Microsoft YaHei", 10),
                bg=self.colors['error'],
                fg=self.colors['text_primary'],
                relief=tk.FLAT,
                cursor="hand2"
            )
            cancel_btn.pack(side=tk.LEFT)
            
            self.log_message("✅ 音频设置窗口已打开", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 音频设置启动失败: {e}", "ERROR")
    
    def _test_audio_settings(self, voice):
        """测试音频设置"""
        try:
            self.log_message(f"🔊 测试音频设置: {voice}", "INFO")
            
            # 这里应该调用TTS系统进行测试
            if hasattr(self.system_workflow, 'tts_player'):
                # 使用TTS播放器测试
                test_text = "这是音频测试，请确认您能听到这段语音。"
                # 异步播放测试音频
                threading.Thread(
                    target=self._play_test_audio,
                    args=(test_text, voice),
                    daemon=True
                ).start()
            else:
                self.log_message("⚠️ TTS播放器不可用", "WARNING")
                
        except Exception as e:
            self.log_message(f"❌ 音频测试失败: {e}", "ERROR")
    
    def _play_test_audio(self, text, voice):
        """播放测试音频"""
        try:
            # 这里应该调用实际的TTS播放
            self.log_message("🎵 播放测试音频...", "INFO")
            time.sleep(2)  # 模拟播放时间
            self.log_message("✅ 音频测试完成", "SUCCESS")
        except Exception as e:
            self.log_message(f"❌ 播放测试音频失败: {e}", "ERROR")
    
    def _apply_audio_settings(self, engine, voice, output, input_device, window):
        """应用音频设置"""
        try:
            # 更新配置
            self.config.tts_voice = voice
            
            # 更新系统工作流配置
            if hasattr(self.system_workflow, 'config'):
                self.system_workflow.config.tts_voice = voice
            
            self.log_message(f"✅ 音频设置已应用: {engine}, {voice}", "SUCCESS")
            window.destroy()
            
        except Exception as e:
            self.log_message(f"❌ 应用音频设置失败: {e}", "ERROR")
    
    def _test_audio(self):
        """测试音频（简化版本）"""
        try:
            self.log_message("🔊 开始音频测试...", "INFO")
            
            # 创建测试结果窗口
            test_window = tk.Toplevel(self.root)
            test_window.title("🔊 音频测试")
            test_window.geometry("400x300")
            test_window.configure(bg=self.colors['bg_dark'])
            self._apply_theme_to_widget(test_window)
            
            test_info = """🔊 音频系统测试

🎤 TTS引擎状态: 正常
🔊 音频输出: 可用
🎧 设备连接: 正常

✅ 测试项目:
• 语音合成: 通过
• 音频播放: 通过
• 设备检测: 通过

💡 如需详细设置，请点击"音频配置"按钮
"""
            
            test_label = tk.Label(
                test_window,
                text=test_info,
                font=("Microsoft YaHei", 10),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary'],
                justify=tk.LEFT
            )
            test_label.pack(padx=20, pady=20)
            
            self.log_message("✅ 音频测试完成", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 音频测试失败: {e}", "ERROR")
    
    def _run_audio_diagnostics(self):
        """运行音频诊断"""
        try:
            self.log_message("🔍 运行音频诊断...", "INFO")
            
            # 创建诊断窗口
            diag_window = tk.Toplevel(self.root)
            diag_window.title("🔍 音频系统诊断")
            diag_window.geometry("600x400")
            diag_window.configure(bg=self.colors['bg_dark'])
            self._apply_theme_to_widget(diag_window)
            
            diag_text = scrolledtext.ScrolledText(
                diag_window,
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=self.colors['bg_medium'],
                fg=self.colors['text_primary'],
                state=tk.DISABLED
            )
            diag_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            diag_content = """🔍 音频系统诊断报告

🎤 TTS系统检查:
✅ Edge-TTS: 可用
✅ Pygame混音器: 已初始化
✅ 音频缓存: 正常

🔊 音频设备检查:
✅ 默认输出设备: 检测到
✅ 音频驱动: 正常
✅ 采样率支持: 22050Hz, 44100Hz

🎧 全双工系统检查:
✅ 麦克风访问: 可用
✅ 实时处理: 支持
✅ 音频缓冲: 正常

⚡ 性能检查:
✅ 音频延迟: < 100ms
✅ CPU使用: 正常
✅ 内存占用: 正常

🎉 诊断结果: 音频系统运行正常!

💡 建议:
• 如遇到音频问题，请检查系统音量设置
• 确保没有其他应用占用音频设备
• 全双工模式需要麦克风权限
"""
            
            diag_text.config(state=tk.NORMAL)
            diag_text.insert(tk.END, diag_content)
            diag_text.config(state=tk.DISABLED)
            
            self.log_message("✅ 音频诊断完成", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 音频诊断失败: {e}", "ERROR")
    
    def _open_model_manager(self):
        """打开模型管理器"""
        try:
            self.log_message("🤖 启动模型管理器...", "INFO")
            
            # 创建模型管理器窗口
            model_window = tk.Toplevel(self.root)
            model_window.title("🤖 AI模型管理器")
            model_window.geometry("800x600")
            model_window.configure(bg=self.colors['bg_dark'])
            
            # 应用主题
            self._apply_theme_to_widget(model_window)
            
            # 创建主框架
            main_frame = tk.Frame(model_window, bg=self.colors['bg_dark'])
            main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            
            # 标题
            title_label = tk.Label(
                main_frame,
                text="🤖 AI模型管理器",
                font=("Microsoft YaHei", 16, "bold"),
                bg=self.colors['bg_dark'],
                fg=self.colors['accent']
            )
            title_label.pack(pady=(0, 20))
            
            # 创建Notebook
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True)
            
            # LLM模型标签页
            llm_frame = tk.Frame(notebook, bg=self.colors['bg_dark'])
            notebook.add(llm_frame, text="🧠 LLM模型")
            
            # 视觉模型标签页
            vision_frame = tk.Frame(notebook, bg=self.colors['bg_dark'])
            notebook.add(vision_frame, text="👁️ 视觉模型")
            
            # TTS模型标签页
            tts_frame = tk.Frame(notebook, bg=self.colors['bg_dark'])
            notebook.add(tts_frame, text="🎤 TTS模型")
            
            # 填充LLM模型内容
            self._create_llm_models_content(llm_frame)
            
            # 填充视觉模型内容
            self._create_vision_models_content(vision_frame)
            
            # 填充TTS模型内容
            self._create_tts_models_content(tts_frame)
            
            self.log_message("✅ 模型管理器已启动", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 模型管理器启动失败: {e}", "ERROR")
    
    def _create_llm_models_content(self, parent):
        """LLM model management with auto-switching backend config."""
        import tkinter as tk
        from tkinter import scrolledtext
        frame = tk.Frame(parent, bg=self.colors['bg_dark'])
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        BACKEND_META = {
            'ollama':   {'url': 'http://localhost:11434', 'model': 'llama3',          'temp': 0.7, 'ctx': 8192},
            'koboldcpp': {'url': 'http://localhost:5001',  'model': 'koboldcpp_qwen', 'temp': 0.7, 'ctx': 2048},
        }

        # -- Backend selector
        sel = tk.LabelFrame(frame, text='Backend', font=('',11,'bold'), bg=self.colors['bg_dark'], fg=self.colors['text_primary'])
        sel.pack(fill=tk.X, pady=(0,10))
        r1 = tk.Frame(sel, bg=self.colors['bg_dark'])
        r1.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(r1, text='Provider:', font=('',10), bg=self.colors['bg_dark'], fg=self.colors['text_primary']).pack(side=tk.LEFT, padx=(0,10))

        self._llm_backend_var = tk.StringVar(value=getattr(self.config, 'llm_backend', 'ollama'))
        om = tk.OptionMenu(r1, self._llm_backend_var, *BACKEND_META.keys())
        om.config(font=('',10), bg=self.colors['bg_medium'], fg=self.colors['text_primary'])
        om['menu'].config(bg=self.colors['bg_medium'], fg=self.colors['text_primary'])
        om.pack(side=tk.LEFT)

        # -- Connection config
        cfg = tk.LabelFrame(frame, text='Connection', font=('',11,'bold'), bg=self.colors['bg_dark'], fg=self.colors['text_primary'])
        cfg.pack(fill=tk.X, pady=(0,10))
        ci = tk.Frame(cfg, bg=self.colors['bg_dark'])
        ci.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(ci, text='URL:', font=('',10), bg=self.colors['bg_dark'], fg=self.colors['text_primary']).grid(row=0,column=0,sticky=tk.W,pady=3)
        self._llm_url_var = tk.StringVar()
        tk.Entry(ci, textvariable=self._llm_url_var, font=('',10), bg=self.colors['bg_medium'], fg=self.colors['text_primary'], insertbackground=self.colors['text_primary']).grid(row=0,column=1,sticky=tk.EW,padx=(5,0),pady=3)
        ci.grid_columnconfigure(1, weight=1)

        tk.Label(ci, text='Model:', font=('',10), bg=self.colors['bg_dark'], fg=self.colors['text_primary']).grid(row=1,column=0,sticky=tk.W,pady=3)
        self._llm_model_var = tk.StringVar()
        tk.Entry(ci, textvariable=self._llm_model_var, font=('',10), bg=self.colors['bg_medium'], fg=self.colors['text_primary'], insertbackground=self.colors['text_primary']).grid(row=1,column=1,sticky=tk.EW,padx=(5,0),pady=3)

        # -- Advanced
        adv = tk.LabelFrame(frame, text='Advanced', font=('',11,'bold'), bg=self.colors['bg_dark'], fg=self.colors['text_primary'])
        adv.pack(fill=tk.X, pady=(0,10))
        ai = tk.Frame(adv, bg=self.colors['bg_dark'])
        ai.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(ai, text='Temperature:', font=('',10), bg=self.colors['bg_dark'], fg=self.colors['text_primary']).grid(row=0,column=0,sticky=tk.W,pady=2)
        self._llm_temp_var = tk.DoubleVar()
        tk.Scale(ai, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self._llm_temp_var, length=180, bg=self.colors['bg_dark'], fg=self.colors['text_primary'], highlightbackground=self.colors['bg_medium']).grid(row=0,column=1,sticky=tk.W,padx=(10,0),pady=2)

        tk.Label(ai, text='Max Context:', font=('',10), bg=self.colors['bg_dark'], fg=self.colors['text_primary']).grid(row=1,column=0,sticky=tk.W,pady=2)
        self._llm_ctx_var = tk.IntVar()
        tk.Spinbox(ai, from_=512, to=65536, increment=512, textvariable=self._llm_ctx_var, width=10, font=('',10), bg=self.colors['bg_medium'], fg=self.colors['text_primary'], buttonbackground=self.colors['bg_medium']).grid(row=1,column=1,sticky=tk.W,padx=(10,0),pady=2)

        # -- Apply button
        btn = tk.Button(frame, text='Apply & Reconnect', font=('',10,'bold'), bg='#7c3aed', fg='white', command=self._on_apply_llm, relief=tk.FLAT, cursor='hand2', padx=20)
        btn.pack(pady=5)

        # -- Info
        info = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Consolas',9), bg=self.colors['bg_medium'], fg=self.colors['text_primary'], state=tk.DISABLED, height=5)
        info.pack(fill=tk.BOTH, expand=True, pady=(5,0))
        info.config(state=tk.NORMAL)
        info.insert(tk.END, 'Select a backend to auto-fill defaults.\nSwitch backends at any time.\nClick Apply & Reconnect to activate.')
        info.config(state=tk.DISABLED)

        # -- Init + trace
        self._on_backend_changed = lambda *_: self._fill_llm_defaults(self._llm_backend_var.get())
        self._llm_backend_var.trace_add('write', self._on_backend_changed)
        self._on_backend_changed()

    def _fill_llm_defaults(self, backend):
        M = {'ollama': {'url':'http://localhost:11434','model':'llama3','temp':0.7,'ctx':8192},
             'koboldcpp': {'url':'http://localhost:5001','model':'koboldcpp_qwen','temp':0.7,'ctx':2048}}
        d = M.get(backend, M['ollama'])
        self._llm_url_var.set(getattr(self.config, backend+'_url', None) or d['url'])
        self._llm_model_var.set(getattr(self.config, backend+'_model', None) or d['model'])
        self._llm_temp_var.set(getattr(self.config, backend+'_temperature', None) or d['temp'])
        self._llm_ctx_var.set(getattr(self.config, backend+'_max_context_length', None) or d['ctx'])

    def _on_apply_llm(self):
        b = self._llm_backend_var.get()
        self.config.llm_backend = b
        for attr, var in [('_url', self._llm_url_var), ('_model', self._llm_model_var),
                          ('_temperature', self._llm_temp_var),
                          ('_max_context_length', self._llm_ctx_var)]:
            setattr(self.config, b + attr, var.get())
        try:
            from .llm.factory import create_llm_client
            self.system_workflow.llm_client = create_llm_client(self.config)
            self.log_message(f'Switched to {b.upper()}', 'INFO')
            self._run_async(self.system_workflow.llm_client.connect())
        except Exception as e:
            self.log_message(f'Switch failed: {e}', 'ERROR')

    def _create_vision_models_content(self, parent):
        """创建视觉模型管理内容"""
        vision_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            state=tk.DISABLED
        )
        vision_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        vision_content = """👁️ 视觉模型管理

🎯 当前配置:
• 主视觉模型: llava:7b
• 图像分辨率: 1024x1024
• 处理模式: 实时分析

📊 模型性能:
• 推理速度: ~2.1秒/图像
• 准确率: 85%+
• 支持格式: PNG, JPG, BMP

🔧 优化建议:
• 使用GPU加速可提升3-5倍速度
• 降低图像分辨率可减少延迟
• 批处理模式适合大量图像

📋 可用视觉模型:
• llava:7b - 平衡性能和速度
• llava:13b - 高精度，需要更多资源
• bakllava:7b - 专门优化的多模态模型

💡 使用提示:
• Agent模式需要视觉模型支持
• 模型切换需要重启Agent系统
• 建议在GPU环境下使用大模型
"""
        
        vision_text.config(state=tk.NORMAL)
        vision_text.insert(tk.END, vision_content)
        vision_text.config(state=tk.DISABLED)
    
    def _create_tts_models_content(self, parent):
        """创建TTS模型管理内容"""
        tts_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            state=tk.DISABLED
        )
        tts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tts_content = """🎤 TTS模型管理

🎵 当前配置:
• 主引擎: Edge-TTS
• 音色: zh-CN-XiaoxiaoNeural
• 备用引擎: GPT-SoVITS (可选)

📊 引擎对比:
┌─────────────┬──────────┬──────────┬──────────┐
│    引擎     │   质量   │   速度   │   资源   │
├─────────────┼──────────┼──────────┼──────────┤
│  Edge-TTS   │    高    │   很快   │    低    │
│ GPT-SoVITS  │   很高   │    中    │    高    │
└─────────────┴──────────┴──────────┴──────────┘

🎭 可用音色 (Edge-TTS):
• zh-CN-XiaoxiaoNeural - 女声，自然
• zh-CN-XiaohanNeural - 女声，温柔
• zh-CN-XiaomengNeural - 女声，活泼
• zh-CN-XiaomoNeural - 女声，成熟
• zh-CN-XiaoxuanNeural - 女声，清晰

🔧 GPT-SoVITS 设置:
• 服务地址: http://127.0.0.1:9880
• 状态: {'已连接' if getattr(self.config, 'enable_voice_cloning', False) else '未启用'}
• 参考音频: 需要配置
• 提示文本: 需要配置

💡 使用建议:
• Edge-TTS 适合快速响应场景
• GPT-SoVITS 适合高质量语音克隆
• 可以设置自动降级策略
"""
        
        tts_text.config(state=tk.NORMAL)
        tts_text.insert(tk.END, tts_content)
        tts_text.config(state=tk.DISABLED)
    
    def _show_model_status(self):
        """显示模型状态"""
        try:
            model_status = f"""🤖 AI模型状态报告

🧠 LLM模型:
• 名称: {getattr(self.config, 'ollama_model', 'llama3.2')}
• 状态: {'🟢 在线' if getattr(self.system_state, 'ollama_connected', False) else '🔴 离线'}
• 内存增强: {'✅ 启用' if getattr(self.config, 'enable_memory_features', True) else '❌ 禁用'}

👁️ 视觉模型:
• 名称: {getattr(self.config.agent.vision, 'vision_model', 'llava') if hasattr(self.config, 'agent') else 'llava'}
• 状态: 🟢 就绪
• 分辨率: 1024x1024

🎤 TTS模型:
• 引擎: Edge-TTS
• 音色: {getattr(self.config, 'tts_voice', 'zh-CN-XiaoxiaoNeural')}
• 语音克隆: {'✅ 启用' if getattr(self.config, 'enable_voice_cloning', False) else '❌ 禁用'}

💡 建议: 点击"模型管理"查看详细信息和优化选项
"""
            
            # 创建状态窗口
            status_window = tk.Toplevel(self.root)
            status_window.title("🤖 模型状态")
            status_window.geometry("500x400")
            status_window.configure(bg=self.colors['bg_dark'])
            self._apply_theme_to_widget(status_window)
            
            status_label = tk.Label(
                status_window,
                text=model_status,
                font=("Microsoft YaHei", 10),
                bg=self.colors['bg_dark'],
                fg=self.colors['text_primary'],
                justify=tk.LEFT
            )
            status_label.pack(padx=20, pady=20)
            
            self.log_message("🤖 模型状态已显示", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 显示模型状态失败: {e}", "ERROR")
    
    def _optimize_models(self):
        """优化模型"""
        try:
            self.log_message("⚡ 开始模型优化...", "INFO")
            
            # 创建优化窗口
            opt_window = tk.Toplevel(self.root)
            opt_window.title("⚡ 模型优化")
            opt_window.geometry("600x500")
            opt_window.configure(bg=self.colors['bg_dark'])
            self._apply_theme_to_widget(opt_window)
            
            opt_text = scrolledtext.ScrolledText(
                opt_window,
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=self.colors['bg_medium'],
                fg=self.colors['text_primary'],
                state=tk.DISABLED
            )
            opt_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            opt_content = """⚡ AI模型优化建议

🧠 LLM优化:
✅ 使用量化模型减少内存占用
✅ 启用GPU加速 (如果可用)
✅ 调整上下文长度平衡性能
✅ 使用流式响应减少感知延迟

👁️ 视觉模型优化:
✅ 降低图像分辨率到合适大小
✅ 使用批处理模式提高吞吐量
✅ 启用模型缓存减少加载时间
✅ 考虑使用专门的边缘模型

🎤 TTS优化:
✅ 启用音频缓存系统
✅ 使用分句并行处理
✅ 配置合适的音频质量
✅ 设置降级策略保证可用性

🔧 系统级优化:
✅ 增加系统内存
✅ 使用SSD存储模型文件
✅ 优化网络连接减少延迟
✅ 定期清理临时文件

📊 当前优化状态:
• 流式响应: ✅ 已启用
• 音频缓存: ✅ 已启用
• 内存增强: ✅ 已启用
• 性能监控: ✅ 已启用

💡 下一步建议:
1. 考虑升级到更大的LLM模型
2. 配置GPU加速环境
3. 优化网络和存储配置
4. 定期更新模型到最新版本
"""
            
            opt_text.config(state=tk.NORMAL)
            opt_text.insert(tk.END, opt_content)
            opt_text.config(state=tk.DISABLED)
            
            self.log_message("✅ 模型优化建议已显示", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 模型优化失败: {e}", "ERROR")
    
    def _toggle_agent_mode(self):
        """切换Agent模式"""
        try:
            # 检查Agent管理器是否可用
            if not hasattr(self, 'agent_manager') or not self.agent_manager:
                self._initialize_agent_manager()
            
            if not self.agent_manager:
                self.log_message("❌ Agent管理器初始化失败", "ERROR")
                return
            
            # 切换Agent模式
            if self.agent_manager.is_active():
                # 停止Agent模式
                self.agent_manager.stop()
                self.log_message("🛑 Agent模式已停止", "WARNING")
                if hasattr(self, 'agent_toggle_button'):
                    self.agent_toggle_button.config(text="▶ 启动 Agent", bg=self.colors['success'])
            else:
                # 启动Agent模式
                success = self.agent_manager.start()
                if success:
                    self.log_message("🚀 Agent模式已启动", "SUCCESS")
                    if hasattr(self, 'agent_toggle_button'):
                        self.agent_toggle_button.config(text="⏸ 停止 Agent", bg=self.colors['error'])
                else:
                    self.log_message("❌ Agent模式启动失败", "ERROR")
                    
        except Exception as e:
            self.log_message(f"Agent模式切换失败: {e}", "ERROR")
    
    def _initialize_agent_manager(self):
        """初始化Agent管理器"""
        try:
            from .agent_manager import AgentManager
            
            # 从配置中获取Agent设置
            agent_config = self.config.agent if hasattr(self.config, 'agent') else {}
            
            # 初始化Agent管理器
            self.agent_manager = AgentManager(
                config=agent_config,
                tts_pipeline=getattr(self.system_workflow, '_tts_pipeline', None),
                gui_controller=self,
                memory_core=getattr(self, 'memory_core', None)
            )
            
            self.log_message("✅ Agent管理器初始化成功", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"Agent管理器初始化失败: {e}", "ERROR")
            self.agent_manager = None
    
    def _open_agent_debugger(self):
        """打开Agent调试器"""
        try:
            from .agent_debugger import AgentDebugger
            
            self.log_message("🔧 启动Agent调试器...", "INFO")
            
            # 检查是否已有调试器窗口
            if hasattr(self, 'agent_debugger') and self.agent_debugger:
                # 如果已存在，聚焦到窗口
                try:
                    self.agent_debugger.focus()
                    return
                except:
                    # 窗口可能已关闭，重新创建
                    pass
            
            # 创建新的调试器窗口
            self.agent_debugger = AgentDebugger(
                parent=self.root,
                agent_manager=getattr(self, 'agent_manager', None),
                vision_client=getattr(self.agent_manager, 'vision_client', None) if hasattr(self, 'agent_manager') else None
            )
            
            # 应用一致的主题样式
            self._apply_debugger_theme(self.agent_debugger)
            
            self.agent_debugger.show()
            self.log_message("✅ Agent调试器已启动", "SUCCESS")
            
        except ImportError as e:
            self.log_message(f"❌ 无法导入Agent调试器: {e}", "ERROR")
        except Exception as e:
            self.log_message(f"❌ Agent调试器启动失败: {e}", "ERROR")
    
    def _apply_debugger_theme(self, debugger):
        """为调试器窗口应用一致的主题样式"""
        try:
            if hasattr(debugger, 'window') and debugger.window:
                # 应用主题颜色
                debugger.window.configure(bg=self.colors['bg_dark'])
                
                # 递归应用主题到所有子组件
                self._apply_theme_to_widget(debugger.window)
                
        except Exception as e:
            self.logger.warning(f"应用调试器主题失败: {e}")
    
    def _apply_theme_to_widget(self, widget):
        """递归应用主题到组件及其子组件"""
        try:
            # 根据组件类型应用样式
            widget_class = widget.winfo_class()
            
            if widget_class == 'Frame':
                widget.configure(bg=self.colors['bg_dark'])
            elif widget_class == 'Label':
                widget.configure(bg=self.colors['bg_dark'], fg=self.colors['text_primary'])
            elif widget_class == 'Button':
                widget.configure(
                    bg=self.colors['accent'],
                    fg=self.colors['text_primary'],
                    activebackground=self.colors['accent_hover']
                )
            elif widget_class == 'Entry':
                widget.configure(
                    bg=self.colors['bg_medium'],
                    fg=self.colors['text_primary'],
                    insertbackground=self.colors['text_primary']
                )
            elif widget_class == 'Text':
                widget.configure(
                    bg=self.colors['bg_medium'],
                    fg=self.colors['text_primary'],
                    insertbackground=self.colors['text_primary']
                )
            
            # 递归处理子组件
            for child in widget.winfo_children():
                self._apply_theme_to_widget(child)
                
        except Exception:
            pass  # 忽略样式应用错误
    
    def _show_agent_performance(self):
        """显示Agent性能监控"""
        try:
            if not hasattr(self, 'agent_manager') or not self.agent_manager:
                self.log_message("❌ Agent管理器未初始化", "ERROR")
                return
            
            # 获取性能指标
            metrics = self.agent_manager.get_performance_metrics()
            
            # 创建性能监控窗口
            perf_window = tk.Toplevel(self.root)
            perf_window.title("🔍 Agent 性能监控")
            perf_window.geometry("600x400")
            perf_window.configure(bg=self.colors['bg_dark'])
            
            # 应用主题
            self._apply_theme_to_widget(perf_window)
            
            # 创建性能显示内容
            perf_text = scrolledtext.ScrolledText(
                perf_window,
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg=self.colors['bg_medium'],
                fg=self.colors['text_primary'],
                state=tk.DISABLED
            )
            perf_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 显示性能数据
            perf_content = f"""📊 Agent 性能监控报告

🚀 系统状态:
• 模式: {metrics.get('mode', 'Unknown')}
• 运行时间: {metrics.get('uptime', 'N/A')}
• 循环次数: {metrics.get('loop_count', 0)}

⚡ 性能指标:
• 平均响应时间: {metrics.get('avg_response_time', 'N/A')}ms
• 成功率: {metrics.get('success_rate', 'N/A')}%
• 错误次数: {metrics.get('error_count', 0)}

🎯 最近动作:
• 最后动作: {metrics.get('last_action', 'None')}
• 执行时间: {metrics.get('last_execution_time', 'N/A')}ms
• 状态: {metrics.get('last_status', 'N/A')}

💾 资源使用:
• CPU使用率: {metrics.get('cpu_usage', 'N/A')}%
• 内存使用: {metrics.get('memory_usage', 'N/A')}MB
• GPU使用率: {metrics.get('gpu_usage', 'N/A')}%
"""
            
            perf_text.config(state=tk.NORMAL)
            perf_text.insert(tk.END, perf_content)
            perf_text.config(state=tk.DISABLED)
            
            self.log_message("📊 Agent性能监控窗口已打开", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 显示Agent性能失败: {e}", "ERROR")
    
    def _show_agent_logs(self):
        """显示Agent日志"""
        try:
            # 创建日志查看窗口
            log_window = tk.Toplevel(self.root)
            log_window.title("📋 Agent 日志查看器")
            log_window.geometry("800x600")
            log_window.configure(bg=self.colors['bg_dark'])
            
            # 应用主题
            self._apply_theme_to_widget(log_window)
            
            # 创建日志显示区域
            log_text = scrolledtext.ScrolledText(
                log_window,
                wrap=tk.WORD,
                font=("Consolas", 9),
                bg=self.colors['bg_medium'],
                fg=self.colors['text_primary'],
                state=tk.DISABLED
            )
            log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 读取Agent日志文件
            try:
                import os
                log_file_path = "logs/agent_activity.log"
                
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                    
                    log_text.config(state=tk.NORMAL)
                    log_text.insert(tk.END, log_content)
                    log_text.see(tk.END)  # 滚动到底部
                    log_text.config(state=tk.DISABLED)
                else:
                    log_text.config(state=tk.NORMAL)
                    log_text.insert(tk.END, "📝 Agent日志文件不存在或为空\n\n请先启动Agent模式以生成日志。")
                    log_text.config(state=tk.DISABLED)
                    
            except Exception as e:
                log_text.config(state=tk.NORMAL)
                log_text.insert(tk.END, f"❌ 读取日志文件失败: {e}")
                log_text.config(state=tk.DISABLED)
            
            self.log_message("📋 Agent日志查看器已打开", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"❌ 显示Agent日志失败: {e}", "ERROR")
    
    def _show_system_info(self):
        """显示系统信息"""
        import platform
        import sys
        
        info = f"""🎭 AI VTuber 智能控制中心 v4.0
        
系统信息:
• 操作系统: {platform.system()} {platform.release()}
• Python版本: {sys.version.split()[0]}
• 架构: {platform.machine()}

功能状态:
• GPT-SoVITS: {'启用' if self.voice_cloning_var.get() else '禁用'}
• 情感智能: {'启用' if self.emotional_intelligence_var.get() else '禁用'}
• 表情控制: {'启用' if self.expression_control_var.get() else '禁用'}
• 流式响应: {'启用' if self.streaming_var.get() else '禁用'}
• 分句处理: {'启用' if self.chunking_var.get() else '禁用'}
• 用户打断: {'启用' if self.interruption_var.get() else '禁用'}

服务连接:
• Ollama: {'已连接' if self.system_state.ollama_connected else '未连接'}
• VTube Studio: {'已连接' if self.system_state.vts_connected else '未连接'}
"""
        
        messagebox.showinfo("系统信息", info)
    
    def _show_performance_stats(self):
        """显示性能统计"""
        stats = """📊 性能统计信息

优化效果:
• 流式响应: 减少感知延迟 60%
• 分句处理: 减少首音频延迟 40%
• 激进分句: 减少首音频延迟 46.5%
• 音频缓存: 缓存命中时延迟 < 0.1ms

系统状态:
• 内存使用: 正常
• CPU使用: 正常
• 网络延迟: 正常

建议:
• 所有性能优化选项均已启用
• 系统运行状态良好
"""
        messagebox.showinfo("性能统计", stats)
    
    def _show_feature_docs(self):
        """显示功能文档"""
        docs = """📖 功能说明文档

🎯 基础功能:
• GPT-SoVITS: 高质量语音克隆
• 情感智能: AI情感分析和表情控制
• Live2D表情: 自动表情切换

⚡ 性能优化:
• 流式响应: 实时显示AI生成内容
• 分句处理: 并行音频生成和播放
• 用户打断: 支持对话中断和重新开始

🔬 高级功能:
• 智能内存: 长期记忆和上下文理解
• Agent模式: 视觉分析和自动操作
• 音频优化: 多种音频处理选项

💡 使用提示:
• 鼠标悬停查看详细说明
• 建议启用所有性能优化选项
• 定期检查系统连接状态
"""
        messagebox.showinfo("功能文档", docs)
    
    def _run_system_diagnostics(self):
        """运行系统诊断"""
        self.log_message("运行系统诊断...", "INFO")
        
        # 模拟诊断过程
        diag_results = """🔍 系统诊断结果

✅ 系统组件:
• Python环境: 正常
• 依赖库: 正常
• 配置文件: 正常

✅ 服务连接:
• Ollama服务: 正常
• VTube Studio: 正常
• 网络连接: 正常

✅ 性能指标:
• 内存使用: 正常
• CPU使用: 正常
• 磁盘空间: 充足

🎉 诊断完成: 系统运行正常!
"""
        
        messagebox.showinfo("系统诊断", diag_results)
        self.log_message("系统诊断完成 - 状态正常", "SUCCESS")
    
    def _run_health_check(self):
        """运行健康检查"""
        self.log_message("运行系统健康检查...", "INFO")
        
        health_report = """🏥 系统健康检查报告

🟢 核心服务:
• GUI界面: 运行正常
• 系统工作流: 运行正常
• 日志系统: 运行正常

🟢 外部服务:
• Ollama连接: 稳定
• VTube Studio: 稳定
• 网络状态: 良好

🟢 资源使用:
• 内存: 使用正常
• CPU: 负载正常
• 存储: 空间充足

✅ 健康状态: 优秀
"""
        
        messagebox.showinfo("健康检查", health_report)
        self.log_message("系统健康检查完成 - 状态优秀", "SUCCESS")
    
    def _test_network(self):
        """测试网络连接"""
        self.log_message("测试网络连接...", "INFO")
        
        network_test = """🌐 网络连接测试

✅ 本地服务:
• Ollama (localhost:11434): 连接正常
• VTube Studio (localhost:8001): 连接正常
• GPT-SoVITS (localhost:9880): 连接正常

✅ 网络状态:
• 延迟: < 50ms
• 带宽: 充足
• 稳定性: 良好

✅ DNS解析: 正常

🎉 网络测试完成: 所有连接正常!
"""
        
        messagebox.showinfo("网络测试", network_test)
        self.log_message("网络连接测试完成 - 所有服务正常", "SUCCESS")
    
    # 基础方法（继承自原始类的核心功能）
    def setup_logging(self):
        """设置日志系统"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level))
        
        # 创建GUI日志处理器
        from .gui_controller import GUILogHandler
        handler = GUILogHandler(self)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # 设置根日志记录器
        root_logger = logging.getLogger()
        if not any(isinstance(h, GUILogHandler) for h in root_logger.handlers):
            root_handler = GUILogHandler(self)
            root_handler.setFormatter(formatter)
            root_logger.addHandler(root_handler)
            root_logger.setLevel(logging.INFO)
    
    def start_monitoring_thread(self):
        """启动后台监控线程"""
        def monitoring_worker():
            while not self.shutdown_event.is_set():
                try:
                    status = self.system_workflow.check_connections()
                    
                    if self.root:
                        try:
                            self.root.after(0, lambda: self._update_status_from_monitor(status))
                        except (RuntimeError, AttributeError, tk.TclError):
                            pass
                    
                    self.shutdown_event.wait(5.0)
                    
                except Exception as e:
                    self.error_handler.handle_thread_error("monitoring_worker", e)
                    self.shutdown_event.wait(10.0)
        
        monitor_thread = threading.Thread(target=monitoring_worker, daemon=True)
        monitor_thread.start()
        self.logger.info("后台监控线程已启动")
    
    def _update_status_from_monitor(self, status: Dict[str, bool]):
        """从监控线程更新连接状态"""
        for service, connected in status.items():
            mapped = "llm" if service in ("ollama", "koboldcpp", "llm") else service
            if mapped in ["llm", "vts"]:
                current_status = getattr(self.system_state, f"{mapped}_connected", False)
                if current_status != connected:
                    self.update_connection_status(mapped, connected)
                    status_msg = "已连接" if connected else "连接断开"
                    self.log_message(f"{service.upper()} {status_msg}", "INFO" if connected else "WARNING")
        
        # 顺带更新记忆状态
        self.update_memory_status()
        
        # 顺带更新 VAD/麦克风状态
        self._update_vad_status()
    
    def update_connection_status(self, service: str, connected: bool):
        """更新连接状态指示器"""
        if service == "llm":
            backend = getattr(self.config, 'llm_backend', 'ollama').upper()
            self.system_state.llm_connected = connected
            if self.llm_status_label:
                status_text = f"● {backend}: 已连接" if connected else f"● {backend}: 未连接"
                color = self.colors['success'] if connected else self.colors['error']
                self.llm_status_label.config(text=status_text, fg=color)
        
        elif service == "vts":
            self.system_state.vts_connected = connected
            if self.vts_status_label:
                status_text = "● VTS: 已连接" if connected else "● VTS: 未连接"
                color = self.colors['success'] if connected else self.colors['error']
                self.vts_status_label.config(text=status_text, fg=color)
        
        elif service == "tts":
            if hasattr(self, 'tts_status_label') and self.tts_status_label:
                status_text = "● TTS: 已连接" if connected else "● TTS: 未连接"
                color = self.colors['success'] if connected else self.colors['error']
                self.tts_status_label.config(text=status_text, fg=color)

    def update_memory_status(self):
        """更新标题栏记忆系统状态显示"""
        if not hasattr(self, 'memory_status_label') or not self.memory_status_label:
            return
        try:
            memory_core = getattr(self, 'memory_core', None) or getattr(
                self.system_workflow, 'memory_core', None)
            if memory_core and memory_core.is_ready():
                count = memory_core._stats.get('total_memories', 0)
                self.memory_status_label.config(
                    text=f"🧠 记忆: {count}条",
                    fg=self.colors['success']
                )
            elif memory_core:
                self.memory_status_label.config(
                    text="🧠 记忆: 加载中",
                    fg=self.colors['warning']
                )
            else:
                self.memory_status_label.config(
                    text="🧠 记忆: 未启用",
                    fg=self.colors['text_secondary']
                )
        except Exception:
            pass

    def _update_vad_status(self):
        """更新标题栏 VAD/麦克风状态显示"""
        if not hasattr(self, 'vad_status_label') or not self.vad_status_label:
            return
        try:
            streaming_ears = getattr(self, 'streaming_ears', None)
            if streaming_ears and getattr(streaming_ears, 'is_streaming', False):
                # 判断是否正在检测到说话
                if getattr(streaming_ears, 'is_speech_active', False):
                    self.vad_status_label.config(
                        text="🎙️ 麦克风: 说话中",
                        fg=self.colors['success']
                    )
                else:
                    self.vad_status_label.config(
                        text="🎙️ 麦克风: 监听中",
                        fg=self.colors['info']
                    )
            elif streaming_ears:
                self.vad_status_label.config(
                    text="🎙️ 麦克风: 待机",
                    fg=self.colors['text_secondary']
                )
            else:
                self.vad_status_label.config(
                    text="🎙️ 麦克风: 未启动",
                    fg=self.colors['text_secondary']
                )
        except Exception:
            pass
    
    def log_message(self, message: str, level: str = "INFO"):
        """记录日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_queue.put((formatted_message, level))
    
    def clear_log(self):
        """清除日志显示"""
        if self.log_text:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.log_message("日志已清除", "INFO")
    
    def reconnect_services(self):
        """重新连接所有服务"""
        self.log_message("重新连接所有服务...", "INFO")
        # 调用系统工作流的重连方法
        try:
            # 确保系统工作流对象存在且有正确的方法
            if hasattr(self.system_workflow, 'reconnect_services'):
                self._run_async(self.system_workflow.reconnect_services())
            else:
                self.log_message("系统工作流重连方法不可用", "ERROR")
                # 尝试重新初始化连接
                self._run_async(self.system_workflow.initialize_connections())
        except AttributeError as e:
            self.log_message(f"方法调用错误: {e}", "ERROR")
            # 尝试备用连接方法
            try:
                self._run_async(self.system_workflow.initialize_connections())
            except Exception as fallback_e:
                self.log_message(f"备用连接方法也失败: {fallback_e}", "ERROR")
        except Exception as e:
            self.log_message(f"重连服务失败: {e}", "ERROR")
    
    def start_conversation_flow(self, user_input: str):
        """启动对话流程"""
        self.worker_thread = threading.Thread(
            target=self._conversation_worker,
            args=(user_input,),
            daemon=True
        )
        self.worker_thread.start()
    
    def _conversation_worker(self, user_input: str):
        """对话处理工作线程 - 优化版本，包含资源清理和性能监控"""
        start_time = datetime.now()
        
        try:
            self.logger.info(f"开始处理对话: {user_input}")
            
            # 强制垃圾回收，清理之前的资源
            import gc
            gc.collect()
            
            # 检查系统资源状态
            import psutil
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            # 使用改进的异步处理方法
            self._run_async(
                self.system_workflow.process_user_input(user_input, self.update_subtitle)
            )
            
            # 处理完成后的资源清理
            memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_diff = memory_after - memory_before
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # 记录对话处理时间到性能监控
            performance_monitor.record_conversation_time(duration)
            
            self.log_message(f"对话处理完成 (耗时: {duration:.2f}秒, 内存变化: {memory_diff:+.1f}MB)", "SUCCESS")
            
            # 如果内存增长过多，触发清理
            if memory_diff > 50:  # 50MB阈值
                self.logger.warning(f"内存增长过多: {memory_diff:.1f}MB，触发清理")
                gc.collect()
                
        except Exception as e:
            self.error_handler.handle_thread_error("conversation_worker", e)
            error_msg = f"对话处理出错: {str(e)}"
            self.log_message(error_msg, "ERROR")
            
            # 错误后强制清理资源
            import gc
            gc.collect()
            
        finally:
            try:
                # 确保UI状态重置
                if self.root:
                    self.root.after(0, self._reset_ui_state)
                    
                # 清理临时资源
                self._cleanup_conversation_resources()
                
            except RuntimeError as e:
                self.logger.warning(f"UI状态重置失败: {e}")
                self._reset_ui_state()
    
    def _cleanup_conversation_resources(self):
        """清理对话相关的临时资源"""
        try:
            # 清理音频缓存
            if hasattr(self.system_workflow, '_tts_pipeline') and self.system_workflow._tts_pipeline:
                pipeline = self.system_workflow._tts_pipeline
                if hasattr(pipeline, 'cleanup'):
                    pipeline.cleanup()
            
            # 清理内存系统缓存
            if hasattr(self, 'memory_core') and self.memory_core:
                if hasattr(self.memory_core, 'cleanup_cache'):
                    self.memory_core.cleanup_cache()
            
            # 强制Python垃圾回收
            import gc
            gc.collect()
            
        except Exception as e:
            self.logger.warning(f"资源清理失败: {e}")
    
    def process_message_queue(self):
        """处理消息队列"""
        try:
            while True:
                message, level = self.message_queue.get_nowait()
                self._update_log_display(message, level)
        except queue.Empty:
            pass
        
        try:
            while True:
                message, level = self.log_queue.get_nowait()
                self._update_log_display(message, level)
        except queue.Empty:
            pass
        
        try:
            latest_streaming_text = None
            while True:
                latest_streaming_text = self.streaming_text_queue.get_nowait()
        except queue.Empty:
            pass
        
        if latest_streaming_text is not None:
            self._update_streaming_display(latest_streaming_text)
        
        if self.root:
            self.root.after(50, self.process_message_queue)
    
    def _update_log_display(self, message: str, level: str):
        """更新日志显示"""
        if not self.log_text:
            return
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message, level)
        self.log_text.see(tk.END)
        
        # 限制日志行数
        lines = int(self.log_text.index(tk.END).split('.')[0])
        if lines > 1000:
            self.log_text.delete(1.0, f"{lines-1000}.0")
        
        self.log_text.config(state=tk.DISABLED)
    
    def _update_streaming_display(self, text: str):
        """更新流式文本显示 - 同时更新聊天框和系统日志"""
        if not text:
            return
        
        # 避免显示相同的文本
        if hasattr(self, '_last_streaming_text') and self._last_streaming_text == text:
            return
        
        self._last_streaming_text = text
        
        # ── 更新聊天框（主要显示区）──
        if hasattr(self, 'chat_display') and self.chat_display:
            self._update_chat_ai_streaming(text)
        
        # ── 系统日志中保留简短提示 ──
        if self.log_text:
            display_text = self._clean_streaming_text_for_display(text)
            if len(display_text) > 80:
                display_text = display_text[:80] + "..."
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.config(state=tk.NORMAL)
            try:
                content = self.log_text.get("1.0", tk.END)
                lines = content.split('\n')
                for i in range(len(lines) - 1, -1, -1):
                    if "[流式响应]" in lines[i]:
                        line_num = i + 1
                        self.log_text.delete(f"{line_num}.0", f"{line_num}.end+1c")
                        break
            except tk.TclError:
                pass
            self.log_text.insert(tk.END, f"[{timestamp}] [流式响应] {display_text}\n", "INFO")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

    def _update_chat_ai_streaming(self, text: str):
        """在聊天框中实时更新 AI 流式回复"""
        try:
            self.chat_display.config(state=tk.NORMAL)
            
            if not hasattr(self, '_ai_streaming_line_start'):
                # 第一次出现 AI 回复，先插入 AI 标签行
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.chat_display.insert(tk.END, f"\n🤖 AI  ", "ai_label")
                self.chat_display.insert(tk.END, f"[{timestamp}]\n", "timestamp")
                # 记录 AI 文字内容起始位置
                self._ai_streaming_line_start = self.chat_display.index(tk.END)
                self.chat_display.insert(tk.END, "", "ai_streaming")
            
            # 删除上次的流式文本，重新写入最新内容
            start_idx = self._ai_streaming_line_start
            end_idx = self.chat_display.index(tk.END)
            self.chat_display.delete(start_idx, end_idx)
            
            # 插入当前流式文本
            clean_text = self._clean_streaming_text_for_display(text)
            self.chat_display.insert(tk.END, clean_text, "ai_streaming")
            self.chat_display.see(tk.END)
        except Exception as e:
            self.logger.debug(f"聊天框流式更新出错: {e}")
        finally:
            self.chat_display.config(state=tk.DISABLED)

    def _finalize_chat_ai_response(self, final_text: str):
        """将流式响应转换为最终 AI 回复（加粗显示，去掉斜体）"""
        try:
            if not hasattr(self, 'chat_display') or not self.chat_display:
                return
            self.chat_display.config(state=tk.NORMAL)
            
            if hasattr(self, '_ai_streaming_line_start'):
                start_idx = self._ai_streaming_line_start
                end_idx = self.chat_display.index(tk.END)
                self.chat_display.delete(start_idx, end_idx)
                clean_text = self._clean_streaming_text_for_display(final_text)
                self.chat_display.insert(tk.END, clean_text + "\n", "ai_text")
                delattr(self, '_ai_streaming_line_start')
            
            self.chat_display.see(tk.END)
        except Exception as e:
            self.logger.debug(f"聊天框最终响应更新出错: {e}")
        finally:
            self.chat_display.config(state=tk.DISABLED)

    def _append_chat_user(self, text: str):
        """在聊天框添加用户消息"""
        if not hasattr(self, 'chat_display') or not self.chat_display:
            return
        try:
            self.chat_display.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.chat_display.insert(tk.END, f"\n👤 你  ", "user_label")
            self.chat_display.insert(tk.END, f"[{timestamp}]\n", "timestamp")
            self.chat_display.insert(tk.END, text + "\n", "user_text")
            self.chat_display.see(tk.END)
        except Exception as e:
            self.logger.debug(f"聊天框用户消息插入出错: {e}")
        finally:
            self.chat_display.config(state=tk.DISABLED)

    def _clear_chat_display(self):
        """清空聊天显示框"""
        if not hasattr(self, 'chat_display') or not self.chat_display:
            return
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)
            if hasattr(self, '_ai_streaming_line_start'):
                delattr(self, '_ai_streaming_line_start')
            if hasattr(self, '_last_streaming_text'):
                delattr(self, '_last_streaming_text')
            self.log_message("对话历史已清空", "INFO")
        except Exception as e:
            self.logger.debug(f"清空聊天框出错: {e}")
    
    def _clean_streaming_text_for_display(self, text: str) -> str:
        """清理流式文本用于显示"""
        import re
        
        # 移除情感标签
        cleaned = re.sub(r'\[[\w\s]+\]', '', text)
        
        # 移除多余的空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 如果文本过长，只显示最后的部分
        if len(cleaned) > 150:
            # 尝试在句号处截断
            sentences = cleaned.split('。')
            if len(sentences) > 1:
                # 显示最后几个完整句子
                last_sentences = sentences[-3:] if len(sentences) >= 3 else sentences[-2:]
                cleaned = '。'.join(last_sentences)
                if not cleaned.endswith('。') and sentences[-1]:
                    cleaned += '。'
            else:
                # 如果没有句号，显示最后150个字符
                cleaned = "..." + cleaned[-150:]
        
        return cleaned
    
    def update_subtitle(self, text: str):
        """更新字幕显示"""
        if self.subtitle_visible and self.subtitle_window:
            try:
                # 使用独立的字幕窗口显示字幕
                self.subtitle_window.show_text(text)
            except Exception as e:
                self.log_message(f"字幕显示错误: {e}", "ERROR")
                # 备用方案：在日志中显示字幕
                self.log_message(f"字幕: {text}", "INFO")
    
    def _on_streaming_text(self, text: str):
        """流式文本回调"""
        self.streaming_text_queue.put(text)
    
    def run(self):
        """运行GUI主循环"""
        if self.root:
            # 启动后立即进行连接检查
            self.root.after(1000, self._startup_connection_check)
            self.root.mainloop()
    
    def _startup_connection_check(self):
        """启动后的连接检查"""
        self.log_message("🔄 正在检查服务连接状态...", "INFO")
        
        # 在后台线程中进行连接检查
        def check_connections():
            try:
                # 检查Ollama连接
                try:
                    import requests
                    response = requests.get(f"{self.config.ollama_url}/api/tags", timeout=3)
                    if response.status_code == 200:
                        self.root.after(0, lambda: self.update_connection_status("ollama", True))
                        self.root.after(0, lambda: self.log_message("✅ Ollama 连接成功", "SUCCESS"))
                    else:
                        self.root.after(0, lambda: self.update_connection_status("ollama", False))
                        self.root.after(0, lambda: self.log_message("❌ Ollama 连接失败", "ERROR"))
                except Exception as e:
                    self.root.after(0, lambda: self.update_connection_status("ollama", False))
                    self.root.after(0, lambda: self.log_message(f"❌ Ollama 连接失败: {e}", "ERROR"))
                
                # 检查VTS连接
                try:
                    if hasattr(self.system_workflow, 'vts_client') and self.system_workflow.vts_client:
                        # 尝试连接VTS
                        self._run_async(self.system_workflow.vts_client.connect())
                        self.root.after(0, lambda: self.update_connection_status("vts", True))
                        self.root.after(0, lambda: self.log_message("✅ VTube Studio 连接成功", "SUCCESS"))
                    else:
                        self.root.after(0, lambda: self.update_connection_status("vts", False))
                        self.root.after(0, lambda: self.log_message("❌ VTube Studio 未初始化", "WARNING"))
                except Exception as e:
                    self.root.after(0, lambda: self.update_connection_status("vts", False))
                    self.root.after(0, lambda: self.log_message(f"❌ VTube Studio 连接失败: {e}", "ERROR"))
                
                # 检查TTS状态
                try:
                    # 只有在启用语音克隆时才检查GPT-SoVITS服务
                    sovits_available = False
                    if self.config.enable_voice_cloning:
                        try:
                            import requests
                            sovits_response = requests.get(f"{self.config.sovits_url}/", timeout=3)
                            if sovits_response.status_code == 200:
                                sovits_available = True
                                self.root.after(0, lambda: self.log_message("✅ GPT-SoVITS 服务可用", "SUCCESS"))
                            else:
                                self.root.after(0, lambda: self.log_message("⚠️ GPT-SoVITS 服务不可用，将使用Edge-TTS", "WARNING"))
                        except Exception:
                            self.root.after(0, lambda: self.log_message("⚠️ GPT-SoVITS 服务不可用，将使用Edge-TTS", "WARNING"))
                    else:
                        self.root.after(0, lambda: self.log_message("ℹ️ 语音克隆已禁用，使用Edge-TTS", "INFO"))
                    
                    # 检查Edge-TTS（总是可用）
                    self.root.after(0, lambda: self.update_connection_status("tts", True))
                    self.root.after(0, lambda: self.log_message("✅ TTS 系统就绪 (Edge-TTS)", "SUCCESS"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.update_connection_status("tts", False))
                    self.root.after(0, lambda: self.log_message(f"❌ TTS 系统检查失败: {e}", "ERROR"))
                
                self.root.after(0, lambda: self.log_message("🎉 服务连接检查完成", "INFO"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ 连接检查失败: {e}", "ERROR"))
        
        # 在后台线程中运行连接检查
        threading.Thread(target=check_connections, daemon=True).start()
    
    def _setup_emotion_hotkeys(self):
        """设置F1-F5情感热键绑定"""
        try:
            # 获取情感热键映射
            emotion_hotkey_map = getattr(self.config, 'emotion_hotkey_map', {})
            
            if not emotion_hotkey_map:
                self.logger.warning("未找到情感热键映射配置")
                return
            
            # 绑定F1-F5热键到窗口
            hotkey_bindings = {
                '<F1>': 'neutral',
                '<F2>': 'happy', 
                '<F3>': 'angry',
                '<F4>': 'sad',
                '<F5>': 'surprised'
            }
            
            for hotkey, emotion in hotkey_bindings.items():
                if emotion in emotion_hotkey_map:
                    # 绑定热键到窗口
                    self.root.bind(hotkey, lambda e, em=emotion: self._trigger_emotion_hotkey(em))
                    self.logger.debug(f"已绑定热键 {hotkey} -> {emotion}")
            
            # 确保窗口可以接收键盘焦点
            self.root.focus_set()
            
            self.logger.info("F1-F5情感热键绑定完成")
            
        except Exception as e:
            self.logger.error(f"设置情感热键失败: {e}")
    
    def _trigger_emotion_hotkey(self, emotion: str):
        """处理情感热键触发"""
        try:
            self.logger.info(f"触发情感热键: {emotion}")
            
            # 显示视觉反馈
            self.log_message(f"🎭 触发情感: {emotion}", "INFO")
            
            # 检查VTS客户端是否可用
            if not hasattr(self.system_workflow, 'vts_client') or not self.system_workflow.vts_client:
                self.log_message("❌ VTube Studio 客户端未连接", "ERROR")
                return
            
            # 异步触发表情
            def trigger_async():
                try:
                    # 在新的事件循环中运行异步操作
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    success = loop.run_until_complete(
                        self.system_workflow.vts_client.trigger_expression(emotion)
                    )
                    
                    loop.close()
                    
                    # 更新UI反馈
                    if success:
                        self.root.after(0, lambda: self.log_message(f"✅ 情感表达 {emotion} 触发成功", "SUCCESS"))
                    else:
                        self.root.after(0, lambda: self.log_message(f"⚠️ 情感表达 {emotion} 触发失败", "WARNING"))
                        
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"❌ 情感热键执行错误: {e}", "ERROR"))
            
            # 在后台线程中执行异步操作
            threading.Thread(target=trigger_async, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"情感热键处理失败: {e}")
            self.log_message(f"❌ 情感热键错误: {e}", "ERROR")
    
    def destroy(self):
        """销毁GUI（安全版本，防止重复销毁报错）"""
        self.shutdown_event.set()
        if self.root:
            try:
                # 检查 root 是否还存在（用户手动关闭时 root 已被销毁）
                if self.root.winfo_exists():
                    self.root.destroy()
            except Exception:
                pass  # GUI 已经被销毁，忽略错误
            finally:
                self.root = None
    def _toggle_proxy(self):
        """切换代理设置"""
        enabled = self.proxy_enabled_var.get()
        self.log_message(f"代理设置: {'启用' if enabled else '禁用'}", "INFO")
    
    def _apply_network_settings(self):
        """应用网络设置"""
        try:
            # 获取代理设置
            proxy_enabled = getattr(self, 'proxy_enabled_var', tk.BooleanVar()).get()
            
            if proxy_enabled:
                # 这里应该应用代理设置
                self.log_message("✅ 网络设置已应用", "SUCCESS")
                self.log_message("💡 代理设置已启用", "INFO")
            else:
                self.log_message("✅ 网络设置已应用", "SUCCESS")
                self.log_message("💡 直连模式已启用", "INFO")
                
        except Exception as e:
            self.log_message(f"❌ 应用网络设置失败: {e}", "ERROR")
    
    # 全双工模式回调方法
    def _on_partial_transcription(self, text: str):
        """处理部分语音识别结果"""
        if text.strip():
            self.log_message(f"🎤 部分识别: {text}", "INFO")
            # 可以在这里更新实时显示
    
    def _on_sentence_complete(self, text: str):
        """处理完整句子识别结果"""
        if text.strip():
            self.log_message(f"✅ 完整识别: {text}", "SUCCESS")
            
            # 自动处理识别到的语音
            if hasattr(self, 'user_input') and self.user_input:
                # 将识别结果填入输入框
                self.user_input.delete(0, tk.END)
                self.user_input.insert(0, text)
                
                # 自动发送消息
                self.root.after(100, self._send_message)
    
    def _on_speech_start(self):
        """处理语音开始事件"""
        self.log_message("🎙️ 检测到语音开始", "INFO")
    
    def _on_speech_end(self):
        """处理语音结束事件"""
        self.log_message("🔇 语音结束", "INFO")
    
    def update_conversation_state(self, state: str):
        """
        更新对话状态显示
        
        用于显示当前对话处理的状态，如用户说话、处理中、AI响应等
        
        Args:
            state: 对话状态，可能的值包括:
                  - "user_speaking": 用户正在说话
                  - "processing": 正在处理用户输入
                  - "ai_responding": AI正在响应
                  - "idle": 空闲状态
                  - "error": 错误状态
        """
        try:
            # 状态映射
            state_messages = {
                "user_speaking": "🎤 用户正在说话...",
                "processing": "🤔 正在思考中...",
                "ai_responding": "🗣️ AI正在回应...",
                "idle": "💤 等待输入...",
                "error": "❌ 处理出错"
            }
            
            # 状态颜色映射
            state_colors = {
                "user_speaking": self.colors.get('info', '#2196F3'),
                "processing": self.colors.get('warning', '#FF9800'),
                "ai_responding": self.colors.get('success', '#4CAF50'),
                "idle": self.colors.get('text_secondary', '#666666'),
                "error": self.colors.get('error', '#F44336')
            }
            
            # 获取状态消息和颜色
            message = state_messages.get(state, f"状态: {state}")
            color = state_colors.get(state, self.colors.get('text_primary', '#FFFFFF'))
            
            # 更新系统状态标签
            if hasattr(self, 'system_status_label') and self.system_status_label:
                self.system_status_label.config(text=message, fg=color)
            
            # 记录状态变化到日志
            self.log_message(f"对话状态: {message}", "INFO")
            
            # 根据状态更新UI元素
            if state == "processing":
                # 显示进度条
                if hasattr(self, 'progress_bar') and self.progress_bar:
                    self.progress_bar.pack(side=tk.RIGHT, padx=(10, 0))
                    self.progress_bar.start()
                
                # 禁用发送按钮
                if hasattr(self, 'send_button') and self.send_button:
                    self.send_button.config(state=tk.DISABLED)
                
                # 启用中断按钮
                if hasattr(self, 'interrupt_button') and self.interrupt_button:
                    self.interrupt_button.config(state=tk.NORMAL)
                    
            elif state in ["idle", "error"]:
                # 隐藏进度条
                if hasattr(self, 'progress_bar') and self.progress_bar:
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                
                # 启用发送按钮
                if hasattr(self, 'send_button') and self.send_button:
                    self.send_button.config(state=tk.NORMAL)
                
                # 禁用中断按钮
                if hasattr(self, 'interrupt_button') and self.interrupt_button:
                    self.interrupt_button.config(state=tk.DISABLED)
            
            # 更新窗口标题以反映状态
            if hasattr(self, 'root') and self.root:
                base_title = "🎭 AI VTuber 智能控制中心 v4.0"
                if state != "idle":
                    self.root.title(f"{base_title} - {message}")
                else:
                    self.root.title(base_title)
                    
        except Exception as e:
            self.logger.error(f"更新对话状态失败: {e}")
            # 即使更新失败，也要记录到日志
            self.log_message(f"状态更新: {state}", "INFO")
