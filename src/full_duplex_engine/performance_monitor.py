"""
Performance Monitor for Full-Duplex Conversational Engine

Provides comprehensive end-to-end latency monitoring and optimization
across the complete pipeline from audio input to AI response output.
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import statistics
import logging

from .logging_config import get_component_logger

logger = get_component_logger("performance_monitor")

@dataclass
class LatencyMeasurement:
    """Single latency measurement with context."""
    component: str
    operation: str
    start_time: float
    end_time: float
    duration: float
    metadata: Dict = field(default_factory=dict)

@dataclass
class EndToEndMetrics:
    """End-to-end performance metrics."""
    # Individual component latencies
    vad_latency_ms: float = 0.0
    asr_latency_ms: float = 0.0
    text_processing_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    audio_output_latency_ms: float = 0.0
    
    # End-to-end measurements
    speech_to_transcription_ms: float = 0.0  # User speech -> final text
    transcription_to_response_ms: float = 0.0  # Final text -> AI response start
    total_conversation_latency_ms: float = 0.0  # Complete cycle
    
    # Interruption performance
    interruption_response_time_ms: float = 0.0  # VAD detection -> audio stop
    
    # Timing consistency metrics
    timing_variance_ms: float = 0.0
    timing_jitter_ms: float = 0.0
    
    # Throughput metrics
    audio_chunks_per_second: float = 0.0
    processing_efficiency: float = 0.0  # % of time spent processing vs waiting

class PerformanceMonitor:
    """
    Comprehensive performance monitoring for the full-duplex engine.
    
    Tracks latency across all components and provides optimization insights.
    """
    
    def __init__(self, history_size: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            history_size: Number of measurements to keep in history
        """
        self.history_size = history_size
        
        # Measurement storage
        self.measurements = deque(maxlen=history_size)
        self.active_measurements: Dict[str, LatencyMeasurement] = {}
        
        # Component-specific measurement queues
        self.vad_measurements = deque(maxlen=100)
        self.asr_measurements = deque(maxlen=100)
        self.text_processing_measurements = deque(maxlen=100)
        self.llm_measurements = deque(maxlen=100)
        self.tts_measurements = deque(maxlen=100)
        self.interruption_measurements = deque(maxlen=100)
        
        # End-to-end conversation tracking
        self.conversation_starts: Dict[str, float] = {}
        self.conversation_measurements = deque(maxlen=50)
        
        # Threading for thread-safe operations
        self.lock = threading.Lock()
        
        # Performance optimization callbacks
        self.optimization_callbacks: List[Callable[[EndToEndMetrics], None]] = []
        
        # Timing consistency tracking
        self.chunk_intervals = deque(maxlen=200)
        self.last_chunk_time = 0.0
        
        logger.info(f"PerformanceMonitor initialized with history_size={history_size}")
    
    def start_measurement(self, component: str, operation: str, metadata: Dict = None) -> str:
        """
        Start a latency measurement.
        
        Args:
            component: Component name (e.g., "vad", "asr", "tts")
            operation: Operation name (e.g., "process_chunk", "generate_audio")
            metadata: Additional context information
            
        Returns:
            Measurement ID for ending the measurement
        """
        measurement_id = f"{component}_{operation}_{time.time()}"
        start_time = time.time()
        
        measurement = LatencyMeasurement(
            component=component,
            operation=operation,
            start_time=start_time,
            end_time=0.0,
            duration=0.0,
            metadata=metadata or {}
        )
        
        with self.lock:
            self.active_measurements[measurement_id] = measurement
        
        logger.debug(f"Started measurement: {measurement_id}")
        return measurement_id
    
    def end_measurement(self, measurement_id: str) -> Optional[float]:
        """
        End a latency measurement.
        
        Args:
            measurement_id: ID returned by start_measurement
            
        Returns:
            Duration in seconds, or None if measurement not found
        """
        end_time = time.time()
        
        with self.lock:
            if measurement_id not in self.active_measurements:
                logger.warning(f"Measurement not found: {measurement_id}")
                return None
            
            measurement = self.active_measurements.pop(measurement_id)
            measurement.end_time = end_time
            measurement.duration = end_time - measurement.start_time
            
            # Store in general history
            self.measurements.append(measurement)
            
            # Store in component-specific queues
            self._store_component_measurement(measurement)
            
            logger.debug(f"Completed measurement: {measurement_id}, "
                        f"duration={measurement.duration*1000:.1f}ms")
            
            return measurement.duration
    
    def _store_component_measurement(self, measurement: LatencyMeasurement) -> None:
        """Store measurement in appropriate component queue."""
        duration_ms = measurement.duration * 1000
        
        if measurement.component == "vad":
            self.vad_measurements.append(duration_ms)
        elif measurement.component == "asr":
            self.asr_measurements.append(duration_ms)
        elif measurement.component == "text_processing":
            self.text_processing_measurements.append(duration_ms)
        elif measurement.component == "llm":
            self.llm_measurements.append(duration_ms)
        elif measurement.component == "tts":
            self.tts_measurements.append(duration_ms)
        elif measurement.component == "interruption":
            self.interruption_measurements.append(duration_ms)
    
    def record_conversation_start(self, conversation_id: str) -> None:
        """Record the start of an end-to-end conversation."""
        with self.lock:
            self.conversation_starts[conversation_id] = time.time()
        logger.debug(f"Started conversation tracking: {conversation_id}")
    
    def record_conversation_end(self, conversation_id: str) -> Optional[float]:
        """
        Record the end of an end-to-end conversation.
        
        Args:
            conversation_id: ID used in record_conversation_start
            
        Returns:
            Total conversation duration in seconds
        """
        end_time = time.time()
        
        with self.lock:
            if conversation_id not in self.conversation_starts:
                logger.warning(f"Conversation start not found: {conversation_id}")
                return None
            
            start_time = self.conversation_starts.pop(conversation_id)
            duration = end_time - start_time
            
            self.conversation_measurements.append(duration * 1000)  # Store in ms
            
            logger.info(f"Conversation completed: {conversation_id}, "
                       f"duration={duration*1000:.1f}ms")
            
            return duration
    
    def record_audio_chunk_timing(self) -> None:
        """Record timing of audio chunk processing for consistency analysis."""
        current_time = time.time()
        
        if self.last_chunk_time > 0:
            interval = current_time - self.last_chunk_time
            with self.lock:
                self.chunk_intervals.append(interval * 1000)  # Store in ms
        
        self.last_chunk_time = current_time
    
    def get_current_metrics(self) -> EndToEndMetrics:
        """Get current performance metrics."""
        with self.lock:
            metrics = EndToEndMetrics()
            
            # Calculate component latencies
            if self.vad_measurements:
                metrics.vad_latency_ms = statistics.mean(self.vad_measurements)
            
            if self.asr_measurements:
                metrics.asr_latency_ms = statistics.mean(self.asr_measurements)
            
            if self.text_processing_measurements:
                metrics.text_processing_latency_ms = statistics.mean(self.text_processing_measurements)
            
            if self.llm_measurements:
                metrics.llm_latency_ms = statistics.mean(self.llm_measurements)
            
            if self.tts_measurements:
                metrics.tts_latency_ms = statistics.mean(self.tts_measurements)
            
            if self.interruption_measurements:
                metrics.interruption_response_time_ms = statistics.mean(self.interruption_measurements)
            
            # Calculate end-to-end metrics
            if self.conversation_measurements:
                metrics.total_conversation_latency_ms = statistics.mean(self.conversation_measurements)
            
            # Calculate speech-to-transcription latency (VAD + ASR)
            if self.vad_measurements and self.asr_measurements:
                metrics.speech_to_transcription_ms = (
                    statistics.mean(self.vad_measurements) + 
                    statistics.mean(self.asr_measurements)
                )
            
            # Calculate transcription-to-response latency (Text Processing + LLM + TTS)
            if (self.text_processing_measurements and 
                self.llm_measurements and 
                self.tts_measurements):
                metrics.transcription_to_response_ms = (
                    statistics.mean(self.text_processing_measurements) +
                    statistics.mean(self.llm_measurements) +
                    statistics.mean(self.tts_measurements)
                )
            
            # Calculate timing consistency metrics
            if self.chunk_intervals:
                intervals = list(self.chunk_intervals)
                metrics.timing_variance_ms = statistics.variance(intervals) if len(intervals) > 1 else 0.0
                metrics.timing_jitter_ms = max(intervals) - min(intervals) if intervals else 0.0
            
            # Calculate throughput metrics
            if self.chunk_intervals:
                expected_interval = 32.0  # 32ms for 512 samples at 16kHz
                actual_interval = statistics.mean(self.chunk_intervals)
                metrics.audio_chunks_per_second = 1000.0 / actual_interval if actual_interval > 0 else 0.0
                metrics.processing_efficiency = min(100.0, (expected_interval / actual_interval) * 100.0)
            
            return metrics
    
    def get_detailed_statistics(self) -> Dict:
        """Get detailed performance statistics for analysis."""
        with self.lock:
            stats = {
                'component_latencies': {},
                'percentiles': {},
                'timing_consistency': {},
                'throughput': {},
                'optimization_recommendations': []
            }
            
            # Component latency statistics
            components = {
                'vad': self.vad_measurements,
                'asr': self.asr_measurements,
                'text_processing': self.text_processing_measurements,
                'llm': self.llm_measurements,
                'tts': self.tts_measurements,
                'interruption': self.interruption_measurements
            }
            
            for component, measurements in components.items():
                if measurements:
                    values = list(measurements)
                    stats['component_latencies'][component] = {
                        'mean_ms': statistics.mean(values),
                        'median_ms': statistics.median(values),
                        'min_ms': min(values),
                        'max_ms': max(values),
                        'std_dev_ms': statistics.stdev(values) if len(values) > 1 else 0.0,
                        'sample_count': len(values)
                    }
                    
                    # Calculate percentiles
                    sorted_values = sorted(values)
                    stats['percentiles'][component] = {
                        'p50_ms': sorted_values[len(sorted_values)//2],
                        'p90_ms': sorted_values[int(len(sorted_values)*0.9)],
                        'p95_ms': sorted_values[int(len(sorted_values)*0.95)],
                        'p99_ms': sorted_values[int(len(sorted_values)*0.99)]
                    }
            
            # Timing consistency analysis
            if self.chunk_intervals:
                intervals = list(self.chunk_intervals)
                stats['timing_consistency'] = {
                    'mean_interval_ms': statistics.mean(intervals),
                    'expected_interval_ms': 32.0,  # 32ms for 512 samples at 16kHz
                    'variance_ms': statistics.variance(intervals) if len(intervals) > 1 else 0.0,
                    'jitter_ms': max(intervals) - min(intervals),
                    'consistency_score': self._calculate_consistency_score(intervals)
                }
            
            # Generate optimization recommendations
            stats['optimization_recommendations'] = self._generate_optimization_recommendations(stats)
            
            return stats
    
    def _calculate_consistency_score(self, intervals: List[float]) -> float:
        """Calculate timing consistency score (0-100, higher is better)."""
        if not intervals or len(intervals) < 2:
            return 100.0
        
        expected_interval = 32.0  # 32ms
        variance = statistics.variance(intervals)
        
        # Score based on how close variance is to zero
        # Lower variance = higher score
        max_acceptable_variance = 100.0  # 100ms² variance threshold
        score = max(0.0, 100.0 - (variance / max_acceptable_variance * 100.0))
        
        return min(100.0, score)
    
    def _generate_optimization_recommendations(self, stats: Dict) -> List[str]:
        """Generate optimization recommendations based on current performance."""
        recommendations = []
        
        # Check component latencies
        component_latencies = stats.get('component_latencies', {})
        
        # VAD optimization
        if 'vad' in component_latencies:
            vad_mean = component_latencies['vad']['mean_ms']
            if vad_mean > 10.0:  # VAD should be <10ms
                recommendations.append(
                    f"VAD latency high ({vad_mean:.1f}ms). Consider reducing chunk size or using GPU acceleration."
                )
        
        # ASR optimization
        if 'asr' in component_latencies:
            asr_mean = component_latencies['asr']['mean_ms']
            if asr_mean > 100.0:  # ASR should be <100ms for streaming
                recommendations.append(
                    f"ASR latency high ({asr_mean:.1f}ms). Consider using smaller model or GPU acceleration."
                )
        
        # LLM optimization
        if 'llm' in component_latencies:
            llm_mean = component_latencies['llm']['mean_ms']
            if llm_mean > 500.0:  # LLM should be <500ms for good UX
                recommendations.append(
                    f"LLM latency high ({llm_mean:.1f}ms). Consider using smaller model or streaming responses."
                )
        
        # TTS optimization
        if 'tts' in component_latencies:
            tts_mean = component_latencies['tts']['mean_ms']
            if tts_mean > 200.0:  # TTS should be <200ms
                recommendations.append(
                    f"TTS latency high ({tts_mean:.1f}ms). Consider using faster voice or caching."
                )
        
        # Interruption response optimization
        if 'interruption' in component_latencies:
            int_mean = component_latencies['interruption']['mean_ms']
            if int_mean > 200.0:  # Interruption should be <200ms per requirements
                recommendations.append(
                    f"Interruption response slow ({int_mean:.1f}ms). Check audio pipeline threading."
                )
        
        # Timing consistency optimization
        timing_consistency = stats.get('timing_consistency', {})
        if timing_consistency:
            consistency_score = timing_consistency.get('consistency_score', 100.0)
            if consistency_score < 80.0:
                recommendations.append(
                    f"Audio timing inconsistent (score: {consistency_score:.1f}). "
                    f"Check system load and audio driver configuration."
                )
        
        return recommendations
    
    def add_optimization_callback(self, callback: Callable[[EndToEndMetrics], None]) -> None:
        """Add callback for performance optimization notifications."""
        self.optimization_callbacks.append(callback)
        logger.debug("Added optimization callback")
    
    def trigger_optimization_analysis(self) -> None:
        """Trigger optimization analysis and notify callbacks."""
        metrics = self.get_current_metrics()
        
        for callback in self.optimization_callbacks:
            try:
                callback(metrics)
            except Exception as e:
                logger.error(f"Error in optimization callback: {e}")
    
    def reset_measurements(self) -> None:
        """Reset all measurements (useful for testing)."""
        with self.lock:
            self.measurements.clear()
            self.active_measurements.clear()
            self.vad_measurements.clear()
            self.asr_measurements.clear()
            self.text_processing_measurements.clear()
            self.llm_measurements.clear()
            self.tts_measurements.clear()
            self.interruption_measurements.clear()
            self.conversation_starts.clear()
            self.conversation_measurements.clear()
            self.chunk_intervals.clear()
            self.last_chunk_time = 0.0
        
        logger.info("Performance measurements reset")
    
    def log_performance_summary(self) -> None:
        """Log a comprehensive performance summary."""
        try:
            metrics = self.get_current_metrics()
            stats = self.get_detailed_statistics()
            
            logger.info("=== Full-Duplex Engine Performance Summary ===")
            
            # Component latencies
            logger.info("Component Latencies:")
            logger.info(f"  VAD: {metrics.vad_latency_ms:.1f}ms")
            logger.info(f"  ASR: {metrics.asr_latency_ms:.1f}ms")
            logger.info(f"  Text Processing: {metrics.text_processing_latency_ms:.1f}ms")
            logger.info(f"  LLM: {metrics.llm_latency_ms:.1f}ms")
            logger.info(f"  TTS: {metrics.tts_latency_ms:.1f}ms")
            
            # End-to-end metrics
            logger.info("End-to-End Metrics:")
            logger.info(f"  Speech → Transcription: {metrics.speech_to_transcription_ms:.1f}ms")
            logger.info(f"  Transcription → Response: {metrics.transcription_to_response_ms:.1f}ms")
            logger.info(f"  Total Conversation: {metrics.total_conversation_latency_ms:.1f}ms")
            logger.info(f"  Interruption Response: {metrics.interruption_response_time_ms:.1f}ms")
            
            # Timing consistency
            logger.info("Timing Consistency:")
            logger.info(f"  Variance: {metrics.timing_variance_ms:.1f}ms²")
            logger.info(f"  Jitter: {metrics.timing_jitter_ms:.1f}ms")
            logger.info(f"  Processing Efficiency: {metrics.processing_efficiency:.1f}%")
            
            # Optimization recommendations
            recommendations = stats.get('optimization_recommendations', [])
            if recommendations:
                logger.info("Optimization Recommendations:")
                for i, rec in enumerate(recommendations, 1):
                    logger.info(f"  {i}. {rec}")
            else:
                logger.info("No optimization recommendations - performance is good!")
            
            logger.info("===============================================")
            
        except Exception as e:
            logger.error(f"Failed to log performance summary: {e}")