"""
Full Chain Monitor - v4.4
全链路监控系统

核心功能:
1. 分布式追踪（Distributed Tracing）
2. 请求/响应全链路监控
3. 性能热点识别
4. 异常追踪
5. 可视化报告生成
"""

import logging
import threading
import time
import uuid
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import contextmanager
import weakref
import traceback as tb


@dataclass
class Span:
    """追踪跨度"""
    span_id: str
    parent_span_id: Optional[str]
    trace_id: str
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)
    status: str = "success"  # success, error, timeout
    
    def finish(self):
        """完成跨度"""
        if self.end_time is None:
            self.end_time = datetime.now()
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def add_tag(self, key: str, value: Any):
        """添加标签"""
        self.tags[key] = value
    
    def add_log(self, message: str, **kwargs):
        """添加日志"""
        self.logs.append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            **kwargs
        })
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'span_id': self.span_id,
            'parent_span_id': self.parent_span_id,
            'trace_id': self.trace_id,
            'operation_name': self.operation_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'tags': self.tags,
            'logs': self.logs,
            'status': self.status
        }


@dataclass
class Trace:
    """追踪"""
    trace_id: str
    root_span: Span
    spans: List[Span] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    
    def add_span(self, span: Span):
        """添加跨度"""
        self.spans.append(span)
    
    def finish(self):
        """完成追踪"""
        if self.end_time is None:
            self.end_time = datetime.now()
            self.total_duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
            if self.root_span:
                self.root_span.finish()
    
    def get_spans_by_operation(self, operation_name: str) -> List[Span]:
        """根据操作名称获取跨度"""
        return [s for s in self.spans if s.operation_name == operation_name]
    
    def get_critical_path(self) -> List[Span]:
        """获取关键路径（耗时最长的路径）"""
        if not self.spans:
            return []
        
        # 构建树结构
        span_map = {s.span_id: s for s in self.spans}
        children = defaultdict(list)
        root = None
        
        for span in self.spans:
            if span.parent_span_id is None:
                root = span
            else:
                children[span.parent_span_id].append(span)
        
        if not root:
            return []
        
        # 找到最长路径
        def find_longest(span: Span) -> List[Span]:
            longest_path = [span]
            max_child_duration = 0
            best_child = None
            
            for child in children[span.span_id]:
                path = find_longest(child)
                child_duration = sum(s.duration_ms or 0 for s in path)
                if child_duration > max_child_duration:
                    max_child_duration = child_duration
                    best_child = path
            
            if best_child:
                longest_path.extend(best_child)
            
            return longest_path
        
        return find_longest(root)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'trace_id': self.trace_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_duration_ms': self.total_duration_ms,
            'root_span': self.root_span.to_dict() if self.root_span else None,
            'spans': [s.to_dict() for s in self.spans],
            'span_count': len(self.spans)
        }


@dataclass
class TraceStats:
    """追踪统计"""
    total_traces: int
    success_traces: int
    error_traces: int
    avg_duration: float
    max_duration: float
    min_duration: float
    p95_duration: float
    operation_stats: Dict[str, Dict]


class FullChainMonitor:
    """
    全链路监控器
    
    核心特性:
    1. 分布式追踪支持
    2. 跨服务调用追踪
    3. 性能分析
    4. 异常定位
    5. 可视化报告
    """
    
    _instance: Optional['FullChainMonitor'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'FullChainMonitor':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化监控器"""
        if self._initialized:
            return
        
        self._initialized = True
        self.logger = logging.getLogger(__name__)
        
        # 追踪存储
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}
        self._traces_lock = threading.Lock()
        
        # 统计
        self._stats = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'errors': 0,
            'max_duration': 0.0,
            'min_duration': float('inf')
        })
        
        # 运行状态
        self._is_running = False
        
        # 持久化
        self._data_dir = Path(__file__).parent.parent / ".workbuddy" / "traces"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 回调
        self._on_trace_complete: List[Callable] = []
        
        self.logger.info("Full Chain Monitor initialized")
    
    def start_trace(self, operation_name: str, parent_span_id: Optional[str] = None) -> Span:
        """
        开始追踪
        
        Args:
            operation_name: 操作名称
            parent_span_id: 父跨度ID
            
        Returns:
            跨度对象
        """
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex
        
        span = Span(
            span_id=span_id,
            parent_span_id=parent_span_id,
            trace_id=trace_id,
            operation_name=operation_name,
            start_time=datetime.now()
        )
        
        with self._traces_lock:
            self._active_spans[span_id] = span
            
            # 如果是根跨度，创建追踪
            if parent_span_id is None:
                trace = Trace(trace_id=trace_id, root_span=span)
                self._traces[trace_id] = trace
        
        return span
    
    @contextmanager
    def trace(self, operation_name: str, parent_span_id: Optional[str] = None):
        """
        追踪上下文管理器
        
        Args:
            operation_name: 操作名称
            parent_span_id: 父跨度ID
            
        Yields:
            跨度对象
        """
        span = self.start_trace(operation_name, parent_span_id)
        try:
            yield span
            span.status = "success"
        except Exception as e:
            span.status = "error"
            span.add_tag("error", str(e))
            span.add_tag("error_type", type(e).__name__)
            span.add_log("error", message=str(e), traceback=tb.format_exc())
            raise
        finally:
            self.finish_span(span.span_id)
    
    def finish_span(self, span_id: str):
        """
        完成跨度
        
        Args:
            span_id: 跨度ID
        """
        with self._traces_lock:
            span = self._active_spans.pop(span_id, None)
            if span is None:
                return
            
            span.finish()
            
            # 添加到追踪
            trace = self._traces.get(span.trace_id)
            if trace:
                trace.add_span(span)
                
                # 如果是根跨度，完成追踪
                if span.parent_span_id is None:
                    trace.finish()
                    self._update_stats(trace)
                    
                    # 触发回调
                    for callback in self._on_trace_complete:
                        try:
                            callback(trace)
                        except Exception as e:
                            self.logger.warning(f"Trace complete callback failed: {e}")
    
    def _update_stats(self, trace: Trace):
        """更新统计"""
        if trace.total_duration_ms is None:
            return
        
        operation_name = trace.root_span.operation_name if trace.root_span else "unknown"
        
        stats = self._stats[operation_name]
        stats['count'] += 1
        stats['total_duration'] += trace.total_duration_ms
        stats['max_duration'] = max(stats['max_duration'], trace.total_duration_ms)
        stats['min_duration'] = min(stats['min_duration'], trace.total_duration_ms)
        
        if trace.root_span and trace.root_span.status == "error":
            stats['errors'] += 1
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """
        获取追踪
        
        Args:
            trace_id: 追踪ID
            
        Returns:
            追踪对象
        """
        with self._traces_lock:
            return self._traces.get(trace_id)
    
    def get_stats(self) -> TraceStats:
        """
        获取统计
        
        Returns:
            追踪统计对象
        """
        total_traces = sum(s['count'] for s in self._stats.values())
        success_traces = total_traces - sum(s['errors'] for s in self._stats.values())
        error_traces = sum(s['errors'] for s in self._stats.values())
        
        total_duration = sum(s['total_duration'] for s in self._stats.values())
        avg_duration = total_duration / total_traces if total_traces > 0 else 0.0
        
        max_duration = max(s['max_duration'] for s in self._stats.values()) if self._stats else 0.0
        min_duration = min(
            s['min_duration'] for s in self._stats.values() 
            if s['min_duration'] != float('inf')
        ) or 0.0
        
        # 计算P95
        all_durations = []
        for trace in self._traces.values():
            if trace.total_duration_ms:
                all_durations.append(trace.total_duration_ms)
        
        if all_durations:
            all_durations.sort()
            p95_idx = int(len(all_durations) * 0.95)
            p95_duration = all_durations[p95_idx]
        else:
            p95_duration = 0.0
        
        # 操作统计
        operation_stats = {}
        for operation_name, stats in self._stats.items():
            operation_stats[operation_name] = {
                'count': stats['count'],
                'avg_duration': stats['total_duration'] / stats['count'] if stats['count'] > 0 else 0.0,
                'error_rate': stats['errors'] / stats['count'] if stats['count'] > 0 else 0.0,
                'max_duration': stats['max_duration'],
            }
        
        return TraceStats(
            total_traces=total_traces,
            success_traces=success_traces,
            error_traces=error_traces,
            avg_duration=avg_duration,
            max_duration=max_duration,
            min_duration=min_duration,
            p95_duration=p95_duration,
            operation_stats=operation_stats
        )
    
    def register_trace_complete_callback(self, callback: Callable):
        """注册追踪完成回调"""
        self._on_trace_complete.append(callback)
    
    def export_trace_json(self, trace_id: str, filepath: str):
        """
        导出追踪为JSON
        
        Args:
            trace_id: 追踪ID
            filepath: 导出文件路径
        """
        trace = self.get_trace(trace_id)
        if trace is None:
            self.logger.warning(f"Trace {trace_id} not found")
            return
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(trace.to_dict(), f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported trace {trace_id} to {filepath}")
    
    def save_all_traces(self):
        """保存所有追踪"""
        output_dir = self._data_dir / datetime.now().strftime("%Y%m%d")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with self._traces_lock:
            for trace_id, trace in self._traces.items():
                filepath = output_dir / f"{trace_id}.json"
                self.export_trace_json(trace_id, str(filepath))
        
        self.logger.info(f"Saved {len(self._traces)} traces to {output_dir}")
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("📊 全链路监控统计")
        print("="*60)
        
        print(f"\n🔍 追踪统计:")
        print(f"  - 总追踪数: {stats.total_traces}")
        print(f"  - 成功追踪: {stats.success_traces}")
        print(f"  - 失败追踪: {stats.error_traces}")
        
        if stats.total_traces > 0:
            success_rate = stats.success_traces / stats.total_traces * 100
            print(f"  - 成功率: {success_rate:.1f}%")
        
        print(f"\n⏱️  性能指标:")
        print(f"  - 平均时长: {stats.avg_duration:.2f}ms")
        print(f"  - 最大时长: {stats.max_duration:.2f}ms")
        print(f"  - 最小时长: {stats.min_duration:.2f}ms")
        print(f"  - P95时长: {stats.p95_duration:.2f}ms")
        
        if stats.operation_stats:
            print(f"\n📈 操作统计（前10个）:")
            sorted_ops = sorted(
                stats.operation_stats.items(),
                key=lambda x: x[1]['avg_duration'],
                reverse=True
            )[:10]
            
            for i, (operation, op_stats) in enumerate(sorted_ops, 1):
                print(f"  {i}. {operation:30s} "
                      f"avg={op_stats['avg_duration']:.2f}ms  "
                      f"max={op_stats['max_duration']:.2f}ms  "
                      f"error={op_stats['error_rate']*100:.1f}%")
        
        print("="*60 + "\n")
    
    def generate_report(self, output_file: str):
        """
        生成可视化报告
        
        Args:
            output_file: 输出文件路径
        """
        stats = self.get_stats()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'stats': {
                'total_traces': stats.total_traces,
                'success_traces': stats.success_traces,
                'error_traces': stats.error_traces,
                'avg_duration_ms': stats.avg_duration,
                'max_duration_ms': stats.max_duration,
                'min_duration_ms': stats.min_duration,
                'p95_duration_ms': stats.p95_duration,
            },
            'operation_stats': stats.operation_stats,
            'recent_traces': [
                trace.to_dict() for trace in list(self._traces.values())[-10:]
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Generated report: {output_file}")


# 全局实例
_monitor_instance: Optional[FullChainMonitor] = None


def get_full_chain_monitor() -> FullChainMonitor:
    """获取全局全链路监控器实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = FullChainMonitor()
    return _monitor_instance
