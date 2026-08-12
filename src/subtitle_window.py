"""
悬浮字幕窗口 - 独立的字幕显示窗口
Floating Subtitle Window - Independent subtitle display window
"""

import tkinter as tk
from tkinter import ttk, font
import threading
import time
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import json
import os

from .pink_theme import get_theme


class SubtitleWindow:
    """
    悬浮字幕窗口类
    
    功能特点：
    - 独立悬浮窗口，可置顶显示
    - 支持固定位置和跟随鼠标模式
    - 可调整字体大小、颜色、透明度
    - 与主GUI保持一致的粉色主题
    - 支持多行文本显示
    - 自动隐藏和显示控制
    """
    
    def __init__(self, parent_gui=None):
        """初始化字幕窗口"""
        self.parent_gui = parent_gui
        self.window: Optional[tk.Toplevel] = None
        self.is_visible = False
        self.is_pinned = False  # 是否固定位置
        self.follow_mouse = False  # 是否跟随鼠标
        
        # 获取主题颜色
        self.colors = get_theme()
        
        # 字幕设置
        self.settings = {
            'font_family': 'Microsoft YaHei',
            'font_size': 24,
            'font_weight': 'bold',
            'text_color': self.colors['text_primary'],
            'bg_color': self.colors['bg_dark'],
            'border_color': self.colors['accent'],
            'transparency': 0.9,  # 透明度 (0.0-1.0)
            'width': 800,
            'height': 120,
            'x_position': 100,
            'y_position': 100,
            'auto_hide_delay': 5.0,  # 自动隐藏延迟(秒)
            'show_border': True,
            'word_wrap': True,
            'max_lines': 3
        }
        
        # 当前显示的文本
        self.current_text = ""
        self.last_update_time = 0
        
        # 自动隐藏定时器
        self.hide_timer: Optional[threading.Timer] = None
        
        # 加载设置
        self.load_settings()
        
        # 创建窗口
        self.create_window()
    
    def create_window(self):
        """创建字幕窗口"""
        if self.window:
            self.window.destroy()
        
        # 创建顶级窗口
        self.window = tk.Toplevel()
        self.window.title("AI VTuber 字幕")
        
        # 设置窗口属性
        self.window.geometry(f"{self.settings['width']}x{self.settings['height']}+{self.settings['x_position']}+{self.settings['y_position']}")
        self.window.configure(bg=self.settings['bg_color'])
        
        # 设置窗口样式
        self.window.overrideredirect(True)  # 无边框窗口
        self.window.attributes('-topmost', True)  # 置顶显示
        self.window.attributes('-alpha', self.settings['transparency'])  # 透明度
        
        # 创建边框框架
        if self.settings['show_border']:
            border_frame = tk.Frame(
                self.window,
                bg=self.settings['border_color'],
                highlightthickness=0
            )
            border_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            
            content_frame = tk.Frame(
                border_frame,
                bg=self.settings['bg_color'],
                highlightthickness=0
            )
            content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        else:
            content_frame = self.window
        
        # 创建文本标签
        self.text_label = tk.Label(
            content_frame,
            text="",
            font=(self.settings['font_family'], self.settings['font_size'], self.settings['font_weight']),
            fg=self.settings['text_color'],
            bg=self.settings['bg_color'],
            wraplength=self.settings['width'] - 20,
            justify=tk.CENTER,
            anchor=tk.CENTER
        )
        self.text_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 绑定鼠标事件
        self.bind_mouse_events()
        
        # 创建右键菜单
        self.create_context_menu()
        
        # 初始隐藏窗口
        self.window.withdraw()
        self.is_visible = False
    
    def bind_mouse_events(self):
        """绑定鼠标事件"""
        # 窗口拖拽
        self.window.bind('<Button-1>', self.start_drag)
        self.window.bind('<B1-Motion>', self.on_drag)
        self.text_label.bind('<Button-1>', self.start_drag)
        self.text_label.bind('<B1-Motion>', self.on_drag)
        
        # 右键菜单
        self.window.bind('<Button-3>', self.show_context_menu)
        self.text_label.bind('<Button-3>', self.show_context_menu)
        
        # 双击设置
        self.window.bind('<Double-Button-1>', self.show_settings)
        self.text_label.bind('<Double-Button-1>', self.show_settings)
    
    def start_drag(self, event):
        """开始拖拽"""
        if not self.is_pinned:
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
            self.drag_start_window_x = self.window.winfo_x()
            self.drag_start_window_y = self.window.winfo_y()
    
    def on_drag(self, event):
        """拖拽过程"""
        if not self.is_pinned:
            x = self.drag_start_window_x + (event.x_root - self.drag_start_x)
            y = self.drag_start_window_y + (event.y_root - self.drag_start_y)
            self.window.geometry(f"+{x}+{y}")
            
            # 更新设置
            self.settings['x_position'] = x
            self.settings['y_position'] = y
    
    def create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.configure(
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent'],
            activeforeground=self.colors['text_primary'],
            font=('Microsoft YaHei', 10)
        )
        
        # 固定/取消固定
        self.context_menu.add_command(
            label="📌 固定位置" if not self.is_pinned else "📌 取消固定",
            command=self.toggle_pin
        )
        
        self.context_menu.add_separator()
        
        # 跟随鼠标
        self.context_menu.add_checkbutton(
            label="🖱️ 跟随鼠标",
            variable=tk.BooleanVar(value=self.follow_mouse),
            command=self.toggle_follow_mouse
        )
        
        self.context_menu.add_separator()
        
        # 字体大小
        font_menu = tk.Menu(self.context_menu, tearoff=0)
        font_menu.configure(
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent']
        )
        
        for size in [16, 20, 24, 28, 32, 36, 40]:
            font_menu.add_command(
                label=f"{size}px",
                command=lambda s=size: self.set_font_size(s)
            )
        
        self.context_menu.add_cascade(label="🔤 字体大小", menu=font_menu)
        
        # 透明度
        alpha_menu = tk.Menu(self.context_menu, tearoff=0)
        alpha_menu.configure(
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent']
        )
        
        for alpha in [0.6, 0.7, 0.8, 0.9, 1.0]:
            alpha_menu.add_command(
                label=f"{int(alpha*100)}%",
                command=lambda a=alpha: self.set_transparency(a)
            )
        
        self.context_menu.add_cascade(label="🌟 透明度", menu=alpha_menu)
        
        self.context_menu.add_separator()
        
        # 设置
        self.context_menu.add_command(
            label="⚙️ 详细设置",
            command=self.show_settings
        )
        
        # 隐藏
        self.context_menu.add_command(
            label="👁️ 隐藏字幕",
            command=self.hide
        )
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        try:
            # 更新固定状态文本
            self.context_menu.entryconfig(
                0,
                label="📌 取消固定" if self.is_pinned else "📌 固定位置"
            )
            
            self.context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"显示右键菜单失败: {e}")
    
    def toggle_pin(self):
        """切换固定状态"""
        self.is_pinned = not self.is_pinned
        if self.parent_gui:
            status = "固定" if self.is_pinned else "取消固定"
            self.parent_gui.log_message(f"字幕窗口已{status}", "INFO")
    
    def toggle_follow_mouse(self):
        """切换跟随鼠标模式"""
        self.follow_mouse = not self.follow_mouse
        if self.parent_gui:
            status = "启用" if self.follow_mouse else "禁用"
            self.parent_gui.log_message(f"字幕跟随鼠标已{status}", "INFO")
        
        if self.follow_mouse:
            self.start_mouse_follow()
        else:
            self.stop_mouse_follow()
    
    def start_mouse_follow(self):
        """开始跟随鼠标"""
        def follow_mouse():
            while self.follow_mouse and self.is_visible:
                try:
                    # 获取鼠标位置
                    x = self.window.winfo_pointerx()
                    y = self.window.winfo_pointery()
                    
                    # 调整位置避免遮挡鼠标
                    window_x = x - self.settings['width'] // 2
                    window_y = y - self.settings['height'] - 20
                    
                    # 确保窗口在屏幕内
                    screen_width = self.window.winfo_screenwidth()
                    screen_height = self.window.winfo_screenheight()
                    
                    window_x = max(0, min(window_x, screen_width - self.settings['width']))
                    window_y = max(0, min(window_y, screen_height - self.settings['height']))
                    
                    self.window.geometry(f"+{window_x}+{window_y}")
                    
                    time.sleep(0.1)  # 100ms更新间隔
                except:
                    break
        
        threading.Thread(target=follow_mouse, daemon=True).start()
    
    def stop_mouse_follow(self):
        """停止跟随鼠标"""
        self.follow_mouse = False
    
    def set_font_size(self, size: int):
        """设置字体大小"""
        self.settings['font_size'] = size
        if self.window and hasattr(self, 'text_label'):
            self.text_label.config(
                font=(self.settings['font_family'], size, self.settings['font_weight'])
            )
        self.save_settings()
        
        if self.parent_gui:
            self.parent_gui.log_message(f"字幕字体大小设置为 {size}px", "INFO")
    
    def set_transparency(self, alpha: float):
        """设置透明度"""
        self.settings['transparency'] = alpha
        if self.window:
            self.window.attributes('-alpha', alpha)
        self.save_settings()
        
        if self.parent_gui:
            self.parent_gui.log_message(f"字幕透明度设置为 {int(alpha*100)}%", "INFO")
    
    def show_settings(self, event=None):
        """显示详细设置窗口"""
        settings_window = tk.Toplevel(self.window)
        settings_window.title("字幕设置")
        settings_window.geometry("400x500")
        settings_window.configure(bg=self.colors['bg_dark'])
        settings_window.attributes('-topmost', True)
        
        # 应用主题
        style = ttk.Style()
        style.configure('Settings.TLabel',
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text_primary'],
                       font=('Microsoft YaHei', 10))
        
        # 创建设置界面
        main_frame = tk.Frame(settings_window, bg=self.colors['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题
        title_label = tk.Label(
            main_frame,
            text="🎬 字幕窗口设置",
            font=('Microsoft YaHei', 14, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg_dark']
        )
        title_label.pack(pady=(0, 20))
        
        # 字体设置
        font_frame = tk.LabelFrame(
            main_frame,
            text="字体设置",
            font=('Microsoft YaHei', 10, 'bold'),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        )
        font_frame.pack(fill=tk.X, pady=10)
        
        # 字体大小滑块
        tk.Label(font_frame, text="字体大小:", bg=self.colors['bg_dark'], fg=self.colors['text_primary']).pack(anchor=tk.W, padx=10, pady=5)
        font_size_var = tk.IntVar(value=self.settings['font_size'])
        font_size_scale = tk.Scale(
            font_frame,
            from_=12, to=48,
            orient=tk.HORIZONTAL,
            variable=font_size_var,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            highlightthickness=0,
            troughcolor=self.colors['bg_medium'],
            activebackground=self.colors['accent']
        )
        font_size_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # 窗口设置
        window_frame = tk.LabelFrame(
            main_frame,
            text="窗口设置",
            font=('Microsoft YaHei', 10, 'bold'),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        )
        window_frame.pack(fill=tk.X, pady=10)
        
        # 透明度滑块
        tk.Label(window_frame, text="透明度:", bg=self.colors['bg_dark'], fg=self.colors['text_primary']).pack(anchor=tk.W, padx=10, pady=5)
        transparency_var = tk.DoubleVar(value=self.settings['transparency'])
        transparency_scale = tk.Scale(
            window_frame,
            from_=0.3, to=1.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=transparency_var,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            highlightthickness=0,
            troughcolor=self.colors['bg_medium'],
            activebackground=self.colors['accent']
        )
        transparency_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # 自动隐藏延迟
        tk.Label(window_frame, text="自动隐藏延迟(秒):", bg=self.colors['bg_dark'], fg=self.colors['text_primary']).pack(anchor=tk.W, padx=10, pady=5)
        hide_delay_var = tk.DoubleVar(value=self.settings['auto_hide_delay'])
        hide_delay_scale = tk.Scale(
            window_frame,
            from_=1.0, to=10.0,
            resolution=0.5,
            orient=tk.HORIZONTAL,
            variable=hide_delay_var,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            highlightthickness=0,
            troughcolor=self.colors['bg_medium'],
            activebackground=self.colors['accent']
        )
        hide_delay_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # 选项设置
        options_frame = tk.LabelFrame(
            main_frame,
            text="显示选项",
            font=('Microsoft YaHei', 10, 'bold'),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        )
        options_frame.pack(fill=tk.X, pady=10)
        
        # 显示边框
        show_border_var = tk.BooleanVar(value=self.settings['show_border'])
        border_cb = tk.Checkbutton(
            options_frame,
            text="显示边框",
            variable=show_border_var,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark']
        )
        border_cb.pack(anchor=tk.W, padx=10, pady=5)
        
        # 自动换行
        word_wrap_var = tk.BooleanVar(value=self.settings['word_wrap'])
        wrap_cb = tk.Checkbutton(
            options_frame,
            text="自动换行",
            variable=word_wrap_var,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_primary'],
            selectcolor=self.colors['bg_medium'],
            activebackground=self.colors['bg_dark']
        )
        wrap_cb.pack(anchor=tk.W, padx=10, pady=5)
        
        # 按钮区域
        button_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
        button_frame.pack(fill=tk.X, pady=20)
        
        # 应用按钮
        apply_btn = tk.Button(
            button_frame,
            text="✅ 应用设置",
            command=lambda: self.apply_settings(
                font_size_var.get(),
                transparency_var.get(),
                hide_delay_var.get(),
                show_border_var.get(),
                word_wrap_var.get(),
                settings_window
            ),
            font=('Microsoft YaHei', 10, 'bold'),
            bg=self.colors['accent'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['accent_hover'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        apply_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 取消按钮
        cancel_btn = tk.Button(
            button_frame,
            text="❌ 取消",
            command=settings_window.destroy,
            font=('Microsoft YaHei', 10),
            bg=self.colors['bg_light'],
            fg=self.colors['text_primary'],
            activebackground=self.colors['bg_medium'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        cancel_btn.pack(side=tk.LEFT)
        
        # 重置按钮
        reset_btn = tk.Button(
            button_frame,
            text="🔄 重置",
            command=lambda: self.reset_settings(settings_window),
            font=('Microsoft YaHei', 10),
            bg=self.colors['warning'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['error'],
            relief=tk.FLAT,
            cursor="hand2"
        )
        reset_btn.pack(side=tk.RIGHT)
    
    def apply_settings(self, font_size, transparency, hide_delay, show_border, word_wrap, settings_window):
        """应用设置"""
        self.settings['font_size'] = font_size
        self.settings['transparency'] = transparency
        self.settings['auto_hide_delay'] = hide_delay
        self.settings['show_border'] = show_border
        self.settings['word_wrap'] = word_wrap
        
        # 重新创建窗口以应用所有设置
        current_text = self.current_text
        was_visible = self.is_visible
        
        self.create_window()
        
        if current_text:
            self.show_text(current_text)
        elif was_visible:
            self.show()
        
        self.save_settings()
        settings_window.destroy()
        
        if self.parent_gui:
            self.parent_gui.log_message("字幕设置已应用", "SUCCESS")
    
    def reset_settings(self, settings_window):
        """重置设置"""
        self.settings = {
            'font_family': 'Microsoft YaHei',
            'font_size': 24,
            'font_weight': 'bold',
            'text_color': self.colors['text_primary'],
            'bg_color': self.colors['bg_dark'],
            'border_color': self.colors['accent'],
            'transparency': 0.9,
            'width': 800,
            'height': 120,
            'x_position': 100,
            'y_position': 100,
            'auto_hide_delay': 5.0,
            'show_border': True,
            'word_wrap': True,
            'max_lines': 3
        }
        
        self.create_window()
        self.save_settings()
        settings_window.destroy()
        
        if self.parent_gui:
            self.parent_gui.log_message("字幕设置已重置", "INFO")
    
    def show_text(self, text: str, duration: Optional[float] = None):
        """显示字幕文本"""
        if not text.strip():
            return
        
        self.current_text = text
        self.last_update_time = time.time()
        
        # 确保窗口存在
        if not self.window:
            self.create_window()
        
        # 更新文本
        if hasattr(self, 'text_label'):
            self.text_label.config(text=text)
        
        # 显示窗口
        self.show()
        
        # 设置自动隐藏
        if duration is None:
            duration = self.settings['auto_hide_delay']
        
        self.set_auto_hide(duration)
    
    def show(self):
        """显示字幕窗口"""
        if self.window:
            self.window.deiconify()
            self.window.lift()
            self.is_visible = True
    
    def hide(self):
        """隐藏字幕窗口"""
        if self.window:
            self.window.withdraw()
            self.is_visible = False
        
        # 取消自动隐藏定时器
        if self.hide_timer:
            self.hide_timer.cancel()
            self.hide_timer = None
    
    def set_auto_hide(self, delay: float):
        """设置自动隐藏"""
        # 取消之前的定时器
        if self.hide_timer:
            self.hide_timer.cancel()
        
        # 设置新的定时器
        if delay > 0:
            self.hide_timer = threading.Timer(delay, self.hide)
            self.hide_timer.start()
    
    def clear(self):
        """清除字幕"""
        self.current_text = ""
        if hasattr(self, 'text_label'):
            self.text_label.config(text="")
        self.hide()
    
    def save_settings(self):
        """保存设置到文件"""
        try:
            settings_dir = ".kiro/settings"
            os.makedirs(settings_dir, exist_ok=True)
            
            settings_file = os.path.join(settings_dir, "subtitle_settings.json")
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存字幕设置失败: {e}")
    
    def load_settings(self):
        """从文件加载设置"""
        try:
            settings_file = ".kiro/settings/subtitle_settings.json"
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"加载字幕设置失败: {e}")
    
    def destroy(self):
        """销毁字幕窗口"""
        if self.hide_timer:
            self.hide_timer.cancel()
        
        if self.window:
            self.window.destroy()
            self.window = None
        
        self.is_visible = False