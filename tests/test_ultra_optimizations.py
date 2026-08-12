"""
Ultra Optimizations Test Suite
超优化功能测试套件

测试所有超优化模块:
1. ChromaDB启动优化
2. 记忆检索优化
3. VTS嘴型同步优化
4. 视觉分析缓存优化
5. 性能监控Dashboard
"""

import pytest
import asyncio
import time
import numpy as np
from pathlib import Path
from typing import Dict, Any

# 导入优化模块
from src.memory_core.memory_loader_optimized import MemoryLoadOptimizer, get_memory_optimizer
from src.memory_core.retrieval_optimizer import (
    RetrievalOptimizer, 
    SmartCache, 
    BatchRetrievalOptimizer,
    RetrievalStrategy
)
from src.vts_client_ultra import (
    VTSClientUltra, 
    VTSMouthSyncOptimizer, 
    VTSUpdate, 
    VTSBatchUpdateQueue
)
from src.vision_cache_ultra import (
    VisionCacheUltra,
    ImageHasher,
    MultiLevelCache,
    TemplatePrecompiler,
    get_vision_cache_ultra
)
from src.performance_dashboard import (
    PerformanceDashboard,
    PerformanceMonitor,
    get_performance_dashboard,
    monitor_performance,
    PerformanceLevel
)


class TestMemoryLoadOptimizer:
    """测试内存加载优化器"""
    
    @pytest.fixture
    def optimizer(self, tmp_path):
        """创建优化器实例"""
        return MemoryLoadOptimizer(str(tmp_path / "memory_db"), "test_collection")
    
    def test_cache_operations(self, optimizer):
        """测试缓存操作"""
        # 保存到缓存
        optimizer.save_to_cache("test_key", {"data": "test_value"})
        
        # 从缓存加载
        loaded = optimizer.load_from_cache("test_key")
        assert loaded is not None
        assert loaded["data"] == "test_value"
        
        # 缓存未命中
        missed = optimizer.load_from_cache("non_existent_key")
        assert missed is None
    
    def test_stats_tracking(self, optimizer):
        """测试统计追踪"""
        # 保存和加载数据
        optimizer.save_to_cache("key1", {"value": 1})
        optimizer.load_from_cache("key1")
        optimizer.load_from_cache("non_existent")
        
        stats = optimizer.get_stats()
        assert stats['cache_hits'] >= 1
        assert stats['cache_misses'] >= 1


class TestSmartCache:
    """测试智能缓存"""
    
    @pytest.fixture
    def cache(self):
        """创建缓存实例"""
        return SmartCache(max_size=100, ttl_seconds=300)
    
    @pytest.fixture
    def mock_result(self):
        """创建模拟结果"""
        from src.memory_core.retrieval_optimizer import QueryResult
        return QueryResult(
            memories=[],
            query_time_ms=50.0,
            cache_hit=False,
            strategy_used=RetrievalStrategy.SEMANTIC
        )
    
    def test_cache_get_set(self, cache, mock_result):
        """测试缓存设置和获取"""
        # 设置缓存
        cache.set("test query", 5, mock_result)
        
        # 获取缓存
        result = cache.get("test query", 5)
        assert result is not None
        assert result.cache_hit is True
    
    def test_cache_miss(self, cache):
        """测试缓存未命中"""
        result = cache.get("non-existent query", 5)
        assert result is None
    
    def test_cache_stats(self, cache, mock_result):
        """测试缓存统计"""
        cache.set("query1", 5, mock_result)
        cache.set("query2", 5, mock_result)
        
        cache.get("query1", 5)
        cache.get("non-existent", 5)
        
        stats = cache.get_stats()
        assert stats['hit_rate'] > 0
        assert stats['misses'] >= 1


class TestBatchRetrievalOptimizer:
    """测试批量检索优化器"""
    
    @pytest.fixture
    def mock_model(self):
        """创建模拟模型"""
        class MockModel:
            def encode(self, texts, **kwargs):
                return np.random.rand(len(texts), 384)
        return MockModel()
    
    @pytest.fixture
    def optimizer(self, mock_model):
        """创建批量检索优化器"""
        return BatchRetrievalOptimizer(mock_model, max_batch_size=32)
    
    def test_batch_encode(self, optimizer, mock_model):
        """测试批量编码"""
        queries = ["query1", "query2", "query3"]
        
        embeddings = optimizer.batch_encode(queries)
        
        assert embeddings.shape == (3, 384)
    
    def test_empty_batch(self, optimizer):
        """测试空批量"""
        embeddings = optimizer.batch_encode([])
        assert len(embeddings) == 0


class TestVTSMouthSyncOptimizer:
    """测试VTS嘴型同步优化器"""
    
    @pytest.fixture
    def optimizer(self):
        """创建嘴型同步优化器"""
        return VTSMouthSyncOptimizer(sample_rate=16000, frame_size=256)
    
    def test_compute_mouth_open(self, optimizer):
        """测试嘴巴张开程度计算"""
        # 静音帧
        silent_frame = np.random.randn(256) * 0.001
        mouth_open = optimizer.compute_mouth_open(silent_frame)
        assert 0.0 <= mouth_open <= 1.0
        
        # 响亮音频帧
        loud_frame = np.random.randn(256) * 0.5
        mouth_open = optimizer.compute_mouth_open(loud_frame)
        assert 0.0 <= mouth_open <= 1.0
    
    def test_get_mouth_parameters(self, optimizer):
        """测试获取嘴型参数"""
        audio_frame = np.random.randn(256) * 0.1
        
        params = optimizer.get_mouth_parameters(audio_frame)
        
        assert "MouthOpen" in params
        assert "MouthOpenSmile" in params
        assert "MouthClose" in params
        assert all(0.0 <= v <= 1.0 for v in params.values())


class TestVTSUpdateQueue:
    """测试VTS更新队列"""
    
    @pytest.fixture
    def queue(self):
        """创建更新队列"""
        return VTSBatchUpdateQueue(batch_window_ms=33, max_queue_size=10)
    
    def test_add_update(self, queue):
        """测试添加更新"""
        update = VTSUpdate(
            parameters={"MouthOpen": 0.5},
            timestamp=time.time(),
            priority=0
        )
        
        success = queue.add(update)
        assert success is True
    
    def test_get_batch(self, queue):
        """测试获取批量更新"""
        update1 = VTSUpdate(
            parameters={"MouthOpen": 0.5},
            timestamp=time.time(),
            priority=0
        )
        update2 = VTSUpdate(
            parameters={"MouthAngry": 0.3},
            timestamp=time.time(),
            priority=1
        )
        
        queue.add(update1)
        queue.add(update2)
        
        batch = queue.get_batch()
        assert batch is not None
        assert "MouthOpen" in batch.parameters
    
    def test_update_merging(self, queue):
        """测试更新合并"""
        update1 = VTSUpdate(
            parameters={"MouthOpen": 0.5, "MouthAngry": 0.2},
            timestamp=time.time(),
            priority=0,
            merge_strategy="replace"
        )
        update2 = VTSUpdate(
            parameters={"MouthAngry": 0.8},
            timestamp=time.time(),
            priority=1,
            merge_strategy="replace"
        )
        
        merged = update1.merge_with(update2)
        assert merged.parameters["MouthOpen"] == 0.5
        assert merged.parameters["MouthAngry"] == 0.8


class TestImageHasher:
    """测试图像哈希器"""
    
    def test_perceptual_hash(self):
        """测试感知哈希"""
        # 创建测试图像
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        hash1 = ImageHasher.perceptual_hash(image)
        hash2 = ImageHasher.perceptual_hash(image)
        
        # 相同图像应有相同哈希
        assert hash1 == hash2
    
    def test_hamming_distance(self):
        """测试汉明距离"""
        hash1 = "0" * 64
        hash2 = "1" * 64
        
        distance = ImageHasher.hamming_distance(hash1, hash2)
        assert distance == 64
    
    def test_is_similar(self):
        """测试相似性判断"""
        hash1 = "0" * 64
        hash2 = "0" * 60 + "11111"
        
        # 相似（汉明距离为5）
        assert ImageHasher.is_similar(hash1, hash2, threshold=5) is True
        
        # 不相似
        assert ImageHasher.is_similar(hash1, hash2, threshold=4) is False


class TestMultiLevelCache:
    """测试多级缓存"""
    
    @pytest.fixture
    def cache(self, tmp_path):
        """创建多级缓存"""
        return MultiLevelCache(
            hot_size=10,
            warm_size=50,
            cold_dir=str(tmp_path / "cold_cache")
        )
    
    @pytest.fixture
    def mock_result(self):
        """创建模拟结果"""
        from src.vision_cache_ultra import VisionAnalysisResult, CacheLevel
        return VisionAnalysisResult(
            image_hash="test_hash",
            result={"test": "data"},
            analysis_time_ms=100.0,
            cache_level=CacheLevel.HOT,
            timestamp=time.time()
        )
    
    def test_hot_cache(self, cache, mock_result):
        """测试热缓存"""
        cache.set("test_key", mock_result)
        
        result = cache.get("test_key")
        assert result is not None
        assert result.image_hash == "test_hash"
    
    def test_cache_promotion(self, cache, mock_result):
        """测试缓存提升"""
        # 填满热缓存
        for i in range(12):
            mock_result.image_hash = f"hash_{i}"
            cache.set(f"key_{i}", mock_result)
        
        # 应该有数据被提升到温缓存
        stats = cache.get_stats()
        assert stats['promotions'] >= 1
    
    def test_cache_stats(self, cache, mock_result):
        """测试缓存统计"""
        cache.set("key1", mock_result)
        cache.get("key1")
        cache.get("non_existent")
        
        stats = cache.get_stats()
        assert stats['hot_hits'] >= 1
        assert stats['misses'] >= 1


class TestVisionCacheUltra:
    """测试视觉缓存"""
    
    @pytest.fixture
    def vision_cache(self, tmp_path):
        """创建视觉缓存"""
        return VisionCacheUltra(cache_dir=str(tmp_path / "vision_cache"))
    
    def test_analyze_with_cache(self, vision_cache):
        """测试带缓存的图像分析"""
        # 创建测试图像
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # 第一次分析（未命中缓存）
        result1 = vision_cache.analyze(image, "test_type")
        assert result1 is not None
        
        # 第二次分析（命中缓存）
        result2 = vision_cache.analyze(image, "test_type")
        assert result2 is not None
        # 应该是缓存命中
        # 注意：实际缓存命中需要ImageHasher计算相同哈希
    
    def test_stats_tracking(self, vision_cache):
        """测试统计追踪"""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        vision_cache.analyze(image)
        
        stats = vision_cache.get_stats()
        assert 'cache' in stats
        assert 'templates' in stats


class TestPerformanceMonitor:
    """测试性能监控器"""
    
    @pytest.fixture
    def monitor(self):
        """创建性能监控器"""
        return PerformanceMonitor("test_module", max_history=100)
    
    def test_record_metric(self, monitor):
        """测试记录指标"""
        monitor.record_metric("test_metric", 50.0, "ms")
        
        metrics = monitor.get_current_metrics()
        assert "test_metric" in metrics
        assert metrics["test_metric"]["value"] == 50.0
    
    def test_threshold_evaluation(self, monitor):
        """测试阈值评估"""
        monitor.configure_threshold("test_metric",
                                   excellent=20, good=40, fair=60, poor=100)
        
        # 优秀
        monitor.record_metric("test_metric", 15.0, "ms")
        metrics = monitor.get_current_metrics()
        assert metrics["test_metric"]["level"] == "excellent"
        
        # 差
        monitor.record_metric("test_metric", 80.0, "ms")
        metrics = monitor.get_current_metrics()
        assert metrics["test_metric"]["level"] == "poor"
    
    def test_statistics(self, monitor):
        """测试统计"""
        for i in range(100):
            monitor.record_metric("test_metric", i, "ms")
        
        stats = monitor.get_statistics("test_metric")
        
        assert stats['count'] == 100
        assert stats['min'] == 0
        assert stats['max'] == 99
        assert stats['avg'] == 49.5
    
    def test_trend_analysis(self, monitor):
        """测试趋势分析"""
        # 改善趋势（值变小）
        for i in range(20, 0, -1):
            monitor.record_metric("test_metric", i, "ms")
        
        trend = monitor.get_trend("test_metric")
        assert trend == "improving"


class TestPerformanceDashboard:
    """测试性能监控面板"""
    
    @pytest.fixture
    def dashboard(self):
        """创建性能监控面板"""
        return PerformanceDashboard(update_interval=0.1)
    
    def test_register_monitor(self, dashboard):
        """测试注册监控器"""
        dashboard.register_monitor("new_module")
        
        dashboard_data = dashboard.get_dashboard_data()
        assert "new_module" in dashboard_data['modules']
    
    def test_record_metric(self, dashboard):
        """测试记录指标"""
        dashboard.record_metric("test_module", "test_metric", 50.0, "ms")
        
        dashboard_data = dashboard.get_dashboard_data()
        assert "test_module" in dashboard_data['modules']
    
    def test_generate_text_report(self, dashboard):
        """测试生成文本报告"""
        dashboard.record_metric("test_module", "test_metric", 50.0, "ms")
        
        report = dashboard.generate_report("text")
        
        assert "性能监控报告" in report
        assert "test_module" in report
    
    def test_generate_json_report(self, dashboard):
        """测试生成JSON报告"""
        dashboard.record_metric("test_module", "test_metric", 50.0, "ms")
        
        report = dashboard.generate_report("json")
        
        import json
        data = json.loads(report)
        assert 'timestamp' in data
        assert 'modules' in data


class TestMonitorDecorator:
    """测试监控装饰器"""
    
    def test_decorator(self):
        """测试装饰器"""
        @monitor_performance("test_module", "test_function")
        def test_function():
            time.sleep(0.01)
            return "success"
        
        result = test_function()
        assert result == "success"
        
        # 检查指标是否被记录
        dashboard = get_performance_dashboard()
        # 注意：可能需要等待一下以确保指标被记录


# 集成测试
class TestIntegration:
    """集成测试"""
    
    def test_memory_retrieval_optimization(self, tmp_path):
        """测试记忆检索优化集成"""
        # 创建优化器
        optimizer = MemoryLoadOptimizer(str(tmp_path / "memory_db"), "test_collection")
        
        # 初始化ChromaDB
        client, collection = optimizer.initialize_chromadb_fast()
        
        assert client is not None
        assert collection is not None
        
        # 关闭
        optimizer.shutdown()
    
    def test_vision_analysis_optimization(self, tmp_path):
        """测试视觉分析优化集成"""
        # 创建视觉缓存
        cache = VisionCacheUltra(cache_dir=str(tmp_path / "vision_cache"))
        
        # 分析图像
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = cache.analyze(image)
        
        assert result is not None
        assert result.analysis_time_ms >= 0
        
        # 获取统计
        stats = cache.get_stats()
        assert 'cache' in stats


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
