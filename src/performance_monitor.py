"""
性能监控模块
Performance Monitoring Module

监控系统性能指标，帮助诊断性能问题
"""

import time
import psutil
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """系统性能监控器"""
    
    def __init__(self, monitoring_interval: float = 5.0):
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 性能指标历史
        self.cpu_history: List[float] = []
        self.memory_history: List[float] = []
        self.conversation_times: List[float] = []
        
        # 性能阈值
        self.cpu_threshold = 80.0  # CPU使用率阈值
        self.memory_threshold = 85.0  # 内存使用率阈值
        self.conversation_time_threshold = 10.0  # 对话时间阈值（秒）
        
        # 统计信息
        self.total_conversations = 0
        self.performance_issues = 0
        self.start_time = datetime.now()
    
    def start_monitoring(self):
        """开始性能监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        logger.info("性能监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                # 获取系统性能指标
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                
                # 记录历史数据
                self.cpu_history.append(cpu_percent)
                self.memory_history.append(memory_percent)
                
                # 保持历史数据在合理范围内（最近100个数据点）
                if len(self.cpu_history) > 100:
                    self.cpu_history.pop(0)
                if len(self.memory_history) > 100:
                    self.memory_history.pop(0)
                
                # 检查性能问题
                if cpu_percent > self.cpu_threshold:
                    logger.warning(f"CPU使用率过高: {cpu_percent:.1f}%")
                    self.performance_issues += 1
                
                if memory_percent > self.memory_threshold:
                    logger.warning(f"内存使用率过高: {memory_percent:.1f}%")
                    self.performance_issues += 1
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"性能监控出错: {e}")
                time.sleep(self.monitoring_interval)
    
    def record_conversation_time(self, duration: float):
        """记录对话处理时间"""
        self.conversation_times.append(duration)
        self.total_conversations += 1
        
        # 保持历史数据在合理范围内
        if len(self.conversation_times) > 50:
            self.conversation_times.pop(0)
        
        # 检查对话时间是否过长
        if duration > self.conversation_time_threshold:
            logger.warning(f"对话处理时间过长: {duration:.2f}秒")
            self.performance_issues += 1
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        now = datetime.now()
        uptime = now - self.start_time
        
        summary = {
            'uptime_seconds': uptime.total_seconds(),
            'total_conversations': self.total_conversations,
            'performance_issues': self.performance_issues,
            'current_cpu_percent': psutil.cpu_percent(),
            'current_memory_percent': psutil.virtual_memory().percent,
            'average_conversation_time': sum(self.conversation_times) / len(self.conversation_times) if self.conversation_times else 0,
            'max_conversation_time': max(self.conversation_times) if self.conversation_times else 0,
            'cpu_average': sum(self.cpu_history) / len(self.cpu_history) if self.cpu_history else 0,
            'memory_average': sum(self.memory_history) / len(self.memory_history) if self.memory_history else 0,
        }
        
        return summary
    
    def log_performance_summary(self):
        """记录性能摘要到日志"""
        summary = self.get_performance_summary()
        
        logger.info("=== 性能监控摘要 ===")
        logger.info(f"运行时间: {summary['uptime_seconds']:.0f}秒")
        logger.info(f"总对话数: {summary['total_conversations']}")
        logger.info(f"性能问题数: {summary['performance_issues']}")
        logger.info(f"当前CPU: {summary['current_cpu_percent']:.1f}%")
        logger.info(f"当前内存: {summary['current_memory_percent']:.1f}%")
        logger.info(f"平均对话时间: {summary['average_conversation_time']:.2f}秒")
        logger.info(f"最长对话时间: {summary['max_conversation_time']:.2f}秒")
        logger.info(f"平均CPU使用率: {summary['cpu_average']:.1f}%")
        logger.info(f"平均内存使用率: {summary['memory_average']:.1f}%")

# 全局性能监控实例
performance_monitor = PerformanceMonitor()