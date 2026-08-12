"""
情感表达增强引擎

实现丰富的情感表达系统,包括:
1. 情感强度和持续时间控制
2. 情感过渡动画
3. 复合情感表达
4. 情感历史和学习
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import deque


logger = logging.getLogger(__name__)


class EmotionType(Enum):
    """情感类型"""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"
    EXCITED = "excited"
    WORRIED = "worried"
    PROUD = "proud"


@dataclass
class EmotionState:
    """情感状态"""
    emotion_type: EmotionType
    intensity: float  # 0.0-1.0
    duration: float  # 持续时间(秒)
    timestamp: float
    is_composite: bool = False
    component_emotions: Dict[str, float] = field(default_factory=dict)


@dataclass
class EmotionTransition:
    """情感过渡"""
    from_emotion: EmotionType
    to_emotion: EmotionType
    duration: float  # 过渡持续时间
    ease_function: str = "ease-in-out"  # 缓动函数


class EmotionEngine:
    """
    情感表达引擎

    功能:
    1. 情感强度控制(0.0-1.0)
    2. 情感持续时间管理
    3. 平滑情感过渡动画
    4. 复合情感支持(如"既开心又惊讶")
    5. 情感历史和学习
    """

    def __init__(self):
        """初始化情感引擎"""
        # 当前情感状态
        self.current_emotion: Optional[EmotionState] = None

        # 情感队列(用于平滑过渡)
        self.emotion_queue: deque = deque(maxlen=10)

        # 情感历史
        self.emotion_history: List[EmotionState] = []
        self.max_history_size = 100

        # 情感统计数据
        self.emotion_stats: Dict[str, int] = {}

        # 复合情感支持
        self.composite_emotions: Dict[str, Dict[str, float]] = {
            "excited_surprise": {
                EmotionType.EXCITED.value: 0.6,
                EmotionType.SURPRISED.value: 0.4
            },
            "worry_care": {
                EmotionType.WORRIED.value: 0.5,
                EmotionType.HAPPY.value: 0.3,
                EmotionType.NEUTRAL.value: 0.2
            }
        }

        # 情感过渡动画配置
        self.transition_duration = 0.5  # 默认过渡500ms
        self.supported_ease_functions = [
            "linear",
            "ease-in",
            "ease-out",
            "ease-in-out"
        ]

        logger.info("EmotionEngine initialized")

    def set_emotion(self,
                   emotion_type: EmotionType,
                   intensity: float = 1.0,
                   duration: float = 3.0):
        """
        设置当前情感

        Args:
            emotion_type: 情感类型
            intensity: 情感强度(0.0-1.0)
            duration: 持续时间(秒)
        """
        # 验证参数
        intensity = np.clip(intensity, 0.0, 1.0)
        duration = max(0.1, duration)  # 最小100ms

        # 创建情感状态
        new_emotion = EmotionState(
            emotion_type=emotion_type,
            intensity=intensity,
            duration=duration,
            timestamp=time.time(),
            is_composite=False
        )

        # 如果有当前情感,创建过渡
        if self.current_emotion:
            transition = EmotionTransition(
                from_emotion=self.current_emotion.emotion_type,
                to_emotion=emotion_type,
                duration=self.transition_duration
            )
            self.emotion_queue.append(transition)

        # 更新当前情感
        old_emotion = self.current_emotion
        self.current_emotion = new_emotion

        # 记录历史
        self._record_emotion(new_emotion)

        logger.info(f"Emotion set: {emotion_type.value} (intensity={intensity:.2f}, duration={duration:.2f}s)")

        return transition if old_emotion else None

    def set_composite_emotion(self,
                             composite_name: str,
                             duration: float = 3.0) -> bool:
        """
        设置复合情感

        Args:
            composite_name: 复合情感名称
            duration: 持续时间(秒)

        Returns:
            bool: 是否成功设置
        """
        if composite_name not in self.composite_emotions:
            logger.warning(f"Unknown composite emotion: {composite_name}")
            return False

        components = self.composite_emotions[composite_name]

        # 创建复合情感状态
        new_emotion = EmotionState(
            emotion_type=EmotionType.NEUTRAL,  # 复合情感用NEUTRAL作为类型
            intensity=1.0,
            duration=duration,
            timestamp=time.time(),
            is_composite=True,
            component_emotions=components
        )

        self.current_emotion = new_emotion
        self._record_emotion(new_emotion)

        logger.info(f"Composite emotion set: {composite_name} (duration={duration:.2f}s)")

        return True

    def get_current_emotion(self) -> Optional[EmotionState]:
        """
        获取当前情感状态

        Returns:
            当前情感状态
        """
        # 检查情感是否过期
        if self.current_emotion:
            elapsed = time.time() - self.current_emotion.timestamp

            if elapsed > self.current_emotion.duration:
                # 情感已过期,恢复到中性
                self.current_emotion = EmotionState(
                    emotion_type=EmotionType.NEUTRAL,
                    intensity=0.5,
                    duration=0.0,
                    timestamp=time.time()
                )

        return self.current_emotion

    def get_emotion_intensity(self) -> float:
        """
        获取当前情感强度

        Returns:
            情感强度(0.0-1.0)
        """
        emotion = self.get_current_emotion()
        return emotion.intensity if emotion else 0.0

    def apply_emotion_transition(self,
                                 progress: float,
                                 transition: EmotionTransition) -> float:
        """
        应用情感过渡动画

        Args:
            progress: 过渡进度(0.0-1.0)
            transition: 过渡对象

        Returns:
            过渡后的强度值
        """
        # 应用缓动函数
        eased_progress = self._apply_ease_function(progress, transition.ease_function)

        return eased_progress

    def _apply_ease_function(self, progress: float, ease_type: str) -> float:
        """
        应用缓动函数

        Args:
            progress: 原始进度(0.0-1.0)
            ease_type: 缓动函数类型

        Returns:
            缓动后的进度
        """
        progress = np.clip(progress, 0.0, 1.0)

        if ease_type == "linear":
            return progress
        elif ease_type == "ease-in":
            return progress * progress
        elif ease_type == "ease-out":
            return 1.0 - (1.0 - progress) * (1.0 - progress)
        elif ease_type == "ease-in-out":
            if progress < 0.5:
                return 2.0 * progress * progress
            else:
                return 1.0 - 2.0 * (1.0 - progress) * (1.0 - progress)
        else:
            return progress

    def _record_emotion(self, emotion: EmotionState):
        """
        记录情感到历史

        Args:
            emotion: 情感状态
        """
        # 添加到历史
        self.emotion_history.append(emotion)

        # 限制历史大小
        if len(self.emotion_history) > self.max_history_size:
            self.emotion_history.pop(0)

        # 更新统计
        if emotion.is_composite:
            stat_key = f"composite_{emotion.component_emotions}"
        else:
            stat_key = emotion.emotion_type.value

        self.emotion_stats[stat_key] = self.emotion_stats.get(stat_key, 0) + 1

    def get_emotion_history(self, count: int = 10) -> List[EmotionState]:
        """
        获取最近的情感历史

        Args:
            count: 返回的历史记录数

        Returns:
            情感历史列表
        """
        return self.emotion_history[-count:]

    def get_emotion_stats(self) -> Dict[str, int]:
        """
        获取情感统计信息

        Returns:
            情感统计字典
        """
        return self.emotion_stats.copy()

    def learn_emotion_pattern(self,
                             context: str,
                             emotion: EmotionType,
                             intensity: float):
        """
        学习情感模式(可扩展为机器学习)

        Args:
            context: 上下文
            emotion: 情感类型
            intensity: 情感强度
        """
        # 简单实现: 记录情感关联
        # 未来可以扩展为:
        # 1. 使用机器学习预测情感
        # 2. 基于上下文自动调整情感
        # 3. 学习用户偏好

        logger.debug(f"Emotion pattern learned: context={context}, emotion={emotion.value}, intensity={intensity:.2f}")

    def predict_emotion(self, context: str) -> Optional[EmotionType]:
        """
        预测情感(可扩展)

        Args:
            context: 上下文

        Returns:
            预测的情感类型
        """
        # 简单实现: 基于关键词
        # 未来可以使用更复杂的NLP模型

        happy_keywords = ["开心", "高兴", "喜欢", "棒", "优秀", "good", "great"]
        sad_keywords = ["难过", "悲伤", "难过", "对不起", "sorry", "sad"]
        angry_keywords = ["生气", "愤怒", "讨厌", "bad", "angry"]
        surprised_keywords = ["惊讶", "意外", "哇", "surprised", "wow"]

        context_lower = context.lower()

        for keyword in happy_keywords:
            if keyword in context_lower:
                return EmotionType.HAPPY

        for keyword in sad_keywords:
            if keyword in context_lower:
                return EmotionType.SAD

        for keyword in angry_keywords:
            if keyword in context_lower:
                return EmotionType.ANGRY

        for keyword in surprised_keywords:
            if keyword in context_lower:
                return EmotionType.SURPRISED

        return EmotionType.NEUTRAL

    def add_composite_emotion(self,
                             name: str,
                             components: Dict[str, float]):
        """
        添加新的复合情感

        Args:
            name: 复合情感名称
            components: 情感组件 {emotion_type: intensity}
        """
        # 验证组件
        total_intensity = sum(components.values())
        if total_intensity == 0:
            logger.error(f"Invalid composite emotion: {name} (total intensity is 0)")
            return

        # 归一化强度
        normalized_components = {
            k: v / total_intensity
            for k, v in components.items()
        }

        self.composite_emotions[name] = normalized_components
        logger.info(f"Composite emotion added: {name}")

    def reset(self):
        """重置情感引擎"""
        self.current_emotion = EmotionState(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            duration=0.0,
            timestamp=time.time()
        )
        self.emotion_queue.clear()
        self.emotion_history.clear()
        self.emotion_stats.clear()

        logger.info("EmotionEngine reset")
