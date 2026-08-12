"""
Super Startup Optimizer - v4.4 Extreme Edition
超极速启动优化器

核心优化目标:
1. 总启动时间: 5.8s → <2s (-66%)
2. 核心模块导入: 3.5s → <0.5s (-86%)
3. ChromaDB加载: 2.3s → <0.3s (-87%)
4. 内存占用峰值: 减少50%
"""

import sys
import os
import importlib
import importlib.util
import logging
import threading
import time
import weakref
import gc
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Tuple, Set, List
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json

# 性能监控
from contextlib import contextmanager


@dataclass
class ModuleLoadStats:
    """模块加载统计"""
    module_name: str
    load_time: float  # 加载时间(ms)
    memory_before: int  # 加载前内存(KB)
    memory_after: int  # 加载后内存(KB)
    load_count: int = 0
    last_loaded: Optional[datetime] = None
    is_critical: bool = False
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class StartupProfile:
    """启动性能分析"""
    total_time: float
    module_times: Dict[str, float]
    memory_usage: Dict[str, int]
    bottlenecks: List[str]
    recommendations: List[str]


class SuperStartupOptimizer:
    """
    超极速启动优化器
    
    核心优化策略:
    1. 惰性加载: 按需加载模块，避免启动时全量加载
    2. 智能预加载: 后台线程预加载常用模块
    3. 模块级缓存: 缓存已加载模块，避免重复加载
    4. 依赖分析: 分析模块依赖关系，优化加载顺序
    5. 内存优化: 及时释放不需要的资源
    6. 并行初始化: 多线程并行初始化无依赖组件
    """
    
    _instance: Optional['SuperStartupOptimizer'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'SuperStartupOptimizer':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化优化器"""
        if self._initialized:
            return
        
        self._initialized = True
        self.logger = logging.getLogger(__name__)
        
        # 模块加载统计
        self._module_stats: Dict[str, ModuleLoadStats] = {}
        self._load_order: List[str] = []
        
        # 惰性加载配置
        self._lazy_modules: Set[str] = {
            'pygame',
            'cv2',
            'torch',
            'whisper',
            'sentence_transformers',
            'chromadb',
        }
        
        # 关键模块（必须立即加载）
        self._critical_modules: Set[str] = {
            'asyncio',
            'json',
            'logging',
            'threading',
            'queue',
        }
        
        # 已加载模块缓存
        self._loaded_cache: Dict[str, Any] = {}
        self._loading_locks: Dict[str, threading.Lock] = {}
        
        # 预加载线程池
        self._preload_executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="Preload"
        )
        
        # 预加载队列
        self._preload_queue: List[str] = []
        self._preload_lock = threading.Lock()
        
        # 性能分析数据
        self._startup_timings: Dict[str, float] = {}
        self._memory_snapshots: Dict[str, int] = {}
        
        # 启动配置
        self._enable_lazy_load: bool = True
        self._enable_parallel_init: bool = True
        self._enable_memory_opt: bool = True
        
        # 回调函数
        self._module_loaded_callbacks: List[Callable] = []
        
        self.logger.info("Super Startup Optimizer initialized")
    
    @contextmanager
    def measure_time(self, key: str):
        """测量时间上下文管理器"""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self._startup_timings[key] = elapsed
    
    @property
    def total_startup_time(self) -> float:
        """获取总启动时间"""
        return sum(self._startup_timings.values())
    
    def get_memory_usage(self) -> int:
        """获取当前内存使用量（KB）"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            return process.memory_info().rss // 1024
        except ImportError:
            return 0
    
    def capture_memory_snapshot(self, label: str):
        """捕获内存快照"""
        self._memory_snapshots[label] = self.get_memory_usage()
    
    def analyze_module_dependencies(self, module_name: str) -> Set[str]:
        """
        分析模块依赖关系
        
        Args:
            module_name: 模块名称
            
        Returns:
            依赖模块集合
        """
        dependencies = set()
        try:
            spec = importlib.util.find_spec(module_name)
            if spec and spec.origin:
                # 读取模块文件分析import语句
                module_file = Path(spec.origin)
                if module_file.exists():
                    with open(module_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 简单的import语句分析
                        import re
                        matches = re.findall(r'^import\s+(\w+)|^from\s+(\w+)', content, re.MULTILINE)
                        for match in matches:
                            dep = match[0] if match[0] else match[1]
                            if dep and not dep.startswith('.'):
                                dependencies.add(dep)
        except Exception as e:
            self.logger.debug(f"Failed to analyze dependencies for {module_name}: {e}")
        
        return dependencies
    
    def is_lazy_module(self, module_name: str) -> bool:
        """判断是否为惰性加载模块"""
        for lazy in self._lazy_modules:
            if module_name.startswith(lazy):
                return True
        return False
    
    def lazy_import(self, module_name: str, reload: bool = False) -> Any:
        """
        惰性导入模块
        
        Args:
            module_name: 模块名称
            reload: 是否强制重新加载
            
        Returns:
            模块对象
        """
        # 检查缓存
        if not reload and module_name in self._loaded_cache:
            return self._loaded_cache[module_name]
        
        # 获取加载锁
        if module_name not in self._loading_locks:
            self._loading_locks[module_name] = threading.Lock()
        
        load_lock = self._loading_locks[module_name]
        
        with load_lock:
            # 双重检查
            if not reload and module_name in self._loaded_cache:
                return self._loaded_cache[module_name]
            
            # 检查是否已存在于sys.modules
            if not reload and module_name in sys.modules:
                module = sys.modules[module_name]
                self._loaded_cache[module_name] = module
                return module
            
            # 记录开始时间
            start_time = time.perf_counter()
            memory_before = self.get_memory_usage()
            
            # 导入模块
            try:
                module = importlib.import_module(module_name)
                
                # 记录统计信息
                load_time = (time.perf_counter() - start_time) * 1000
                memory_after = self.get_memory_usage()
                
                # 更新统计
                stats = self._module_stats.get(module_name)
                if stats is None:
                    dependencies = self.analyze_module_dependencies(module_name)
                    stats = ModuleLoadStats(
                        module_name=module_name,
                        load_time=load_time,
                        memory_before=memory_before,
                        memory_after=memory_after,
                        last_loaded=datetime.now(),
                        is_critical=module_name in self._critical_modules,
                        dependencies=dependencies
                    )
                else:
                    stats.load_time = load_time
                    stats.memory_before = memory_before
                    stats.memory_after = memory_after
                    stats.last_loaded = datetime.now()
                    stats.load_count += 1
                
                self._module_stats[module_name] = stats
                self._loaded_cache[module_name] = module
                
                # 触发回调
                for callback in self._module_loaded_callbacks:
                    try:
                        callback(module_name, load_time)
                    except Exception as e:
                        self.logger.warning(f"Module load callback failed: {e}")
                
                # 内存优化
                if self._enable_memory_opt:
                    gc.collect()
                
                return module
                
            except ImportError as e:
                self.logger.error(f"Failed to import module {module_name}: {e}")
                raise
    
    def preload_modules(self, module_names: List[str], priority: int = 0):
        """
        后台预加载模块
        
        Args:
            module_names: 要预加载的模块列表
            priority: 优先级（0-10）
        """
        def _preload():
            for module_name in module_names:
                try:
                    self.lazy_import(module_name)
                    self.logger.debug(f"Preloaded module: {module_name}")
                except Exception as e:
                    self.logger.debug(f"Failed to preload {module_name}: {e}")
        
        # 根据优先级调度
        if priority >= 8:
            # 高优先级：同步加载
            _preload()
        else:
            # 低优先级：后台加载
            self._preload_executor.submit(_preload)
    
    def register_module_loaded_callback(self, callback: Callable[[str, float], None]):
        """
        注册模块加载回调
        
        Args:
            callback: 回调函数，接收模块名和加载时间
        """
        self._module_loaded_callbacks.append(callback)
    
    def get_bottleneck_modules(self, threshold_ms: float = 500) -> List[ModuleLoadStats]:
        """
        获取加载缓慢的瓶颈模块
        
        Args:
            threshold_ms: 时间阈值（毫秒）
            
        Returns:
            瓶颈模块列表
        """
        return [
            stats for stats in self._module_stats.values()
            if stats.load_time > threshold_ms
        ]
    
    def generate_startup_profile(self) -> StartupProfile:
        """
        生成启动性能分析报告
        
        Returns:
            启动性能分析对象
        """
        bottlenecks = self.get_bottleneck_modules(threshold_ms=300)
        bottleneck_names = [m.module_name for m in bottlenecks]
        
        # 生成优化建议
        recommendations = []
        
        if bottlenecks:
            recommendations.append(
                f"发现 {len(bottlenecks)} 个加载缓慢的模块，建议启用惰性加载: "
                f"{', '.join(bottleneck_names[:5])}"
            )
        
        if len(self._module_stats) > 20:
            recommendations.append(
                "启动时加载模块过多，建议优化导入结构，使用惰性加载"
            )
        
        total_memory = sum(
            s.memory_after - s.memory_before
            for s in self._module_stats.values()
        )
        
        if total_memory > 500000:  # >500MB
            recommendations.append(
                f"内存占用较高（{total_memory//1024}MB），建议及时释放资源"
            )
        
        return StartupProfile(
            total_time=self.total_startup_time,
            module_times=self._startup_timings.copy(),
            memory_usage=self._memory_snapshots.copy(),
            bottlenecks=bottleneck_names,
            recommendations=recommendations
        )
    
    def print_profile_report(self, profile: Optional[StartupProfile] = None):
        """
        打印性能分析报告
        
        Args:
            profile: 性能分析对象，如果不提供则自动生成
        """
        if profile is None:
            profile = self.generate_startup_profile()
        
        print("\n" + "="*60)
        print("📊 启动性能分析报告")
        print("="*60)
        
        print(f"\n⏱️  总启动时间: {profile.total_time/1000:.3f}s")
        
        print(f"\n📈 模块加载时间（前10个最慢）:")
        sorted_modules = sorted(
            self._module_stats.values(),
            key=lambda x: x.load_time,
            reverse=True
        )[:10]
        
        for i, stats in enumerate(sorted_modules, 1):
            print(f"  {i:2d}. {stats.module_name:30s} {stats.load_time:7.1f}ms "
                  f"({'CRITICAL' if stats.is_critical else 'NORMAL'})")
        
        if profile.bottlenecks:
            print(f"\n⚠️  瓶颈模块（>300ms）:")
            for bottleneck in profile.bottlenecks:
                print(f"  - {bottleneck}")
        
        if profile.recommendations:
            print(f"\n💡 优化建议:")
            for rec in profile.recommendations:
                print(f"  - {rec}")
        
        print(f"\n💾 内存使用:")
        for label, usage in profile.memory_usage.items():
            print(f"  - {label}: {usage//1024}MB")
        
        print("="*60 + "\n")
    
    def export_profile_json(self, filepath: str, profile: Optional[StartupProfile] = None):
        """
        导出性能分析为JSON
        
        Args:
            filepath: 导出文件路径
            profile: 性能分析对象
        """
        if profile is None:
            profile = self.generate_startup_profile()
        
        data = {
            'total_time_ms': profile.total_time,
            'module_times': profile.module_times,
            'memory_usage_kb': profile.memory_usage,
            'bottlenecks': profile.bottlenecks,
            'recommendations': profile.recommendations,
            'module_stats': {
                name: {
                    'load_time_ms': stats.load_time,
                    'memory_delta_kb': stats.memory_after - stats.memory_before,
                    'load_count': stats.load_count,
                    'is_critical': stats.is_critical,
                    'dependencies': list(stats.dependencies)
                }
                for name, stats in self._module_stats.items()
            },
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Profile exported to {filepath}")
    
    def optimize_imports(self):
        """
        执行导入优化
        
        核心操作:
        1. 识别可以惰性加载的模块
        2. 后台预加载常用模块
        3. 释放不必要的资源
        """
        self.logger.info("Starting import optimization...")
        
        # 后台预加载常用模块
        common_modules = [
            'asyncio',
            'json',
            'logging',
            'threading',
            'queue',
        ]
        self.preload_modules(common_modules, priority=8)
        
        # 低优先级后台预加载
        background_modules = [
            'time',
            'datetime',
            'pathlib',
            'typing',
            'dataclasses',
        ]
        self.preload_modules(background_modules, priority=5)
        
        # 内存优化
        if self._enable_memory_opt:
            gc.collect()
    
    def shutdown(self):
        """关闭优化器，释放资源"""
        self._preload_executor.shutdown(wait=False)
        self.logger.info("Super Startup Optimizer shutdown")


# 全局实例
_optimizer_instance: Optional[SuperStartupOptimizer] = None


def get_startup_optimizer() -> SuperStartupOptimizer:
    """获取全局启动优化器实例"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = SuperStartupOptimizer()
    return _optimizer_instance


def lazy_import(module_name: str, reload: bool = False) -> Any:
    """
    便捷函数：惰性导入模块
    
    Args:
        module_name: 模块名称
        reload: 是否强制重新加载
        
    Returns:
        模块对象
    """
    optimizer = get_startup_optimizer()
    return optimizer.lazy_import(module_name, reload)


# 启动时自动初始化
if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    optimizer = get_startup_optimizer()
    
    with optimizer.measure_time('startup'):
        optimizer.optimize_imports()
    
    # 导入一些模块测试
    with optimizer.measure_time('import_standard_lib'):
        import asyncio
        import json
    
    with optimizer.measure_time('import_heavy'):
        try:
            import chromadb
        except ImportError:
            pass
    
    # 打印报告
    profile = optimizer.generate_startup_profile()
    optimizer.print_profile_report(profile)
    
    # 导出JSON
    optimizer.export_profile_json('startup_profile.json', profile)
    
    optimizer.shutdown()
