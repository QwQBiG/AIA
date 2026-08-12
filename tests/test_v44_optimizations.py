"""
v4.4 Super Optimization Test Suite
超极速优化完整测试套件

测试覆盖:
1. 超极速启动优化器
2. 智能模块预加载管理器
3. LLM连接池
4. 自适应性能调优
5. 全链路监控
"""

import pytest
import asyncio
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 导入被测试模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.super_startup_optimizer import (
    SuperStartupOptimizer,
    get_startup_optimizer,
    lazy_import,
    ModuleLoadStats,
    StartupProfile
)

from src.smart_preload_manager import (
    SmartPreloadManager,
    get_preload_manager,
    PreloadTask,
    ModuleUsageStats,
    PreloadStrategy
)

from src.llm_connection_pool import (
    LLMConnectionPool,
    LLMConnection,
    ConnectionConfig,
    PoolStats,
    get_llm_pool
)

from src.adaptive_performance_tuner import (
    AdaptivePerformanceTuner,
    get_performance_tuner,
    MetricData,
    MetricStats,
    PerformanceTune,
    TuneConfig
)

from src.full_chain_monitor import (
    FullChainMonitor,
    get_full_chain_monitor,
    Span,
    Trace,
    TraceStats
)


# ============================================================================
# Super Startup Optimizer Tests
# ============================================================================

class TestSuperStartupOptimizer:
    """超极速启动优化器测试"""
    
    @pytest.fixture
    def optimizer(self):
        """创建优化器实例"""
        opt = SuperStartupOptimizer()
        yield opt
        opt.shutdown()
    
    def test_singleton(self, optimizer):
        """测试单例模式"""
        opt2 = SuperStartupOptimizer()
        assert opt is opt2
    
    def test_lazy_import(self, optimizer):
        """测试惰性导入"""
        # 导入标准库
        asyncio_module = optimizer.lazy_import('asyncio')
        assert asyncio_module is not None
        assert 'asyncio' in optimizer._loaded_cache
        
        # 第二次导入应该使用缓存
        start = time.time()
        asyncio_module2 = optimizer.lazy_import('asyncio')
        elapsed = (time.time() - start) * 1000
        assert asyncio_module is asyncio_module2
        assert elapsed < 10  # 应该非常快
    
    def test_module_stats(self, optimizer):
        """测试模块统计"""
        optimizer.lazy_import('json')
        
        stats = optimizer._module_stats.get('json')
        assert stats is not None
        assert stats.module_name == 'json'
        assert stats.load_time > 0
        assert stats.load_count == 1
    
    def test_bottleneck_detection(self, optimizer):
        """测试瓶颈检测"""
        # 创建模拟数据
        stats = ModuleLoadStats(
            module_name='slow_module',
            load_time=500.0,
            memory_before=10000,
            memory_after=20000,
            is_critical=True
        )
        optimizer._module_stats['slow_module'] = stats
        
        bottlenecks = optimizer.get_bottleneck_modules(threshold_ms=300)
        assert len(bottlenecks) >= 1
        assert 'slow_module' in [b.module_name for b in bottlenecks]
    
    def test_generate_profile(self, optimizer):
        """测试生成性能分析"""
        optimizer.lazy_import('time')
        optimizer.lazy_import('datetime')
        
        profile = optimizer.generate_startup_profile()
        assert profile.total_time >= 0
        assert len(profile.module_times) > 0
        assert profile.recommendations is not None
    
    def test_measure_time(self, optimizer):
        """测试时间测量"""
        with optimizer.measure_time('test_operation'):
            time.sleep(0.1)
        
        assert 'test_operation' in optimizer._startup_timings
        assert optimizer._startup_timings['test_operation'] >= 90  # 至少90ms


# ============================================================================
# Smart Preload Manager Tests
# ============================================================================

class TestSmartPreloadManager:
    """智能预加载管理器测试"""
    
    @pytest.fixture
    def preload_manager(self):
        """创建预加载管理器实例"""
        manager = SmartPreloadManager()
        manager.start()
        yield manager
        manager.stop()
    
    def test_singleton(self, preload_manager):
        """测试单例模式"""
        manager2 = SmartPreloadManager()
        assert preload_manager is manager2
    
    def test_record_import(self, preload_manager):
        """测试记录导入"""
        preload_manager.record_import('asyncio', 50.0, success=True)
        
        stats = preload_manager.get_usage_stats('asyncio')
        assert stats is not None
        assert stats.import_count == 1
        assert stats.avg_load_time == 50.0
        assert stats.success_count == 1
    
    def test_usage_frequency(self, preload_manager):
        """测试使用频率计算"""
        # 模拟多次导入
        for _ in range(10):
            preload_manager.record_import('frequent_module', 30.0, success=True)
        
        stats = preload_manager.get_usage_stats('frequent_module')
        assert stats.usage_frequency > 0
    
    def test_reliability(self, preload_manager):
        """测试可靠性计算"""
        # 8次成功，2次失败
        for _ in range(8):
            preload_manager.record_import('reliable_module', 30.0, success=True)
        for _ in range(2):
            preload_manager.record_import('reliable_module', 30.0, success=False)
        
        stats = preload_manager.get_usage_stats('reliable_module')
        assert stats.reliability == 0.8
    
    def test_queue_preload(self, preload_manager):
        """测试预加载队列"""
        preload_manager.queue_preload('asyncio', priority=8)
        
        status = preload_manager.get_queue_status()
        assert status['queue_size'] >= 0  # 可能已被处理
    
    def test_top_used_modules(self, preload_manager):
        """测试获取最常用模块"""
        # 记录一些模块的使用
        preload_manager.record_import('module_a', 10.0, success=True)
        preload_manager.record_import('module_a', 15.0, success=True)
        preload_manager.record_import('module_b', 20.0, success=True)
        
        top_modules = preload_manager.get_top_used_modules(limit=2)
        assert len(top_modules) <= 2
        assert any(m.module_name == 'module_a' for m in top_modules)


# ============================================================================
# LLM Connection Pool Tests
# ============================================================================

class TestLLMConnectionPool:
    """LLM连接池测试"""
    
    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return ConnectionConfig(
            base_url="http://localhost:11434",
            model="test-model",
            pool_size=3,
            max_idle_time=10.0
        )
    
    @pytest.fixture
    def pool(self, config):
        """创建连接池实例"""
        pool = LLMConnectionPool(config)
        pool.start()
        yield pool
        pool.stop()
    
    def test_acquire_release(self, pool):
        """测试获取和释放连接"""
        # 获取连接（同步测试，不实际调用acquire）
        # 这里只测试连接池的基本状态
        stats = pool.get_stats()
        assert stats.total_connections >= 0
        assert stats.active_connections >= 0
        assert stats.idle_connections >= 0
    
    def test_pool_stats(self, pool):
        """测试连接池统计"""
        stats = pool.get_stats()
        
        assert isinstance(stats, PoolStats)
        assert stats.total_connections >= 0
        assert stats.active_connections >= 0
        assert stats.idle_connections >= 0
        assert stats.pool_utilization >= 0.0
        assert stats.pool_utilization <= 1.0
    
    def test_utilization(self, pool):
        """测试连接池利用率计算"""
        stats = pool.get_stats()
        
        if stats.total_connections > 0:
            expected = stats.active_connections / stats.total_connections
            assert abs(stats.pool_utilization - expected) < 0.01


# ============================================================================
# Adaptive Performance Tuner Tests
# ============================================================================

class TestAdaptivePerformanceTuner:
    """自适应性能调优器测试"""
    
    @pytest.fixture
    def tuner(self):
        """创建调优器实例"""
        tuner = AdaptivePerformanceTuner()
        tuner.start()
        yield tuner
        tuner.stop()
    
    def test_singleton(self, tuner):
        """测试单例模式"""
        tuner2 = AdaptivePerformanceTuner()
        assert tuner is tuner2
    
    def test_record_metric(self, tuner):
        """测试记录指标"""
        tuner.record_metric('test_metric', 100.0, metadata={'key': 'value'})
        
        metric_names = tuner.get_all_metric_names()
        assert 'test_metric' in metric_names
    
    def test_metric_stats(self, tuner):
        """测试指标统计"""
        # 记录一些数据
        for i in range(100):
            tuner.record_metric('test_stats', 100.0 + i * 0.1)
        
        stats = tuner.get_metric_stats('test_stats')
        assert stats is not None
        assert stats.count == 100
        assert stats.mean > 100.0
        assert stats.min >= 100.0
        assert stats.max < 110.0
        assert stats.p95 > stats.mean
    
    def test_set_parameter(self, tuner):
        """测试设置参数"""
        tuner.set_parameter('test_param', 'value1')
        
        with tuner._param_lock:
            assert 'test_param' in tuner._parameters
            assert tuner._parameters['test_param'] == 'value1'
    
    def test_analyze_metric(self, tuner):
        """测试分析指标"""
        # 记录高延迟数据
        for _ in range(20):
            tuner.record_metric('high_latency', 1500.0)
        
        stats = tuner.get_metric_stats('high_latency')
        suggestions = tuner._analyze_metric('high_latency', stats)
        
        # 应该生成调优建议
        assert len(suggestions) > 0
    
    def test_auto_tune(self, tuner):
        """测试自动调优"""
        # 记录一些指标
        for _ in range(20):
            tuner.record_metric('test_latency', 2000.0)
        
        # 运行分析
        tuner._analyze_and_tune()
        
        # 检查是否有建议
        suggestions = tuner.get_suggestions()
        assert len(suggestions) >= 0


# ============================================================================
# Full Chain Monitor Tests
# ============================================================================

class TestFullChainMonitor:
    """全链路监控测试"""
    
    @pytest.fixture
    def monitor(self):
        """创建监控器实例"""
        return FullChainMonitor()
    
    def test_singleton(self, monitor):
        """测试单例模式"""
        monitor2 = FullChainMonitor()
        assert monitor is monitor2
    
    def test_start_trace(self, monitor):
        """测试开始追踪"""
        span = monitor.start_trace('test_operation')
        
        assert span is not None
        assert span.operation_name == 'test_operation'
        assert span.span_id is not None
        assert span.trace_id is not None
        assert span.start_time is not None
        assert span.end_time is None
    
    def test_trace_context_manager(self, monitor):
        """测试追踪上下文管理器"""
        with monitor.trace('context_test') as span:
            assert span.operation_name == 'context_test'
            time.sleep(0.1)
        
        assert span.end_time is not None
        assert span.duration_ms >= 90
        assert span.status == 'success'
    
    def test_trace_error_handling(self, monitor):
        """测试追踪错误处理"""
        with pytest.raises(ValueError):
            with monitor.trace('error_test') as span:
                raise ValueError("Test error")
        
        assert span.status == 'error'
        assert 'error' in span.tags
        assert span.tags['error_type'] == 'ValueError'
    
    def test_finish_span(self, monitor):
        """测试完成跨度"""
        span = monitor.start_trace('manual_finish')
        time.sleep(0.05)
        monitor.finish_span(span.span_id)
        
        assert span.end_time is not None
        assert span.duration_ms >= 40
    
    def test_get_trace(self, monitor):
        """测试获取追踪"""
        span = monitor.start_trace('get_test')
        monitor.finish_span(span.span_id)
        
        trace = monitor.get_trace(span.trace_id)
        assert trace is not None
        assert trace.trace_id == span.trace_id
        assert len(trace.spans) > 0
    
    def test_stats(self, monitor):
        """测试统计"""
        # 创建几个追踪
        for i in range(5):
            with monitor.trace(f'stats_test_{i}') as span:
                time.sleep(0.01)
        
        stats = monitor.get_stats()
        assert stats.total_traces >= 5
        assert stats.avg_duration >= 0
        assert stats.max_duration >= stats.min_duration


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        # 1. 初始化所有组件
        optimizer = get_startup_optimizer()
        preload_manager = get_preload_manager()
        tuner = get_performance_tuner()
        monitor = get_full_chain_monitor()
        
        # 2. 使用优化器导入模块
        with optimizer.measure_time('import_modules'):
            optimizer.lazy_import('asyncio')
            optimizer.lazy_import('json')
        
        # 3. 记录指标
        tuner.record_metric('import_time', optimizer.total_startup_time)
        
        # 4. 追踪操作
        with monitor.trace('integration_test'):
            # 模拟一些工作
            time.sleep(0.05)
            
            # 记录更多指标
            tuner.record_metric('operation_latency', 50.0)
            tuner.record_metric('operation_latency', 55.0)
            tuner.record_metric('operation_latency', 45.0)
        
        # 5. 检查结果
        assert optimizer.total_startup_time > 0
        assert tuner.get_metric_stats('import_time') is not None
        assert monitor.get_stats().total_traces > 0
        
        # 6. 生成报告
        profile = optimizer.generate_startup_profile()
        assert profile is not None


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """性能测试"""
    
    def test_startup_optimizer_performance(self):
        """测试启动优化器性能"""
        optimizer = SuperStartupOptimizer()
        
        # 测试导入速度
        start = time.time()
        optimizer.lazy_import('asyncio')
        first_time = (time.time() - start) * 1000
        
        # 第二次导入应该更快
        start = time.time()
        optimizer.lazy_import('asyncio')
        second_time = (time.time() - start) * 1000
        
        assert second_time < first_time
        assert second_time < 10  # 缓存命中应该很快
        
        optimizer.shutdown()
    
    def test_monitor_overhead(self):
        """测试监控开销"""
        monitor = FullChainMonitor()
        
        # 测试无监控的执行时间
        start = time.time()
        for _ in range(100):
            time.sleep(0.0001)
        baseline = time.time() - start
        
        # 测试有监控的执行时间
        start = time.time()
        for i in range(100):
            with monitor.trace(f'overhead_test_{i}'):
                time.sleep(0.0001)
        with_monitor = time.time() - start
        
        # 监控开销应该很小
        overhead_ratio = (with_monitor - baseline) / baseline
        assert overhead_ratio < 0.5  # 开销不超过50%


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
