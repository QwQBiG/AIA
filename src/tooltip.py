"""
Tooltip System for Tkinter GUI

Provides hover tooltips for GUI elements with customizable appearance
and delay settings. Supports both simple text and rich formatted tooltips.
"""

import tkinter as tk
from typing import Optional, Union


class ToolTip:
    """
    创建悬停工具提示的类
    
    当鼠标悬停在绑定的控件上时显示提示文本。
    支持自定义延迟、样式和位置。
    """
    
    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        delay: int = 500,
        wrap_length: int = 300,
        bg_color: str = "#2d1b2e",
        fg_color: str = "#ffffff",
        border_color: str = "#ff69b4",
        font: tuple = ("Microsoft YaHei", 9)
    ):
        """
        初始化工具提示
        
        Args:
            widget: 要绑定提示的控件
            text: 提示文本
            delay: 显示延迟（毫秒）
            wrap_length: 文本换行宽度（像素）
            bg_color: 背景颜色
            fg_color: 文字颜色
            border_color: 边框颜色
            font: 字体设置
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wrap_length = wrap_length
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.border_color = border_color
        self.font = font
        
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.scheduled_id: Optional[str] = None
        
        # 绑定事件
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<ButtonPress>", self._on_leave)
    
    def _on_enter(self, event=None) -> None:
        """鼠标进入控件时调度显示提示"""
        self._cancel_scheduled()
        self.scheduled_id = self.widget.after(self.delay, self._show_tooltip)
    
    def _on_leave(self, event=None) -> None:
        """鼠标离开控件时隐藏提示"""
        self._cancel_scheduled()
        self._hide_tooltip()
    
    def _cancel_scheduled(self) -> None:
        """取消已调度的显示"""
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
    
    def _show_tooltip(self) -> None:
        """显示工具提示窗口"""
        if self.tooltip_window:
            return
        
        # 获取控件位置
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # 创建提示窗口
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_attributes("-topmost", True)
        
        # 创建边框效果
        frame = tk.Frame(
            self.tooltip_window,
            bg=self.border_color,
            padx=1,
            pady=1
        )
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建内容标签
        label = tk.Label(
            frame,
            text=self.text,
            justify=tk.LEFT,
            bg=self.bg_color,
            fg=self.fg_color,
            font=self.font,
            wraplength=self.wrap_length,
            padx=8,
            pady=6
        )
        label.pack()
        
        # 设置位置
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # 确保提示在屏幕内
        self.tooltip_window.update_idletasks()
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()
        tip_width = self.tooltip_window.winfo_width()
        tip_height = self.tooltip_window.winfo_height()
        
        # 调整位置防止超出屏幕
        if x + tip_width > screen_width:
            x = screen_width - tip_width - 10
        if y + tip_height > screen_height:
            y = self.widget.winfo_rooty() - tip_height - 5
        
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
    
    def _hide_tooltip(self) -> None:
        """隐藏工具提示窗口"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_text(self, new_text: str) -> None:
        """更新提示文本"""
        self.text = new_text
        if self.tooltip_window:
            self._hide_tooltip()
            self._show_tooltip()
    
    def destroy(self) -> None:
        """销毁工具提示并解绑事件"""
        self._cancel_scheduled()
        self._hide_tooltip()
        try:
            self.widget.unbind("<Enter>")
            self.widget.unbind("<Leave>")
            self.widget.unbind("<ButtonPress>")
        except tk.TclError:
            pass


def create_tooltip(widget: tk.Widget, text: str, **kwargs) -> ToolTip:
    """
    便捷函数：为控件创建工具提示
    
    Args:
        widget: 要绑定提示的控件
        text: 提示文本
        **kwargs: 其他 ToolTip 参数
        
    Returns:
        ToolTip 实例
    """
    return ToolTip(widget, text, **kwargs)


# 完整的提示文本字典（中英文双语）
TOOLTIP_TEXTS = {
    # ==================== 主界面控件 ====================
    
    # 消息输入区
    "input_entry": "在此输入要发送给 AI 的消息\n\n💡 提示：\n• 按 Enter 快速发送\n• 支持多行文本输入\n• 处理中可打断（需启用打断功能）",
    
    "send_button": "发送消息给 AI 虚拟主播\n\n⚡ 快捷键：Enter\n📝 功能：\n• 触发完整对话流程\n• 自动生成语音和表情\n• 支持流式响应显示",
    
    # 连接状态
    "ollama_status": "Ollama LLM 服务连接状态\n\n🔗 服务信息：\n• 默认端口：11434\n• 提供 AI 对话能力\n• 支持本地模型运行",
    
    "vts_status": "VTube Studio 连接状态\n\n🎭 服务信息：\n• 默认端口：8001\n• 控制 Live2D 表情\n• 需要启用 API 插件",
    
    # 控制按钮
    "clear_log": "清除日志显示区域\n\n🗑️ 功能：\n• 清空所有日志消息\n• 不影响日志文件\n• 释放界面显示空间",
    
    "reconnect": "重新连接所有外部服务\n\n🔄 重连服务：\n• Ollama LLM 服务\n• VTube Studio\n• GPT-SoVITS 语音服务\n\n💡 适用场景：\n• 服务意外断开\n• 网络恢复后重连\n• 服务重启后",
    
    # ==================== 基础设置标签页 ====================
    
    "voice_cloning": "🎤 GPT-SoVITS 语音克隆\n\n启用本地语音克隆服务，提供个性化声音\n\n✅ 优势：\n• 高质量语音合成\n• 支持声音克隆\n• 本地运行保护隐私\n\n⚙️ 要求：\n• 需运行 GPT-SoVITS 服务\n• 默认端口：9880\n• 失败时自动切换到 Edge-TTS",
    
    "emotional_intelligence": "💭 情感智能分析\n\n让 AI 响应包含情感标签\n\n🎯 功能：\n• 识别对话情感（开心/悲伤/生气等）\n• 输出结构化情感标签\n• 触发对应 Live2D 表情\n\n📋 支持情感：\n• happy, sad, angry, surprised\n• neutral, excited, confused\n• 需配合表情控制使用",
    
    "expression_control": "😊 Live2D 表情控制\n\n根据情感自动切换 Live2D 表情\n\n🎭 功能：\n• 情感标签 → 表情映射\n• 自动触发热键切换\n• 支持自定义表情配置\n\n⚙️ 要求：\n• 需要 VTube Studio 连接\n• 需配置表情热键映射\n• 需启用情感智能",
    
    # ==================== 性能优化标签页 ====================
    
    "streaming": "⚡ 流式响应显示\n\n实时显示 AI 生成的文本内容\n\n✨ 优势：\n• 无需等待完整响应\n• 实时查看生成进度\n• 提升交互体验\n\n📊 性能：\n• 延迟：< 100ms\n• 支持长文本流式输出",
    
    "chunking": "📝 智能分句处理\n\n自动在句子边界分割文本\n\n🚀 优势：\n• 音频并行生成和播放\n• 减少整体响应延迟\n• 更自然的对话节奏\n\n⚙️ 工作原理：\n• 检测句子边界（。！？）\n• 逐句生成音频\n• 边生成边播放",
    
    "interruption": "✋ 用户打断支持\n\n允许在 AI 响应过程中发送新消息\n\n💡 功能：\n• 立即停止当前音频\n• 清空播放队列\n• 处理新的输入\n\n🎯 适用场景：\n• AI 回答偏题时\n• 需要紧急提问\n• 改变话题方向",
    
    "warmup": "🔥 系统预热加载\n\n系统启动时预加载模型到内存\n\n⚡ 优势：\n• 减少首次响应延迟\n• 提升用户体验\n• 模型常驻内存\n\n⚠️ 注意：\n• 需要重启后生效\n• 占用更多内存\n• 启动时间稍长",
    
    # ==================== UX 优化标签页 ====================
    
    "subtitle": "📺 同步字幕显示\n\n音频播放时显示对应文本\n\n✨ 功能：\n• 实时同步显示\n• 支持自定义字体大小\n• 可随时开关\n\n📊 性能：\n• 同步延迟：< 50ms\n• 自动换行显示",
    
    "cache": "💾 音频缓存系统\n\n缓存常用短语的音频文件\n\n🚀 性能提升：\n• 缓存命中：< 0.1ms\n• 比实时生成快 2000 倍\n• 节省 TTS 服务资源\n\n💡 适用内容：\n• 常用问候语\n• 固定回复短语\n• 高频使用内容\n\n⚠️ 注意：需要重启后生效",
    
    "aggressive_split": "✂️ 激进分句模式\n\n在逗号处也进行分句\n\n⚡ 性能提升：\n• 减少首音频延迟 46.5%\n• 更快的响应感知\n• 适合长句子\n\n⚙️ 工作原理：\n• 标准模式：仅在 。！？ 分句\n• 激进模式：在 ，。！？ 分句\n• 更细粒度的音频生成",
    
    "text_cleaning": "🧹 文本清洗处理\n\n自动清理文本中的特殊字符\n\n🎯 清理内容：\n• Emoji 表情符号\n• Markdown 格式标记\n• 特殊控制字符\n\n✅ 优势：\n• 提升 TTS 合成质量\n• 避免朗读错误\n• 更自然的语音输出",
    
    "parenthetical": "🔇 移除括号内容\n\n移除括号内的注释和动作描述\n\n📝 示例：\n• 原文：你好（微笑）\n• 处理后：你好\n\n🎯 适用场景：\n• 避免朗读动作描述\n• 移除旁白注释\n• 保持语音自然",
    
    # ==================== Agent Mode 控制 ====================
    
    "agent_toggle": "🤖 启动/停止 Agent Mode\n\n启用 AI 视觉分析和自动操作\n\n⚡ 功能：\n• 屏幕截图分析\n• 自动决策和操作\n• 智能任务执行\n\n🛡️ 安全措施：\n• 按 F9 紧急停止\n• 支持单步调试\n• 操作前确认\n\n💡 建议：\n• 首次使用先打开 Debugger\n• 测试坐标准确性\n• 了解操作逻辑后再启用",
    
    "loop_interval": "⏱️ Agent 循环间隔\n\n每次分析-操作循环的等待时间\n\n⚙️ 参数说明：\n• 单位：秒\n• 范围：0.5 - 10.0\n• 推荐值：1.0 - 3.0\n\n⚖️ 权衡：\n• 较小值：响应更快，CPU 占用高\n• 较大值：CPU 占用低，响应较慢",
    
    "cooldown_period": "❄️ 动作冷却时间\n\n执行动作后的等待时间\n\n⚙️ 参数说明：\n• 单位：秒\n• 范围：0.1 - 5.0\n• 推荐值：0.5 - 2.0\n\n🎯 作用：\n• 防止操作过于频繁\n• 等待界面响应\n• 避免误操作",
    
    "capture_region": "📐 屏幕监控区域\n\n选择 Agent 监控的屏幕范围\n\n🖥️ 选项：\n• 全屏：监控整个屏幕\n• 自定义：指定区域 (X, Y, W, H)\n\n⚡ 性能优化：\n• 限制区域可提升分析速度\n• 减少不必要的视觉处理\n• 聚焦关键区域",
    
    # ==================== 高级功能按钮 ====================
    
    "system_info": "ℹ️ 系统信息\n\n查看系统版本和功能状态\n\n📋 显示内容：\n• 系统版本信息\n• 已启用功能列表\n• 服务连接状态\n• 配置文件路径\n• Python 和系统信息",
    
    "performance_stats": "📊 性能统计\n\n查看系统性能指标和优化效果\n\n📈 统计内容：\n• 响应速度指标\n• 优化效果对比\n• 系统稳定性信息\n• 性能提升建议",
    
    "feature_docs": "📖 功能说明文档\n\n打开详细的功能说明窗口\n\n📚 文档内容：\n• 核心功能模块介绍\n• 详细使用说明\n• 配置选项解释\n• 使用场景建议\n• 性能指标说明",
    
    "debugger": "🔧 Agent Debugger\n\n打开 Agent 可视化调试工具\n\n🛠️ 调试功能：\n• 单步执行分析\n• 可视化决策过程\n• 坐标校准工具\n• DPI 缩放调整\n• 原始数据查看\n\n💡 适用场景：\n• 测试 Agent 决策\n• 校准坐标系统\n• 调试操作问题",
    
    # ==================== Agent Debugger 界面 ====================
    
    "manual_step": "👣 单步执行\n\n执行一次完整的分析流程（不执行动作）\n\n🔄 执行流程：\n1. 截取屏幕画面\n2. 发送给 VLM 分析\n3. 显示分析结果\n4. 标注目标位置\n\n💡 用途：\n• 检查 AI 决策逻辑\n• 验证视觉识别准确性\n• 测试不同场景",
    
    "execute": "▶️ 执行动作\n\n确认并执行上一步分析的动作\n\n⚠️ 注意：\n• 仅在有待定动作时可用\n• 执行前请确认动作正确\n• 支持点击、拖拽、输入等\n\n🛡️ 安全：\n• 需要手动确认\n• 可随时取消\n• 按 F9 紧急停止",
    
    "test_center": "🎯 测试中心点击\n\n点击屏幕中心以测试坐标准确性\n\n🔧 用途：\n• 校准坐标系统\n• 检查 DPI 缩放\n• 验证点击精度\n\n📊 预期结果：\n• 应该点击屏幕正中心\n• 如有偏移需调整 DPI Scale",
    
    "dpi_scale": "📏 DPI 缩放因子\n\n修正高分屏的坐标偏移\n\n⚙️ 参数说明：\n• 1.0 = 100% 缩放（标准）\n• 1.25 = 125% 缩放\n• 1.5 = 150% 缩放\n• 2.0 = 200% 缩放\n\n🔧 调整方法：\n1. 点击 Test Center Click\n2. 观察点击位置偏移\n3. 调整 DPI Scale 值\n4. 点击 Apply 应用\n5. 重新测试直到准确",
    
    "show_raw": "📄 查看原始数据\n\n显示完整的 VLM 交互数据\n\n📋 显示内容：\n• 完整 VLM Prompt\n• 原始 JSON 响应\n• 解析后的结构\n• 错误信息（如有）\n\n🔍 用途：\n• 调试分析问题\n• 理解 AI 决策\n• 优化 Prompt\n• 排查错误",
    
    "always_on_top": "📌 窗口置顶\n\n切换调试器窗口置顶状态\n\n💡 功能：\n• 保持窗口在最前\n• 方便观察操作过程\n• 不被其他窗口遮挡\n\n🎯 适用场景：\n• 调试时需要同时查看\n• 监控 Agent 操作\n• 多窗口工作",
    
    "refresh_screenshot": "🔄 刷新截图\n\n重新截取当前屏幕画面\n\n💡 用途：\n• 更新显示内容\n• 查看最新状态\n• 不触发分析",
    
    "clear_annotations": "🧹 清除标注\n\n清除截图上的所有标注\n\n💡 用途：\n• 查看原始截图\n• 清理视觉干扰\n• 重新开始标注",
    
    # ==================== Agent Debugger 控件 ====================
    
    "manual_step": "👣 单步执行\n\n执行一次完整的分析流程（不执行动作）\n\n🔄 执行流程：\n1. 截取屏幕画面\n2. 发送给 VLM 分析\n3. 显示分析结果\n4. 标注目标位置\n\n💡 用途：\n• 检查 AI 决策逻辑\n• 验证视觉识别准确性\n• 测试不同场景\n\n⚠️ 注意：\n• 不会自动执行动作\n• 需要手动点击执行动作按钮",
    
    "execute": "▶️ 执行动作\n\n确认并执行上一步分析的动作\n\n⚠️ 注意：\n• 仅在有待定动作时可用\n• 执行前请确认动作正确\n• 支持点击、拖拽、输入等\n\n🛡️ 安全：\n• 需要手动确认\n• 可随时取消\n• 按 F9 紧急停止\n\n💡 建议：\n• 首次使用先测试简单动作\n• 确认坐标准确性\n• 了解操作逻辑后再使用",
    
    "test_center": "🎯 测试中心点击\n\n点击屏幕中心以测试坐标准确性\n\n🔧 用途：\n• 校准坐标系统\n• 检查 DPI 缩放\n• 验证点击精度\n\n📊 预期结果：\n• 应该点击屏幕正中心\n• 如有偏移需调整 DPI 缩放\n\n💡 提示：\n• 在 2560x1600 屏幕上应点击 (1280, 800)\n• 如果点击位置不对，调整 DPI 缩放值",
    
    "dpi_scale": "📏 DPI 缩放因子\n\n修正高分屏的坐标偏移\n\n⚙️ 参数说明：\n• 1.0 = 100% 缩放（标准）\n• 1.25 = 125% 缩放\n• 1.5 = 150% 缩放\n• 2.0 = 200% 缩放\n\n🔧 调整方法：\n1. 点击测试中心点击\n2. 观察点击位置偏移\n3. 调整 DPI 缩放值\n4. 点击应用按钮\n5. 重新测试直到准确\n\n💡 提示：\n• Windows 显示设置中的缩放比例\n• 通常与系统缩放设置一致",
    
    "show_raw": "📄 查看原始数据\n\n显示完整的 VLM 交互数据\n\n📋 显示内容：\n• 完整 VLM Prompt\n• 原始 JSON 响应\n• 解析后的结构\n• 错误信息（如有）\n\n🔍 用途：\n• 调试分析问题\n• 理解 AI 决策\n• 优化 Prompt\n• 排查错误\n\n💡 功能：\n• 支持复制到剪贴板\n• 显示 JSON 格式验证\n• 提供数据分析",
    
    "always_on_top": "📌 窗口置顶\n\n切换调试器窗口置顶状态\n\n💡 功能：\n• 保持窗口在最前\n• 方便观察操作过程\n• 不被其他窗口遮挡\n\n🎯 适用场景：\n• 调试时需要同时查看\n• 监控 Agent 操作\n• 多窗口工作\n\n⚠️ 注意：\n• 可能会遮挡其他窗口\n• 可随时取消置顶",
}
