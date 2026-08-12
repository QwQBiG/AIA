"""
自然行为系统 - GUI扩展模块
Natural Behavior System - GUI Extension

为现有GUI添加自然行为系统控制面板
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from typing import Optional

from src.natural_speaker import NaturalSpeaker
from src.natural_thinker import NaturalThinker
from src.natural_behavior import NaturalBehavior


class NaturalBehaviorPanel:
    """自然行为系统GUI面板"""
    
    def __init__(self, parent, action_engine=None, vision_client=None, tts_pipeline=None, vts_client=None):
        """
        初始化GUI面板
        
        Args:
            parent: 父窗口
            action_engine: 动作引擎
            vision_client: 视觉客户端
            tts_pipeline: TTS管道
            vts_client: VTS客户端
        """
        self.parent = parent
        self.action_engine = action_engine
        self.vision_client = vision_client
        self.tts_pipeline = tts_pipeline
        self.vts_client = vts_client
        
        # 组件
        self.natural_behavior = None
        self.is_running = False
        self.worker_thread = None
        
        # 颜色方案
        self.colors = {
            'primary': '#4ecca3',
            'secondary': '#393e46',
            'accent': '#ffc107',
            'danger': '#e74c3c',
            'success': '#2ecc71',
            'bg_dark': '#232931',
            'bg_medium': '#393e46',
            'bg_light': '#eeeeee',
            'text_primary': '#ffffff',
            'text_secondary': '#b0b0b0'
        }
        
        # 创建面板
        self._create_panel()
        
    def _create_panel(self):
        """创建GUI面板"""
        # 主面板
        self.panel = tk.Frame(self.parent, bg=self.colors['bg_dark'])
        self.panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        title_frame = tk.Frame(self.panel, bg=self.colors['bg_dark'])
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(
            title_frame,
            text="🎮 自然行为系统",
            font=("Microsoft YaHei", 14, "bold"),
            fg=self.colors['primary'],
            bg=self.colors['bg_dark']
        ).pack(side=tk.LEFT)
        
        # 状态标签
        self.status_label = tk.Label(
            title_frame,
            text="● 未启动",
            font=("Microsoft YaHei", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_dark']
        )
        self.status_label.pack(side=tk.RIGHT)
        
        # 控制区域
        control_frame = tk.Frame(self.panel, bg=self.colors['bg_medium'], relief=tk.RIDGE, bd=2)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 启动/停止按钮
        self.start_stop_btn = tk.Button(
            control_frame,
            text="启动自然行为",
            command=self._toggle_behavior,
            font=("Microsoft YaHei", 12, "bold"),
            bg=self.colors['success'],
            fg=self.colors['text_primary'],
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=8
        )
        self.start_stop_btn.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 设置按钮
        settings_btn = tk.Button(
            control_frame,
            text="设置",
            command=self._show_settings,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_light'],
            fg=self.colors['text_secondary'],
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=8
        )
        settings_btn.pack(side=tk.LEFT, padx=5, pady=10)
        
        # 日志区域
        log_frame = tk.Frame(self.panel, bg=self.colors['bg_dark'])
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            log_frame,
            text="行为日志",
            font=("Microsoft YaHei", 11, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        ).pack(anchor=tk.W)
        
        self.log_display = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg=self.colors['bg_dark'],
            fg=self.colors['text_secondary'],
            state=tk.DISABLED,
            height=15,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.colors['primary']
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
    def _toggle_behavior(self):
        """切换自然行为系统"""
        if self.is_running:
            self._stop_behavior()
        else:
            self._start_behavior()
            
    def _start_behavior(self):
        """启动自然行为系统"""
        if not self.action_engine or not self.vision_client:
            self._log("错误: 缺少必要组件", error=True)
            return
            
        try:
            # 创建自然行为系统
            self.natural_behavior = NaturalBehavior(
                action_engine=self.action_engine,
                vision_client=self.vision_client,
                tts_pipeline=self.tts_pipeline,
                vts_client=self.vts_client
            )
            
            # 启动工作线程
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._behavior_loop, daemon=True)
            self.worker_thread.start()
            
            # 更新UI
            self.start_stop_btn.config(text="停止自然行为", bg=self.colors['danger'])
            self.status_label.config(text="● 运行中", fg=self.colors['success'])
            self._log("自然行为系统已启动")
            
        except Exception as e:
            self._log(f"启动失败: {e}", error=True)
            
    def _stop_behavior(self):
        """停止自然行为系统"""
        try:
            self.is_running = False
            
            if self.worker_thread:
                self.worker_thread.join(timeout=2.0)
                
            # 更新UI
            self.start_stop_btn.config(text="启动自然行为", bg=self.colors['success'])
            self.status_label.config(text="● 未启动", fg=self.colors['text_secondary'])
            self._log("自然行为系统已停止")
            
        except Exception as e:
            self._log(f"停止失败: {e}", error=True)
            
    def _behavior_loop(self):
        """行为循环"""
        while self.is_running:
            try:
                # 观察环境
                observation = self.vision_client.observe()
                
                # 执行行为
                result = self.natural_behavior.behave(observation)
                
                # 记录日志
                self._log(f"[行为] {result.speech} -> {result.action}")
                
                # 短暂休息
                time.sleep(0.5)
                
            except Exception as e:
                self._log(f"错误: {e}", error=True)
                time.sleep(1.0)
                
    def _show_settings(self):
        """显示设置对话框"""
        settings_window = tk.Toplevel(self.parent)
        settings_window.title("自然行为系统设置")
        settings_window.geometry("400x300")
        settings_window.configure(bg=self.colors['bg_dark'])
        
        # 设置内容
        tk.Label(
            settings_window,
            text="说话概率",
            font=("Microsoft YaHei", 11),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        ).pack(pady=10)
        
        speak_prob_scale = tk.Scale(
            settings_window,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            highlightthickness=0
        )
        speak_prob_scale.set(30)
        speak_prob_scale.pack(fill=tk.X, padx=20)
        
        tk.Label(
            settings_window,
            text="犯错概率",
            font=("Microsoft YaHei", 11),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_dark']
        ).pack(pady=10)
        
        error_prob_scale = tk.Scale(
            settings_window,
            from_=0,
            to=50,
            orient=tk.HORIZONTAL,
            font=("Microsoft YaHei", 10),
            bg=self.colors['bg_medium'],
            fg=self.colors['text_primary'],
            highlightthickness=0
        )
        error_prob_scale.set(10)
        error_prob_scale.pack(fill=tk.X, padx=20)
        
        # 应用按钮
        tk.Button(
            settings_window,
            text="应用",
            command=settings_window.destroy,
            font=("Microsoft YaHei", 11, "bold"),
            bg=self.colors['primary'],
            fg=self.colors['text_primary'],
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=8
        ).pack(pady=20)
        
    def _log(self, message: str, error: bool = False):
        """记录日志"""
        timestamp = time.strftime("%H:%M:%S")
        tag = "error" if error else "normal"
        
        # 在后台线程中更新UI
        def update_log():
            self.log_display.config(state=tk.NORMAL)
            self.log_display.insert(tk.END, f"[{timestamp}] {message}\n", tag)
            self.log_display.see(tk.END)
            self.log_display.config(state=tk.DISABLED)
            
        # 使用after在主线程中更新
        self.parent.after(0, update_log)
        
    def destroy(self):
        """销毁面板"""
        self._stop_behavior()
        self.panel.destroy()
