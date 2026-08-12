#!/usr/bin/env python
"""测试自然行为系统"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.natural_behavior import NaturalBehavior

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
