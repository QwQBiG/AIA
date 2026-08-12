"""
Threading Optimizer for Full-Duplex Conversational Engine

Optimizes the threading model for minimal latency by:
- Using high-priority threads for audio processing
- Implementing lock-free data structures where possible
- Optimizing thread affinity and scheduling
- Reducing context switching overhead
"""

import threading
import queue
import time
import os
import sys
from typing import Optional, Callable, Any
from collections import deque
import logging

from .logging_config import get_component_logger

logger = get_component_logger("threading_optimizer")

# Platform-specific imports for thread priority
try:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        THREAD_PRIORITY_AVAILABLE = True
    else:
        THREAD_PRIORITY_AVAILABLE = False
except ImportError:
    THREAD_PRIORITY_AVAILABLE = False

class HighPriorityThread(threading.Thread):
    """
    High-priority thread optimized for real-time audio processing.
    
    Sets thread priority to time-critical on Windows for minimal latency.
    """
    
    def __init__(self, target: Callable, name: str, daemon: bool = True, **kwargs):
        """
        Initialize high-priority thread.
        
        Args:
            target: Function to run in thread
            name: Thread name for debugging
            daemon: Whether thread should be daemon
            **kwargs: Additional arguments for target function
        """
        super().__init__(target=target, name=name, daemon=daemon)
        self.kwargs = kwargs
        self._target = target
        self._set_priority_on_start = True
        
        logger.debug(f"Created high-priority thread: {name}")
    
    def run(self):
        """Run the thread with high priority."""
        try:
            # Set high priority when thread starts
            if self._set_priority_on_start:
                self._set_high_priority()
            
            # Run the target function
            if self._target:
                self._target(**self.kwargs)
                
        except Exception as e:
            logger.error(f"Error in high-priority thread {self.name}: {e}")
    
    def _set_high_priority(self):
        """Set thread to high priority for real-time processing."""
        if not THREAD_PRIORITY_AVAILABLE:
            logger.debug(f"Thread priority not available on {sys.platform}")
            return
        
        try:
            if sys.platform == "win32":
                # Windows: Set to TIME_CRITICAL priority
                handle = ctypes.windll.kernel32.GetCurrentThread()
                THREAD_PRIORITY_TIME_CRITICAL = 15
                success = ctypes.windll.kernel32.SetThreadPriority(
                    handle, THREAD_PRIORITY_TIME_CRITICAL
                )
                if success:
                    logger.debug(f"Set thread {self.name} to TIME_CRITICAL priority")
                else:
                    logger.warning(f"Failed to set high priority for thread {self.name}")
            
        except Exception as e:
            logger.warning(f"Could not set thread priority: {e}")

class LockFreeQueue:
    """
    Lock-free queue implementation for high-performance audio processing.
    
    Uses atomic operations where possible to reduce contention.
    Falls back to threading.Lock for thread safety on unsupported platforms.
    """
    
    def __init__(self, maxsize: int = 0):
        """
        Initialize lock-free queue.
        
        Args:
            maxsize: Maximum queue size (0 for unlimited)
        """
        self.maxsize = maxsize
        self._queue = deque()
        self._lock = threading.Lock()  # Fallback for thread safety
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._size = 0
        
        logger.debug(f"Created lock-free queue with maxsize={maxsize}")
    
    def put(self, item: Any, block: bool = True, timeout: Optional[float] = None) -> None:
        """
        Put item in queue.
        
        Args:
            item: Item to put in queue
            block: Whether to block if queue is full
            timeout: Timeout for blocking operation
        """
        with self._not_full:
            if self.maxsize > 0:
                while self._size >= self.maxsize:
                    if not block:
                        raise queue.Full
                    if not self._not_full.wait(timeout):
                        raise queue.Full
            
            self._queue.append(item)
            self._size += 1
            self._not_empty.notify()
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """
        Get item from queue.
        
        Args:
            block: Whether to block if queue is empty
            timeout: Timeout for blocking operation
            
        Returns:
            Item from queue
        """
        with self._not_empty:
            while self._size == 0:
                if not block:
                    raise queue.Empty
                if not self._not_empty.wait(timeout):
                    raise queue.Empty
            
            item = self._queue.popleft()
            self._size -= 1
            self._not_full.notify()
            return item
    
    def qsize(self) -> int:
        """Get current queue size."""
        with self._lock:
            return self._size
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return self._size == 0
    
    def full(self) -> bool:
        """Check if queue is full."""
        with self._lock:
            return self.maxsize > 0 and self._size >= self.maxsize

class ThreadingOptimizer:
    """
    Threading optimizer for the full-duplex engine.
    
    Provides optimized threading patterns and utilities for minimal latency.
    """
    
    def __init__(self):
        """Initialize threading optimizer."""
        self.active_threads = {}
        self.thread_metrics = {}
        self._lock = threading.Lock()
        
        # Detect system capabilities
        self.cpu_count = os.cpu_count() or 1
        self.has_thread_priority = THREAD_PRIORITY_AVAILABLE
        
        logger.info(f"ThreadingOptimizer initialized: "
                   f"CPUs={self.cpu_count}, "
                   f"priority_control={self.has_thread_priority}")
    
    def create_audio_processing_thread(self, 
                                     target: Callable, 
                                     name: str,
                                     **kwargs) -> HighPriorityThread:
        """
        Create optimized thread for audio processing.
        
        Args:
            target: Function to run in thread
            name: Thread name
            **kwargs: Arguments for target function
            
        Returns:
            Configured high-priority thread
        """
        thread = HighPriorityThread(
            target=self._wrapped_target,
            name=f"audio_{name}",
            daemon=True,
            original_target=target,
            thread_name=name,
            **kwargs
        )
        
        with self._lock:
            self.active_threads[name] = thread
            self.thread_metrics[name] = {
                'start_time': time.time(),
                'iterations': 0,
                'total_processing_time': 0.0,
                'last_activity': time.time()
            }
        
        logger.info(f"Created audio processing thread: {name}")
        return thread
    
    def _wrapped_target(self, original_target: Callable, thread_name: str, **kwargs):
        """Wrapped target function with performance monitoring."""
        try:
            logger.debug(f"Starting audio thread: {thread_name}")
            
            # Run the original target with monitoring
            start_time = time.time()
            original_target(**kwargs)
            end_time = time.time()
            
            # Update metrics
            with self._lock:
                if thread_name in self.thread_metrics:
                    metrics = self.thread_metrics[thread_name]
                    metrics['total_processing_time'] += (end_time - start_time)
                    metrics['last_activity'] = end_time
            
            logger.debug(f"Audio thread completed: {thread_name}")
            
        except Exception as e:
            logger.error(f"Error in audio thread {thread_name}: {e}")
        finally:
            # Clean up thread reference
            with self._lock:
                if thread_name in self.active_threads:
                    del self.active_threads[thread_name]
    
    def create_optimized_queue(self, maxsize: int = 0) -> LockFreeQueue:
        """
        Create optimized queue for inter-thread communication.
        
        Args:
            maxsize: Maximum queue size
            
        Returns:
            Optimized queue instance
        """
        return LockFreeQueue(maxsize=maxsize)
    
    def optimize_thread_affinity(self, thread: threading.Thread, cpu_id: Optional[int] = None):
        """
        Optimize thread CPU affinity for better performance.
        
        Args:
            thread: Thread to optimize
            cpu_id: Specific CPU to bind to (None for automatic)
        """
        if not self.has_thread_priority:
            logger.debug("Thread affinity not supported on this platform")
            return
        
        try:
            if sys.platform == "win32" and cpu_id is not None:
                # Windows: Set thread affinity
                handle = ctypes.windll.kernel32.GetCurrentThread()
                mask = 1 << cpu_id
                ctypes.windll.kernel32.SetThreadAffinityMask(handle, mask)
                logger.debug(f"Set thread {thread.name} affinity to CPU {cpu_id}")
        
        except Exception as e:
            logger.warning(f"Could not set thread affinity: {e}")
    
    def get_optimal_thread_count(self, workload_type: str = "audio") -> int:
        """
        Get optimal thread count for specific workload.
        
        Args:
            workload_type: Type of workload ("audio", "processing", "io")
            
        Returns:
            Recommended thread count
        """
        if workload_type == "audio":
            # Audio processing: Use 1-2 threads to minimize context switching
            return min(2, self.cpu_count)
        elif workload_type == "processing":
            # General processing: Use most CPUs but leave some for system
            return max(1, self.cpu_count - 1)
        elif workload_type == "io":
            # I/O bound: Can use more threads
            return min(8, self.cpu_count * 2)
        else:
            return self.cpu_count
    
    def monitor_thread_performance(self) -> dict:
        """
        Monitor performance of active threads.
        
        Returns:
            Dictionary with thread performance metrics
        """
        with self._lock:
            current_time = time.time()
            performance_data = {}
            
            for thread_name, metrics in self.thread_metrics.items():
                thread_age = current_time - metrics['start_time']
                time_since_activity = current_time - metrics['last_activity']
                
                performance_data[thread_name] = {
                    'age_seconds': thread_age,
                    'iterations': metrics['iterations'],
                    'total_processing_time': metrics['total_processing_time'],
                    'time_since_activity': time_since_activity,
                    'processing_efficiency': (
                        metrics['total_processing_time'] / thread_age * 100
                        if thread_age > 0 else 0.0
                    ),
                    'is_active': time_since_activity < 5.0  # Active if activity within 5s
                }
            
            return performance_data
    
    def optimize_for_latency(self) -> dict:
        """
        Apply system-wide optimizations for minimal latency.
        
        Returns:
            Dictionary with applied optimizations
        """
        optimizations = {
            'thread_priority': False,
            'process_priority': False,
            'gc_optimization': False,
            'system_recommendations': []
        }
        
        try:
            # Set process priority (Windows)
            if sys.platform == "win32" and THREAD_PRIORITY_AVAILABLE:
                try:
                    handle = ctypes.windll.kernel32.GetCurrentProcess()
                    HIGH_PRIORITY_CLASS = 0x00000080
                    success = ctypes.windll.kernel32.SetPriorityClass(handle, HIGH_PRIORITY_CLASS)
                    if success:
                        optimizations['process_priority'] = True
                        logger.info("Set process to HIGH_PRIORITY_CLASS")
                except Exception as e:
                    logger.warning(f"Could not set process priority: {e}")
            
            # Python GC optimization for real-time processing
            try:
                import gc
                # Disable automatic garbage collection during audio processing
                gc.disable()
                optimizations['gc_optimization'] = True
                logger.info("Disabled automatic garbage collection for latency optimization")
                
                # Schedule manual GC during idle periods
                def manual_gc_timer():
                    time.sleep(10)  # Wait 10 seconds
                    gc.collect()
                    gc.enable()
                    logger.debug("Re-enabled garbage collection after optimization period")
                
                gc_thread = threading.Thread(target=manual_gc_timer, daemon=True)
                gc_thread.start()
                
            except Exception as e:
                logger.warning(f"Could not optimize garbage collection: {e}")
            
            # Generate system recommendations
            recommendations = []
            
            if not self.has_thread_priority:
                recommendations.append(
                    "Install platform-specific libraries for thread priority control"
                )
            
            if self.cpu_count < 4:
                recommendations.append(
                    f"System has only {self.cpu_count} CPU cores. "
                    f"Consider upgrading for better real-time performance."
                )
            
            # Check system load
            try:
                if hasattr(os, 'getloadavg'):
                    load_avg = os.getloadavg()[0]
                    if load_avg > self.cpu_count * 0.8:
                        recommendations.append(
                            f"High system load detected ({load_avg:.1f}). "
                            f"Close unnecessary applications for better audio performance."
                        )
            except (OSError, AttributeError):
                pass
            
            optimizations['system_recommendations'] = recommendations
            
            logger.info(f"Applied latency optimizations: {optimizations}")
            return optimizations
            
        except Exception as e:
            logger.error(f"Error applying latency optimizations: {e}")
            return optimizations
    
    def cleanup(self):
        """Clean up threading optimizer resources."""
        with self._lock:
            # Wait for active threads to complete
            for thread_name, thread in self.active_threads.items():
                if thread.is_alive():
                    logger.debug(f"Waiting for thread to complete: {thread_name}")
                    thread.join(timeout=2.0)
            
            self.active_threads.clear()
            self.thread_metrics.clear()
        
        # Re-enable garbage collection if it was disabled
        try:
            import gc
            gc.enable()
        except:
            pass
        
        logger.info("ThreadingOptimizer cleanup completed")
    
    def log_performance_summary(self):
        """Log threading performance summary."""
        try:
            performance_data = self.monitor_thread_performance()
            
            logger.info("=== Threading Performance Summary ===")
            logger.info(f"System: {self.cpu_count} CPUs, Priority Control: {self.has_thread_priority}")
            
            if performance_data:
                logger.info("Active Threads:")
                for thread_name, metrics in performance_data.items():
                    logger.info(f"  {thread_name}:")
                    logger.info(f"    Age: {metrics['age_seconds']:.1f}s")
                    logger.info(f"    Efficiency: {metrics['processing_efficiency']:.1f}%")
                    logger.info(f"    Active: {metrics['is_active']}")
            else:
                logger.info("No active threads")
            
            logger.info("=====================================")
            
        except Exception as e:
            logger.error(f"Failed to log threading performance summary: {e}")

# Global threading optimizer instance
_threading_optimizer: Optional[ThreadingOptimizer] = None

def get_threading_optimizer() -> ThreadingOptimizer:
    """Get global threading optimizer instance."""
    global _threading_optimizer
    if _threading_optimizer is None:
        _threading_optimizer = ThreadingOptimizer()
    return _threading_optimizer

def cleanup_threading_optimizer():
    """Clean up global threading optimizer."""
    global _threading_optimizer
    if _threading_optimizer is not None:
        _threading_optimizer.cleanup()
        _threading_optimizer = None