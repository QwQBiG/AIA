"""
Smart Module Preload Manager - v4.4
智能模块预加载管理系统

核心功能:
1. 基于使用频率的智能预加载
2. 自适应预加载策略
3. 后台线程预加载，不阻塞主流程
4. 预加载优先级管理
5. 预加载失败自动降级
"""

import logging
import threading
import time
import heapq
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future
from collections import defaultdict, deque
import weakref

from .super_startup_optimizer import get_startup_optimizer


@dataclass(order=True)
class PreloadTask:
    """预加载任务"""
    priority: int  # 优先级（0-10），数字越大优先级越高
    module_name: str = field(compare=False)
    callback: Optional[callable] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    last_attempt: Optional[datetime] = field(default=None, compare=False)
    created_at: datetime = field(default_factory=datetime.now, compare=False)


@dataclass
class ModuleUsageStats:
    """模块使用统计"""
    module_name: str
    import_count: int = 0
    last_used: Optional[datetime] = None
    first_used: Optional[datetime] = None
    total_load_time: float = 0.0
    avg_load_time: float = 0.0
    fail_count: int = 0
    success_count: int = 0
    preload_success: bool = False
    
    @property
    def usage_frequency(self) -> float:
        """计算使用频率（次/小时）"""
        if self.first_used is None or self.import_count == 0:
            return 0.0
        
        hours_elapsed = (datetime.now() - self.first_used).total_seconds() / 3600
        if hours_elapsed < 0.1:  # 不足6分钟
            return float(self.import_count)
        
        return self.import_count / hours_elapsed
    
    @property
    def reliability(self) -> float:
        """计算可靠性（成功率）"""
        total = self.success_count + self.fail_count
        if total == 0:
            return 1.0
        return self.success_count / total


@dataclass
class PreloadStrategy:
    """预加载策略"""
    max_preload_threads: int = 4
    max_queue_size: int = 50
    priority_threshold: int = 6
    retry_delay_ms: int = 1000
    max_memory_mb: int = 500
    enable_adaptive: bool = True
    usage_history_window_hours: int = 24


class SmartPreloadManager:
    """
    智能模块预加载管理器
    
    核心特性:
    1. 基于使用频率自动识别需要预加载的模块
    2. 优先级队列管理预加载任务
    3. 自适应调整预加载策略
    4. 跟踪模块使用统计
    5. 持久化预加载配置
    """
    
    _instance: Optional['SmartPreloadManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'SmartPreloadManager':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化预加载管理器"""
        if self._initialized:
            return
        
        self._initialized = True
        self.logger = logging.getLogger(__name__)
        
        # 预加载策略
        self._strategy = PreloadStrategy()
        
        # 预加载任务队列（最小堆，按优先级排序）
        self._task_queue: List[PreloadTask] = []
        self._queue_lock = threading.Lock()
        self._queue_not_empty = threading.Condition(self._queue_lock)
        
        # 模块使用统计
        self._usage_stats: Dict[str, ModuleUsageStats] = {}
        self._stats_lock = threading.Lock()
        
        # 预加载线程池
        self._preload_executor: Optional[ThreadPoolExecutor] = None
        
        # 运行状态
        self._is_running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # 持久化文件
        self._stats_file = Path(__file__).parent.parent / ".workbuddy" / "preload_stats.json"
        
        # 回调函数
        self._on_preload_complete: List[callable] = []
        
        # 启动优化器
        self._startup_optimizer = get_startup_optimizer()
        
        self.logger.info("Smart Preload Manager initialized")
    
    def start(self):
        """启动预加载管理器"""
        if self._is_running:
            return
        
        self._is_running = True
        
        # 加载历史统计
        self._load_stats_from_file()
        
        # 创建线程池
        self._preload_executor = ThreadPoolExecutor(
            max_workers=self._strategy.max_preload_threads,
            thread_name_prefix="Preload"
        )
        
        # 启动工作线程
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="PreloadManager",
            daemon=True
        )
        self._worker_thread.start()
        
        self.logger.info("Smart Preload Manager started")
    
    def stop(self):
        """停止预加载管理器"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # 唤醒工作线程
        with self._queue_not_empty:
            self._queue_not_empty.notify_all()
        
        # 等待工作线程结束
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        
        # 关闭线程池
        if self._preload_executor:
            self._preload_executor.shutdown(wait=False)
        
        # 保存统计
        self._save_stats_to_file()
        
        self.logger.info("Smart Preload Manager stopped")
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self._is_running:
            task = self._get_next_task()
            
            if task is None:
                # 没有任务，等待
                with self._queue_not_empty:
                    self._queue_not_empty.wait(timeout=1.0)
                continue
            
            # 执行预加载
            self._execute_preload_task(task)
    
    def _get_next_task(self) -> Optional[PreloadTask]:
        """从队列获取下一个任务"""
        with self._queue_lock:
            if not self._task_queue:
                return None
            
            # 弹出优先级最高的任务
            return heapq.heappop(self._task_queue)
    
    def _execute_preload_task(self, task: PreloadTask):
        """
        执行预加载任务
        
        Args:
            task: 预加载任务
        """
        start_time = time.time()
        
        try:
            # 记录尝试时间
            task.last_attempt = datetime.now()
            
            # 使用启动优化器导入模块
            module = self._startup_optimizer.lazy_import(task.module_name)
            
            # 更新统计
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_preload_success(task.module_name, elapsed_ms)
            
            # 触发回调
            if task.callback:
                try:
                    task.callback(task.module_name, True, elapsed_ms)
                except Exception as e:
                    self.logger.warning(f"Preload callback failed: {e}")
            
            # 触发全局回调
            for callback in self._on_preload_complete:
                try:
                    callback(task.module_name, True, elapsed_ms)
                except Exception as e:
                    self.logger.warning(f"Global preload callback failed: {e}")
            
            self.logger.debug(f"Preloaded {task.module_name} in {elapsed_ms:.1f}ms")
            
        except Exception as e:
            # 预加载失败
            self._record_preload_failure(task.module_name)
            
            # 重试逻辑
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                # 降低优先级重新入队
                task.priority = max(0, task.priority - 2)
                with self._queue_lock:
                    if len(self._task_queue) < self._strategy.max_queue_size:
                        heapq.heappush(self._task_queue, task)
                self.logger.warning(
                    f"Preload failed for {task.module_name}, "
                    f"retry {task.retry_count}/{task.max_retries}: {e}"
                )
            else:
                self.logger.error(
                    f"Preload failed for {task.module_name} "
                    f"after {task.max_retries} retries: {e}"
                )
            
            # 触发失败回调
            if task.callback:
                try:
                    task.callback(task.module_name, False, 0)
                except Exception as e:
                    self.logger.warning(f"Preload callback failed: {e}")
    
    def record_import(self, module_name: str, load_time_ms: float, success: bool = True):
        """
        记录模块导入
        
        Args:
            module_name: 模块名称
            load_time_ms: 加载时间（毫秒）
            success: 是否成功
        """
        with self._stats_lock:
            stats = self._usage_stats.get(module_name)
            if stats is None:
                stats = ModuleUsageStats(module_name=module_name)
                self._usage_stats[module_name] = stats
            
            stats.import_count += 1
            stats.last_used = datetime.now()
            if stats.first_used is None:
                stats.first_used = datetime.now()
            
            stats.total_load_time += load_time_ms
            stats.avg_load_time = stats.total_load_time / stats.import_count
            
            if success:
                stats.success_count += 1
            else:
                stats.fail_count += 1
        
        # 自适应预加载
        if self._strategy.enable_adaptive:
            self._adaptive_preload(module_name, stats)
    
    def _record_preload_success(self, module_name: str, elapsed_ms: float):
        """记录预加载成功"""
        with self._stats_lock:
            stats = self._usage_stats.get(module_name)
            if stats:
                stats.preload_success = True
                stats.success_count += 1
    
    def _record_preload_failure(self, module_name: str):
        """记录预加载失败"""
        with self._stats_lock:
            stats = self._usage_stats.get(module_name)
            if stats:
                stats.fail_count += 1
    
    def _adaptive_preload(self, module_name: str, stats: ModuleUsageStats):
        """
        自适应预加载决策
        
        Args:
            module_name: 模块名称
            stats: 模块使用统计
        """
        # 判断是否需要预加载
        should_preload = (
            stats.usage_frequency > 1.0  # 每小时使用超过1次
            or stats.import_count >= 3  # 总导入次数超过3次
        ) and stats.reliability > 0.8  # 可靠性大于80%
        
        if should_preload and not stats.preload_success:
            # 添加到预加载队列
            priority = self._calculate_preload_priority(stats)
            self.queue_preload(module_name, priority=priority)
    
    def _calculate_preload_priority(self, stats: ModuleUsageStats) -> int:
        """
        计算预加载优先级
        
        Args:
            stats: 模块使用统计
            
        Returns:
            优先级（0-10）
        """
        priority = 5  # 基础优先级
        
        # 使用频率越高，优先级越高
        if stats.usage_frequency > 5.0:
            priority += 3
        elif stats.usage_frequency > 2.0:
            priority += 2
        elif stats.usage_frequency > 1.0:
            priority += 1
        
        # 可靠性越高，优先级越高
        if stats.reliability > 0.95:
            priority += 1
        
        # 最近使用过，优先级更高
        if stats.last_used and (datetime.now() - stats.last_used) < timedelta(hours=1):
            priority += 1
        
        # 加载时间越长，优先级越高
        if stats.avg_load_time > 500:
            priority += 1
        elif stats.avg_load_time > 200:
            priority += 0
        
        # 限制在0-10之间
        return min(10, max(0, priority))
    
    def queue_preload(
        self,
        module_name: str,
        priority: int = 5,
        callback: Optional[callable] = None
    ):
        """
        添加预加载任务到队列
        
        Args:
            module_name: 模块名称
            priority: 优先级（0-10）
            callback: 完成回调函数
        """
        with self._queue_lock:
            # 检查队列大小
            if len(self._task_queue) >= self._strategy.max_queue_size:
                self.logger.warning(f"Preload queue full, dropping {module_name}")
                return
            
            # 检查是否已在队列中
            for task in self._task_queue:
                if task.module_name == module_name:
                    # 更新优先级（取最大值）
                    task.priority = max(task.priority, priority)
                    heapq.heapify(self._task_queue)
                    self.logger.debug(f"Updated priority for {module_name}: {task.priority}")
                    return
            
            # 创建新任务
            task = PreloadTask(
                priority=priority,
                module_name=module_name,
                callback=callback
            )
            heapq.heappush(self._task_queue, task)
            
            # 唤醒工作线程
            self._queue_not_empty.notify()
            
            self.logger.debug(f"Queued preload for {module_name} with priority {priority}")
    
    def register_preload_callback(self, callback: callable):
        """
        注册预加载完成回调
        
        Args:
            callback: 回调函数 (module_name: str, success: bool, time_ms: float) -> None
        """
        self._on_preload_complete.append(callback)
    
    def get_usage_stats(self, module_name: str) -> Optional[ModuleUsageStats]:
        """
        获取模块使用统计
        
        Args:
            module_name: 模块名称
            
        Returns:
            使用统计对象
        """
        with self._stats_lock:
            return self._usage_stats.get(module_name)
    
    def get_top_used_modules(self, limit: int = 10) -> List[ModuleUsageStats]:
        """
        获取使用频率最高的模块
        
        Args:
            limit: 返回数量限制
            
        Returns:
            模块统计列表，按使用频率降序
        """
        with self._stats_lock:
            sorted_stats = sorted(
                self._usage_stats.values(),
                key=lambda x: x.usage_frequency,
                reverse=True
            )
            return sorted_stats[:limit]
    
    def _load_stats_from_file(self):
        """从文件加载历史统计"""
        if not self._stats_file.exists():
            return
        
        try:
            with open(self._stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self._stats_lock:
                for module_name, stats_data in data.items():
                    stats = ModuleUsageStats(module_name=module_name)
                    stats.import_count = stats_data.get('import_count', 0)
                    stats.total_load_time = stats_data.get('total_load_time', 0)
                    stats.fail_count = stats_data.get('fail_count', 0)
                    stats.success_count = stats_data.get('success_count', 0)
                    
                    if stats.import_count > 0:
                        stats.avg_load_time = stats.total_load_time / stats.import_count
                    
                    # 解析时间
                    last_used_str = stats_data.get('last_used')
                    if last_used_str:
                        stats.last_used = datetime.fromisoformat(last_used_str)
                    
                    first_used_str = stats_data.get('first_used')
                    if first_used_str:
                        stats.first_used = datetime.fromisoformat(first_used_str)
                    
                    self._usage_stats[module_name] = stats
            
            self.logger.info(f"Loaded stats for {len(self._usage_stats)} modules")
            
        except Exception as e:
            self.logger.warning(f"Failed to load stats from file: {e}")
    
    def _save_stats_to_file(self):
        """保存统计到文件"""
        try:
            with self._stats_lock:
                data = {}
                for module_name, stats in self._usage_stats.items():
                    data[module_name] = {
                        'import_count': stats.import_count,
                        'total_load_time': stats.total_load_time,
                        'avg_load_time': stats.avg_load_time,
                        'fail_count': stats.fail_count,
                        'success_count': stats.success_count,
                        'last_used': stats.last_used.isoformat() if stats.last_used else None,
                        'first_used': stats.first_used.isoformat() if stats.first_used else None,
                    }
            
            self._stats_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._stats_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved stats for {len(data)} modules to {self._stats_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save stats to file: {e}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        获取队列状态
        
        Returns:
            队列状态字典
        """
        with self._queue_lock:
            return {
                'queue_size': len(self._task_queue),
                'max_queue_size': self._strategy.max_queue_size,
                'tracked_modules': len(self._usage_stats),
                'is_running': self._is_running,
            }
    
    def print_status_report(self):
        """打印状态报告"""
        status = self.get_queue_status()
        top_modules = self.get_top_used_modules(5)
        
        print("\n" + "="*60)
        print("📊 智能预加载管理器状态报告")
        print("="*60)
        
        print(f"\n🔄 队列状态:")
        print(f"  - 队列大小: {status['queue_size']}/{status['max_queue_size']}")
        print(f"  - 跟踪模块: {status['tracked_modules']}")
        print(f"  - 运行状态: {'运行中' if status['is_running'] else '已停止'}")
        
        if top_modules:
            print(f"\n🔥 最常用模块（前5）:")
            for i, stats in enumerate(top_modules, 1):
                print(f"  {i}. {stats.module_name:30s} "
                      f"{stats.import_count:3d}次  "
                      f"{stats.usage_frequency:.2f}/h  "
                      f"{stats.avg_load_time:.0f}ms  "
                      f"{'✓' if stats.preload_success else '✗'}")
        
        print("="*60 + "\n")


# 全局实例
_preload_manager_instance: Optional[SmartPreloadManager] = None


def get_preload_manager() -> SmartPreloadManager:
    """获取全局预加载管理器实例"""
    global _preload_manager_instance
    if _preload_manager_instance is None:
        _preload_manager_instance = SmartPreloadManager()
    return _preload_manager_instance
