"""
Performance Dashboard - 实时性能监控面板
Real-time Performance Monitoring Dashboard

功能:
1. 实时性能指标监控
2. 可视化性能趋势
3. 系统健康状态
4. 性能瓶颈识别
5. 自动性能报告
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
from datetime import datetime, timedelta
from enum import Enum
import weakref

import numpy as np


class PerformanceLevel(Enum):
    """性能级别"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"           # 良好
    FAIR = "fair"           # 一般
    POOR = "poor"           # 差
    CRITICAL = "critical"   # 严重


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: float
    level: PerformanceLevel = PerformanceLevel.GOOD
    threshold_excellent: Optional[float] = None
    threshold_good: Optional[float] = None
    threshold_fair: Optional[float] = None
    threshold_poor: Optional[float] = None
    
    def __post_init__(self):
        """自动评估性能级别"""
        self._evaluate_level()
    
    def _evaluate_level(self):
        """评估性能级别"""
        if self.threshold_excellent is not None:
            if self.value <= self.threshold_excellent:
                self.level = PerformanceLevel.EXCELLENT
                return
        
        if self.threshold_good is not None:
            if self.value <= self.threshold_good:
                self.level = PerformanceLevel.GOOD
                return
        
        if self.threshold_fair is not None:
            if self.value <= self.threshold_fair:
                self.level = PerformanceLevel.FAIR
                return
        
        if self.threshold_poor is not None:
            if self.value <= self.threshold_poor:
                self.level = PerformanceLevel.POOR
                return
        
        self.level = PerformanceLevel.CRITICAL
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class PerformanceMonitor:
    """
    性能监控器（单个模块）
    
    监控特定模块的性能指标
    """
    
    def __init__(self, module_name: str, max_history: int = 1000):
        """
        初始化性能监控器
        
        Args:
            module_name: 模块名称
            max_history: 最大历史记录数
        """
        self.module_name = module_name
        self.max_history = max_history
        self.logger = logging.getLogger(__name__)
        
        # 指标历史
        self._metrics_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        
        # 当前指标
        self._current_metrics: Dict[str, PerformanceMetric] = {}
        
        # 阈值配置
        self._thresholds: Dict[str, Dict[str, float]] = {}
        
        # 统计
        self._stats = {
            'total_metrics': 0,
            'alerts_triggered': 0
        }
        
        # 回调函数
        self._alert_callbacks: List[Callable] = []
        
        self._lock = threading.Lock()
    
    def configure_threshold(self, metric_name: str, 
                          excellent: Optional[float] = None,
                          good: Optional[float] = None,
                          fair: Optional[float] = None,
                          poor: Optional[float] = None):
        """
        配置指标阈值
        
        Args:
            metric_name: 指标名称
            excellent: 优秀阈值
            good: 良好阈值
            fair: 一般阈值
            poor: 差阈值
        """
        with self._lock:
            self._thresholds[metric_name] = {
                'excellent': excellent,
                'good': good,
                'fair': fair,
                'poor': poor
            }
            
            # 更新当前指标的阈值
            if metric_name in self._current_metrics:
                metric = self._current_metrics[metric_name]
                metric.threshold_excellent = excellent
                metric.threshold_good = good
                metric.threshold_fair = fair
                metric.threshold_poor = poor
                metric._evaluate_level()
    
    def record_metric(self, name: str, value: float, unit: str = "ms"):
        """
        记录性能指标
        
        Args:
            name: 指标名称
            value: 指标值
            unit: 单位
        """
        timestamp = time.time()
        
        # 获取阈值
        thresholds = self._thresholds.get(name, {})
        
        # 创建性能指标
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=timestamp,
            threshold_excellent=thresholds.get('excellent'),
            threshold_good=thresholds.get('good'),
            threshold_fair=thresholds.get('fair'),
            threshold_poor=thresholds.get('poor')
        )
        
        with self._lock:
            # 保存当前指标
            self._current_metrics[name] = metric
            
            # 添加到历史
            self._metrics_history[name].append(metric)
            self._stats['total_metrics'] += 1
            
            # 检查是否需要报警
            if metric.level in [PerformanceLevel.POOR, PerformanceLevel.CRITICAL]:
                self._trigger_alert(metric)
    
    def _trigger_alert(self, metric: PerformanceMetric):
        """触发性能报警"""
        self._stats['alerts_triggered'] += 1
        
        alert_msg = (
            f"Performance Alert [{self.module_name}]: "
            f"{metric.name} = {metric.value}{metric.unit} "
            f"(Level: {metric.level.value})"
        )
        
        self.logger.warning(alert_msg)
        
        # 调用回调
        for callback in self._alert_callbacks:
            try:
                callback(self.module_name, metric)
            except Exception as e:
                self.logger.error(f"Alert callback failed: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """
        添加报警回调
        
        Args:
            callback: 回调函数
        """
        self._alert_callbacks.append(callback)
    
    def get_current_metrics(self) -> Dict[str, Dict]:
        """获取当前指标"""
        with self._lock:
            return {
                name: metric.to_dict()
                for name, metric in self._current_metrics.items()
            }
    
    def get_metric_history(self, metric_name: str, 
                          limit: Optional[int] = None) -> List[Dict]:
        """
        获取指标历史
        
        Args:
            metric_name: 指标名称
            limit: 返回数量限制
            
        Returns:
            历史指标列表
        """
        with self._lock:
            history = list(self._metrics_history[metric_name])
            
            if limit is not None:
                history = history[-limit:]
            
            return [metric.to_dict() for metric in history]
    
    def get_statistics(self, metric_name: str) -> Dict[str, Any]:
        """
        获取指标统计信息
        
        Args:
            metric_name: 指标名称
            
        Returns:
            统计信息
        """
        with self._lock:
            history = self._metrics_history[metric_name]
            
            if not history:
                return {}
            
            values = [metric.value for metric in history]
            
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'median': np.median(values),
                'std': np.std(values),
                'p50': np.percentile(values, 50),
                'p90': np.percentile(values, 90),
                'p95': np.percentile(values, 95),
                'p99': np.percentile(values, 99)
            }
    
    def get_trend(self, metric_name: str, window: int = 10) -> str:
        """
        获取指标趋势
        
        Args:
            metric_name: 指标名称
            window: 时间窗口大小
            
        Returns:
            趋势描述 (improving, stable, degrading)
        """
        with self._lock:
            history = list(self._metrics_history[metric_name][-window:])
            
            if len(history) < 2:
                return "stable"
            
            recent_avg = sum(m.value for m in history[-5:]) / min(5, len(history))
            older_avg = sum(m.value for m in history[:-5]) / max(1, len(history) - 5)
            
            if recent_avg < older_avg * 0.9:
                return "improving"
            elif recent_avg > older_avg * 1.1:
                return "degrading"
            else:
                return "stable"


class PerformanceDashboard:
    """
    性能监控面板（主类）
    
    集成所有模块的性能监控
    """
    
    def __init__(self, update_interval: float = 1.0):
        """
        初始化性能监控面板
        
        Args:
            update_interval: 更新间隔（秒）
        """
        self.update_interval = update_interval
        self.logger = logging.getLogger(__name__)
        
        # 模块监控器
        self._monitors: Dict[str, PerformanceMonitor] = {}
        self._monitors_lock = threading.Lock()
        
        # 全局统计
        self._global_stats = {
            'start_time': time.time(),
            'total_metrics': 0,
            'total_alerts': 0
        }
        
        # 监控线程
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_running = False
        
        # 预配置常用模块
        self._initialize_default_monitors()
    
    def _initialize_default_monitors(self):
        """初始化默认监控器"""
        # 记忆检索
        self.register_monitor("memory_retrieval", max_history=1000)
        self.configure_threshold("memory_retrieval", "query_time",
                                excellent=20, good=40, fair=60, poor=100)
        
        # VTS嘴型同步
        self.register_monitor("vts_mouth_sync", max_history=1000)
        self.configure_threshold("vts_mouth_sync", "update_time",
                                excellent=30, good=60, fair=100, poor=150)
        
        # 视觉分析
        self.register_monitor("vision_analysis", max_history=500)
        self.configure_threshold("vision_analysis", "analysis_time",
                                excellent=300, good=600, fair=1000, poor=2000)
        
        # LLM生成
        self.register_monitor("llm_generation", max_history=500)
        self.configure_threshold("llm_generation", "generation_time",
                                excellent=1000, good=2000, fair=3000, poor=5000)
        
        # TTS合成
        self.register_monitor("tts_synthesis", max_history=1000)
        self.configure_threshold("tts_synthesis", "synthesis_time",
                                excellent=100, good=200, fair=300, poor=500)
    
    def register_monitor(self, module_name: str, 
                        max_history: int = 1000) -> PerformanceMonitor:
        """
        注册监控器
        
        Args:
            module_name: 模块名称
            max_history: 最大历史记录数
            
        Returns:
            性能监控器实例
        """
        with self._monitors_lock:
            if module_name not in self._monitors:
                monitor = PerformanceMonitor(module_name, max_history)
                self._monitors[module_name] = monitor
            
            return self._monitors[module_name]
    
    def configure_threshold(self, module_name: str, metric_name: str,
                          excellent: Optional[float] = None,
                          good: Optional[float] = None,
                          fair: Optional[float] = None,
                          poor: Optional[float] = None):
        """
        配置指标阈值
        
        Args:
            module_name: 模块名称
            metric_name: 指标名称
            excellent: 优秀阈值
            good: 良好阈值
            fair: 一般阈值
            poor: 差阈值
        """
        with self._monitors_lock:
            if module_name in self._monitors:
                self._monitors[module_name].configure_threshold(
                    metric_name, excellent, good, fair, poor
                )
    
    def record_metric(self, module_name: str, metric_name: str,
                     value: float, unit: str = "ms"):
        """
        记录性能指标
        
        Args:
            module_name: 模块名称
            metric_name: 指标名称
            value: 指标值
            unit: 单位
        """
        with self._monitors_lock:
            if module_name not in self._monitors:
                self.register_monitor(module_name)
            
            self._monitors[module_name].record_metric(metric_name, value, unit)
            self._global_stats['total_metrics'] += 1
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        获取面板数据
        
        Returns:
            完整的面板数据
        """
        with self._monitors_lock:
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': time.time() - self._global_stats['start_time'],
                'global_stats': self._global_stats.copy(),
                'modules': {}
            }
            
            for module_name, monitor in self._monitors.items():
                dashboard_data['modules'][module_name] = {
                    'current_metrics': monitor.get_current_metrics(),
                    'stats': {
                        'total_metrics': monitor._stats['total_metrics'],
                        'alerts_triggered': monitor._stats['alerts_triggered']
                    }
                }
            
            return dashboard_data
    
    def generate_report(self, format: str = "text") -> str:
        """
        生成性能报告
        
        Args:
            format: 报告格式 (text, json, html)
            
        Returns:
            报告内容
        """
        dashboard_data = self.get_dashboard_data()
        
        if format == "json":
            return json.dumps(dashboard_data, indent=2)
        
        elif format == "text":
            return self._generate_text_report(dashboard_data)
        
        elif format == "html":
            return self._generate_html_report(dashboard_data)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_text_report(self, data: Dict) -> str:
        """生成文本格式报告"""
        lines = [
            "=" * 60,
            "性能监控报告",
            "=" * 60,
            f"生成时间: {data['timestamp']}",
            f"运行时长: {data['uptime_seconds']:.1f}秒",
            f"总指标数: {data['global_stats']['total_metrics']}",
            "",
            "模块性能概况:",
            "-" * 60
        ]
        
        for module_name, module_data in data['modules'].items():
            lines.append(f"\n{module_name}:")
            lines.append(f"  总指标数: {module_data['stats']['total_metrics']}")
            lines.append(f"  报警次数: {module_data['stats']['alerts_triggered']}")
            
            for metric_name, metric_data in module_data['current_metrics'].items():
                lines.append(
                    f"  {metric_name}: {metric_data['value']:.2f}{metric_data['unit']} "
                    f"({metric_data['level']})"
                )
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _generate_html_report(self, data: Dict) -> str:
        """生成HTML格式报告"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>性能监控报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #4CAF50; color: white; padding: 15px; }}
        .module {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; 
                   border-radius: 5px; }}
        .excellent {{ background: #4CAF50; color: white; }}
        .good {{ background: #2196F3; color: white; }}
        .fair {{ background: #FF9800; color: white; }}
        .poor {{ background: #f44336; color: white; }}
        .critical {{ background: #9C27B0; color: white; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>性能监控报告</h1>
        <p>生成时间: {data['timestamp']}</p>
        <p>运行时长: {data['uptime_seconds']:.1f}秒</p>
        <p>总指标数: {data['global_stats']['total_metrics']}</p>
    </div>
"""
        
        for module_name, module_data in data['modules'].items():
            html += f"""
    <div class="module">
        <h2>{module_name}</h2>
        <p>总指标数: {module_data['stats']['total_metrics']}</p>
        <p>报警次数: {module_data['stats']['alerts_triggered']}</p>
"""
            
            for metric_name, metric_data in module_data['current_metrics'].items():
                html += f"""
        <div class="metric {metric_data['level']}">
            <strong>{metric_name}</strong>: 
            {metric_data['value']:.2f}{metric_data['unit']}
        </div>
"""
            
            html += """
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html
    
    def start_monitoring(self):
        """启动监控线程"""
        if self._monitoring_running:
            return
        
        self._monitoring_running = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="PerformanceDashboard",
            daemon=True
        )
        self._monitoring_thread.start()
        
        self.logger.info("Performance monitoring started")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self._monitoring_running:
            try:
                # 定期生成报告（可选）
                # report = self.generate_report("text")
                # self.logger.debug(report)
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                time.sleep(1.0)
    
    def stop_monitoring(self):
        """停止监控"""
        self._monitoring_running = False
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=2.0)
        
        self.logger.info("Performance monitoring stopped")


# 全局单例
_performance_dashboard: Optional[PerformanceDashboard] = None
_dashboard_lock = threading.Lock()


def get_performance_dashboard() -> PerformanceDashboard:
    """获取全局性能监控面板实例"""
    global _performance_dashboard
    
    if _performance_dashboard is None:
        with _dashboard_lock:
            if _performance_dashboard is None:
                _performance_dashboard = PerformanceDashboard()
                _performance_dashboard.start_monitoring()
    
    return _performance_dashboard


# 装饰器
def monitor_performance(module_name: str, metric_name: str, unit: str = "ms"):
    """
    性能监控装饰器
    
    Args:
        module_name: 模块名称
        metric_name: 指标名称
        unit: 单位
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            dashboard = get_performance_dashboard()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                dashboard.record_metric(
                    module_name, metric_name, execution_time, unit
                )
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                dashboard.record_metric(
                    module_name, f"{metric_name}_error", execution_time, unit
                )
                raise
        
        return wrapper
    return decorator
