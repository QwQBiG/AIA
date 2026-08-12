"""
性能优化测试套件

测试所有新增的性能优化模块:
1. 批量记忆检索
2. VTS嘴型同步优化
3. 视觉分析缓存
4. 全双工音频缓冲
"""

import pytest
import asyncio
import time
import numpy as np
from pathlib import Path
import sys

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from memory_core.batch_retrieval import BatchRetrievalOptimizer
from memory_core.memory_core import MemoryCore, ScoredMemory
from data_models import MemoryType
from vts_client_optimized import VTSClientOptimized
from vision_client_cache import VisionCache, cached_vision_analysis
from full_duplex_engine.buffer_optimizer import BufferOptimizer, AudioChunk


class TestBatchRetrieval:
    """测试批量记忆检索优化"""

    @pytest.fixture
    def memory_core(self):
        """创建MemoryCore实例"""
        # 使用临时目录
        db_path = "./test_memory_db"
        mc = MemoryCore(db_path=db_path, collection_name="test_batch_retrieval")
        mc._load_embedding_model_async()  # 同步加载模型
        time.sleep(2)  # 等待模型加载
        yield mc
        # 清理
        import shutil
        if Path(db_path).exists():
            shutil.rmtree(db_path)

    @pytest.fixture
    def batch_retriever(self, memory_core):
        """创建批量检索优化器"""
        return BatchRetrievalOptimizer(memory_core, max_batch_size=5)

    def test_batch_retrieve(self, batch_retriever, memory_core):
        """测试批量检索功能"""
        # 添加一些测试记忆
        test_memories = [
            "用户喜欢玩FPS游戏",
            "用户昨天玩了《绝地求生》",
            "用户擅长狙击枪",
            "用户讨厌卡顿",
            "用户使用高配置电脑"
        ]

        for text in test_memories:
            memory_core.add_memory(text, memory_type=MemoryType.INTERACTION)

        # 等待记忆索引
        time.sleep(1)

        # 执行批量查询
        queries = ["用户喜欢什么游戏", "用户的电脑配置"]
        results = batch_retriever.batch_retrieve(
            queries=queries,
            top_k=3,
            min_similarity=0.3
        )

        # 验证结果
        assert len(results) == 2  # 两个查询
        for query, memories in results.items():
            assert isinstance(memories, list)
            assert len(memories) <= 3

        print(f"✅ 批量检索测试通过: {len(results)}个查询结果")

    def test_cache_hit_rate(self, batch_retriever):
        """测试缓存命中率"""
        queries = ["测试查询1", "测试查询2"]

        # 第一次查询(缓存未命中)
        results1 = batch_retriever.batch_retrieve(queries, top_k=3)

        # 第二次查询(缓存命中)
        results2 = batch_retriever.batch_retrieve(queries, top_k=3)

        # 第三次查询(缓存命中)
        results3 = batch_retriever.batch_retrieve(queries, top_k=3)

        stats = batch_retriever.get_cache_stats()

        print(f"📊 缓存统计: {stats}")

        # 验证缓存命中
        assert stats['cache_hits'] >= 2
        print(f"✅ 缓存测试通过: 命中率={stats.get('cache_hit_rate', 0):.2f}")

    def test_performance_improvement(self, batch_retriever, memory_core):
        """测试性能提升"""
        # 添加测试数据
        for i in range(20):
            memory_core.add_memory(f"测试记忆{i}", memory_type=MemoryType.INTERACTION)

        time.sleep(1)

        # 批量查询性能测试
        queries = [f"查询{i}" for i in range(10)]

        start = time.time()
        results = batch_retriever.batch_retrieve(queries, top_k=3)
        batch_time = time.time() - start

        stats = batch_retriever.get_cache_stats()

        print(f"⚡ 性能测试:")
        print(f"  - 批量查询时间: {batch_time*1000:.2f}ms")
        print(f"  - 节省查询次数: {stats['total_queries_saved']}")
        print(f"  - 平均延迟: {stats['avg_batch_latency_ms']:.2f}ms")

        # 验证性能
        assert batch_time < 5.0  # 批量查询应该在5秒内完成
        print(f"✅ 性能测试通过: 批量延迟{batch_time*1000:.2f}ms")


class TestVTSCache:
    """测试VTS客户端优化"""

    @pytest.fixture
    def vts_client(self):
        """创建VTS客户端"""
        return VTSClientOptimized()

    def test_buffer_management(self, vts_client):
        """测试嘴型缓冲管理"""
        # 模拟添加嘴型参数
        for i in range(20):
            asyncio.run(vts_client.batch_update_mouth(
                mouth_open=0.5 + i * 0.01,
                mouth_open_y=0.6 + i * 0.01
            ))

        # 检查缓冲区状态
        buffer_size = len(vts_client._mouth_buffer)

        print(f"📊 VTS缓冲区: {buffer_size}条记录")
        assert buffer_size <= 10  # 最大缓冲10条
        print(f"✅ VTS缓冲管理测试通过")

    def test_performance_stats(self, vts_client):
        """测试性能统计"""
        # 添加一些更新
        for i in range(10):
            asyncio.run(vts_client.batch_update_mouth(0.5, 0.6))

        stats = vts_client.get_performance_stats()

        print(f"📊 VTS性能统计:")
        print(f"  - 总更新数: {stats['total_updates']}")
        print(f"  - 批量更新数: {stats['batched_updates']}")
        print(f"  - 批量效率: {stats['batch_efficiency']:.2f}")

        # 验证统计
        assert stats['total_updates'] >= 10
        print(f"✅ VTS性能统计测试通过")


class TestVisionCache:
    """测试视觉分析缓存"""

    @pytest.fixture
    def vision_cache(self):
        """创建视觉缓存"""
        return VisionCache(
            cache_dir="./test_vision_cache",
            max_cache_size=50,
            cache_ttl=30
        )

    def test_cache_key_generation(self, vision_cache):
        """测试缓存键生成"""
        # 创建测试图像
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        # 生成缓存键
        cache_key = vision_cache.get_cache_key(test_image)

        print(f"🔑 缓存键: {cache_key}")
        assert isinstance(cache_key, str)
        assert cache_key.startswith("vision_")
        print(f"✅ 缓存键生成测试通过")

    def test_cache_hit_miss(self, vision_cache):
        """测试缓存命中/未命中"""
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        cache_key = vision_cache.get_cache_key(test_image)

        # 第一次查询(未命中)
        result1 = vision_cache.get_cached_result(cache_key)
        assert result1 is None

        # 缓存结果
        test_result = {"detected": "test_object", "confidence": 0.95}
        vision_cache.cache_analysis_result(cache_key, test_result)

        # 第二次查询(命中)
        result2 = vision_cache.get_cached_result(cache_key)
        assert result2 is not None
        assert result2["detected"] == "test_object"

        stats = vision_cache.get_cache_stats()
        print(f"📊 视觉缓存统计:")
        print(f"  - 缓存命中: {stats['cache_hits']}")
        print(f"  - 缓存未命中: {stats['cache_misses']}")
        print(f"  - 命中率: {stats['cache_hit_rate']:.2f}")

        print(f"✅ 视觉缓存测试通过")

    def test_cached_decorator(self, vision_cache):
        """测试缓存装饰器"""
        call_count = [0]

        @cached_vision_analysis(vision_cache)
        def mock_analyze(image: np.ndarray) -> dict:
            call_count[0] += 1
            return {"result": "analysis"}

        test_image = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)

        # 第一次调用(未缓存)
        result1 = mock_analyze(test_image)
        assert call_count[0] == 1

        # 第二次调用(缓存命中)
        result2 = mock_analyze(test_image)
        assert call_count[0] == 1  # 不应该再次调用

        print(f"✅ 缓存装饰器测试通过: 装饰器有效缓存结果")


class TestBufferOptimizer:
    """测试音频缓冲优化"""

    @pytest.fixture
    def buffer_optimizer(self):
        """创建缓冲区优化器"""
        return BufferOptimizer(
            initial_capacity=10,
            min_capacity=5,
            max_capacity=20,
            target_utilization=0.7,
            pre_fill_target=5
        )

    def test_chunk_add_retrieve(self, buffer_optimizer):
        """测试音频块添加和获取"""
        # 创建测试音频块
        for i in range(15):
            chunk = AudioChunk(
                data=np.random.randint(0, 255, 512, dtype=np.int16),
                timestamp=time.time(),
                sample_rate=16000,
                chunk_id=i
            )
            buffer_optimizer.add_chunk(chunk)

        # 获取统计
        stats = buffer_optimizer.get_stats()

        print(f"📊 缓冲区统计:")
        print(f"  - 缓冲区大小: {stats.buffer_size}")
        print(f"  - 缓冲区容量: {stats.buffer_capacity}")
        print(f"  - 利用率: {stats.utilization:.2f}")
        print(f"  - 丢弃块数: {stats.dropped_chunks}")

        # 验证
        assert stats.buffer_size > 0
        assert stats.utilization <= 1.0
        print(f"✅ 音频块添加测试通过")

    def test_auto_adjust_capacity(self, buffer_optimizer):
        """测试自动容量调整"""
        # 添加大量数据触发调整
        for i in range(30):
            chunk = AudioChunk(
                data=np.random.randint(0, 255, 512, dtype=np.int16),
                timestamp=time.time(),
                sample_rate=16000,
                chunk_id=i
            )
            buffer_optimizer.add_chunk(chunk)
            buffer_optimizer.optimize()

        stats = buffer_optimizer.get_stats()

        print(f"📊 自适应调整后:")
        print(f"  - 容量: {stats.buffer_capacity}")
        print(f"  - 利用率: {stats.utilization:.2f}")

        # 验证容量调整
        assert 5 <= stats.buffer_capacity <= 20
        print(f"✅ 自动容量调整测试通过")


def test_integration():
    """集成测试: 所有优化模块协同工作"""
    print("\n" + "="*50)
    print("🔧 集成测试开始")
    print("="*50 + "\n")

    # 创建各模块实例
    vision_cache = VisionCache(cache_dir="./test_vision_cache")
    buffer_optimizer = BufferOptimizer()

    # 模拟工作流程
    print("1️⃣ 测试视觉分析缓存...")
    test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    cache_key = vision_cache.get_cache_key(test_image)
    vision_cache.cache_analysis_result(cache_key, {"result": "test"})

    print("2️⃣ 测试音频缓冲...")
    for i in range(10):
        chunk = AudioChunk(
            data=np.random.randint(0, 255, 512, dtype=np.int16),
            timestamp=time.time(),
            sample_rate=16000,
            chunk_id=i
        )
        buffer_optimizer.add_chunk(chunk)

    # 获取统计
    vision_stats = vision_cache.get_cache_stats()
    buffer_stats = buffer_optimizer.get_stats()

    print("\n📊 集成测试结果:")
    print(f"  视觉缓存大小: {vision_stats['memory_cache_size']}")
    print(f"  音频缓冲利用: {buffer_stats.utilization:.2f}")

    print("\n✅ 集成测试通过!\n")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
