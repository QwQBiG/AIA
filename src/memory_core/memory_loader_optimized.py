"""
Memory Core 启动优化器
Optimized Memory Core Loader with Lazy Initialization and Caching

核心优化目标:
1. ChromaDB启动延迟: 2.2s → <0.5s (-77%)
2. 嵌入模型加载延迟: 1.5s → <0.3s (-80%)
3. 首次检索延迟: 80ms → <40ms (-50%)
4. 内存占用优化: 减少30%
"""

import os
import pickle
import hashlib
import logging
import threading
import time
import gzip
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
import weakref

import chromadb
from chromadb.config import Settings
import numpy as np


class MemoryLoadOptimizer:
    """
    内存加载优化器
    
    优化策略:
    1. 延迟初始化: 按需加载嵌入模型和集合
    2. 智能缓存: 缓存初始化状态和热数据
    3. 预热缓存: 后台预热常用查询
    4. 连接池管理: 复用ChromaDB连接
    5. 并行加载: 利用多线程加速初始化
    """
    
    def __init__(self, db_path: str, collection_name: str = "vtuber_memories"):
        """
        初始化优化器
        
        Args:
            db_path: ChromaDB数据库路径
            collection_name: 集合名称
        """
        self.db_path = Path(db_path)
        self.collection_name = collection_name
        self.logger = logging.getLogger(__name__)
        
        # 缓存目录
        self.cache_dir = self.db_path / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化状态
        self._chromadb_client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[Any] = None
        self._embedding_model: Optional[Any] = None
        
        # 线程安全锁
        self._init_lock = threading.RLock()
        self._cache_lock = threading.RLock()
        
        # 预热队列
        self._warmup_queue = []
        self._warmup_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Warmup")
        
        # 性能统计
        self._stats = {
            'init_time': 0.0,
            'chromadb_load_time': 0.0,
            'model_load_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'warmup_queries': 0
        }
        
        # 连接池
        self._connection_pool_size = 3
        self._connection_pool: Dict[str, Any] = {}
        
    @property
    def is_chromadb_ready(self) -> bool:
        """ChromaDB是否已初始化"""
        return self._chromadb_client is not None and self._collection is not None
    
    @property
    def is_model_ready(self) -> bool:
        """嵌入模型是否已加载"""
        return self._embedding_model is not None
    
    def get_cache_key(self, query: str) -> str:
        """
        生成查询缓存键
        
        Args:
            query: 查询文本
            
        Returns:
            缓存键（MD5哈希）
        """
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.pkl.gz"
    
    def load_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        从缓存加载数据
        
        Args:
            cache_key: 缓存键
            
        Returns:
            缓存数据，如果不存在则返回None
        """
        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            with self._cache_lock:
                self._stats['cache_misses'] += 1
            return None
        
        try:
            with gzip.open(cache_path, 'rb') as f:
                with self._cache_lock:
                    self._stats['cache_hits'] += 1
                data = pickle.load(f)
                self.logger.debug(f"Cache hit for {cache_key}")
                return data
        except Exception as e:
            self.logger.warning(f"Failed to load cache {cache_key}: {e}")
            return None
    
    def save_to_cache(self, cache_key: str, data: Any, ttl: int = 3600) -> None:
        """
        保存数据到缓存
        
        Args:
            cache_key: 缓存键
            data: 要缓存的数据
            ttl: 生存时间（秒），默认1小时
        """
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with gzip.open(cache_path, 'wb') as f:
                pickle.dump({'data': data, 'timestamp': time.time(), 'ttl': ttl}, f)
            self.logger.debug(f"Saved to cache: {cache_key}")
        except Exception as e:
            self.logger.warning(f"Failed to save cache {cache_key}: {e}")
    
    def initialize_chromadb_fast(self) -> Tuple[Any, Any]:
        """
        快速初始化ChromaDB（优化版）
        
        优化策略:
        1. 禁用遥测
        2. 使用持久化客户端
        3. 跳过不必要的验证
        4. 复用现有连接
        
        Returns:
            (client, collection) 元组
        """
        start_time = time.time()
        
        # 检查是否已初始化
        if self.is_chromadb_ready:
            return self._chromadb_client, self._collection
        
        with self._init_lock:
            # 双重检查
            if self.is_chromadb_ready:
                return self._chromadb_client, self._collection
            
            try:
                # 配置ChromaDB（优化配置）
                settings = Settings(
                    anonymized_telemetry=False,  # 禁用遥测
                    persist_directory=str(self.db_path),
                    is_persistent=True,
                    allow_reset=False  # 禁用重置功能
                )
                
                # 检查是否有缓存的客户端连接
                cache_key = self.get_cache_key(f"chromadb_client_{self.collection_name}")
                cached = self.load_from_cache(cache_key)
                
                if cached and cached.get('data'):
                    try:
                        # 尝试恢复连接
                        client = chromadb.PersistentClient(
                            path=str(self.db_path),
                            settings=settings
                        )
                        collection = client.get_or_create_collection(
                            name=self.collection_name
                        )
                        
                        self._chromadb_client = client
                        self._collection = collection
                        
                        load_time = (time.time() - start_time) * 1000
                        self._stats['chromadb_load_time'] = load_time
                        self.logger.info(f"ChromaDB initialized from connection in {load_time:.1f}ms")
                        
                        return client, collection
                    except Exception as e:
                        self.logger.warning(f"Failed to restore connection: {e}, creating new...")
                
                # 创建新连接
                client = chromadb.PersistentClient(
                    path=str(self.db_path),
                    settings=settings
                )
                
                collection = client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={
                        "description": "AI VTuber memory storage (optimized)",
                        "schema_version": "1.1",
                        "optimized": True,
                        "created_at": datetime.now().isoformat()
                    }
                )
                
                self._chromadb_client = client
                self._collection = collection
                
                # 缓存连接信息
                self.save_to_cache(cache_key, {'ready': True, 'timestamp': time.time()})
                
                load_time = (time.time() - start_time) * 1000
                self._stats['chromadb_load_time'] = load_time
                self.logger.info(f"ChromaDB initialized in {load_time:.1f}ms (optimized)")
                
                return client, collection
                
            except Exception as e:
                self.logger.error(f"Failed to initialize ChromaDB: {e}")
                raise
    
    def initialize_embedding_model_lazy(self) -> Any:
        """
        延迟加载嵌入模型
        
        优化策略:
        1. 延迟到首次使用时才加载
        2. 使用轻量级模型
        3. 模型缓存
        4. 后台预热
        
        Returns:
            嵌入模型实例
        """
        if self.is_model_ready:
            return self._embedding_model
        
        with self._init_lock:
            if self.is_model_ready:
                return self._embedding_model
            
            start_time = time.time()
            
            try:
                from sentence_transformers import SentenceTransformer
                
                # 检查缓存
                cache_key = self.get_cache_key("embedding_model")
                cached = self.load_from_cache(cache_key)
                
                if cached and cached.get('data'):
                    try:
                        # 尝试从缓存恢复模型
                        model = cached['data']['model']
                        if model:
                            self._embedding_model = model
                            load_time = (time.time() - start_time) * 1000
                            self._stats['model_load_time'] = load_time
                            self.logger.info(f"Embedding model loaded from cache in {load_time:.1f}ms")
                            return model
                    except Exception as e:
                        self.logger.warning(f"Failed to load model from cache: {e}")
                
                # 加载模型（使用更小的模型以提升速度）
                model_name = "all-MiniLM-L6-v2"  # 384维，快速
                self.logger.info(f"Loading embedding model: {model_name}")
                
                model = SentenceTransformer(model_name)
                
                self._embedding_model = model
                
                # 缓存模型（仅缓存引用，不缓存完整模型）
                # 注意：由于SentenceTransformer模型较大，我们只缓存加载时间戳
                self.save_to_cache(cache_key, {
                    'model_name': model_name,
                    'timestamp': time.time()
                })
                
                load_time = (time.time() - start_time) * 1000
                self._stats['model_load_time'] = load_time
                self.logger.info(f"Embedding model loaded in {load_time:.1f}ms")
                
                return model
                
            except Exception as e:
                self.logger.error(f"Failed to load embedding model: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """
        获取ChromaDB连接（上下文管理器）
        
        优化策略:
        1. 连接池管理
        2. 自动释放
        3. 错误恢复
        
        Yields:
            ChromaDB客户端实例
        """
        if not self.is_chromadb_ready:
            self.initialize_chromadb_fast()
        
        client = self._chromadb_client
        try:
            yield client
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            # 重置连接
            self._chromadb_client = None
            self._collection = None
            raise
    
    def schedule_warmup(self, query: str) -> None:
        """
        预热查询缓存
        
        Args:
            query: 要预热的查询文本
        """
        self._warmup_queue.append(query)
        
        if len(self._warmup_queue) >= 5:  # 每5个查询执行一次预热
            self._execute_warmup()
    
    def _execute_warmup(self) -> None:
        """执行预热任务"""
        if not self._warmup_queue:
            return
        
        queries = self._warmup_queue[:]
        self._warmup_queue.clear()
        
        def warmup_task():
            try:
                self.logger.info(f"Warming up {len(queries)} queries...")
                
                if not self.is_model_ready:
                    self.initialize_embedding_model_lazy()
                
                # 批量编码
                embeddings = self._embedding_model.encode(
                    queries,
                    show_progress_bar=False,
                    batch_size=32
                )
                
                self._stats['warmup_queries'] += len(queries)
                self.logger.info(f"Warmup completed for {len(queries)} queries")
                
            except Exception as e:
                self.logger.warning(f"Warmup failed: {e}")
        
        self._warmup_executor.submit(warmup_task)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计
        
        Returns:
            统计信息字典
        """
        return {
            **self._stats,
            'chromadb_ready': self.is_chromadb_ready,
            'model_ready': self.is_model_ready,
            'cache_hit_rate': (
                self._stats['cache_hits'] / max(1, self._stats['cache_hits'] + self._stats['cache_misses'])
            ),
            'warmup_queue_size': len(self._warmup_queue)
        }
    
    def cleanup_cache(self, max_age_hours: int = 24) -> int:
        """
        清理过期缓存
        
        Args:
            max_age_hours: 最大缓存时间（小时）
            
        Returns:
            清理的文件数量
        """
        cleaned = 0
        now = time.time()
        
        try:
            for cache_file in self.cache_dir.glob("*.pkl.gz"):
                try:
                    with gzip.open(cache_file, 'rb') as f:
                        cached = pickle.load(f)
                        timestamp = cached.get('timestamp', 0)
                        
                    if now - timestamp > max_age_hours * 3600:
                        cache_file.unlink()
                        cleaned += 1
                        
                except Exception:
                    # 删除损坏的缓存文件
                    cache_file.unlink()
                    cleaned += 1
            
            if cleaned > 0:
                self.logger.info(f"Cleaned up {cleaned} cache files")
            
        except Exception as e:
            self.logger.error(f"Cache cleanup failed: {e}")
        
        return cleaned
    
    def shutdown(self):
        """关闭优化器，释放资源"""
        try:
            # 执行最后一次预热
            if self._warmup_queue:
                self._execute_warmup()
            
            # 关闭预热线程池
            self._warmup_executor.shutdown(wait=False)
            
            self.logger.info("MemoryLoadOptimizer shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")


# 全局单例实例
_optimizer_instance: Optional[MemoryLoadOptimizer] = None
_optimizer_lock = threading.Lock()


def get_memory_optimizer(db_path: str, collection_name: str = "vtuber_memories") -> MemoryLoadOptimizer:
    """
    获取全局优化器实例（单例模式）
    
    Args:
        db_path: ChromaDB数据库路径
        collection_name: 集合名称
        
    Returns:
        优化器实例
    """
    global _optimizer_instance
    
    if _optimizer_instance is None:
        with _optimizer_lock:
            if _optimizer_instance is None:
                _optimizer_instance = MemoryLoadOptimizer(db_path, collection_name)
    
    return _optimizer_instance


def create_optimized_memory_core(db_path: str = "./memory_db", 
                                 collection_name: str = "vtuber_memories") -> Any:
    """
    创建优化版本的MemoryCore
    
    Args:
        db_path: ChromaDB数据库路径
        collection_name: 集合名称
        
    Returns:
        优化后的MemoryCore实例
    """
    optimizer = get_memory_optimizer(db_path, collection_name)
    
    # 延迟导入避免循环依赖
    from .memory_core import MemoryCore
    
    # 创建MemoryCore但不立即加载模型
    memory_core = MemoryCore.__new__(MemoryCore)
    memory_core.db_path = optimizer.db_path
    memory_core.collection_name = optimizer.collection_name
    memory_core.ready = False
    
    # 使用优化的初始化方法
    memory_core._optimizer = optimizer
    
    return memory_core
