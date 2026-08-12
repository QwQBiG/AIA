"""
自然思考系统 - 像真人一样自然思考

特点：
- 不是每次都明显思考
- 默想多于说出
- 思考时间短
- 偶尔犹豫
- 快速决定
"""

import random
import time
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """决策结果"""
    action: str
    reason: str
    confidence: float  # 信心 0-1
    hesitation_time: float  # 犹豫时间（秒）


class NaturalThinker:
    """自然思考系统"""
    
    def __init__(self):
        """初始化自然思考系统"""
        # 思考参数
        self.think_probability = 0.4  # 40%概率明显思考
        self.silent_think_probability = 0.6  # 60%概率默想
        self.min_think_time = 0.5  # 最小思考时间（秒）
        self.max_think_time = 2.0  # 最大思考时间（秒）
        
        # 犹豫参数
        self.hesitation_probability = 0.3  # 30%概率犹豫
        self.hesitation_time = 1.0  # 犹豫时间（秒）
        
        # 决策历史
        self.decision_history = []
        
        logger.info("自然思考系统初始化完成")
    
    def think(self, observation: dict) -> List[str]:
        """
        思考（可能不明显）
        
        Args:
            observation: 观察结果
        
        Returns:
            思考内容列表（可能为空）
        """
        # 随机决定是否明显思考
        if random.random() < self.think_probability:
            return self._think_obviously(observation)
        else:
            return self._think_silently(observation)
    
    def _think_obviously(self, observation: dict) -> List[str]:
        """明显思考"""
        thoughts = []
        
        # 观察环境
        observation_thought = self._observe_environment(observation)
        if observation_thought:
            thoughts.append(observation_thought)
            time.sleep(random.uniform(0.3, 0.5))
        
        # 分析情况
        analysis_thought = self._analyze_situation(observation)
        if analysis_thought:
            thoughts.append(analysis_thought)
            time.sleep(random.uniform(0.2, 0.4))
        
        # 考虑选项
        options_thought = self._consider_options(observation)
        if options_thought:
            thoughts.append(options_thought)
            time.sleep(random.uniform(0.3, 0.6))
        
        # 做出决定
        decision_thought = self._make_decision(observation)
        if decision_thought:
            thoughts.append(decision_thought)
        
        return thoughts
    
    def _think_silently(self, observation: dict) -> List[str]:
        """默想（不明显）"""
        # 默想，不说出来
        self._internal_think(observation)
        return []
    
    def _internal_think(self, observation: dict):
        """内部思考（默想）"""
        # 快速思考，不说出来
        thinking_time = random.uniform(0.1, 0.3)
        time.sleep(thinking_time)
    
    def decide(self, observation: dict) -> Decision:
        """
        做出决策
        
        Args:
            observation: 观察结果
        
        Returns:
            决策结果
        """
        # 分析情况
        situation = self._analyze_situation(observation)
        
        # 考虑选项
        options = self._get_options(observation)
        
        # 选择最佳选项
        selected_option = self._select_best_option(options, observation)
        
        # 计算信心
        confidence = self._calculate_confidence(selected_option, observation)
        
        # 是否犹豫
        hesitation_time = 0.0
        if confidence < 0.7 and random.random() < self.hesitation_probability:
            hesitation_time = self.hesitation_time
        
        # 生成理由
        reason = self._generate_reason(selected_option, observation)
        
        decision = Decision(
            action=selected_option,
            reason=reason,
            confidence=confidence,
            hesitation_time=hesitation_time
        )
        
        # 记录决策
        self.decision_history.append(decision)
        
        # 如果需要犹豫
        if hesitation_time > 0:
            time.sleep(hesitation_time)
        
        return decision
    
    def _observe_environment(self, observation: dict) -> Optional[str]:
        """观察环境"""
        main_element = observation.get('main_element', '')
        
        if not main_element:
            return None
        
        # 随机选择表达
        expressions = [
            f"嗯...{main_element}",
            f"有个{main_element}",
            f"哦，{main_element}",
        ]
        
        return random.choice(expressions) if random.random() < 0.5 else None
    
    def _analyze_situation(self, observation: dict) -> Optional[str]:
        """分析情况"""
        context = observation.get('context', '')
        main_element = observation.get('main_element', '')
        
        if not context:
            return None
        
        # 危险情况
        if '危险' in context or '怪物' in context:
            expressions = [
                "有点危险",
                "这个不好处理",
                "需要小心",
            ]
            return random.choice(expressions) if random.random() < 0.7 else None
        
        # 稀有物品
        rare_items = ['钻石', '金矿', '铁矿', '煤炭']
        if any(item in main_element for item in rare_items):
            expressions = [
                "这个需要工具",
                "但是我没有...",
                "先做个工具吧",
            ]
            return random.choice(expressions) if random.random() < 0.6 else None
        
        # 普通情况
        return None
    
    def _consider_options(self, observation: dict) -> Optional[str]:
        """考虑选项"""
        options = self._get_options(observation)
        
        if len(options) <= 1:
            return None
        
        # 随机选择表达
        expressions = [
            "可以...",
            "或者...",
            "我想想...",
        ]
        
        return random.choice(expressions) if random.random() < 0.4 else None
    
    def _make_decision(self, observation: dict) -> Optional[str]:
        """做出决定"""
        options = self._get_options(observation)
        
        if not options:
            return None
        
        selected = random.choice(options)
        
        # 随机选择表达
        expressions = [
            f"那就{selected}吧",
            f"先{selected}",
            f"去{selected}",
        ]
        
        return random.choice(expressions) if random.random() < 0.6 else None
    
    def _get_options(self, observation: dict) -> List[str]:
        """获取选项"""
        main_element = observation.get('main_element', '')
        action = observation.get('action', '')
        context = observation.get('context', '')
        
        options = []
        
        # 根据主要元素生成选项
        if main_element:
            options.append(f"去{main_element}")
            options.append(f"看看{main_element}")
        
        # 根据动作生成选项
        if action:
            options.append(f"{action}")
        
        # 根据上下文生成选项
        if context:
            if '工具' in context:
                options.append('做个工具')
            if '危险' in context:
                options.append('跑')
                options.append('打')
            if '天黑' in context or '夜晚' in context:
                options.append('做个床')
        
        return options
    
    def _select_best_option(self, options: List[str], observation: dict) -> str:
        """选择最佳选项"""
        if not options:
            return '继续'
        
        # 简单的选择策略
        context = observation.get('context', '')
        
        # 危险情况优先逃跑
        if '危险' in context or '怪物' in context:
            return '跑' if '跑' in options else options[0]
        
        # 稀有物品优先获取
        main_element = observation.get('main_element', '')
        rare_items = ['钻石', '金矿', '铁矿', '煤炭']
        if any(item in main_element for item in rare_items):
            return options[0]
        
        # 随机选择
        return random.choice(options)
    
    def _calculate_confidence(self, selected_option: str, observation: dict) -> float:
        """计算信心"""
        context = observation.get('context', '')
        
        # 熟悉情况信心高
        familiar_situations = ['收集', '砍树', '挖矿']
        if any(situation in selected_option for situation in familiar_situations):
            return random.uniform(0.7, 0.9)
        
        # 危险情况信心低
        if '危险' in context or '怪物' in context:
            return random.uniform(0.4, 0.7)
        
        # 普通情况
        return random.uniform(0.5, 0.8)
    
    def _generate_reason(self, selected_option: str, observation: dict) -> str:
        """生成理由"""
        context = observation.get('context', '')
        
        # 根据上下文生成理由
        if '危险' in context or '怪物' in context:
            return "太危险了，先保命"
        
        if '天黑' in context or '夜晚' in context:
            return "天快黑了，需要休息"
        
        if '工具' in context:
            return "需要工具才能做这个"
        
        # 简单理由
        return "先做这个"
    
    def think_and_decide(self, observation: dict) -> Tuple[List[str], Decision]:
        """
        思考并决策
        
        Args:
            observation: 观察结果
        
        Returns:
            (思考内容列表, 决策结果)
        """
        # 思考
        thoughts = self.think(observation)
        
        # 决策
        decision = self.decide(observation)
        
        return thoughts, decision
    
    def get_decision_stats(self) -> dict:
        """获取决策统计"""
        if not self.decision_history:
            return {
                'total_decisions': 0,
                'avg_confidence': 0.0,
                'hesitation_rate': 0.0
            }
        
        total = len(self.decision_history)
        avg_confidence = sum(d.confidence for d in self.decision_history) / total
        hesitation_count = sum(1 for d in self.decision_history if d.hesitation_time > 0)
        hesitation_rate = hesitation_count / total
        
        return {
            'total_decisions': total,
            'avg_confidence': avg_confidence,
            'hesitation_rate': hesitation_rate
        }


# 使用示例
if __name__ == "__main__":
    # 创建自然思考系统
    thinker = NaturalThinker()
    
    # 测试1: 正常观察
    print("测试自然思考系统：")
    
    observation1 = {
        'main_element': '树',
        'action': '砍',
        'context': '需要木头'
    }
    
    thoughts1 = thinker.think(observation1)
    decision1 = thinker.decide(observation1)
    
    print(f"\n观察1: {observation1}")
    print(f"思考: {thoughts1}")
    print(f"决策: {decision1.action}")
    print(f"理由: {decision1.reason}")
    print(f"信心: {decision1.confidence}")
    print(f"犹豫时间: {decision1.hesitation_time}")
    
    # 测试2: 危险情况
    observation2 = {
        'main_element': '僵尸',
        'action': '打',
        'context': '危险'
    }
    
    thoughts2 = thinker.think(observation2)
    decision2 = thinker.decide(observation2)
    
    print(f"\n观察2: {observation2}")
    print(f"思考: {thoughts2}")
    print(f"决策: {decision2.action}")
    print(f"理由: {decision2.reason}")
    print(f"信心: {decision2.confidence}")
    print(f"犹豫时间: {decision2.hesitation_time}")
    
    # 测试3: 稀有物品
    observation3 = {
        'main_element': '钻石',
        'action': '挖',
        'context': '需要工具'
    }
    
    thoughts3 = thinker.think(observation3)
    decision3 = thinker.decide(observation3)
    
    print(f"\n观察3: {observation3}")
    print(f"思考: {thoughts3}")
    print(f"决策: {decision3.action}")
    print(f"理由: {decision3.reason}")
    print(f"信心: {decision3.confidence}")
    print(f"犹豫时间: {decision3.hesitation_time}")
    
    # 测试4: 决策统计
    print("\n决策统计:")
    stats = thinker.get_decision_stats()
    print(f"总决策数: {stats['total_decisions']}")
    print(f"平均信心: {stats['avg_confidence']:.2f}")
    print(f"犹豫率: {stats['hesitation_rate']:.2%}")
    
    print("\n[测试完成]")
