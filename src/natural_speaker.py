"""
自然说话系统 - 像真人一样自然说话

特点：
- 简短，1-2句话
- 想到什么说什么
- 口语化，随意
- 自言自语
- 不对观众说
- 偶尔说话，不是一直说
"""

import random
import time
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Thought:
    """思考内容"""
    content: str
    importance: float  # 重要性 0-1
    urgency: float  # 紧急性 0-1


class NaturalSpeaker:
    """自然说话系统"""
    
    def __init__(self, tts_pipeline=None, vts_client=None):
        """
        初始化自然说话系统
        
        Args:
            tts_pipeline: TTS管道（可选）
            vts_client: VTS客户端（可选，用于表情）
        """
        self.tts_pipeline = tts_pipeline
        self.vts_client = vts_client
        
        # 说话参数
        self.speak_probability = 0.3  # 30%概率说话
        self.min_speak_interval = 2.0  # 最小说话间隔（秒）
        self.last_speak_time = 0.0
        
        # 说话频率控制
        self.speak_count = 0
        self.action_count = 0
        self.speak_ratio = 0.3  # 说话比例（30%的动作会说话）
        
        # 说话队列
        self.speak_queue = []
        
        logger.info("自然说话系统初始化完成")
    
    def should_speak(self, observation: dict = None) -> bool:
        """
        判断是否应该说话
        
        Args:
            observation: 观察结果（可选）
        
        Returns:
            是否应该说话
        """
        # 检查最小间隔
        current_time = time.time()
        if current_time - self.last_speak_time < self.min_speak_interval:
            return False
        
        # 如果有观察，检查重要性
        if observation:
            obs_type = observation.get('type', '')
            important_types = ['monster', 'item', 'danger']
            
            # 重要观察必须说
            if obs_type in important_types:
                return True
        
        # 随机决定
        return random.random() < self.speak_probability
    
    def speak(self, content: str, emotion: str = "neutral") -> bool:
        """
        说话
        
        Args:
            content: 说话内容
            emotion: 情绪（neutral, happy, sad, angry, surprised）
        
        Returns:
            是否成功说话
        """
        # 简化内容
        content = self._simplify_content(content)
        
        # 确保简短
        content = self._shorten_content(content)
        
        # 如果内容为空，不说话
        if not content:
            return False
        
        try:
            # 记录说话时间
            self.last_speak_time = time.time()
            self.speak_count += 1
            
            # TTS说话
            if self.tts_pipeline:
                self.tts_pipeline.speak(content, emotion=emotion)
            
            # VTS表情
            if self.vts_client:
                self._set_emotion(emotion)
            
            logger.info(f"说话: {content} (情绪: {emotion})")
            return True
        
        except Exception as e:
            logger.error(f"说话失败: {e}")
            return False
    
    def _simplify_content(self, content: str) -> str:
        """简化内容"""
        # 移除标点
        import re
        content = re.sub(r'[^\w\s，。]', '', content)
        
        # 移除多余空格
        content = ' '.join(content.split())
        
        return content.strip()
    
    def _shorten_content(self, content: str) -> str:
        """缩短内容"""
        # 分句
        sentences = [s.strip() for s in content.split('。') if s.strip()]
        
        # 最多保留2句话
        if len(sentences) > 2:
            sentences = sentences[:2]
        
        # 重新组合
        content = '。'.join(sentences)
        if content and not content.endswith('。'):
            content += '。'
        
        # 限制长度（最多20字）
        if len(content) > 20:
            content = content[:20]
            # 确保以句号结尾
            if not content.endswith('。'):
                content = content[:content.rfind('，')] + '。' if '，' in content else content + '。'
        
        return content
    
    def _set_emotion(self, emotion: str):
        """设置VTS表情"""
        try:
            emotion_map = {
                'neutral': 0,    # 中性
                'happy': 1,      # 开心
                'sad': 2,        # 难过
                'angry': 3,      # 生气
                'surprised': 4   # 惊讶
            }
            
            if emotion in emotion_map:
                # 简化的表情设置（实际实现取决于VTS API）
                logger.debug(f"设置表情: {emotion}")
                # self.vts_client.set_emotion(emotion_map[emotion])
        
        except Exception as e:
            logger.warning(f"设置表情失败: {e}")
    
    def think_and_speak(self, observation: dict) -> bool:
        """
        观察环境，思考并说话
        
        Args:
            observation: 观察结果
        
        Returns:
            是否说话了
        """
        # 生成思考
        thought = self._generate_thought(observation)
        
        # 判断是否说话
        if not self.should_speak(thought):
            return False
        
        # 说话
        return self.speak(thought.content)
    
    def _generate_thought(self, observation: dict) -> Thought:
        """
        生成思考内容
        
        Args:
            observation: 观察结果
        
        Returns:
            思考内容
        """
        # 从观察中提取关键信息
        main_element = observation.get('main_element', '')
        action = observation.get('action', '')
        context = observation.get('context', '')
        
        # 随机选择表达方式
        expressions = self._get_expressions(main_element, action, context)
        
        if not expressions:
            return Thought("", 0.0, 0.0)
        
        # 随机选择一个
        content = random.choice(expressions)
        
        # 计算重要性和紧急性
        importance = self._calculate_importance(main_element, context)
        urgency = self._calculate_urgency(main_element, context)
        
        return Thought(content, importance, urgency)
    
    def _get_expressions(self, main_element: str, action: str, context: str) -> List[str]:
        """
        获取表达方式
        
        Args:
            main_element: 主要元素
            action: 动作
            context: 上下文
        
        Returns:
            表达方式列表
        """
        expressions = []
        
        # 根据主要元素生成表达
        if main_element:
            expressions.extend([
                f"{main_element}",
                f"有个{main_element}",
                f"哦，{main_element}",
            ])
        
        # 根据动作生成表达
        if action:
            expressions.extend([
                f"{action}",
                f"去{action}",
                f"要{action}",
            ])
        
        # 根据上下文生成表达
        if context:
            expressions.extend([
                f"{context}",
            ])
        
        return expressions
    
    def _calculate_importance(self, main_element: str, context: str) -> float:
        """计算重要性"""
        # 稀有物品更重要
        rare_items = ['钻石', '金矿', '铁矿', '煤炭', '红石']
        if any(item in main_element for item in rare_items):
            return 0.8
        
        # 危险情况更重要
        danger_situations = ['怪物', '僵尸', '爬行者', '危险', '血量低']
        if any(situation in context for situation in danger_situations):
            return 0.9
        
        # 普通情况
        return 0.5
    
    def _calculate_urgency(self, main_element: str, context: str) -> float:
        """计算紧急性"""
        # 危险情况紧急
        danger_situations = ['怪物', '僵尸', '爬行者', '危险', '血量低']
        if any(situation in context for situation in danger_situations):
            return 0.9
        
        # 稀有物品紧急
        rare_items = ['钻石', '金矿', '铁矿', '煤炭', '红石']
        if any(item in main_element for item in rare_items):
            return 0.7
        
        # 普通情况不紧急
        return 0.3
    
    def respond_to_comment(self, comment: str) -> bool:
        """
        回应弹幕
        
        Args:
            comment: 弹幕内容
        
        Returns:
            是否回应了
        """
        # 不是所有弹幕都回应
        if random.random() > 0.3:  # 30%概率回应
            return False
        
        # 生成回应
        response = self._generate_comment_response(comment)
        
        # 说话
        return self.speak(response)
    
    def _generate_comment_response(self, comment: str) -> str:
        """生成弹幕回应"""
        # 简单的回应模板
        responses = [
            f"弹幕说{comment}",
            f"嗯，{comment}",
            f"{comment}...",
        ]
        
        return random.choice(responses)
    
    def update_action_count(self):
        """更新动作计数"""
        self.action_count += 1
    
    def get_speak_stats(self) -> dict:
        """获取说话统计"""
        if self.action_count == 0:
            return {
                'speak_count': self.speak_count,
                'action_count': self.action_count,
                'speak_ratio': 0.0
            }
        
        return {
            'speak_count': self.speak_count,
            'action_count': self.action_count,
            'speak_ratio': self.speak_count / self.action_count
        }


# 使用示例
if __name__ == "__main__":
    # 创建自然说话系统
    speaker = NaturalSpeaker()
    
    # 测试说话
    print("测试自然说话系统：")
    
    # 测试1: 正常观察
    observation1 = {
        'main_element': '树',
        'action': '砍',
        'context': '需要木头'
    }
    
    thought1 = speaker._generate_thought(observation1)
    print(f"观察1: {observation1}")
    print(f"思考: {thought1.content}")
    print(f"重要性: {thought1.importance}")
    print(f"是否说话: {speaker.should_speak(thought1)}")
    
    # 测试2: 重要观察
    observation2 = {
        'main_element': '钻石',
        'action': '挖',
        'context': '发现稀有物品'
    }
    
    thought2 = speaker._generate_thought(observation2)
    print(f"\n观察2: {observation2}")
    print(f"思考: {thought2.content}")
    print(f"重要性: {thought2.importance}")
    print(f"是否说话: {speaker.should_speak(thought2)}")
    
    # 测试3: 危险情况
    observation3 = {
        'main_element': '僵尸',
        'action': '打',
        'context': '危险'
    }
    
    thought3 = speaker._generate_thought(observation3)
    print(f"\n观察3: {observation3}")
    print(f"思考: {thought3.content}")
    print(f"重要性: {thought3.importance}")
    print(f"是否说话: {speaker.should_speak(thought3)}")
    
    # 测试4: 内容简化
    test_content = "嗯，我现在要去砍一点木头，然后做一个镐子，这样我就能去挖石头了，然后再..."
    simplified = speaker._shorten_content(test_content)
    print(f"\n原始内容: {test_content}")
    print(f"简化后: {simplified}")
    
    print("\n[测试完成]")
