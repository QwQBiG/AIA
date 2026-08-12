"""
视觉客户端 - AI VTuber 视觉分析模块

本模块提供屏幕捕获和视觉分析功能，使用高性能截图库 (mss) 
和视觉语言模型 (Ollama VLM) 进行场景理解。

核心功能：
- 高速屏幕截图（使用 mss 库）
- 图片优化和 Base64 编码
- VLM 场景分析和动作决策
- 坐标归一化（像素 -> 百分比）

工作流程：
1. capture_screen() 截取屏幕
2. analyze_scene() 发送给 VLM 分析
3. 返回 AgentCommand 包含动作指令

使用示例：
    client = VisionClient({"vision_model": "llava"})
    image_b64 = await client.capture_screen()
    command, dimensions = await client.analyze_scene(image_b64)
    print(f"动作: {command.action_type}, 目标: {command.target}")
"""

import asyncio
import base64
import io
import logging
import time
import threading
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

import mss
from PIL import Image
import ollama


@dataclass
class AgentCommand:
    """
    VLM 分析返回的结构化命令
    
    属性:
        thought: AI 的思考过程（用于调试）
        commentary: 给观众的解说文本
        action_type: 动作类型 ("click", "keypress", "drag", "wait", "none")
        target: 目标坐标，百分比格式 (x_percent, y_percent)，范围 0.0-1.0
        key: 按键名称（仅 keypress 动作使用）
        confidence: 置信度 (0.0-1.0)
        timestamp: 命令生成时间戳
        x, y: 像素坐标（向后兼容）
        bounding_box: 目标边界框（可选）
    """
    thought: str
    commentary: str
    action_type: str
    target: Optional[Tuple[float, float]]
    key: Optional[str]
    confidence: float
    timestamp: datetime
    
    # 向后兼容的像素坐标
    x: Optional[int] = None
    y: Optional[int] = None
    bounding_box: Optional[Dict[str, int]] = None


class VisionClient:
    """
    高性能视觉客户端
    
    集成 mss 高速截图和 Ollama VLM 视觉分析。
    支持多线程安全的截图操作。
    
    属性:
        model_name: VLM 模型名称（如 "llava"）
        capture_region: 默认截图区域
        max_dimension: 图片最大尺寸（用于优化）
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化视觉客户端
        
        参数:
            config: 配置字典，包含：
                - vision_model: VLM 模型名称（默认 "llava"）
                - capture_region: 截图区域 (x, y, w, h)
                - max_image_dimension: 最大图片尺寸（默认 1024）
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # 使用线程本地存储处理 mss 多线程问题
        self._thread_local = threading.local()
        
        # Ollama VLM 客户端
        self.ollama_client = ollama.Client()
        self.model_name = config.get('vision_model', 'llava')
        
        # 截图设置
        self.capture_region = config.get('capture_region', None)
        self.max_dimension = config.get('max_image_dimension', 1024)
        
        # 原始数据存储（供调试器访问）
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None
        
        self.logger.info(f"视觉客户端初始化完成，模型: {self.model_name}")
    
    def _get_sct(self) -> mss.mss:
        """
        获取线程本地的 mss 实例
        
        mss 使用 Windows GDI 资源，这些资源是线程本地的，
        因此每个线程需要独立的 mss 实例。
        
        返回:
            线程本地的 mss 实例
        """
        if not hasattr(self._thread_local, 'sct') or self._thread_local.sct is None:
            self._thread_local.sct = mss.mss()
            self.logger.debug(f"为线程 {threading.current_thread().name} 创建新的 mss 实例")
        return self._thread_local.sct
    
    async def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """
        使用 mss 截取屏幕并转换为优化的 Base64 字符串
        
        参数:
            region: 可选的截图区域 (x, y, width, height)
            
        返回:
            Base64 编码的图片字符串
        """
        try:
            # 获取线程安全的 mss 实例
            sct = self._get_sct()
            
            # 使用传入的区域或默认区域
            capture_region = region or self.capture_region
            
            if capture_region:
                # 截取指定区域
                monitor = {
                    "top": capture_region[1],
                    "left": capture_region[0], 
                    "width": capture_region[2],
                    "height": capture_region[3]
                }
                self.logger.debug(f"[视觉] 截取区域: {capture_region}")
            else:
                # 截取主显示器
                monitor = sct.monitors[1]
                self.logger.debug(f"[视觉] 截取全屏: {monitor['width']}x{monitor['height']}")
            
            # 高速截图
            screenshot = sct.grab(monitor)
            
            # 转换为 PIL 图片
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            original_size = img.size
            
            # 优化图片尺寸
            img = self._optimize_image_size(img)
            
            # 转换为 Base64
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            self.logger.debug(
                f"[视觉] 截图完成: 原始={original_size}, "
                f"优化后={img.size}, base64长度={len(img_b64)}"
            )
            return img_b64
            
        except Exception as e:
            self.logger.error(f"[视觉] 截图失败: {e}")
            raise
    
    def _optimize_image_size(self, img: Image.Image) -> Image.Image:
        """
        优化图片尺寸以提升 VLM 处理效率
        
        参数:
            img: PIL 图片对象
            
        返回:
            优化后的 PIL 图片
        """
        width, height = img.size
        max_dim = max(width, height)
        
        if max_dim > self.max_dimension:
            # 保持宽高比缩放
            if width > height:
                new_width = self.max_dimension
                new_height = int(height * (self.max_dimension / width))
            else:
                new_height = self.max_dimension
                new_width = int(width * (self.max_dimension / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.logger.debug(f"图片已缩放: {width}x{height} -> {new_width}x{new_height}")
        
        return img
    
    async def analyze_scene(self, image_b64: str, context: str = "gaming", 
                          action_history: Optional[list] = None,
                          user_instruction: Optional[str] = None) -> Tuple[AgentCommand, Tuple[int, int]]:
        """
        发送图片给 VLM 进行场景分析
        
        参数:
            image_b64: Base64 编码的截图
            context: 上下文提示 ("gaming", "desktop", "application")
            action_history: 最近的动作历史（防止幻觉）
            user_instruction: 用户指令（可选）
            
        返回:
            (AgentCommand, 图片尺寸) 元组
        """
        try:
            # 获取图片尺寸用于坐标归一化
            image_data = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(image_data))
            image_dimensions = img.size  # (width, height)
            
            # 构建上下文感知的提示词
            prompt = self._build_analysis_prompt(context, action_history, user_instruction)
            
            # 保存原始提示词供调试
            self.last_prompt = prompt
            
            # 发送给 Ollama VLM
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                images=[image_b64],
                format="json"
            )
            
            # 保存原始响应供调试
            self.last_raw_response = response.get('response', '无响应')
            
            # 解析响应并归一化坐标
            command = self._parse_vlm_response(response['response'], image_dimensions)
            
            self.logger.debug(f"VLM 分析完成: {command.action_type}, 置信度 {command.confidence}")
            return command, image_dimensions
            
        except Exception as e:
            self.logger.error(f"VLM 分析失败: {e}")
            # 返回安全的回退命令
            return AgentCommand(
                thought=f"分析失败: {str(e)}",
                commentary="我现在看不清屏幕。",
                action_type="wait",
                target=None,
                key=None,
                confidence=0.0,
                timestamp=datetime.now()
            ), (1920, 1080)
    
    def _build_analysis_prompt(self, context: str, action_history: Optional[list] = None, 
                              user_instruction: Optional[str] = None) -> str:
        """构建 VLM 分析提示词"""
        
        # 用户指令模式
        if user_instruction and user_instruction.strip():
            base_prompt = f"""你是一个帮助用户玩游戏的 AI 助手。

**用户指令**: "{user_instruction}"

**你的任务**: 
1. 仔细观察截图
2. 找到用户想要交互的目标
3. 点击它或执行请求的动作

**上下文**: {context}
"""
            
            if action_history:
                history_text = " -> ".join([f"{action.get('action_type', 'unknown')}" 
                                          for action in action_history[-3:]])
                base_prompt += f"\n**最近动作**: {history_text}\n"
            
            base_prompt += """
**响应格式** (仅 JSON):
{
  "thought": "我看到 [用户想要的] 在 [位置]，所以我要 [动作]",
  "commentary": "正在执行你的指令！",
  "action_type": "click|wait|none",
  "target": [x, y] 或 null,
  "confidence": 0.7-1.0
}

现在分析截图并执行用户指令:"""
        
        else:
            # 自主模式
            base_prompt = f"""你是一个正在玩游戏的 AI。你的目标是点击可交互的元素。

**寻找目标**:
1. 按钮（开始、播放、继续等）- 点击它们
2. 彩色物体或形状 - 点击它们
3. 菜单项或图标 - 点击它们
4. 任何可点击的 UI 元素 - 点击它们

**规则**:
- 如果看到任何可点击的东西 → 使用 "click" 动作
- 如果屏幕正在加载/动画中 → 使用 "wait" 动作
- 如果屏幕完全空白 → 使用 "none" 动作
- 除非绝对必要，避免使用 "wait"

**上下文**: {context}
"""
            
            if action_history:
                history_text = " -> ".join([f"{action.get('action_type', 'unknown')}" 
                                          for action in action_history[-3:]])
                base_prompt += f"\n**最近 3 个动作**: {history_text}\n"
            
            base_prompt += """
**响应格式** (仅 JSON):
{
  "thought": "我看到 [什么] 在 [哪里]，所以我要 [动作]",
  "commentary": "给观众的简短评论",
  "action_type": "click|wait|none",
  "target": [x, y] 或 null,
  "confidence": 0.7-1.0
}

现在分析并响应:"""
        
        return base_prompt
    
    def _parse_vlm_response(self, response_text: str, image_dimensions: Tuple[int, int]) -> AgentCommand:
        """解析 VLM JSON 响应并归一化坐标"""
        import json
        
        try:
            data = json.loads(response_text)
            
            # 验证必需字段
            required_fields = ['thought', 'commentary', 'action_type', 'confidence']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 将目标坐标转换为百分比 (0.0-1.0)
            target = None
            pixel_x, pixel_y = None, None
            
            if data.get('target') and isinstance(data['target'], list) and len(data['target']) == 2:
                pixel_x = int(data['target'][0])
                pixel_y = int(data['target'][1])
                
                # 像素坐标转百分比
                image_width, image_height = image_dimensions
                if image_width > 0 and image_height > 0:
                    percent_x = pixel_x / image_width
                    percent_y = pixel_y / image_height
                    
                    # 限制在有效范围内
                    percent_x = max(0.0, min(1.0, percent_x))
                    percent_y = max(0.0, min(1.0, percent_y))
                    
                    target = (percent_x, percent_y)
                    
                    self.logger.debug(
                        f"坐标转换: 像素({pixel_x}, {pixel_y}) -> "
                        f"百分比({percent_x:.3f}, {percent_y:.3f}) 图片尺寸 {image_width}x{image_height}"
                    )
            
            return AgentCommand(
                thought=str(data['thought']),
                commentary=str(data['commentary']),
                action_type=str(data['action_type']),
                target=target,
                key=data.get('key'),
                confidence=float(data['confidence']),
                timestamp=datetime.now(),
                x=pixel_x,
                y=pixel_y,
                bounding_box=data.get('bounding_box')
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.logger.error(f"解析 VLM 响应失败: {e}")
            return AgentCommand(
                thought="响应解析失败",
                commentary="我无法理解看到的内容。",
                action_type="wait",
                target=None,
                key=None,
                confidence=0.0,
                timestamp=datetime.now()
            )
    
    async def cleanup_temporary_data(self):
        """清理临时图片数据和缓存对象"""
        try:
            import gc
            gc.collect()
            self.logger.debug("视觉客户端临时数据已清理")
        except Exception as e:
            self.logger.error(f"清理临时数据时出错: {e}")
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, '_thread_local') and hasattr(self._thread_local, 'sct'):
            try:
                self._thread_local.sct.close()
                self._thread_local.sct = None
            except Exception as e:
                self.logger.warning(f"关闭 mss 实例时出错: {e}")
        self.logger.info("视觉客户端清理完成")
