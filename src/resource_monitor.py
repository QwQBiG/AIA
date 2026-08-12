"""
Resource Monitor for AI VTuber Vision-Action Agent

This module provides CPU and memory usage tracking, automatic performance scaling,
and rate limiting for VLM requests to prevent resource exhaustion.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

import psutil


@dataclass
class ResourceMetrics:
    """Current system resource metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    timestamp: datetime
    
    # Process-specific metrics
    process_cpu_percent: float = 0.0
    process_memory_mb: float = 0.0
    process_threads: int = 0


@dataclass
class PerformanceThresholds:
    """Performance thresholds for automatic scaling"""
    cpu_high: float = 80.0  # CPU usage above this triggers scaling
    cpu_critical: float = 90.0  # CPU usage above this triggers emergency scaling
    memory_high: float = 85.0  # Memory usage above this triggers scaling
    memory_critical: float = 95.0  # Memory usage above this triggers emergency scaling
    
    # Rate limiting thresholds
    vlm_requests_per_minute: int = 30  # Max VLM requests per minute
    vlm_requests_per_hour: int = 1000  # Max VLM requests per hour
    
    # Performance scaling factors
    scale_factor_moderate: float = 1.5  # Multiply intervals by this when resources are high
    scale_factor_aggressive: float = 3.0  # Multiply intervals by this when resources are critical


class ResourceMonitor:
    """Monitors system resources and provides automatic performance scaling"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ResourceMonitor with configuration
        
        Args:
            config: Configuration dictionary containing monitoring settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Performance thresholds
        thresholds_config = config.get('performance_thresholds', {})
        self.thresholds = PerformanceThresholds(
            cpu_high=thresholds_config.get('cpu_high', 80.0),
            cpu_critical=thresholds_config.get('cpu_critical', 90.0),
            memory_high=thresholds_config.get('memory_high', 85.0),
            memory_critical=thresholds_config.get('memory_critical', 95.0),
            vlm_requests_per_minute=thresholds_config.get('vlm_requests_per_minute', 30),
            vlm_requests_per_hour=thresholds_config.get('vlm_requests_per_hour', 1000),
            scale_factor_moderate=thresholds_config.get('scale_factor_moderate', 1.5),
            scale_factor_aggressive=thresholds_config.get('scale_factor_aggressive', 3.0)
        )
        
        # Monitoring settings
        self.monitoring_interval = config.get('monitoring_interval', 5.0)  # seconds
        self.history_size = config.get('history_size', 60)  # Keep 60 samples (5 minutes at 5s intervals)
        
        # Resource tracking
        self.metrics_history: deque = deque(maxlen=self.history_size)
        self.current_metrics: Optional[ResourceMetrics] = None
        
        # Process tracking
        self.process = psutil.Process()
        self.baseline_metrics: Optional[ResourceMetrics] = None
        
        # Rate limiting for VLM requests
        self.vlm_request_times: deque = deque()  # Track request timestamps
        self.vlm_request_lock = threading.Lock()
        
        # Performance scaling state
        self.current_scale_factor = 1.0
        self.last_scale_change = datetime.now()
        self.scale_change_cooldown = timedelta(seconds=30)  # Minimum time between scale changes
        
        # Monitoring thread
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # Callbacks for performance scaling
        self.scale_callbacks: list = []
        
        self.logger.info("ResourceMonitor initialized")
    
    def start_monitoring(self):
        """Start resource monitoring in background thread"""
        if self.monitoring_active:
            self.logger.warning("Resource monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        # Capture baseline metrics
        self._capture_baseline_metrics()
        
        self.logger.info("Resource monitoring started")
    
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2.0)
        
        self.logger.info("Resource monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop (runs in background thread)"""
        while self.monitoring_active:
            try:
                # Capture current metrics
                metrics = self._capture_metrics()
                
                # Store in history
                self.metrics_history.append(metrics)
                self.current_metrics = metrics
                
                # Check for performance scaling needs
                self._check_performance_scaling(metrics)
                
                # Clean up old VLM request timestamps
                self._cleanup_vlm_request_history()
                
                # Wait for next monitoring cycle
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(self.monitoring_interval * 2)  # Wait longer on error
    
    def _capture_metrics(self) -> ResourceMetrics:
        """Capture current system and process metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network_io = psutil.net_io_counters()
            
            # Process metrics
            process_cpu = self.process.cpu_percent()
            process_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
            process_threads = self.process.num_threads()
            
            return ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_io_read_mb=(disk_io.read_bytes / (1024 * 1024)) if disk_io else 0.0,
                disk_io_write_mb=(disk_io.write_bytes / (1024 * 1024)) if disk_io else 0.0,
                network_sent_mb=(network_io.bytes_sent / (1024 * 1024)) if network_io else 0.0,
                network_recv_mb=(network_io.bytes_recv / (1024 * 1024)) if network_io else 0.0,
                timestamp=datetime.now(),
                process_cpu_percent=process_cpu,
                process_memory_mb=process_memory,
                process_threads=process_threads
            )
            
        except Exception as e:
            self.logger.error(f"Failed to capture metrics: {e}")
            # Return safe default metrics
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=1024.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                timestamp=datetime.now()
            )
    
    def _capture_baseline_metrics(self):
        """Capture baseline metrics for comparison"""
        try:
            self.baseline_metrics = self._capture_metrics()
            self.logger.info(f"Baseline metrics captured: CPU {self.baseline_metrics.cpu_percent:.1f}%, "
                           f"Memory {self.baseline_metrics.memory_percent:.1f}%")
        except Exception as e:
            self.logger.error(f"Failed to capture baseline metrics: {e}")
    
    def _check_performance_scaling(self, metrics: ResourceMetrics):
        """Check if performance scaling is needed based on current metrics"""
        try:
            # Calculate average metrics over recent history
            if len(self.metrics_history) < 3:
                return  # Need some history for reliable scaling decisions
            
            recent_metrics = list(self.metrics_history)[-5:]  # Last 5 samples
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            
            # Determine required scale factor
            new_scale_factor = 1.0
            
            # Check critical thresholds first
            if avg_cpu >= self.thresholds.cpu_critical or avg_memory >= self.thresholds.memory_critical:
                new_scale_factor = self.thresholds.scale_factor_aggressive
                self.logger.warning(f"Critical resource usage detected: CPU {avg_cpu:.1f}%, Memory {avg_memory:.1f}%")
            
            # Check high thresholds
            elif avg_cpu >= self.thresholds.cpu_high or avg_memory >= self.thresholds.memory_high:
                new_scale_factor = self.thresholds.scale_factor_moderate
                self.logger.info(f"High resource usage detected: CPU {avg_cpu:.1f}%, Memory {avg_memory:.1f}%")
            
            # Apply scaling if needed and cooldown has passed
            if (new_scale_factor != self.current_scale_factor and 
                datetime.now() - self.last_scale_change >= self.scale_change_cooldown):
                
                self._apply_performance_scaling(new_scale_factor, avg_cpu, avg_memory)
            
        except Exception as e:
            self.logger.error(f"Error checking performance scaling: {e}")
    
    def _apply_performance_scaling(self, scale_factor: float, cpu_percent: float, memory_percent: float):
        """Apply performance scaling by notifying registered callbacks"""
        try:
            old_scale = self.current_scale_factor
            self.current_scale_factor = scale_factor
            self.last_scale_change = datetime.now()
            
            # Notify all registered callbacks
            for callback in self.scale_callbacks:
                try:
                    callback(scale_factor, cpu_percent, memory_percent)
                except Exception as e:
                    self.logger.error(f"Error in scale callback: {e}")
            
            self.logger.info(f"Performance scaling applied: {old_scale:.1f}x -> {scale_factor:.1f}x "
                           f"(CPU: {cpu_percent:.1f}%, Memory: {memory_percent:.1f}%)")
            
        except Exception as e:
            self.logger.error(f"Error applying performance scaling: {e}")
    
    def register_scale_callback(self, callback: Callable[[float, float, float], None]):
        """
        Register callback for performance scaling events
        
        Args:
            callback: Function that takes (scale_factor, cpu_percent, memory_percent)
        """
        self.scale_callbacks.append(callback)
        self.logger.debug("Performance scaling callback registered")
    
    def can_make_vlm_request(self) -> bool:
        """
        Check if a VLM request can be made based on rate limiting
        
        Returns:
            True if request is allowed, False if rate limited
        """
        with self.vlm_request_lock:
            now = datetime.now()
            
            # Clean up old requests
            self._cleanup_vlm_request_history()
            
            # Check per-minute limit
            minute_ago = now - timedelta(minutes=1)
            recent_requests = sum(1 for req_time in self.vlm_request_times if req_time >= minute_ago)
            
            if recent_requests >= self.thresholds.vlm_requests_per_minute:
                self.logger.warning(f"VLM request rate limited: {recent_requests} requests in last minute")
                return False
            
            # Check per-hour limit
            hour_ago = now - timedelta(hours=1)
            hourly_requests = sum(1 for req_time in self.vlm_request_times if req_time >= hour_ago)
            
            if hourly_requests >= self.thresholds.vlm_requests_per_hour:
                self.logger.warning(f"VLM request rate limited: {hourly_requests} requests in last hour")
                return False
            
            return True
    
    def record_vlm_request(self):
        """Record a VLM request for rate limiting tracking"""
        with self.vlm_request_lock:
            self.vlm_request_times.append(datetime.now())
            self.logger.debug(f"VLM request recorded, total tracked: {len(self.vlm_request_times)}")
    
    def _cleanup_vlm_request_history(self):
        """Clean up old VLM request timestamps"""
        cutoff_time = datetime.now() - timedelta(hours=2)  # Keep 2 hours of history
        
        # Remove old timestamps
        while self.vlm_request_times and self.vlm_request_times[0] < cutoff_time:
            self.vlm_request_times.popleft()
    
    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """Get current resource metrics"""
        return self.current_metrics
    
    def get_metrics_history(self) -> list:
        """Get historical resource metrics"""
        return list(self.metrics_history)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        if not self.current_metrics:
            return {"status": "no_data", "message": "No metrics available"}
        
        try:
            # Calculate averages over recent history
            if self.metrics_history:
                recent_metrics = list(self.metrics_history)[-10:]  # Last 10 samples
                avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
                avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
                avg_process_cpu = sum(m.process_cpu_percent for m in recent_metrics) / len(recent_metrics)
                avg_process_memory = sum(m.process_memory_mb for m in recent_metrics) / len(recent_metrics)
            else:
                avg_cpu = self.current_metrics.cpu_percent
                avg_memory = self.current_metrics.memory_percent
                avg_process_cpu = self.current_metrics.process_cpu_percent
                avg_process_memory = self.current_metrics.process_memory_mb
            
            # Determine performance status
            status = "optimal"
            if (avg_cpu >= self.thresholds.cpu_critical or 
                avg_memory >= self.thresholds.memory_critical):
                status = "critical"
            elif (avg_cpu >= self.thresholds.cpu_high or 
                  avg_memory >= self.thresholds.memory_high):
                status = "degraded"
            
            # VLM rate limiting status
            with self.vlm_request_lock:
                minute_ago = datetime.now() - timedelta(minutes=1)
                recent_vlm_requests = sum(1 for req_time in self.vlm_request_times if req_time >= minute_ago)
            
            return {
                "status": status,
                "current_scale_factor": self.current_scale_factor,
                "system_metrics": {
                    "cpu_percent": self.current_metrics.cpu_percent,
                    "memory_percent": self.current_metrics.memory_percent,
                    "memory_available_mb": self.current_metrics.memory_available_mb,
                    "avg_cpu_percent": avg_cpu,
                    "avg_memory_percent": avg_memory
                },
                "process_metrics": {
                    "cpu_percent": self.current_metrics.process_cpu_percent,
                    "memory_mb": self.current_metrics.process_memory_mb,
                    "threads": self.current_metrics.process_threads,
                    "avg_cpu_percent": avg_process_cpu,
                    "avg_memory_mb": avg_process_memory
                },
                "rate_limiting": {
                    "vlm_requests_last_minute": recent_vlm_requests,
                    "vlm_requests_limit_minute": self.thresholds.vlm_requests_per_minute,
                    "vlm_requests_remaining": max(0, self.thresholds.vlm_requests_per_minute - recent_vlm_requests),
                    "can_make_request": self.can_make_vlm_request()
                },
                "thresholds": {
                    "cpu_high": self.thresholds.cpu_high,
                    "cpu_critical": self.thresholds.cpu_critical,
                    "memory_high": self.thresholds.memory_high,
                    "memory_critical": self.thresholds.memory_critical
                },
                "monitoring": {
                    "active": self.monitoring_active,
                    "samples_collected": len(self.metrics_history),
                    "last_update": self.current_metrics.timestamp.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating performance summary: {e}")
            return {"status": "error", "message": str(e)}
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_monitoring()
        self.logger.info("ResourceMonitor cleanup complete")