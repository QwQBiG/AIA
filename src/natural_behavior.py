"""
自然行为系统 - 像真人一样自然行为

特点：
- 90%时间专注于游戏
- 偶尔看弹幕（10%概率）
- 偶尔说话（30%概率）
- 会犯错
- 会分心
- 正常速度，不快不慢
"""

import random
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .natural_speaker import NaturalSpeaker
from .natural_thinker import NaturalThinker

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """动作结果"""
    success: bool
    action: str
    reason: str
    error: Optional[str] = None


class NaturalBehavior:
    """自然行为系统"""
    
    def __init__(self, action_engine=None, vision_client=None, tts_pipeline=None, vts_client=None):
        """
        初始化自然行为系统
        
        Args:
            action_engine: 动作引擎
            vision_client: 视觉客户端
            tts_pipeline: TTS管道
            vts_client: VTS客户端
        """
        self.action_engine = action_engine
        self.vision_client = vision_client
        
        # 子系统
        self.speaker = NaturalSpeaker(tts_pipeline, vts_client)
        self.thinker = NaturalThinker()
        
        # 行为参数
        self.focus_ratio = 0.9  # 90%时间专注于游戏
        self.comment_check_probability = 0.1  # 10%概率看弹幕
        self.speak_probability = 0.3  # 30%概率说话
        self.mistake_probability = 0.1  # 10%概率犯错
        self.distracted_probability = 0.05  # 5%概率分心
        
        # 状态
        self.active = False
        self.current_task = None
        
        # 统计
        self.action_count = 0
        self.mistake_count = 0
        self.distracted_count = 0
        
        logger.info("自然行为系统初始化完成")
    
    def start(self):
        """启动行为系统"""
        self.active = True
        logger.info("自然行为系统已启动")
    
    def stop(self):
        """停止行为系统"""
        self.active = False
        logger.info("自然行为系统已停止")
    
    def behave(self, observation: dict) -> ActionResult:
        """
        自然行为
        
        Args:
            observation: 观察结果
        
        Returns:
            动作结果
        """
        if not self.active:
            return ActionResult(False, "未启动", "系统未启动")
        
        # 1. 思考
        thoughts, decision = self.thinker.think_and_decide(observation)
        
        # 2. 说出思考
        for thought in thoughts:
            self.speaker.speak(thought)
        
        # 3. 执行动作
        result = self.execute_action(decision, observation)
        
        # 4. 更新统计
        self.action_count += 1
        self.speaker.update_action_count()
        
        # 5. 偶尔看弹幕
        if random.random() < self.comment_check_probability:
            self.check_comments()
        
        # 6. 偶尔分心
        if random.random() < self.distracted_probability:
            self.distracted_count += 1
            self._be_distracted()
        
        return result
    
    def execute_action(self, decision, observation: dict) -> ActionResult:
        """
        执行动作
        
        Args:
            decision: 决策
            observation: 观察结果
        
        Returns:
            动作结果
        """
        try:
            # 是否犯错
            if random.random() < self.mistake_probability:
                return self._make_mistake(decision, observation)
            
            # 正常执行
            return self._execute_normal(decision, observation)
        
        except Exception as e:
            logger.error(f"执行动作失败: {e}")
            return ActionResult(False, decision, f"执行失败: {str(e)}", str(e))
    
    def _execute_normal(self, decision, observation: dict) -> ActionResult:
        """正常执行动作"""
        # 根据决策执行动作
        decision_action = decision.action if hasattr(decision, 'action') else decision
        
        if decision_action == '跑':
            result = self._run_away()
        elif decision_action == '打':
            result = self._attack()
        elif '砍' in decision_action or '树' in decision_action:
            result = self._chop_tree()
        elif '挖' in decision_action or '矿' in decision_action:
            result = self._mine()
        elif '做' in decision_action or '工具' in decision_action:
            result = self._craft_tool()
        elif '床' in decision_action:
            result = self._make_bed()
        else:
            result = self._do_generic(decision_action)
        
        return result
    
    def _make_mistake(self, decision, observation: dict) -> ActionResult:
        """犯错"""
        self.mistake_count += 1
        
        # 随机选择一种错误
        mistakes = [
            self._wrong_direction,
            self._forget_item,
            self._wrong_tool,
            self._click_wrong
        ]
        
        mistake_func = random.choice(mistakes)
        return mistake_func(decision, observation)
    
    def _wrong_direction(self, decision, observation: dict) -> ActionResult:
        """方向错误"""
        self.speaker.speak("诶，走反了", emotion="surprised")
        time.sleep(1.0)
        self.speaker.speak("换个方向")
        
        decision_action = decision.action if hasattr(decision, 'action') else decision
        return ActionResult(False, decision_action, "方向错误，已纠正", "走错了")
        time.sleep(1.0)
        self.speaker.speak("换个方向")
        
        return ActionResult(False, decision, "方向错误，已纠正", "走错了")
    
    def _forget_item(self, decision, observation: dict) -> ActionResult:
        """忘记物品"""
        self.speaker.speak("哦，我没有这个", emotion="surprised")
        time.sleep(0.5)
        self.speaker.speak("先去找找")
        
        decision_action = decision.action if hasattr(decision, 'action') else decision
        return ActionResult(False, decision_action, "忘记物品，需补充", "没有这个物品")
        time.sleep(0.5)
        self.speaker.speak("先去找找")
        
        return ActionResult(False, decision, "忘记物品，需补充", "没有这个物品")
    
    def _wrong_tool(self, decision, observation: dict) -> ActionResult:
        """工具错误"""
        self.speaker.speak("嗯...这个不对", emotion="confused")
        time.sleep(0.5)
        self.speaker.speak("换个工具")
        
        decision_action = decision.action if hasattr(decision, 'action') else decision
        return ActionResult(False, decision_action, "工具错误，需更换", "工具不对")
        time.sleep(0.5)
        self.speaker.speak("换个工具")
        
        return ActionResult(False, decision, "工具错误，需更换", "工具不对")
    
    def _click_wrong(self, decision, observation: dict) -> ActionResult:
        """点错位置"""
        self.speaker.speak("哎呀，点错了", emotion="surprised")
        time.sleep(0.5)
        self.speaker.speak("重来")
        
        decision_action = decision.action if hasattr(decision, 'action') else decision
        return ActionResult(False, decision_action, "点错位置，需重试", "点错了")
        time.sleep(0.5)
        self.speaker.speak("重来")
        
        return ActionResult(False, decision, "点错位置，需重试", "点错了")
    
    def _be_distracted(self):
        """分心"""
        # 停顿一下
        time.sleep(random.uniform(1.0, 2.0))
        
        # 可能说点什么
        distractions = [
            "嗯...",
            "哦...",
            "我想想...",
        ]
        
        if random.random() < 0.5:
            self.speaker.speak(random.choice(distractions))
    
    def check_comments(self):
        """检查弹幕"""
        # 简单模拟
        if random.random() < 0.3:
            comment = random.choice(["做个床", "先砍树", "小心怪物", "加油"])
            self.speaker.respond_to_comment(comment)
    
    def _run_away(self) -> ActionResult:
        """逃跑"""
        self.speaker.speak("跑")
        time.sleep(0.5)
        
        if self.action_engine:
            # 实际执行逃跑动作
            pass
        
        return ActionResult(True, "跑", "成功逃跑")
    
    def _attack(self) -> ActionResult:
        """攻击"""
        self.speaker.speak("打一下")
        time.sleep(0.3)
        
        if self.action_engine:
            # 实际执行攻击动作
            pass
        
        # 偶尔需要打多下
        if random.random() < 0.3:
            self.speaker.speak("再打一下")
            time.sleep(0.3)
        
        return ActionResult(True, "打", "成功攻击")
    
    def _chop_tree(self) -> ActionResult:
        """砍树"""
        self.speaker.speak("砍树")
        time.sleep(0.5)
        
        # 持续砍一段时间
        chop_time = random.uniform(2.0, 4.0)
        start_time = time.time()
        
        while time.time() - start_time < chop_time:
            if self.action_engine:
                # 实际执行砍树动作
                pass
            time.sleep(0.5)
        
        # 偶尔说话
        if random.random() < 0.3:
            self.speaker.speak("嗯...差不多了")
        
        return ActionResult(True, "砍树", "成功砍树")
    
    def _mine(self) -> ActionResult:
        """挖矿"""
        self.speaker.speak("挖矿")
        time.sleep(0.5)
        
        # 持续挖一段时间
        mine_time = random.uniform(3.0, 5.0)
        start_time = time.time()
        
        while time.time() - start_time < mine_time:
            if self.action_engine:
                # 实际执行挖矿动作
                pass
            time.sleep(0.5)
        
        return ActionResult(True, "挖矿", "成功挖矿")
    
    def _craft_tool(self) -> ActionResult:
        """制作工具"""
        self.speaker.speak("做个工具")
        time.sleep(0.5)
        
        if self.action_engine:
            # 实际执行制作工具动作
            pass
        
        time.sleep(1.0)
        
        return ActionResult(True, "做工具", "成功制作工具")
    
    def _make_bed(self) -> ActionResult:
        """做床"""
        self.speaker.speak("做个床")
        time.sleep(0.5)
        
        # 检查材料
        if random.random() < 0.3:
            self.speaker.speak("需要羊毛", emotion="confused")
            time.sleep(0.5)
            self.speaker.speak("找羊去")
            return ActionResult(False, "做床", "需要羊毛", "缺少羊毛")
        
        if self.action_engine:
            # 实际执行做床动作
            pass
        
        time.sleep(1.0)
        
        return ActionResult(True, "做床", "成功制作床")
    
    def _do_generic(self, action: str) -> ActionResult:
        """执行通用动作"""
        self.speaker.speak(action)
        time.sleep(0.5)
        
        if self.action_engine:
            # 实际执行通用动作
            pass
        
        time.sleep(1.0)
        
        return ActionResult(True, action, f"成功执行: {action}")
    
    def get_behavior_stats(self) -> Dict[str, Any]:
        """获取行为统计"""
        speak_stats = self.speaker.get_speak_stats()
        decision_stats = self.thinker.get_decision_stats()
        
        mistake_rate = self.mistake_count / self.action_count if self.action_count > 0 else 0.0
        distracted_rate = self.distracted_count / self.action_count if self.action_count > 0 else 0.0
        
        return {
            'action_count': self.action_count,
            'mistake_count': self.mistake_count,
            'distracted_count': self.distracted_count,
            'mistake_rate': mistake_rate,
            'distracted_rate': distracted_rate,
            'speak_stats': speak_stats,
            'decision_stats': decision_stats
        }


# 使用示例
if __name__ == "__main__":
    # 创建自然行为系统
    behavior = NaturalBehavior()
    behavior.start()
    
    print("测试自然行为系统：")
    
    # 测试1: 正常行为
    observation1 = {
        'main_element': '树',
        'action': '砍',
        'context': '需要木头'
    }
    
    result1 = behavior.behave(observation1)
    print(f"\n观察1: {observation1}")
    print(f"结果: {result1.success}")
    print(f"动作: {result1.action}")
    print(f"理由: {result1.reason}")
    if result1.error:
        print(f"错误: {result1.error}")
    
    # 测试2: 危险情况
    observation2 = {
        'main_element': '僵尸',
        'action': '打',
        'context': '危险'
    }
    
    result2 = behavior.behave(observation2)
    print(f"\n观察2: {observation2}")
    print(f"结果: {result2.success}")
    print(f"动作: {result2.action}")
    print(f"理由: {result2.reason}")
    
    # 测试3: 稀有物品
    observation3 = {
        'main_element': '钻石',
        'action': '挖',
        'context': '需要工具'
    }
    
    result3 = behavior.behave(observation3)
    print(f"\n观察3: {observation3}")
    print(f"结果: {result3.success}")
    print(f"动作: {result3.action}")
    print(f"理由: {result3.reason}")
    
    # 测试4: 行为统计
    print("\n行为统计:")
    stats = behavior.get_behavior_stats()
    print(f"动作数: {stats['action_count']}")
    print(f"错误数: {stats['mistake_count']}")
    print(f"分心数: {stats['distracted_count']}")
    print(f"错误率: {stats['mistake_rate']:.2%}")
    print(f"分心率: {stats['distracted_rate']:.2%}")
    print(f"说话数: {stats['speak_stats']['speak_count']}")
    print(f"说话比例: {stats['speak_stats']['speak_ratio']:.2%}")
    print(f"决策数: {stats['decision_stats']['total_decisions']}")
    print(f"平均信心: {stats['decision_stats']['avg_confidence']:.2f}")
    
    behavior.stop()
    
    print("\n[测试完成]")
