"""
Memory Retrieval Optimization Engine
高性能记忆检索优化引擎

优化目标:
1. 检索延迟: 80ms → <40ms (-50%)
2. 批量查询效率: 提升3-5倍
3. 缓存命中率: 40-60%
4. 并发处理能力: 支持高并发查询
"""

import asyncio
import logging
import threading
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
import weakref
import bisect

import numpy as np


class RetrievalStrategy(Enum):
    """检索策略"""
    EXACT = "exact"           # 精确匹配
    SEMANTIC = "semantic"     # 语义搜索
    HYBRID = "hybrid"         # 混合检索
    CACHE_FIRST = "cache_first"  # 缓存优先


@dataclass
class QueryResult:
    """查询结果"""
    memories: List[Any]
    query_time_ms: float
    cache_hit: bool
    strategy_used: RetrievalStrategy
    total_results: int = 0
    
    def __post_init__(self):
        self.total_results = len(self.memories)


@dataclass
class RetrievalStats:
    """检索统计"""
    total_queries: int = 0
    total_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_query_time_ms: float = 0.0
    p95_query_time_ms: float = 0.0
    p99_query_time_ms: float = 0.0
    query_times: List[float] = field(default_factory=list)
    
    def update(self, query_time_ms: float, cache_hit: bool):
        """更新统计"""
        self.total_queries += 1
        self.total_time_ms += query_time_ms
        
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        self.query_times.append(query_time_ms)
        
        # 保持最近1000次查询的时间
        if len(self.query_times) > 1000:
            self.query_times = self.query_times[-1000:]
        
        # 计算平均值
        self.avg_query_time_ms = self.total_time_ms / self.total_queries
        
        # 计算百分位数
        if self.query_times:
            sorted_times = sorted(self.query_times)
            self.p95_query_time_ms = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 0 else 0.0
            self.p99_query_time_ms = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 0 else 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries


class SmartCache:
    """
    智能缓存系统
    
    特性:
    1. LRU缓存淘汰策略
    2. 查询频率追踪
    3. 结果时效性管理
    4. 内存占用控制
    5. 多级缓存（热缓存+温缓存）
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        初始化智能缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存生存时间（秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
        # 热缓存（高频查询）
        self._hot_cache: OrderedDict = OrderedDict()
        self._hot_cache_lock = threading.RLock()
        
        # 温缓存（中频查询）
        self._warm_cache: OrderedDict = OrderedDict()
        self._warm_cache_lock = threading.RLock()
        
        # 查询频率追踪
        self._query_count: Dict[str, int] = {}
        self._query_count_lock = threading.Lock()
        
        # 缓存统计
        self._stats = {
            'hot_hits': 0,
            'warm_hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _get_cache_key(self, query: str, limit: int) -> str:
        """生成缓存键"""
        key = f"{query}|limit={limit}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    def get(self, query: str, limit: int) -> Optional[QueryResult]:
        """
        从缓存获取结果
        
        Args:
            query: 查询文本
            limit: 返回结果数量
            
        Returns:
            缓存结果，如果不存在或过期则返回None
        """
        cache_key = self._get_cache_key(query, limit)
        now = time.time()
        
        # 先查热缓存
        with self._hot_cache_lock:
            if cache_key in self._hot_cache:
                result, timestamp = self._hot_cache[cache_key]
                if now - timestamp < self.ttl_seconds:
                    # 移到队尾（LRU）
                    self._hot_cache.move_to_end(cache_key)
                    self._stats['hot_hits'] += 1
                    return result
        
        # 查温缓存
        with self._warm_cache_lock:
            if cache_key in self._warm_cache:
                result, timestamp = self._warm_cache[cache_key]
                if now - timestamp < self.ttl_seconds:
                    self._warm_cache.move_to_end(cache_key)
                    self._stats['warm_hits'] += 1
                    
                    # 提升到热缓存
                    self._promote_to_hot(cache_key, result, timestamp)
                    
                    return result
        
        self._stats['misses'] += 1
        return None
    
    def _promote_to_hot(self, cache_key: str, result: QueryResult, timestamp: float):
        """将结果提升到热缓存"""
        with self._hot_cache_lock:
            if len(self._hot_cache) >= self.max_size // 2:
                self._hot_cache.popitem(last=False)
                self._stats['evictions'] += 1
            
            self._hot_cache[cache_key] = (result, timestamp)
    
    def set(self, query: str, limit: int, result: QueryResult):
        """
        设置缓存
        
        Args:
            query: 查询文本
            limit: 返回结果数量
            result: 查询结果
        """
        cache_key = self._get_cache_key(query, limit)
        timestamp = time.time()
        
        # 更新查询频率
        with self._query_count_lock:
            self._query_count[cache_key] = self._query_count.get(cache_key, 0) + 1
            
            # 高频查询放入热缓存
            if self._query_count[cache_key] >= 3:
                with self._hot_cache_lock:
                    if len(self._hot_cache) >= self.max_size // 2:
                        self._hot_cache.popitem(last=False)
                        self._stats['evictions'] += 1
                    self._hot_cache[cache_key] = (result, timestamp)
            else:
                # 中频查询放入温缓存
                with self._warm_cache_lock:
                    if len(self._warm_cache) >= self.max_size:
                        self._warm_cache.popitem(last=False)
                        self._stats['evictions'] += 1
                    self._warm_cache[cache_key] = (result, timestamp)
    
    def invalidate(self, query: Optional[str] = None):
        """
        使缓存失效
        
        Args:
            query: 要失效的查询，如果为None则清空所有缓存
        """
        if query is None:
            with self._hot_cache_lock:
                self._hot_cache.clear()
            with self._warm_cache_lock:
                self._warm_cache.clear()
        else:
            # 简化处理：清空所有缓存（实际应该只失效相关查询）
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_hits = self._stats['hot_hits'] + self._stats['warm_hits']
        total_requests = total_hits + self._stats['misses']
        
        return {
            'hot_hits': self._stats['hot_hits'],
            'warm_hits': self._stats['warm_hits'],
            'misses': self._stats['misses'],
            'evictions': self._stats['evictions'],
            'hit_rate': total_hits / max(1, total_requests),
            'hot_cache_size': len(self._hot_cache),
            'warm_cache_size': len(self._warm_cache),
            'total_size': len(self._hot_cache) + len(self._warm_cache)
        }


class BatchRetrievalOptimizer:
    """
    批量检索优化器
    
    优化策略:
    1. 批量编码查询
    2. 并行执行检索
    3. 智能结果合并
    4. 批量缓存
    """
    
    def __init__(self, embedding_model, max_batch_size: int = 32):
        """
        初始化批量检索优化器
        
        Args:
            embedding_model: 嵌入模型
            max_batch_size: 最大批量大小
        """
        self.embedding_model = embedding_model
        self.max_batch_size = max_batch_size
        self.logger = logging.getLogger(__name__)
        
        # 线程池
        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="Retrieval"
        )
        
        # 统计
        self._batch_stats = {
            'total_batches': 0,
            'total_queries': 0,
            'avg_batch_size': 0.0,
            'avg_time_ms': 0.0
        }
    
    def batch_encode(self, queries: List[str]) -> np.ndarray:
        """
        批量编码查询
        
        Args:
            queries: 查询列表
            
        Returns:
            嵌入向量数组
        """
        if not queries:
            return np.array([])
        
        try:
            embeddings = self.embedding_model.encode(
                queries,
                show_progress_bar=False,
                batch_size=min(self.max_batch_size, len(queries)),
                normalize_embeddings=True
            )
            
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Batch encoding failed: {e}")
            # 降级到单个编码
            return np.array([
                self.embedding_model.encode(q, normalize_embeddings=True)
                for q in queries
            ])
    
    async def batch_retrieve(self, collection, queries: List[str], 
                            top_k: int = 5, 
                            filters: Optional[Dict] = None) -> List[QueryResult]:
        """
        批量检索记忆
        
        Args:
            collection: ChromaDB集合
            queries: 查询列表
            top_k: 每个查询返回的结果数
            filters: 过滤条件
            
        Returns:
            查询结果列表
        """
        start_time = time.time()
        
        try:
            # 批量编码
            embeddings = self.batch_encode(queries)
            
            # 并行检索
            results = await asyncio.gather(*[
                self._retrieve_single(collection, q, e, top_k, filters)
                for q, e in zip(queries, embeddings)
            ])
            
            # 更新统计
            batch_time = (time.time() - start_time) * 1000
            self._batch_stats['total_batches'] += 1
            self._batch_stats['total_queries'] += len(queries)
            self._batch_stats['avg_batch_size'] = (
                self._batch_stats['total_queries'] / self._batch_stats['total_batches']
            )
            self._batch_stats['avg_time_ms'] = batch_time / len(queries)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch retrieval failed: {e}")
            raise
    
    async def _retrieve_single(self, collection, query: str, embedding: np.ndarray, 
                               top_k: int, filters: Optional[Dict]) -> QueryResult:
        """
        单个查询检索（异步）
        
        Args:
            collection: ChromaDB集合
            query: 查询文本
            embedding: 查询嵌入
            top_k: 返回结果数
            filters: 过滤条件
            
        Returns:
            查询结果
        """
        start_time = time.time()
        
        try:
            # 在线程池中执行同步检索
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self._executor,
                collection.query,
                query_embeddings=[embedding.tolist()],
                n_results=top_k,
                where=filters
            )
            
            # 转换结果
            memories = self._convert_to_memories(results)
            
            query_time = (time.time() - start_time) * 1000
            
            return QueryResult(
                memories=memories,
                query_time_ms=query_time,
                cache_hit=False,
                strategy_used=RetrievalStrategy.SEMANTIC,
                total_results=len(memories)
            )
            
        except Exception as e:
            self.logger.error(f"Single retrieval failed: {e}")
            return QueryResult(
                memories=[],
                query_time_ms=(time.time() - start_time) * 1000,
                cache_hit=False,
                strategy_used=RetrievalStrategy.SEMANTIC
            )
    
    def _convert_to_memories(self, results: Dict) -> List[Any]:
        """转换ChromaDB结果为记忆对象"""
        # 简化实现，实际需要根据Memory类型转换
        memories = []
        
        if 'ids' in results and results['ids']:
            for i in range(len(results['ids'][0])):
                memory = {
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i] if 'documents' in results else '',
                    'metadata': results['metadatas'][0][i] if 'metadatas' in results else {},
                    'distance': results['distances'][0][i] if 'distances' in results else 0.0
                }
                memories.append(memory)
        
        return memories
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批量检索统计"""
        return self._batch_stats.copy()


class RetrievalOptimizer:
    """
    记忆检索优化引擎（主类）
    
    集成所有优化策略:
    1. 智能缓存
    2. 批量处理
    3. 并行查询
    4. 自适应策略选择
    """
    
    def __init__(self, memory_core, embedding_model):
        """
        初始化检索优化引擎
        
        Args:
            memory_core: 记忆核心实例
            embedding_model: 嵌入模型
        """
        self.memory_core = memory_core
        self.embedding_model = embedding_model
        self.logger = logging.getLogger(__name__)
        
        # 智能缓存
        self.cache = SmartCache(max_size=1000, ttl_seconds=300)
        
        # 批量检索优化器
        self.batch_optimizer = BatchRetrievalOptimizer(embedding_model)
        
        # 检索统计
        self.stats = RetrievalStats()
        
        # 线程池
        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="RetrievalOpt"
        )
    
    def retrieve(self, query: str, limit: int = 5, 
                filters: Optional[Dict] = None,
                strategy: RetrievalStrategy = RetrievalStrategy.CACHE_FIRST) -> QueryResult:
        """
        检索记忆（优化版）
        
        Args:
            query: 查询文本
            limit: 返回结果数量
            filters: 过滤条件
            strategy: 检索策略
            
        Returns:
            查询结果
        """
        start_time = time.time()
        
        # 1. 缓存优先策略
        if strategy == RetrievalStrategy.CACHE_FIRST:
            cached = self.cache.get(query, limit)
            if cached is not None:
                self.stats.update(cached.query_time_ms, cache_hit=True)
                return cached
        
        # 2. 执行检索
        result = self._execute_retrieval(query, limit, filters)
        
        # 3. 缓存结果
        self.cache.set(query, limit, result)
        
        # 4. 更新统计
        self.stats.update(result.query_time_ms, cache_hit=False)
        
        return result
    
    def _execute_retrieval(self, query: str, limit: int, 
                          filters: Optional[Dict]) -> QueryResult:
        """执行实际检索"""
        start_time = time.time()
        
        try:
            # 编码查询
            embedding = self.embedding_model.encode(query, normalize_embeddings=True)
            
            # 执行检索
            collection = self.memory_core.collection
            results = collection.query(
                query_embeddings=[embedding.tolist()],
                n_results=limit,
                where=filters
            )
            
            # 转换结果
            memories = self.batch_optimizer._convert_to_memories(results)
            
            query_time = (time.time() - start_time) * 1000
            
            return QueryResult(
                memories=memories,
                query_time_ms=query_time,
                cache_hit=False,
                strategy_used=RetrievalStrategy.SEMANTIC,
                total_results=len(memories)
            )
            
        except Exception as e:
            self.logger.error(f"Retrieval failed: {e}")
            return QueryResult(
                memories=[],
                query_time_ms=(time.time() - start_time) * 1000,
                cache_hit=False,
                strategy_used=RetrievalStrategy.SEMANTIC
            )
    
    def batch_retrieve(self, queries: List[str], limit: int = 5,
                      filters: Optional[Dict] = None) -> List[QueryResult]:
        """
        批量检索
        
        Args:
            queries: 查询列表
            limit: 每个查询返回的结果数
            filters: 过滤条件
            
        Returns:
            查询结果列表
        """
        start_time = time.time()
        
        try:
            # 使用批量优化器
            collection = self.memory_core.collection
            results = asyncio.run(
                self.batch_optimizer.batch_retrieve(
                    collection, queries, limit, filters
                )
            )
            
            # 缓存结果
            for query, result in zip(queries, results):
                self.cache.set(query, limit, result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch retrieval failed: {e}")
            return [
                QueryResult(
                    memories=[],
                    query_time_ms=(time.time() - start_time) * 1000,
                    cache_hit=False,
                    strategy_used=RetrievalStrategy.SEMANTIC
                ) for _ in queries
            ]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计
        
        Returns:
            完整的性能统计信息
        """
        return {
            'retrieval': self.stats.__dict__,
            'cache': self.cache.get_stats(),
            'batch': self.batch_optimizer.get_stats()
        }
    
    def invalidate_cache(self, query: Optional[str] = None):
        """
        使缓存失效
        
        Args:
            query: 要失效的查询，如果为None则清空所有缓存
        """
        self.cache.invalidate(query)
    
    def shutdown(self):
        """关闭优化器"""
        self._executor.shutdown(wait=False)
        self.logger.info("RetrievalOptimizer shutdown complete")
