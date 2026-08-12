#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化测试脚本 - 验证 Critical 和 High Priority Bug 修复

测试范围：
1. VTS Client 死锁风险
2. GUI 协程重用
3. SystemWorkflow 重复启动
4. Whisper 延迟优化
5. TTS 管道非阻塞
6. 记忆系统 importance_score 计算
7. Async context 回调修复

作者: AI Assistant
日期: 2026-03-22
"""

import asyncio
import sys
import time
import logging
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.vts_client import VTSClient
import src.memory_core.memory_core as MemoryCore

# Windows 编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class TestResults:
    """测试结果统计"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"[PASS] {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"[FAIL] {test_name}: {error}")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "="*60)
        print(f"测试总结: {self.passed}/{total} 通过")
        if self.failed > 0:
            print(f"失败的测试:")
            for test, error in self.errors:
                print(f"  - {test}: {error}")
        print("="*60)
        return self.failed == 0


def test_vts_client_lock_structure():
    """测试 VTS Client 锁结构（移除 threading.Lock 嵌套）"""
    print("\n[TEST] Test 1: VTS Client Lock Structure")
    results = TestResults()

    vts_client = VTSClient()

    # 检查 threading.Lock 是否已移除
    if vts_client._connection_lock is None:
        results.add_pass("threading.Lock 已移除")
    else:
        results.add_fail("threading.Lock 未移除", "仍存在死锁风险")

    # 检查 asyncio.Lock 是否保留
    if vts_client._async_lock is None:
        results.add_fail("asyncio.Lock 丢失", "需要 asyncio.Lock 进行异步操作")
    else:
        results.add_pass("asyncio.Lock 存在")

    return results


def test_vts_mouth_parameter_optimization():
    """测试 VTS Mouth Parameter 优化（fire-and-forget）"""
    print("\n[TEST] 测试 2: VTS Mouth Parameter 优化")
    results = TestResults()

    import inspect
    from src.vts_client import VTSClient

    # 检查 _set_mouth_parameters 方法
    source = inspect.getsource(VTSClient._set_mouth_parameters)

    # 检查是否移除了响应等待
    if "await asyncio.wait_for(self.websocket.recv()" not in source:
        results.add_pass("Mouth parameter 响应等待已移除")
    else:
        results.add_fail("Mouth parameter 仍等待响应", "仍存在性能瓶颈")

    return results


def test_gui_run_async_simplification():
    """测试 GUI _run_async 简化"""
    print("\n[TEST] 测试 3: GUI _run_async 简化")
    results = TestResults()

    import inspect
    from src.gui_controller import gui_controller as GUIController

    # 检查 _run_async 方法
    source = inspect.getsource(GUIController._run_async)

    # 检查是否移除了复杂的 ThreadPoolExecutor
    if "ThreadPoolExecutor" not in source:
        results.add_pass("ThreadPoolExecutor 已移除")
    else:
        results.add_fail("ThreadPoolExecutor 仍存在", "逻辑仍有简化空间")

    # 检查协程重用问题是否修复
    if "current_loop.create_task(coro)" in source and \
       "executor.submit" not in source:
        results.add_pass("协程重用问题已修复")
    else:
        results.add_fail("协程重用问题可能未修复", "需要检查逻辑")

    return results


def test_system_workflow_duplicate_start():
    """测试 SystemWorkflow 重复启动修复"""
    print("\n[TEST] 测试 4: SystemWorkflow 重复启动修复")
    results = TestResults()

    import inspect
    import src.system_workflow as SystemWorkflow

    # 检查 _process_user_input_streaming 方法
    source = inspect.getsource(SystemWorkflow.system_workflow.SystemWorkflow._process_user_input_streaming)

    # 检查重复的 start 调用
    start_count = source.count("await self._tts_pipeline.start(on_subtitle)")

    if start_count == 1:
        results.add_pass(f"TTS Pipeline 仅启动一次")
    else:
        results.add_fail(f"TTS Pipeline 启动了 {start_count} 次", "存在重复启动")

    return results


def test_whisper_best_of_optimization():
    """测试 Whisper best_of 优化"""
    print("\n[TEST] 测试 5: Whisper best_of 优化")
    results = TestResults()

    import inspect
    from src.full_duplex_engine import whisper_asr

    # 检查 transcribe 调用
    source = inspect.getsource(whisper_asr.WhisperASR._process_audio)

    if 'best_of=1' in source:
        results.add_pass("best_of 设置为 1")
    elif 'best_of=5' in source:
        results.add_fail("best_of 仍为 5", "延迟仍然很高")
    else:
        results.add_fail("best_of 参数未找到", "需要检查配置")

    return results


def test_tts_play_filler_nonblocking():
    """测试 TTS play_filler 非阻塞"""
    print("\n[TEST] 测试 6: TTS play_filler 非阻塞")
    results = TestResults()

    import inspect
    import src.tts_pipeline as TTSPipeline

    # 检查 play_filler 方法
    source = inspect.getsource(TTSPipeline.tts_pipeline.src.tts_pipeline.TTSPipeline.play_filler)

    if "threading.Thread" in source and "daemon=True" in source:
        results.add_pass("play_filler 使用后台线程")
    else:
        results.add_fail("play_filler 可能阻塞", "未使用后台线程")

    return results


def test_tts_idle_timeout():
    """测试 TTS 空闲等待超时"""
    print("\n[TEST] 测试 7: TTS 空闲等待超时")
    results = TestResults()

    import inspect
    import src.system_workflow as SystemWorkflow

    # 检查 _process_user_input_streaming 方法
    source = inspect.getsource(SystemWorkflow.system_workflow.SystemWorkflow._process_user_input_streaming)

    if "timeout_seconds" in source and "timeout_seconds =" in source:
        results.add_pass("空闲等待添加了超时保护")
    else:
        results.add_fail("空闲等待无超时保护", "可能导致无限等待")

    return results


def test_memory_importance_score_calculation():
    """测试记忆 importance_score 计算"""
    print("\n[TEST] 测试 8: 记忆 importance_score 计算")
    results = TestResults()

    import inspect
    import src.memory_core.memory_core as MemoryCore

    # 检查 _calculate_importance_score 方法是否存在
    if hasattr(MemoryCore.memory_core.MemoryCore, '_calculate_importance_score'):
        results.add_pass("_calculate_importance_score 方法存在")

        # 检查方法逻辑
        source = inspect.getsource(MemoryCore.memory_core.MemoryCore._calculate_importance_score)

        factors = []
        if "content length" in source.lower() or "len(content)" in source:
            factors.append("content length")
        if "entity count" in source.lower() or "len(entities)" in source:
            factors.append("entity count")
        if "interaction_type" in source:
            factors.append("interaction_type")
        if "access_count" in source:
            factors.append("access_count")

        if len(factors) >= 3:
            results.add_pass(f"Importance 计算考虑了 {len(factors)} 个因素")
        else:
            results.add_fail(f"Importance 计算仅考虑 {len(factors)} 个因素", "逻辑可能过于简单")
    else:
        results.add_fail("_calculate_importance_score 方法不存在", "需要实现")

    return results


def test_on_sentence_async_callback():
    """测试 on_sentence 异步回调修复"""
    print("\n[TEST] 测试 9: on_sentence 异步回调修复")
    results = TestResults()

    import inspect
    import src.system_workflow as SystemWorkflow

    # 检查 _process_user_input_streaming 方法中的 on_sentence 回调
    source = inspect.getsource(SystemWorkflow.system_workflow.SystemWorkflow._process_user_input_streaming)

    if "call_soon_threadsafe" in source:
        results.add_pass("使用 call_soon_threadsafe 安全调度")
    elif "asyncio.create_task" in source and "get_running_loop" in source:
        results.add_pass("添加了运行循环检测")
    else:
        results.add_fail("可能存在 RuntimeError 风险", "未正确处理非异步上下文")

    return results


def test_audio_thread_join_replacement():
    """测试 audio_thread.join() 替换"""
    print("\n[TEST] 测试 10: audio_thread.join() 替换")
    results = TestResults()

    import inspect
    import src.system_workflow as SystemWorkflow

    # 检查 _process_tts_and_animation 方法
    source = inspect.getsource(SystemWorkflow.system_workflow.SystemWorkflow._process_tts_and_animation)

    if "audio_thread.join()" not in source:
        results.add_pass("audio_thread.join() 已移除")
    else:
        results.add_fail("audio_thread.join() 仍然存在", "会阻塞事件循环")

    return results


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("AI VTuber 系统 Bug 修复验证测试")
    print("="*60)

    all_results = []

    try:
        all_results.append(test_vts_client_lock_structure())
        all_results.append(test_vts_mouth_parameter_optimization())
        all_results.append(test_gui_run_async_simplification())
        all_results.append(test_system_workflow_duplicate_start())
        all_results.append(test_whisper_best_of_optimization())
        all_results.append(test_tts_play_filler_nonblocking())
        all_results.append(test_tts_idle_timeout())
        all_results.append(test_memory_importance_score_calculation())
        all_results.append(test_on_sentence_async_callback())
        all_results.append(test_audio_thread_join_replacement())

        # 汇总结果
        total_passed = sum(r.passed for r in all_results)
        total_failed = sum(r.failed for r in all_results)
        total_tests = total_passed + total_failed

        print("\n" + "="*60)
        print(f"[SUMMARY] 总体测试结果: {total_passed}/{total_tests} 通过")
        if total_failed == 0:
            print("[SUCCESS] 所有 Critical/High Priority Bug 修复验证通过！")
        else:
            print(f"[WARNING]  仍有 {total_failed} 个测试失败")
        print("="*60)

        return total_failed == 0

    except Exception as e:
        print(f"\n[ERROR] 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
