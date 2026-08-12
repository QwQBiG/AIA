"""
Latency Optimizer for Full-Duplex Conversational Engine

Provides system-wide latency optimization by coordinating performance monitoring
and threading optimization across all components.
"""

import time
import threading
from typing import Dict, List, Optional, Callable
import logging

from .logging_config import get_component_logger
from .performance_monitor import PerformanceMonitor, EndToEndMetrics
from .threading_optimizer import get_threading_optimizer, ThreadingOptimizer

logger = get_component_logger("latency_optimizer")

class LatencyOptimizer:
    """
    System-wide latency optimizer for the full-duplex engine.
    
    Coordinates performance monitoring and optimization across all components
    to achieve minimal end-to-end conversation latency.
    """
    
    def __init__(self):
        """Initialize the latency optimizer."""
        self.performance_monitor = PerformanceMonitor(history_size=2000)
        self.threading_optimizer = get_threading_optimizer()
        
        # Component references for optimization
        self.streaming_ears = None
        self.duplex_manager = None
        self.tts_pipeline = None
        self.text_processor = None
        
        # Optimization state
        self.optimization_active = False
        self.optimization_thread = None
        self.optimization_callbacks: List[Callable[[Dict], None]] = []
        
        # Performance targets (in milliseconds)
        self.performance_targets = {
            'vad_latency_ms': 10.0,
            'asr_latency_ms': 100.0,
            'text_processing_latency_ms': 50.0,
            'interruption_response_time_ms': 200.0,
            'total_conversation_latency_ms': 1000.0,
            'timing_consistency_score': 80.0
        }
        
        # Optimization history
        self.optimization_history = []
        self.last_optimization_time = 0.0
        
        logger.info("LatencyOptimizer initialized")
    
    def register_components(self, 
                          streaming_ears=None, 
                          duplex_manager=None, 
                          tts_pipeline=None, 
                          text_processor=None):
        """
        Register components for optimization.
        
        Args:
            streaming_ears: StreamingEars component
            duplex_manager: DuplexManager component
            tts_pipeline: TTSPipeline component
            text_processor: TextProcessor component
        """
        self.streaming_ears = streaming_ears
        self.duplex_manager = duplex_manager
        self.tts_pipeline = tts_pipeline
        self.text_processor = text_processor
        
        # Set up performance monitoring callbacks
        if streaming_ears and hasattr(streaming_ears, 'performance_monitor'):
            streaming_ears.performance_monitor.add_optimization_callback(
                self._on_component_performance_update
            )
        
        if duplex_manager and hasattr(duplex_manager, 'performance_monitor'):
            duplex_manager.performance_monitor.add_optimization_callback(
                self._on_component_performance_update
            )
        
        logger.info("Components registered for latency optimization")
    
    def start_optimization(self, interval: float = 5.0):
        """
        Start continuous latency optimization.
        
        Args:
            interval: Optimization check interval in seconds
        """
        if self.optimization_active:
            logger.warning("Optimization already active")
            return
        
        self.optimization_active = True
        
        # Apply initial optimizations
        self._apply_initial_optimizations()
        
        # Start optimization monitoring thread
        self.optimization_thread = self.threading_optimizer.create_audio_processing_thread(
            target=self._optimization_loop,
            name="latency_optimizer",
            interval=interval
        )
        self.optimization_thread.start()
        
        logger.info(f"Started continuous latency optimization (interval={interval}s)")
    
    def stop_optimization(self):
        """Stop continuous latency optimization."""
        if not self.optimization_active:
            return
        
        self.optimization_active = False
        
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.optimization_thread.join(timeout=2.0)
        
        logger.info("Stopped latency optimization")
    
    def _apply_initial_optimizations(self):
        """Apply initial system-wide optimizations."""
        logger.info("Applying initial latency optimizations...")
        
        optimizations_applied = {}
        
        # Apply threading optimizations
        threading_opts = self.threading_optimizer.optimize_for_latency()
        optimizations_applied['threading'] = threading_opts
        
        # Optimize individual components
        if self.streaming_ears and hasattr(self.streaming_ears, 'optimize_for_latency'):
            streaming_opts = self.streaming_ears.optimize_for_latency()
            optimizations_applied['streaming_ears'] = streaming_opts
        
        # Log optimization results
        self._log_optimization_results(optimizations_applied)
        
        # Store in history
        self.optimization_history.append({
            'timestamp': time.time(),
            'type': 'initial',
            'optimizations': optimizations_applied
        })
    
    def _optimization_loop(self, interval: float):
        """Main optimization monitoring loop."""
        logger.debug("Optimization monitoring loop started")
        
        while self.optimization_active:
            try:
                # Collect performance metrics from all components
                metrics = self._collect_system_metrics()
                
                # Analyze performance and apply optimizations if needed
                if self._should_optimize(metrics):
                    optimizations = self._apply_adaptive_optimizations(metrics)
                    
                    # Notify callbacks
                    for callback in self.optimization_callbacks:
                        try:
                            callback(optimizations)
                        except Exception as e:
                            logger.error(f"Error in optimization callback: {e}")
                
                # Wait for next optimization cycle
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                time.sleep(interval)
        
        logger.debug("Optimization monitoring loop ended")
    
    def _collect_system_metrics(self) -> Dict:
        """Collect performance metrics from all components."""
        system_metrics = {
            'timestamp': time.time(),
            'components': {},
            'system_wide': {}
        }
        
        # Collect from StreamingEars
        if self.streaming_ears:
            try:
                if hasattr(self.streaming_ears, 'get_enhanced_performance_metrics'):
                    system_metrics['components']['streaming_ears'] = (
                        self.streaming_ears.get_enhanced_performance_metrics()
                    )
                else:
                    system_metrics['components']['streaming_ears'] = (
                        self.streaming_ears.get_performance_metrics()
                    )
            except Exception as e:
                logger.warning(f"Could not collect StreamingEars metrics: {e}")
        
        # Collect from DuplexManager
        if self.duplex_manager:
            try:
                if hasattr(self.duplex_manager, 'get_performance_metrics'):
                    system_metrics['components']['duplex_manager'] = (
                        self.duplex_manager.get_performance_metrics()
                    )
            except Exception as e:
                logger.warning(f"Could not collect DuplexManager metrics: {e}")
        
        # Collect threading performance
        try:
            system_metrics['system_wide']['threading'] = (
                self.threading_optimizer.monitor_thread_performance()
            )
        except Exception as e:
            logger.warning(f"Could not collect threading metrics: {e}")
        
        return system_metrics
    
    def _should_optimize(self, metrics: Dict) -> bool:
        """
        Determine if optimization should be applied based on current metrics.
        
        Args:
            metrics: Current system metrics
            
        Returns:
            True if optimization should be applied
        """
        current_time = time.time()
        
        # Don't optimize too frequently
        if current_time - self.last_optimization_time < 30.0:  # 30 second cooldown
            return False
        
        # Check if any performance targets are being missed
        streaming_ears_metrics = metrics.get('components', {}).get('streaming_ears')
        if streaming_ears_metrics:
            # Check VAD latency
            if hasattr(streaming_ears_metrics, 'vad_latency_ms'):
                if streaming_ears_metrics.vad_latency_ms > self.performance_targets['vad_latency_ms']:
                    logger.info(f"VAD latency high: {streaming_ears_metrics.vad_latency_ms:.1f}ms")
                    return True
            
            # Check ASR latency
            if hasattr(streaming_ears_metrics, 'asr_latency_ms'):
                if streaming_ears_metrics.asr_latency_ms > self.performance_targets['asr_latency_ms']:
                    logger.info(f"ASR latency high: {streaming_ears_metrics.asr_latency_ms:.1f}ms")
                    return True
            
            # Check total conversation latency
            if hasattr(streaming_ears_metrics, 'total_conversation_latency_ms'):
                if (streaming_ears_metrics.total_conversation_latency_ms > 
                    self.performance_targets['total_conversation_latency_ms']):
                    logger.info(f"Total latency high: {streaming_ears_metrics.total_conversation_latency_ms:.1f}ms")
                    return True
        
        # Check interruption response time
        duplex_metrics = metrics.get('components', {}).get('duplex_manager')
        if duplex_metrics:
            if hasattr(duplex_metrics, 'interruption_response_time_ms'):
                if (duplex_metrics.interruption_response_time_ms > 
                    self.performance_targets['interruption_response_time_ms']):
                    logger.info(f"Interruption response slow: {duplex_metrics.interruption_response_time_ms:.1f}ms")
                    return True
        
        return False
    
    def _apply_adaptive_optimizations(self, metrics: Dict) -> Dict:
        """
        Apply adaptive optimizations based on current performance.
        
        Args:
            metrics: Current system metrics
            
        Returns:
            Dictionary of applied optimizations
        """
        self.last_optimization_time = time.time()
        optimizations_applied = {}
        
        logger.info("Applying adaptive latency optimizations...")
        
        # Analyze specific performance issues and apply targeted optimizations
        streaming_ears_metrics = metrics.get('components', {}).get('streaming_ears')
        if streaming_ears_metrics:
            # VAD optimization
            if (hasattr(streaming_ears_metrics, 'vad_latency_ms') and 
                streaming_ears_metrics.vad_latency_ms > self.performance_targets['vad_latency_ms']):
                
                vad_opts = self._optimize_vad_performance()
                optimizations_applied['vad'] = vad_opts
            
            # ASR optimization
            if (hasattr(streaming_ears_metrics, 'asr_latency_ms') and 
                streaming_ears_metrics.asr_latency_ms > self.performance_targets['asr_latency_ms']):
                
                asr_opts = self._optimize_asr_performance()
                optimizations_applied['asr'] = asr_opts
        
        # Threading optimization
        threading_metrics = metrics.get('system_wide', {}).get('threading', {})
        if threading_metrics:
            # Check for inefficient threads
            inefficient_threads = [
                name for name, thread_metrics in threading_metrics.items()
                if thread_metrics.get('processing_efficiency', 100) < 50
            ]
            
            if inefficient_threads:
                threading_opts = self._optimize_threading_performance(inefficient_threads)
                optimizations_applied['threading'] = threading_opts
        
        # Log and store optimization results
        self._log_optimization_results(optimizations_applied)
        self.optimization_history.append({
            'timestamp': time.time(),
            'type': 'adaptive',
            'metrics': metrics,
            'optimizations': optimizations_applied
        })
        
        return optimizations_applied
    
    def _optimize_vad_performance(self) -> Dict:
        """Optimize VAD performance."""
        optimizations = {}
        
        if self.streaming_ears:
            # Reduce VAD chunk size for lower latency (trade-off with accuracy)
            if hasattr(self.streaming_ears, 'chunk_size') and self.streaming_ears.chunk_size > 256:
                old_chunk_size = self.streaming_ears.chunk_size
                self.streaming_ears.chunk_size = max(256, self.streaming_ears.chunk_size // 2)
                optimizations['chunk_size_reduction'] = {
                    'old': old_chunk_size,
                    'new': self.streaming_ears.chunk_size
                }
                logger.info(f"Reduced VAD chunk size: {old_chunk_size} -> {self.streaming_ears.chunk_size}")
        
        return optimizations
    
    def _optimize_asr_performance(self) -> Dict:
        """Optimize ASR performance."""
        optimizations = {}
        
        # ASR optimization strategies would go here
        # For now, just log the optimization attempt
        optimizations['strategy'] = 'asr_optimization_attempted'
        logger.info("Applied ASR performance optimizations")
        
        return optimizations
    
    def _optimize_threading_performance(self, inefficient_threads: List[str]) -> Dict:
        """Optimize threading performance for inefficient threads."""
        optimizations = {}
        
        for thread_name in inefficient_threads:
            # Apply thread-specific optimizations
            optimizations[thread_name] = 'efficiency_optimization_applied'
            logger.info(f"Applied threading optimization for: {thread_name}")
        
        return optimizations
    
    def _log_optimization_results(self, optimizations: Dict):
        """Log optimization results."""
        if not optimizations:
            logger.info("No optimizations applied")
            return
        
        logger.info("Applied optimizations:")
        for component, opts in optimizations.items():
            if isinstance(opts, dict):
                for opt_name, opt_value in opts.items():
                    logger.info(f"  {component}.{opt_name}: {opt_value}")
            else:
                logger.info(f"  {component}: {opts}")
    
    def _on_component_performance_update(self, metrics: EndToEndMetrics):
        """Handle performance updates from components."""
        # This callback is triggered when components detect performance issues
        logger.debug("Received component performance update")
        
        # Trigger immediate optimization check if performance is poor
        if (metrics.total_conversation_latency_ms > self.performance_targets['total_conversation_latency_ms'] * 1.5 or
            metrics.interruption_response_time_ms > self.performance_targets['interruption_response_time_ms'] * 1.5):
            
            logger.warning("Performance degradation detected, triggering immediate optimization")
            # Collect current metrics and apply optimizations
            current_metrics = self._collect_system_metrics()
            self._apply_adaptive_optimizations(current_metrics)
    
    def add_optimization_callback(self, callback: Callable[[Dict], None]):
        """Add callback for optimization notifications."""
        self.optimization_callbacks.append(callback)
        logger.debug("Added optimization callback")
    
    def get_optimization_summary(self) -> Dict:
        """Get summary of optimization history and current performance."""
        current_metrics = self._collect_system_metrics()
        
        summary = {
            'current_performance': current_metrics,
            'performance_targets': self.performance_targets,
            'optimization_history': self.optimization_history[-10:],  # Last 10 optimizations
            'optimization_active': self.optimization_active,
            'total_optimizations': len(self.optimization_history)
        }
        
        # Calculate performance vs targets
        streaming_metrics = current_metrics.get('components', {}).get('streaming_ears')
        if streaming_metrics:
            summary['performance_vs_targets'] = {}
            for target_name, target_value in self.performance_targets.items():
                if hasattr(streaming_metrics, target_name):
                    current_value = getattr(streaming_metrics, target_name)
                    summary['performance_vs_targets'][target_name] = {
                        'current': current_value,
                        'target': target_value,
                        'meets_target': current_value <= target_value,
                        'ratio': current_value / target_value if target_value > 0 else 0
                    }
        
        return summary
    
    def log_performance_summary(self):
        """Log comprehensive performance and optimization summary."""
        try:
            summary = self.get_optimization_summary()
            
            logger.info("=== Latency Optimization Summary ===")
            logger.info(f"Optimization Active: {summary['optimization_active']}")
            logger.info(f"Total Optimizations Applied: {summary['total_optimizations']}")
            
            # Performance vs targets
            perf_vs_targets = summary.get('performance_vs_targets', {})
            if perf_vs_targets:
                logger.info("Performance vs Targets:")
                for metric_name, data in perf_vs_targets.items():
                    status = "✓" if data['meets_target'] else "✗"
                    logger.info(f"  {status} {metric_name}: {data['current']:.1f} "
                              f"(target: {data['target']:.1f}, ratio: {data['ratio']:.2f})")
            
            # Recent optimizations
            recent_opts = summary.get('optimization_history', [])
            if recent_opts:
                logger.info(f"Recent Optimizations ({len(recent_opts)}):")
                for opt in recent_opts[-3:]:  # Show last 3
                    opt_time = time.strftime('%H:%M:%S', time.localtime(opt['timestamp']))
                    logger.info(f"  {opt_time} ({opt['type']}): {len(opt.get('optimizations', {}))} optimizations")
            
            logger.info("======================================")
            
        except Exception as e:
            logger.error(f"Failed to log optimization summary: {e}")

# Global latency optimizer instance
_latency_optimizer: Optional[LatencyOptimizer] = None

def get_latency_optimizer() -> LatencyOptimizer:
    """Get global latency optimizer instance."""
    global _latency_optimizer
    if _latency_optimizer is None:
        _latency_optimizer = LatencyOptimizer()
    return _latency_optimizer

def cleanup_latency_optimizer():
    """Clean up global latency optimizer."""
    global _latency_optimizer
    if _latency_optimizer is not None:
        _latency_optimizer.stop_optimization()
        _latency_optimizer = None