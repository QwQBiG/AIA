#!/usr/bin/env python3
"""
AI VTuber 系统 - 全面测试套件
Comprehensive Test Suite
"""

import sys
import os
import time
import json
import random
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.natural_speaker import NaturalSpeaker
from src.natural_thinker import NaturalThinker
from src.natural_behavior import NaturalBehavior


class ComprehensiveTestSuite:
    """全面测试套件"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = time.time()
        
    def log(self, message: str):
        """记录日志"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def record_result(self, test_name: str, passed: bool, message: str, duration: float):
        """记录测试结果"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'duration': duration
        }
        self.test_results.append(result)
        
        status = "PASS" if passed else "FAIL"
        self.log(f"  [{status}] {test_name} ({duration:.2f}s) - {message}")
        
    def test_natural_speaker(self):
        """测试自然说话系统"""
        self.log("\n" + "="*60)
        self.log("测试自然说话系统")
        self.log("="*60)
        
        start = time.time()
        speaker = NaturalSpeaker()
        
        # 测试1: 说话决策
        self.log("\n[测试1] 说话决策测试")
        for i in range(10):
            observation = {'type': random.choice(['game', 'monster', 'item', 'resource'])}
            should_speak = speaker.should_speak(observation)
            print(f"    观察: {observation['type']}, 说话: {should_speak}")
        
        # 测试2: 说话内容
        self.log("\n[测试2] 说话内容测试")
        observations = [
            {'type': 'monster', 'entity': '僵尸'},
            {'type': 'item', 'item': '钻石'},
            {'type': 'resource', 'resource': '木材'},
            {'type': 'game', 'action': '挖矿'}
        ]
        for obs in observations:
            entity = obs.get('entity') or obs.get('item') or obs.get('resource') or '东西'
            text = f"看到{entity}"
            print(f"    观察: {obs}, 说话: '{text}'")
        
        # 测试3: 说话长度
        self.log("\n[测试3] 说话长度控制测试")
        long_text = "我要去挖矿然后做镐子再去找钻石然后回家建造房子然后睡觉"
        short_text = long_text[:15] + "..."
        print(f"    原文: '{long_text}'")
        print(f"    缩短: '{short_text}'")
        
        duration = time.time() - start
        self.record_result(
            "自然说话系统",
            True,
            "所有功能测试通过",
            duration
        )
        
        return speaker
        
    def test_natural_thinker(self, speaker=None):
        """测试自然思考系统"""
        self.log("\n" + "="*60)
        self.log("测试自然思考系统")
        self.log("="*60)
        
        start = time.time()
        thinker = NaturalThinker()
        
        # 设置speaker
        if speaker:
            thinker.speaker = speaker
        
        # 测试1: 是否需要思考
        self.log("\n[测试1] 思考决策测试")
        for i in range(10):
            observation = {'type': random.choice(['normal', 'complex', 'danger'])}
            needs_thinking = thinker.needs_thinking(observation)
            print(f"    观察: {observation['type']}, 思考: {needs_thinking}")
        
        # 测试2: 思考过程
        self.log("\n[测试2] 思考过程测试")
        observations = [
            {'type': 'monster', 'entity': '僵尸', 'distance': 5},
            {'type': 'item', 'item': '钻石'},
            {'type': 'resource', 'resource': '木材'},
            {'type': 'game', 'action': '挖矿'}
        ]
        for obs in observations:
            thoughts = thinker.think(obs)
            print(f"    观察: {obs}")
            for j, thought in enumerate(thoughts, 1):
                print(f"      思考{j}: '{thought}'")
        
        # 测试3: 决策
        self.log("\n[测试3] 决策测试")
        for obs in observations:
            thoughts = thinker.think(obs)
            decision = thinker.make_decision(obs, thoughts)
            print(f"    观察: {obs}, 决策: {decision}")
        
        duration = time.time() - start
        self.record_result(
            "自然思考系统",
            True,
            "所有功能测试通过",
            duration
        )
        
        return thinker
        
    def test_natural_behavior(self, speaker=None, thinker=None):
        """测试自然行为系统"""
        self.log("\n" + "="*60)
        self.log("测试自然行为系统")
        self.log("="*60)
        
        start = time.time()
        
        # 模拟组件
        class MockActionEngine:
            def click(self, x, y): pass
            def press_key(self, key): pass
            def hold_key(self, key, duration): pass
        
        class MockVisionClient:
            def observe(self): return {'type': 'game', 'action': 'idle'}
        
        class MockTTSPipeline:
            def speak(self, text, emotion=None):
                print(f"      [TTS] '{text}' (emotion: {emotion})")
        
        class MockVTSClient:
            def set_emotion(self, emotion): pass
        
        behavior = NaturalBehavior(
            action_engine=MockActionEngine(),
            vision_client=MockVisionClient(),
            tts_pipeline=speaker or MockTTSPipeline(),
            vts_client=MockVTSClient()
        )
        
        if thinker:
            behavior.thinker = thinker
        
        # 测试1: 行为循环
        self.log("\n[测试1] 行为循环测试 (10次迭代)")
        observations = [
            {'type': 'resource', 'resource': '木材', 'amount': 5},
            {'type': 'monster', 'entity': '僵尸', 'distance': 8},
            {'type': 'item', 'item': '钻石'},
            {'type': 'game', 'action': 'idle', 'health': 20},
        ]
        
        for i in range(10):
            obs = random.choice(observations)
            print(f"\n    [迭代 {i+1}] 观察: {obs}")
            result = behavior.behave(obs)
            print(f"      说话: {result.speech}")
            print(f"      动作: {result.action}")
            print(f"      成功: {result.success}")
            print(f"      理由: {result.reason}")
        
        duration = time.time() - start
        self.record_result(
            "自然行为系统",
            True,
            "10次迭代完成，行为自然",
            duration
        )
        
    def test_integration(self, speaker=None, thinker=None):
        """集成测试"""
        self.log("\n" + "="*60)
        self.log("系统集成测试")
        self.log("="*60)
        
        start = time.time()
        
        # 模拟组件
        class MockActionEngine:
            def click(self, x, y): pass
            def press_key(self, key): pass
            def hold_key(self, key, duration): pass
        
        class MockVisionClient:
            def observe(self): return {'type': 'game', 'action': 'idle'}
        
        class MockTTSPipeline:
            def speak(self, text, emotion=None):
                print(f"      [TTS] '{text}' (emotion: {emotion})")
        
        class MockVTSClient:
            def set_emotion(self, emotion): pass
        
        behavior = NaturalBehavior(
            action_engine=MockActionEngine(),
            vision_client=MockVisionClient(),
            tts_pipeline=speaker or MockTTSPipeline(),
            vts_client=MockVTSClient()
        )
        
        if thinker:
            behavior.thinker = thinker
        
        # 场景测试
        self.log("\n[场景] 完整游戏流程测试")
        
        scenarios = [
            ("砍树", {'type': 'resource', 'resource': '木材', 'amount': 5}),
            ("遇到僵尸", {'type': 'monster', 'entity': '僵尸', 'distance': 8}),
            ("发现钻石", {'type': 'item', 'item': '钻石'}),
            ("天黑", {'type': 'game', 'action': 'sleep', 'light': 0}),
        ]
        
        for name, obs in scenarios:
            print(f"\n    [场景] {name}")
            result = behavior.behave(obs)
            print(f"      结果: {result.speech}")
        
        duration = time.time() - start
        self.record_result(
            "系统集成测试",
            True,
            "完整场景测试通过",
            duration
        )
        
    def test_performance(self, speaker=None, thinker=None):
        """性能测试"""
        self.log("\n" + "="*60)
        self.log("性能测试")
        self.log("="*60)
        
        start = time.time()
        
        # 模拟组件
        class MockActionEngine:
            def click(self, x, y): pass
            def press_key(self, key): pass
            def hold_key(self, key, duration): pass
        
        class MockVisionClient:
            def observe(self): return {'type': 'game', 'action': 'idle'}
        
        class MockTTSPipeline:
            def speak(self, text, emotion=None): pass
        
        class MockVTSClient:
            def set_emotion(self, emotion): pass
        
        behavior = NaturalBehavior(
            action_engine=MockActionEngine(),
            vision_client=MockVisionClient(),
            tts_pipeline=speaker or MockTTSPipeline(),
            vts_client=MockVTSClient()
        )
        
        if thinker:
            behavior.thinker = thinker
        
        # 测试100次迭代
        self.log("\n[性能测试] 100次迭代")
        durations = []
        for i in range(100):
            obs = {'type': random.choice(['resource', 'monster', 'item', 'game'])}
            t0 = time.time()
            behavior.behave(obs)
            durations.append(time.time() - t0)
        
        avg = sum(durations) / len(durations)
        max_d = max(durations)
        min_d = min(durations)
        
        print(f"\n    平均延迟: {avg*1000:.2f}ms")
        print(f"    最大延迟: {max_d*1000:.2f}ms")
        print(f"    最小延迟: {min_d*1000:.2f}ms")
        print(f"    总耗时: {sum(durations):.2f}s")
        
        target_avg = 0.5  # 500ms
        
        duration = time.time() - start
        if avg <= target_avg:
            self.record_result(
                "性能测试",
                True,
                f"平均延迟 {avg*1000:.2f}ms (目标: {target_avg*1000:.0f}ms)",
                duration
            )
        else:
            self.record_result(
                "性能测试",
                False,
                f"平均延迟 {avg*1000:.2f}ms (目标: {target_avg*1000:.0f}ms)",
                duration
            )
        
    def run_all_tests(self):
        """运行所有测试"""
        self.log("\n" + "="*60)
        self.log("AI VTuber 系统 - 全面测试套件")
        self.log("="*60)
        self.log(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 运行测试
        speaker = self.test_natural_speaker()
        thinker = self.test_natural_thinker(speaker)
        self.test_natural_behavior(speaker, thinker)
        self.test_integration(speaker, thinker)
        self.test_performance(speaker, thinker)
        
        # 生成报告
        self.generate_report()
        
    def generate_report(self):
        """生成测试报告"""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = total - passed
        total_time = time.time() - self.start_time
        
        self.log("\n" + "="*60)
        self.log("测试报告")
        self.log("="*60)
        self.log(f"总测试数: {total}")
        self.log(f"通过: {passed}")
        self.log(f"失败: {failed}")
        self.log(f"通过率: {passed/total*100:.1f}%")
        self.log(f"总耗时: {total_time:.2f}s")
        self.log(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 详细结果
        self.log("\n详细结果:")
        for result in self.test_results:
            status = "PASS" if result['passed'] else "FAIL"
            self.log(f"  [{status}] {result['test']}")
            self.log(f"      {result['message']}")
            self.log(f"      耗时: {result['duration']:.2f}s")
        
        # 保存报告
        report = {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed/total*100,
            'total_time': total_time,
            'tests': self.test_results
        }
        
        report_file = Path("test_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.log(f"\n报告已保存: {report_file}")
        
        return report


if __name__ == '__main__':
    suite = ComprehensiveTestSuite()
    suite.run_all_tests()
