"""
Comprehensive Error Handler for Full-Duplex Conversational Engine

Provides centralized error handling, recovery mechanisms, and graceful degradation
for all full-duplex engine components.
"""

import logging
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from collections import deque
import traceback

from .logging_config import get_component_logger

logger = get_component_logger("error_handler")

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification."""
    AUDIO_HARDWARE = "audio_hardware"
    MODEL_LOADING = "model_loading"
    PROCESSING = "processing"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    THREADING = "threading"
    MEMORY = "memory"
    UNKNOWN = "unknown"

@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    timestamp: float
    component: str
    error_type: str
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception: Optional[Exception] = None
    traceback_str: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    metadata: Dict = field(default_factory=dict)

@dataclass
class RecoveryStrategy:
    """Recovery strategy for specific error types."""
    name: str
    description: str
    handler: Callable
    max_attempts: int = 3
    cooldown_seconds: float = 5.0
    severity_threshold: ErrorSeverity = ErrorSeverity.MEDIUM

class FullDuplexErrorHandler:
    """
    Comprehensive error handler for the full-duplex engine.
    
    Provides centralized error logging, recovery mechanisms, and graceful degradation.
    """
    
    def __init__(self, max_error_history: int = 1000):
        """
        Initialize error handler.
        
        Args:
            max_error_history: Maximum number of error records to keep
        """
        self.max_error_history = max_error_history
        
        # Error tracking
        self.error_history = deque(maxlen=max_error_history)
        self.error_counts = {}
        self.consecutive_errors = {}
        self.last_error_times = {}
        
        # Recovery strategies
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {}
        self.recovery_attempts = {}
        
        # Component states
        self.component_states = {}
        self.fallback_states = {}
        
        # Threading for thread-safe operations
        self.lock = threading.Lock()
        
        # Error callbacks
        self.error_callbacks: List[Callable[[ErrorRecord], None]] = []
        self.recovery_callbacks: List[Callable[[str, bool], None]] = []
        
        # Initialize default recovery strategies
        self._initialize_default_strategies()
        
        logger.info("FullDuplexErrorHandler initialized")
    
    def _initialize_default_strategies(self):
        """Initialize default recovery strategies."""
        
        # VAD model recovery
        self.register_recovery_strategy(RecoveryStrategy(
            name="vad_model_recovery",
            description="Recover VAD model by reinitializing or falling back to basic detection",
            handler=self._recover_vad_model,
            max_attempts=3,
            cooldown_seconds=10.0,
            severity_threshold=ErrorSeverity.MEDIUM
        ))
        
        # ASR model recovery
        self.register_recovery_strategy(RecoveryStrategy(
            name="asr_model_recovery",
            description="Recover ASR model by reinitializing or using cached version",
            handler=self._recover_asr_model,
            max_attempts=2,
            cooldown_seconds=30.0,
            severity_threshold=ErrorSeverity.HIGH
        ))
        
        # Audio device recovery
        self.register_recovery_strategy(RecoveryStrategy(
            name="audio_device_recovery",
            description="Recover audio device by reinitializing or switching devices",
            handler=self._recover_audio_device,
            max_attempts=3,
            cooldown_seconds=5.0,
            severity_threshold=ErrorSeverity.HIGH
        ))
        
        # Memory recovery
        self.register_recovery_strategy(RecoveryStrategy(
            name="memory_recovery",
            description="Recover from memory issues by clearing caches and forcing GC",
            handler=self._recover_memory,
            max_attempts=2,
            cooldown_seconds=15.0,
            severity_threshold=ErrorSeverity.HIGH
        ))
        
        # Threading recovery
        self.register_recovery_strategy(RecoveryStrategy(
            name="threading_recovery",
            description="Recover from threading issues by restarting threads",
            handler=self._recover_threading,
            max_attempts=2,
            cooldown_seconds=10.0,
            severity_threshold=ErrorSeverity.HIGH
        ))
    
    def handle_error(self, 
                    component: str,
                    error_type: str,
                    exception: Exception,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    category: ErrorCategory = ErrorCategory.UNKNOWN,
                    metadata: Dict = None) -> ErrorRecord:
        """
        Handle an error occurrence.
        
        Args:
            component: Component where error occurred
            error_type: Type of error
            exception: The exception that occurred
            severity: Error severity level
            category: Error category
            metadata: Additional error context
            
        Returns:
            ErrorRecord for the handled error
        """
        current_time = time.time()
        
        # Create error record
        error_record = ErrorRecord(
            timestamp=current_time,
            component=component,
            error_type=error_type,
            severity=severity,
            category=category,
            message=str(exception),
            exception=exception,
            traceback_str=traceback.format_exc(),
            metadata=metadata or {}
        )
        
        with self.lock:
            # Store error record
            self.error_history.append(error_record)
            
            # Update error counts
            error_key = f"{component}:{error_type}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            
            # Track consecutive errors
            if error_key in self.last_error_times:
                time_since_last = current_time - self.last_error_times[error_key]
                if time_since_last < 60.0:  # Within 1 minute
                    self.consecutive_errors[error_key] = self.consecutive_errors.get(error_key, 0) + 1
                else:
                    self.consecutive_errors[error_key] = 1
            else:
                self.consecutive_errors[error_key] = 1
            
            self.last_error_times[error_key] = current_time
        
        # Log error
        self._log_error(error_record)
        
        # Notify callbacks
        for callback in self.error_callbacks:
            try:
                callback(error_record)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
        
        # Attempt recovery if appropriate
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._attempt_recovery(error_record)
        
        return error_record
    
    def _log_error(self, error_record: ErrorRecord):
        """Log error with appropriate level."""
        log_message = (f"{error_record.component} - {error_record.error_type}: "
                      f"{error_record.message}")
        
        if error_record.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
            if error_record.traceback_str:
                logger.critical(f"Traceback:\n{error_record.traceback_str}")
        elif error_record.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
            if error_record.traceback_str:
                logger.debug(f"Traceback:\n{error_record.traceback_str}")
        elif error_record.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def _attempt_recovery(self, error_record: ErrorRecord):
        """Attempt recovery for the given error."""
        recovery_key = f"{error_record.component}:{error_record.error_type}"
        
        # Find applicable recovery strategy
        strategy = self._find_recovery_strategy(error_record)
        if not strategy:
            logger.debug(f"No recovery strategy found for {recovery_key}")
            return
        
        # Check if we should attempt recovery
        if not self._should_attempt_recovery(strategy, recovery_key):
            logger.debug(f"Recovery cooldown active for {recovery_key}")
            return
        
        logger.info(f"Attempting recovery for {recovery_key} using strategy: {strategy.name}")
        
        try:
            # Mark recovery attempt
            error_record.recovery_attempted = True
            
            # Track recovery attempt
            if recovery_key not in self.recovery_attempts:
                self.recovery_attempts[recovery_key] = {
                    'count': 0,
                    'last_attempt': 0,
                    'successful': False
                }
            
            self.recovery_attempts[recovery_key]['count'] += 1
            self.recovery_attempts[recovery_key]['last_attempt'] = time.time()
            
            # Execute recovery strategy
            success = strategy.handler(error_record)
            
            # Update recovery status
            error_record.recovery_successful = success
            self.recovery_attempts[recovery_key]['successful'] = success
            
            if success:
                logger.info(f"Recovery successful for {recovery_key}")
                # Reset consecutive error count on successful recovery
                with self.lock:
                    if recovery_key in self.consecutive_errors:
                        self.consecutive_errors[recovery_key] = 0
            else:
                logger.warning(f"Recovery failed for {recovery_key}")
            
            # Notify recovery callbacks
            for callback in self.recovery_callbacks:
                try:
                    callback(recovery_key, success)
                except Exception as e:
                    logger.error(f"Error in recovery callback: {e}")
        
        except Exception as e:
            logger.error(f"Error during recovery attempt for {recovery_key}: {e}")
            error_record.recovery_successful = False
    
    def _find_recovery_strategy(self, error_record: ErrorRecord) -> Optional[RecoveryStrategy]:
        """Find appropriate recovery strategy for error."""
        # Look for specific strategy first
        specific_key = f"{error_record.component}_{error_record.error_type}_recovery"
        if specific_key in self.recovery_strategies:
            return self.recovery_strategies[specific_key]
        
        # Look for category-based strategy
        category_strategies = {
            ErrorCategory.MODEL_LOADING: ["vad_model_recovery", "asr_model_recovery"],
            ErrorCategory.AUDIO_HARDWARE: ["audio_device_recovery"],
            ErrorCategory.MEMORY: ["memory_recovery"],
            ErrorCategory.THREADING: ["threading_recovery"]
        }
        
        if error_record.category in category_strategies:
            for strategy_name in category_strategies[error_record.category]:
                if strategy_name in self.recovery_strategies:
                    strategy = self.recovery_strategies[strategy_name]
                    if error_record.severity.value >= strategy.severity_threshold.value:
                        return strategy
        
        return None
    
    def _should_attempt_recovery(self, strategy: RecoveryStrategy, recovery_key: str) -> bool:
        """Check if recovery should be attempted."""
        if recovery_key not in self.recovery_attempts:
            return True
        
        attempts = self.recovery_attempts[recovery_key]
        
        # Check max attempts
        if attempts['count'] >= strategy.max_attempts:
            return False
        
        # Check cooldown
        time_since_last = time.time() - attempts['last_attempt']
        if time_since_last < strategy.cooldown_seconds:
            return False
        
        return True
    
    def register_recovery_strategy(self, strategy: RecoveryStrategy):
        """Register a recovery strategy."""
        self.recovery_strategies[strategy.name] = strategy
        logger.debug(f"Registered recovery strategy: {strategy.name}")
    
    def _recover_vad_model(self, error_record: ErrorRecord) -> bool:
        """Recover VAD model."""
        try:
            logger.info("Attempting VAD model recovery...")
            
            # Try to get the component that failed
            component = error_record.metadata.get('component_instance')
            if component and hasattr(component, '_initialize_vad_model'):
                # Reinitialize VAD model
                component._initialize_vad_model()
                
                # Check if recovery was successful
                if component.vad_model is not None:
                    logger.info("VAD model recovery successful")
                    return True
                else:
                    # Fall back to basic audio level detection
                    logger.info("VAD model recovery failed, activating fallback")
                    component.vad_fallback_active = True
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"VAD model recovery failed: {e}")
            return False
    
    def _recover_asr_model(self, error_record: ErrorRecord) -> bool:
        """Recover ASR model."""
        try:
            logger.info("Attempting ASR model recovery...")
            
            # Try to get the component that failed
            component = error_record.metadata.get('component_instance')
            if component and hasattr(component, '_initialize_asr_model'):
                # Reinitialize ASR model
                component._initialize_asr_model()
                
                # Check if recovery was successful
                if component.asr_model is not None:
                    logger.info("ASR model recovery successful")
                    return True
                else:
                    # Activate ASR fallback
                    logger.info("ASR model recovery failed, activating fallback")
                    component.asr_fallback_active = True
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"ASR model recovery failed: {e}")
            return False
    
    def _recover_audio_device(self, error_record: ErrorRecord) -> bool:
        """Recover audio device."""
        try:
            logger.info("Attempting audio device recovery...")
            
            # Try to get the component that failed
            component = error_record.metadata.get('component_instance')
            if component and hasattr(component, 'stop_streaming') and hasattr(component, 'start_streaming'):
                # Restart audio streaming
                component.stop_streaming()
                time.sleep(1.0)  # Brief pause
                component.start_streaming()
                
                if component.is_streaming:
                    logger.info("Audio device recovery successful")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Audio device recovery failed: {e}")
            return False
    
    def _recover_memory(self, error_record: ErrorRecord) -> bool:
        """Recover from memory issues."""
        try:
            logger.info("Attempting memory recovery...")
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Clear component caches if available
            component = error_record.metadata.get('component_instance')
            if component:
                # Clear audio buffers
                if hasattr(component, 'audio_buffer'):
                    with getattr(component, 'buffer_lock', threading.Lock()):
                        component.audio_buffer.clear()
                
                # Clear processing queues
                if hasattr(component, 'processing_queue'):
                    while not component.processing_queue.empty():
                        try:
                            component.processing_queue.get_nowait()
                        except:
                            break
            
            logger.info("Memory recovery completed")
            return True
            
        except Exception as e:
            logger.error(f"Memory recovery failed: {e}")
            return False
    
    def _recover_threading(self, error_record: ErrorRecord) -> bool:
        """Recover from threading issues."""
        try:
            logger.info("Attempting threading recovery...")
            
            # Try to get the component that failed
            component = error_record.metadata.get('component_instance')
            if component and hasattr(component, 'audio_thread'):
                # Check if thread is still alive
                if component.audio_thread and component.audio_thread.is_alive():
                    logger.info("Audio thread is still alive, no recovery needed")
                    return True
                
                # Restart the processing thread
                if hasattr(component, '_processing_loop') and hasattr(component, 'threading_optimizer'):
                    component.audio_thread = component.threading_optimizer.create_audio_processing_thread(
                        target=component._processing_loop,
                        name="streaming_ears_processor_recovery"
                    )
                    component.audio_thread.start()
                    
                    logger.info("Threading recovery successful - restarted processing thread")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Threading recovery failed: {e}")
            return False
    
    def add_error_callback(self, callback: Callable[[ErrorRecord], None]):
        """Add callback for error notifications."""
        self.error_callbacks.append(callback)
        logger.debug("Added error callback")
    
    def add_recovery_callback(self, callback: Callable[[str, bool], None]):
        """Add callback for recovery notifications."""
        self.recovery_callbacks.append(callback)
        logger.debug("Added recovery callback")
    
    def get_error_statistics(self) -> Dict:
        """Get comprehensive error statistics."""
        with self.lock:
            current_time = time.time()
            
            # Calculate error rates
            recent_errors = [
                error for error in self.error_history
                if current_time - error.timestamp < 3600  # Last hour
            ]
            
            # Group by component and type
            component_stats = {}
            category_stats = {}
            severity_stats = {}
            
            for error in recent_errors:
                # Component stats
                if error.component not in component_stats:
                    component_stats[error.component] = {'count': 0, 'types': {}}
                component_stats[error.component]['count'] += 1
                
                if error.error_type not in component_stats[error.component]['types']:
                    component_stats[error.component]['types'][error.error_type] = 0
                component_stats[error.component]['types'][error.error_type] += 1
                
                # Category stats
                category_key = error.category.value
                category_stats[category_key] = category_stats.get(category_key, 0) + 1
                
                # Severity stats
                severity_key = error.severity.value
                severity_stats[severity_key] = severity_stats.get(severity_key, 0) + 1
            
            return {
                'total_errors': len(self.error_history),
                'recent_errors_1h': len(recent_errors),
                'error_rate_per_hour': len(recent_errors),
                'component_stats': component_stats,
                'category_stats': category_stats,
                'severity_stats': severity_stats,
                'consecutive_errors': dict(self.consecutive_errors),
                'recovery_attempts': dict(self.recovery_attempts),
                'active_fallbacks': dict(self.fallback_states)
            }
    
    def get_system_health(self) -> Dict:
        """Get overall system health assessment."""
        stats = self.get_error_statistics()
        current_time = time.time()
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Deduct for recent errors
        recent_errors = stats['recent_errors_1h']
        if recent_errors > 0:
            health_score -= min(50, recent_errors * 5)  # Max 50 point deduction
        
        # Deduct for consecutive errors
        max_consecutive = max(self.consecutive_errors.values()) if self.consecutive_errors else 0
        if max_consecutive > 3:
            health_score -= min(30, (max_consecutive - 3) * 10)
        
        # Deduct for critical errors
        critical_errors = stats['severity_stats'].get('critical', 0)
        if critical_errors > 0:
            health_score -= min(40, critical_errors * 20)
        
        health_score = max(0, health_score)
        
        # Determine health status
        if health_score >= 90:
            health_status = "excellent"
        elif health_score >= 75:
            health_status = "good"
        elif health_score >= 50:
            health_status = "fair"
        elif health_score >= 25:
            health_status = "poor"
        else:
            health_status = "critical"
        
        return {
            'health_score': health_score,
            'health_status': health_status,
            'total_errors': stats['total_errors'],
            'recent_errors': recent_errors,
            'max_consecutive_errors': max_consecutive,
            'active_recoveries': len([
                attempts for attempts in self.recovery_attempts.values()
                if current_time - attempts['last_attempt'] < 300  # Active within 5 minutes
            ]),
            'recommendations': self._generate_health_recommendations(stats, health_score)
        }
    
    def _generate_health_recommendations(self, stats: Dict, health_score: int) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []
        
        if health_score < 50:
            recommendations.append("System health is poor. Consider restarting the full-duplex engine.")
        
        # Check for frequent errors
        if stats['recent_errors_1h'] > 10:
            recommendations.append("High error rate detected. Check system resources and configuration.")
        
        # Check for specific component issues
        component_stats = stats.get('component_stats', {})
        for component, data in component_stats.items():
            if data['count'] > 5:
                recommendations.append(f"Frequent errors in {component}. Check component configuration.")
        
        # Check for category-specific issues
        category_stats = stats.get('category_stats', {})
        if category_stats.get('audio_hardware', 0) > 3:
            recommendations.append("Audio hardware issues detected. Check audio device configuration.")
        
        if category_stats.get('model_loading', 0) > 2:
            recommendations.append("Model loading issues detected. Check model cache and network connectivity.")
        
        if category_stats.get('memory', 0) > 1:
            recommendations.append("Memory issues detected. Consider reducing buffer sizes or restarting.")
        
        return recommendations
    
    
    def handle_fallback_success(self, component: str, fallback_type: str):
        """处理备用方案成功激活，减少健康分数惩罚"""
        current_time = time.time()
        
        # 记录备用方案成功
        if not hasattr(self, 'fallback_successes'):
            self.fallback_successes = {}
        
        self.fallback_successes[f"{component}_{fallback_type}"] = {
            'timestamp': current_time,
            'component': component,
            'fallback_type': fallback_type
        }
        
        # 减少相关错误的影响
        if component in self.consecutive_errors:
            self.consecutive_errors[component] = max(0, self.consecutive_errors[component] - 2)
        
        logger.info(f"Fallback success recorded: {component} -> {fallback_type}")
    
    def get_system_health(self) -> Dict:
        """Get overall system health assessment with fallback consideration."""
        stats = self.get_error_statistics()
        current_time = time.time()
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Deduct for recent errors
        recent_errors = stats['recent_errors_1h']
        if recent_errors > 0:
            health_score -= min(50, recent_errors * 5)  # Max 50 point deduction
        
        # Deduct for consecutive errors
        max_consecutive = max(self.consecutive_errors.values()) if self.consecutive_errors else 0
        if max_consecutive > 3:
            health_score -= min(30, (max_consecutive - 3) * 10)
        
        # Deduct for critical errors
        critical_errors = stats['severity_stats'].get('critical', 0)
        if critical_errors > 0:
            health_score -= min(40, critical_errors * 20)
        
        # Boost score for successful fallbacks
        if hasattr(self, 'fallback_successes'):
            recent_fallbacks = [
                fb for fb in self.fallback_successes.values()
                if current_time - fb['timestamp'] < 3600  # Within last hour
            ]
            if recent_fallbacks:
                health_score += min(25, len(recent_fallbacks) * 10)  # Boost for working fallbacks
        
        health_score = max(0, min(100, health_score))  # Clamp to 0-100
        
        # Determine health status
        if health_score >= 90:
            health_status = "excellent"
        elif health_score >= 75:
            health_status = "good"
        elif health_score >= 50:
            health_status = "fair"
        elif health_score >= 25:
            health_status = "poor"
        else:
            health_status = "critical"
        
        return {
            'health_score': health_score,
            'health_status': health_status,
            'total_errors': stats['total_errors'],
            'recent_errors': recent_errors,
            'max_consecutive_errors': max_consecutive,
            'active_recoveries': len([
                attempts for attempts in self.recovery_attempts.values()
                if current_time - attempts['last_attempt'] < 300  # Active within 5 minutes
            ]),
            'active_fallbacks': len(getattr(self, 'fallback_successes', {})),
            'recommendations': self._generate_health_recommendations(stats, health_score)
        }

    def log_error_summary(self):
        """Log comprehensive error summary."""
        try:
            stats = self.get_error_statistics()
            health = self.get_system_health()
            
            logger.info("=== Full-Duplex Engine Error Summary ===")
            logger.info(f"System Health: {health['health_status'].upper()} (Score: {health['health_score']}/100)")
            logger.info(f"Total Errors: {stats['total_errors']}")
            logger.info(f"Recent Errors (1h): {stats['recent_errors_1h']}")
            
            # Component breakdown
            if stats['component_stats']:
                logger.info("Errors by Component:")
                for component, data in stats['component_stats'].items():
                    logger.info(f"  {component}: {data['count']} errors")
            
            # Category breakdown
            if stats['category_stats']:
                logger.info("Errors by Category:")
                for category, count in stats['category_stats'].items():
                    logger.info(f"  {category}: {count} errors")
            
            # Recovery status
            active_recoveries = health['active_recoveries']
            if active_recoveries > 0:
                logger.info(f"Active Recovery Attempts: {active_recoveries}")
            
            # Recommendations
            recommendations = health['recommendations']
            if recommendations:
                logger.info("Recommendations:")
                for i, rec in enumerate(recommendations, 1):
                    logger.info(f"  {i}. {rec}")
            
            logger.info("=========================================")
            
        except Exception as e:
            logger.error(f"Failed to log error summary: {e}")

# Global error handler instance
_error_handler: Optional[FullDuplexErrorHandler] = None

def get_error_handler() -> FullDuplexErrorHandler:
    """Get global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = FullDuplexErrorHandler()
    return _error_handler

def cleanup_error_handler():
    """Clean up global error handler."""
    global _error_handler
    if _error_handler is not None:
        _error_handler = None