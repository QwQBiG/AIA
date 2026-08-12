"""
Adaptive Performance Tuner - v4.4
自适应性能调优系统

核心功能:
1. 实时性能监控
2. 自动识别性能瓶颈
3. 智能参数调优
4. 预测性优化
5. A/B测试支持
"""

import logging
import threading
import time
import json
import statistics
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import weakref
import numpy as np


@dataclass
class MetricData:
    """指标数据点"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricStats:
    """指标统计"""
    mean: float
    median: float
    std: float
    min: float
    max: float
    p95: float  # 95百分位
    p99: float  # 99百分位
    count: int
    trend: str  # 'up', 'down', 'stable'
    trend_rate: float  # 变化率


@dataclass
class PerformanceTune:
    """性能调优建议"""
    target_metric: str
    current_value: float
    target_value: float
    parameter: str
    current_param_value: Any
    suggested_param_value: Any
    confidence: float  # 置信度0-1
    reason: str
    estimated_improvement: float  # 预估提升百分比


@dataclass
class TuneConfig:
    """调优配置"""
    metric_window_size: int = 1000  # 指标窗口大小
    tune_interval: float = 60.0  # 调优间隔（秒）
    confidence_threshold: float = 0.7  # 置信度阈值
    max_param_changes: int = 5  # 最大参数变更次数
    enable_auto_tune: bool = True  # 启用自动调优
    enable_prediction: bool = True  # 启用预测性优化


class AdaptivePerformanceTuner:
    """
    自适应性能调优器
    
    核心特性:
    1. 收集各类性能指标
    2. 分析性能趋势
    3. 识别瓶颈和异常
    4. 提供调优建议
    5. 自动应用调优（可选）
    """
    
    _instance: Optional['AdaptivePerformanceTuner'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'AdaptivePerformanceTuner':
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化调优器"""
        if self._initialized:
            return
        
        self._initialized = True
        self.logger = logging.getLogger(__name__)
        
        # 调优配置
        self._config = TuneConfig()
        
        # 指标数据存储
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self._config.metric_window_size))
        self._metrics_lock = threading.Lock()
        
        # 参数追踪
        self._parameters: Dict[str, Any] = {}
        self._param_history: Dict[str, List[Tuple[datetime, Any]]] = defaultdict(list)
        self._param_lock = threading.Lock()
        
        # 调优建议
        self._tune_suggestions: List[PerformanceTune] = []
        self._tune_history: List[Tuple[datetime, PerformanceTune]] = []
        self._tune_lock = threading.Lock()
        
        # 运行状态
        self._is_running = False
        self._tune_thread: Optional[threading.Thread] = None
        
        # 回调函数
        self._on_metric_update: List[Callable] = []
        self._on_tune_suggested: List[Callable] = []
        self._on_parameter_changed: List[Callable] = []
        
        # 持久化
        self._data_dir = Path(__file__).parent.parent / ".workbuddy" / "performance_tuner"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("Adaptive Performance Tuner initialized")
    
    def start(self):
        """启动调优器"""
        if self._is_running:
            return
        
        self._is_running = True
        
        # 加载历史数据
        self._load_data()
        
        # 启动调优线程
        self._tune_thread = threading.Thread(
            target=self._tune_loop,
            name="PerformanceTuner",
            daemon=True
        )
        self._tune_thread.start()
        
        self.logger.info("Adaptive Performance Tuner started")
    
    def stop(self):
        """停止调优器"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # 等待调优线程结束
        if self._tune_thread:
            self._tune_thread.join(timeout=5)
        
        # 保存数据
        self._save_data()
        
        self.logger.info("Adaptive Performance Tuner stopped")
    
    def record_metric(self, metric_name: str, value: float, metadata: Optional[Dict] = None):
        """
        记录指标
        
        Args:
            metric_name: 指标名称
            value: 指标值
            metadata: 元数据
        """
        data = MetricData(
            timestamp=datetime.now(),
            value=value,
            metadata=metadata or {}
        )
        
        with self._metrics_lock:
            self._metrics[metric_name].append(data)
        
        # 触发回调
        for callback in self._on_metric_update:
            try:
                callback(metric_name, value, metadata)
            except Exception as e:
                self.logger.warning(f"Metric update callback failed: {e}")
    
    def set_parameter(self, param_name: str, value: Any, auto_tune: bool = False):
        """
        设置参数
        
        Args:
            param_name: 参数名称
            value: 参数值
            auto_tune: 是否自动调优
        """
        with self._param_lock:
            old_value = self._parameters.get(param_name)
            self._parameters[param_name] = value
            
            # 记录历史
            self._param_history[param_name].append((datetime.now(), value))
            
            # 触发回调
            for callback in self._on_parameter_changed:
                try:
                    callback(param_name, old_value, value, auto_tune)
                except Exception as e:
                    self.logger.warning(f"Parameter change callback failed: {e}")
        
        if not auto_tune:
            self.logger.info(f"Parameter '{param_name}' changed: {old_value} -> {value}")
    
    def get_metric_stats(self, metric_name: str) -> Optional[MetricStats]:
        """
        获取指标统计
        
        Args:
            metric_name: 指标名称
            
        Returns:
            指标统计对象
        """
        with self._metrics_lock:
            data_list = list(self._metrics.get(metric_name, []))
        
        if not data_list:
            return None
        
        values = [d.value for d in data_list]
        
        # 计算基本统计
        mean = statistics.mean(values)
        median = statistics.median(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        
        # 计算百分位
        sorted_values = sorted(values)
        n = len(sorted_values)
        p95 = sorted_values[int(n * 0.95)] if n > 0 else 0.0
        p99 = sorted_values[int(n * 0.99)] if n > 0 else 0.0
        
        # 分析趋势
        if len(values) >= 10:
            recent = values[-10:]
            older = values[-20:-10]
            recent_mean = statistics.mean(recent)
            older_mean = statistics.mean(older)
            
            if recent_mean > older_mean * 1.05:
                trend = "up"
            elif recent_mean < older_mean * 0.95:
                trend = "down"
            else:
                trend = "stable"
            
            trend_rate = (recent_mean - older_mean) / older_mean if older_mean != 0 else 0.0
        else:
            trend = "stable"
            trend_rate = 0.0
        
        return MetricStats(
            mean=mean,
            median=median,
            std=std,
            min=min(values),
            max=max(values),
            p95=p95,
            p99=p99,
            count=len(values),
            trend=trend,
            trend_rate=trend_rate
        )
    
    def get_all_metric_names(self) -> List[str]:
        """获取所有指标名称"""
        with self._metrics_lock:
            return list(self._metrics.keys())
    
    def _tune_loop(self):
        """调优循环"""
        while self._is_running:
            try:
                self._analyze_and_tune()
                time.sleep(self._config.tune_interval)
            except Exception as e:
                self.logger.error(f"Tune loop failed: {e}")
    
    def _analyze_and_tune(self):
        """分析性能并生成调优建议"""
        self.logger.debug("Running performance analysis...")
        
        # 获取所有指标统计
        metric_names = self.get_all_metric_names()
        
        for metric_name in metric_names:
            stats = self.get_metric_stats(metric_name)
            if stats is None:
                continue
            
            # 分析每个指标
            suggestions = self._analyze_metric(metric_name, stats)
            
            # 添加到建议列表
            with self._tune_lock:
                self._tune_suggestions.extend(suggestions)
        
        # 如果启用自动调优，应用建议
        if self._config.enable_auto_tune:
            self._apply_auto_tune()
    
    def _analyze_metric(self, metric_name: str, stats: MetricStats) -> List[PerformanceTune]:
        """
        分析单个指标并生成调优建议
        
        Args:
            metric_name: 指标名称
            stats: 指标统计
            
        Returns:
            调优建议列表
        """
        suggestions = []
        
        # 延迟相关指标（越低越好）
        if 'latency' in metric_name or 'time' in metric_name or 'delay' in metric_name:
            if stats.mean > 1000:  # >1秒
                suggestions.append(PerformanceTune(
                    target_metric=metric_name,
                    current_value=stats.mean,
                    target_value=500.0,
                    parameter=f"{metric_name}_optimization_level",
                    current_param_value='normal',
                    suggested_param_value='aggressive',
                    confidence=0.8,
                    reason=f"{metric_name}平均值({stats.mean:.1f}ms)过高，建议启用激进优化",
                    estimated_improvement=30.0
                ))
            
            if stats.p95 > stats.mean * 2:
                suggestions.append(PerformanceTune(
                    target_metric=metric_name,
                    current_value=stats.p95,
                    target_value=stats.mean * 1.5,
                    parameter=f"{metric_name}_timeout",
                    current_param_value=None,
                    suggested_param_value=stats.mean * 2,
                    confidence=0.7,
                    reason=f"{metric_name}的P95({stats.p95:.1f}ms)远高于平均值，可能存在长尾延迟",
                    estimated_improvement=20.0
                ))
        
        # 吞吐量相关指标（越高越好）
        if 'throughput' in metric_name or 'qps' in metric_name:
            if stats.trend == 'down' and stats.trend_rate < -0.1:
                suggestions.append(PerformanceTune(
                    target_metric=metric_name,
                    current_value=stats.mean,
                    target_value=stats.mean * 1.2,
                    parameter='pool_size',
                    current_param_value=None,
                    suggested_param_value=5,
                    confidence=0.75,
                    reason=f"{metric_name}持续下降({stats.trend_rate:.1%})，建议增加连接池大小",
                    estimated_improvement=25.0
                ))
        
        # 错误率相关指标（越低越好）
        if 'error' in metric_name or 'fail' in metric_name:
            if stats.mean > 0.05:  # >5%
                suggestions.append(PerformanceTune(
                    target_metric=metric_name,
                    current_value=stats.mean * 100,
                    target_value=1.0,
                    parameter='retry_policy',
                    current_param_value=None,
                    suggested_param_value='exponential_backoff',
                    confidence=0.85,
                    reason=f"{metric_name}过高({stats.mean*100:.1f}%)，建议启用指数退避重试",
                    estimated_improvement=40.0
                ))
        
        return suggestions
    
    def _apply_auto_tune(self):
        """应用自动调优"""
        with self._tune_lock:
            # 按置信度排序
            sorted_suggestions = sorted(
                self._tune_suggestions,
                key=lambda x: x.confidence,
                reverse=True
            )
            
            # 应用前N个建议
            applied = 0
            for suggestion in sorted_suggestions:
                if applied >= self._config.max_param_changes:
                    break
                
                if suggestion.confidence >= self._config.confidence_threshold:
                    self.set_parameter(
                        suggestion.parameter,
                        suggestion.suggested_param_value,
                        auto_tune=True
                    )
                    
                    # 记录历史
                    self._tune_history.append((datetime.now(), suggestion))
                    applied += 1
                    
                    self.logger.info(
                        f"Auto-tune applied: {suggestion.parameter} = {suggestion.suggested_param_value} "
                        f"(confidence: {suggestion.confidence:.2f})"
                    )
            
            # 清空建议
            self._tune_suggestions.clear()
    
    def register_metric_callback(self, callback: Callable):
        """注册指标更新回调"""
        self._on_metric_update.append(callback)
    
    def register_tune_suggestion_callback(self, callback: Callable):
        """注册调优建议回调"""
        self._on_tune_suggested.append(callback)
    
    def register_parameter_change_callback(self, callback: Callable):
        """注册参数变更回调"""
        self._on_parameter_changed.append(callback)
    
    def get_suggestions(self, limit: int = 10) -> List[PerformanceTune]:
        """
        获取调优建议
        
        Args:
            limit: 返回数量限制
            
        Returns:
            调优建议列表
        """
        with self._tune_lock:
            sorted_suggestions = sorted(
                self._tune_suggestions,
                key=lambda x: x.confidence,
                reverse=True
            )
            return sorted_suggestions[:limit]
    
    def get_tune_history(self, limit: int = 50) -> List[Tuple[datetime, PerformanceTune]]:
        """
        获取调优历史
        
        Args:
            limit: 返回数量限制
            
        Returns:
            调优历史列表
        """
        with self._tune_lock:
            return self._tune_history[-limit:]
    
    def _save_data(self):
        """保存数据"""
        try:
            # 保存参数历史
            param_file = self._data_dir / "parameters.json"
            with open(param_file, 'w', encoding='utf-8') as f:
                data = {}
                for param_name, history in self._param_history.items():
                    data[param_name] = [
                        {
                            'timestamp': ts.isoformat(),
                            'value': value
                        }
                        for ts, value in history[-100:]  # 只保存最近100条
                    ]
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved data to {param_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save data: {e}")
    
    def _load_data(self):
        """加载数据"""
        try:
            param_file = self._data_dir / "parameters.json"
            if param_file.exists():
                with open(param_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                with self._param_lock:
                    for param_name, history in data.items():
                        for item in history:
                            ts = datetime.fromisoformat(item['timestamp'])
                            value = item['value']
                            self._param_history[param_name].append((ts, value))
                
                self.logger.debug(f"Loaded parameters from {param_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to load data: {e}")
    
    def print_report(self):
        """打印性能报告"""
        print("\n" + "="*60)
        print("📊 自适应性能调优报告")
        print("="*60)
        
        # 打印指标统计
        metric_names = self.get_all_metric_names()
        print(f"\n📈 指标统计（前10个）:")
        for i, metric_name in enumerate(metric_names[:10], 1):
            stats = self.get_metric_stats(metric_name)
            if stats:
                print(f"  {i}. {metric_name:30s} "
                      f"avg={stats.mean:.2f}  "
                      f"p95={stats.p95:.2f}  "
                      f"trend={stats.trend}({stats.trend_rate:.1%})")
        
        # 打印调优建议
        suggestions = self.get_suggestions(5)
        if suggestions:
            print(f"\n💡 调优建议（前5个）:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. [{suggestion.confidence:.0%}] {suggestion.reason}")
                print(f"     参数: {suggestion.parameter} = {suggestion.suggested_param_value}")
                print(f"     预估提升: {suggestion.estimated_improvement:.0f}%")
        
        # 打印当前参数
        with self._param_lock:
            if self._parameters:
                print(f"\n⚙️  当前参数:")
                for param_name, value in list(self._parameters.items())[:10]:
                    print(f"  - {param_name}: {value}")
        
        print("="*60 + "\n")


# 全局实例
_tuner_instance: Optional[AdaptivePerformanceTuner] = None


def get_performance_tuner() -> AdaptivePerformanceTuner:
    """获取全局性能调优器实例"""
    global _tuner_instance
    if _tuner_instance is None:
        _tuner_instance = AdaptivePerformanceTuner()
    return _tuner_instance
