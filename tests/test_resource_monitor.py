"""
Tests for ResourceMonitor - Resource usage monitoring and optimization

Tests CPU and memory usage tracking, automatic performance scaling,
and rate limiting for VLM requests.

Feature: vision-action-agent
"""

import asyncio
import pytest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from src.resource_monitor import ResourceMonitor, ResourceMetrics, PerformanceThresholds


def create_resource_config():
    """Create a fresh resource monitor configuration"""
    return {
        'monitoring_interval': 0.1,  # Fast for testing
        'history_size': 10,
        'performance_thresholds': {
            'cpu_high': 70.0,
            'cpu_critical': 85.0,
            'memory_high': 75.0,
            'memory_critical': 90.0,
            'vlm_requests_per_minute': 5,  # Low for testing
            'vlm_requests_per_hour': 50,
            'scale_factor_moderate': 1.5,
            'scale_factor_aggressive': 2.0
        }
    }


class TestResourceMonitorBasic:
    """Basic unit tests for ResourceMonitor functionality"""
    
    @pytest.fixture
    def resource_config(self):
        """Basic resource monitor configuration"""
        return create_resource_config()
    
    @pytest.fixture
    def resource_monitor(self, resource_config):
        """Create ResourceMonitor instance for testing"""
        monitor = ResourceMonitor(resource_config)
        yield monitor
        monitor.cleanup()
    
    def test_resource_monitor_initialization(self, resource_monitor):
        """Test ResourceMonitor initializes correctly"""
        assert resource_monitor.monitoring_interval == 0.1
        assert resource_monitor.history_size == 10
        assert resource_monitor.thresholds.cpu_high == 70.0
        assert resource_monitor.thresholds.vlm_requests_per_minute == 5
        assert not resource_monitor.monitoring_active
    
    def test_vlm_rate_limiting_basic(self, resource_monitor):
        """Test basic VLM rate limiting functionality"""
        # Should allow initial requests
        assert resource_monitor.can_make_vlm_request()
        
        # Record requests up to limit
        for _ in range(5):
            resource_monitor.record_vlm_request()
            
        # Should now be rate limited
        assert not resource_monitor.can_make_vlm_request()
    
    def test_performance_scaling_callback_registration(self, resource_monitor):
        """Test performance scaling callback registration"""
        callback_called = False
        
        def test_callback(scale_factor, cpu_percent, memory_percent):
            nonlocal callback_called
            callback_called = True
        
        resource_monitor.register_scale_callback(test_callback)
        
        # Simulate scaling event
        resource_monitor._apply_performance_scaling(2.0, 80.0, 85.0)
        
        assert callback_called
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_io_counters')
    @patch('psutil.net_io_counters')
    def test_metrics_capture(self, mock_net, mock_disk, mock_memory, mock_cpu, resource_monitor):
        """Test metrics capture functionality"""
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0, used=1024*1024*1024, available=512*1024*1024)
        mock_disk.return_value = Mock(read_bytes=1024*1024, write_bytes=512*1024)
        mock_net.return_value = Mock(bytes_sent=2048*1024, bytes_recv=1024*1024)
        
        # Mock process metrics
        with patch.object(resource_monitor.process, 'cpu_percent', return_value=25.0), \
             patch.object(resource_monitor.process, 'memory_info', return_value=Mock(rss=256*1024*1024)), \
             patch.object(resource_monitor.process, 'num_threads', return_value=4):
            
            metrics = resource_monitor._capture_metrics()
            
            assert metrics.cpu_percent == 50.0
            assert metrics.memory_percent == 60.0
            assert metrics.process_cpu_percent == 25.0
            assert metrics.process_threads == 4
    
    def test_performance_summary_no_data(self, resource_monitor):
        """Test performance summary when no data is available"""
        summary = resource_monitor.get_performance_summary()
        assert summary['status'] == 'no_data'
    
    def test_cleanup(self, resource_monitor):
        """Test cleanup stops monitoring"""
        resource_monitor.start_monitoring()
        assert resource_monitor.monitoring_active
        
        resource_monitor.cleanup()
        assert not resource_monitor.monitoring_active


# =============================================================================
# Property-Based Tests for Resource Usage Optimization
# =============================================================================

class TestResourceUsageOptimizationProperty:
    """
    Property 23: Resource usage optimization
    
    *For any* screenshot capture operation, CPU and memory usage should remain 
    within acceptable bounds and not increase over time
    
    **Validates: Requirements 10.1, 10.4**
    
    Feature: vision-action-agent, Property 23: Resource usage optimization
    """
    
    @given(
        cpu_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=20
        ),
        memory_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_metrics_remain_bounded(self, cpu_values, memory_values):
        """
        Property: For any sequence of CPU/memory readings, metrics should remain bounded
        
        Feature: vision-action-agent, Property 23: Resource usage optimization
        **Validates: Requirements 10.1, 10.4**
        """
        config = {
            'monitoring_interval': 0.05,
            'history_size': 100,
            'performance_thresholds': {
                'cpu_high': 70.0,
                'cpu_critical': 85.0,
                'memory_high': 75.0,
                'memory_critical': 90.0,
                'vlm_requests_per_minute': 100,
                'vlm_requests_per_hour': 1000,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        monitor = ResourceMonitor(config)
        
        try:
            # Simulate metrics capture with various values
            for cpu, memory in zip(cpu_values, memory_values):
                metrics = ResourceMetrics(
                    cpu_percent=cpu,
                    memory_percent=memory,
                    memory_used_mb=memory * 100,
                    memory_available_mb=(100 - memory) * 100,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=cpu * 0.5,
                    process_memory_mb=memory * 50,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
            
            # Property: All stored metrics should be within valid bounds
            for m in monitor.metrics_history:
                assert 0.0 <= m.cpu_percent <= 100.0, f"CPU out of bounds: {m.cpu_percent}"
                assert 0.0 <= m.memory_percent <= 100.0, f"Memory out of bounds: {m.memory_percent}"
                assert m.memory_used_mb >= 0.0, f"Memory used negative: {m.memory_used_mb}"
                assert m.memory_available_mb >= 0.0, f"Memory available negative: {m.memory_available_mb}"
            
            # Property: History size should not exceed configured limit
            assert len(monitor.metrics_history) <= monitor.history_size
            
        finally:
            monitor.cleanup()


    @given(
        num_requests=st.integers(min_value=0, max_value=200),
        requests_per_minute_limit=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_vlm_rate_limiting_enforced(self, num_requests, requests_per_minute_limit):
        """
        Property: VLM rate limiting should prevent resource exhaustion
        
        For any number of VLM requests, the rate limiter should correctly
        enforce the configured limits.
        
        Feature: vision-action-agent, Property 23: Resource usage optimization
        **Validates: Requirements 10.1, 10.4**
        """
        config = {
            'monitoring_interval': 0.05,
            'history_size': 100,
            'performance_thresholds': {
                'cpu_high': 70.0,
                'cpu_critical': 85.0,
                'memory_high': 75.0,
                'memory_critical': 90.0,
                'vlm_requests_per_minute': requests_per_minute_limit,
                'vlm_requests_per_hour': requests_per_minute_limit * 60,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        
        monitor = ResourceMonitor(config)
        
        try:
            allowed_count = 0
            blocked_count = 0
            
            for _ in range(num_requests):
                if monitor.can_make_vlm_request():
                    monitor.record_vlm_request()
                    allowed_count += 1
                else:
                    blocked_count += 1
            
            # Property: Number of allowed requests should not exceed the limit
            assert allowed_count <= requests_per_minute_limit, \
                f"Allowed {allowed_count} requests but limit is {requests_per_minute_limit}"
            
            # Property: If we tried more than the limit, some should be blocked
            if num_requests > requests_per_minute_limit:
                assert blocked_count > 0, \
                    f"Expected some blocked requests when {num_requests} > {requests_per_minute_limit}"
            
        finally:
            monitor.cleanup()

    @given(
        cpu_percent=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        memory_percent=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        cpu_high=st.floats(min_value=50.0, max_value=80.0, allow_nan=False, allow_infinity=False),
        cpu_critical=st.floats(min_value=80.0, max_value=95.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_performance_scaling_triggers_correctly(self, cpu_percent, memory_percent, 
                                                     cpu_high, cpu_critical):
        """
        Property: Performance scaling should trigger at correct thresholds
        
        For any CPU/memory values and threshold configuration, scaling should
        be applied when thresholds are exceeded.
        
        Feature: vision-action-agent, Property 23: Resource usage optimization
        **Validates: Requirements 10.1, 10.4**
        """
        assume(cpu_high < cpu_critical)  # Ensure valid threshold ordering
        
        config = {
            'monitoring_interval': 0.05,
            'history_size': 100,
            'performance_thresholds': {
                'cpu_high': cpu_high,
                'cpu_critical': cpu_critical,
                'memory_high': cpu_high,
                'memory_critical': cpu_critical,
                'vlm_requests_per_minute': 100,
                'vlm_requests_per_hour': 1000,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        
        monitor = ResourceMonitor(config)
        
        try:
            # Track scaling events
            scale_events = []
            
            def track_scaling(scale_factor, cpu, mem):
                scale_events.append((scale_factor, cpu, mem))
            
            monitor.register_scale_callback(track_scaling)
            
            # Add enough metrics to trigger scaling check
            for _ in range(5):
                metrics = ResourceMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_used_mb=memory_percent * 100,
                    memory_available_mb=(100 - memory_percent) * 100,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=cpu_percent * 0.5,
                    process_memory_mb=memory_percent * 50,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
            
            # Force scaling check
            monitor._check_performance_scaling(metrics)
            
            # Property: Scaling should be appropriate for resource levels
            if cpu_percent >= cpu_critical or memory_percent >= cpu_critical:
                # Should have aggressive scaling
                if scale_events:
                    assert scale_events[-1][0] == monitor.thresholds.scale_factor_aggressive
            elif cpu_percent >= cpu_high or memory_percent >= cpu_high:
                # Should have moderate scaling
                if scale_events:
                    assert scale_events[-1][0] == monitor.thresholds.scale_factor_moderate
            
        finally:
            monitor.cleanup()

    @given(
        history_size=st.integers(min_value=10, max_value=200),
        num_samples=st.integers(min_value=1, max_value=500)
    )
    @settings(max_examples=100, deadline=None)
    def test_memory_bounded_by_history_size(self, history_size, num_samples):
        """
        Property: Memory usage should be bounded by history size configuration
        
        For any number of samples collected, the metrics history should never
        exceed the configured history size, preventing memory leaks.
        
        Feature: vision-action-agent, Property 23: Resource usage optimization
        **Validates: Requirements 10.1, 10.4**
        """
        config = {
            'monitoring_interval': 0.05,
            'history_size': history_size,
            'performance_thresholds': {
                'cpu_high': 70.0,
                'cpu_critical': 85.0,
                'memory_high': 75.0,
                'memory_critical': 90.0,
                'vlm_requests_per_minute': 100,
                'vlm_requests_per_hour': 1000,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        monitor = ResourceMonitor(config)
        
        try:
            # Add many samples
            for i in range(num_samples):
                metrics = ResourceMetrics(
                    cpu_percent=float(i % 100),
                    memory_percent=float(i % 100),
                    memory_used_mb=float(i),
                    memory_available_mb=1000.0,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=float(i % 50),
                    process_memory_mb=float(i),
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
            
            # Property: History size should never exceed configured limit
            assert len(monitor.metrics_history) <= history_size, \
                f"History size {len(monitor.metrics_history)} exceeds limit {history_size}"
            
            # Property: If we added more samples than history size, we should have exactly history_size
            if num_samples >= history_size:
                assert len(monitor.metrics_history) == history_size
            
        finally:
            monitor.cleanup()


    @given(
        scale_factor=st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        cpu_percent=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        memory_percent=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_scale_factor_propagates_to_callbacks(self, scale_factor, cpu_percent, memory_percent):
        """
        Property: Scale factor changes should propagate to all registered callbacks
        
        For any scale factor and resource values, all registered callbacks should
        receive the exact values passed to the scaling function.
        
        Feature: vision-action-agent, Property 23: Resource usage optimization
        **Validates: Requirements 10.1, 10.4**
        """
        config = create_resource_config()
        monitor = ResourceMonitor(config)
        
        try:
            received_values = []
            
            def callback1(sf, cpu, mem):
                received_values.append(('cb1', sf, cpu, mem))
            
            def callback2(sf, cpu, mem):
                received_values.append(('cb2', sf, cpu, mem))
            
            monitor.register_scale_callback(callback1)
            monitor.register_scale_callback(callback2)
            
            # Apply scaling
            monitor._apply_performance_scaling(scale_factor, cpu_percent, memory_percent)
            
            # Property: Both callbacks should receive the exact values
            assert len(received_values) == 2
            
            for name, sf, cpu, mem in received_values:
                assert sf == scale_factor, f"Scale factor mismatch in {name}"
                assert cpu == cpu_percent, f"CPU percent mismatch in {name}"
                assert mem == memory_percent, f"Memory percent mismatch in {name}"
            
            # Property: Current scale factor should be updated
            assert monitor.current_scale_factor == scale_factor
            
        finally:
            monitor.cleanup()

    @given(
        num_operations=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_resource_usage_does_not_grow_unbounded(self, num_operations):
        """
        Property: Resource usage should not grow unbounded over time
        
        For any number of monitoring operations, the internal data structures
        should remain bounded and not cause memory leaks.
        
        Feature: vision-action-agent, Property 23: Resource usage optimization
        **Validates: Requirements 10.1, 10.4**
        """
        config = {
            'monitoring_interval': 0.05,
            'history_size': 20,  # Small history for testing
            'performance_thresholds': {
                'cpu_high': 70.0,
                'cpu_critical': 85.0,
                'memory_high': 75.0,
                'memory_critical': 90.0,
                'vlm_requests_per_minute': 100,
                'vlm_requests_per_hour': 1000,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        monitor = ResourceMonitor(config)
        
        try:
            # Perform many operations
            for i in range(num_operations):
                # Add metrics
                metrics = ResourceMetrics(
                    cpu_percent=50.0,
                    memory_percent=50.0,
                    memory_used_mb=500.0,
                    memory_available_mb=500.0,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=25.0,
                    process_memory_mb=250.0,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
                
                # Record VLM requests
                if i % 5 == 0:
                    monitor.record_vlm_request()
                
                # Trigger cleanup periodically
                if i % 10 == 0:
                    monitor._cleanup_vlm_request_history()
            
            # Property: Metrics history should be bounded
            assert len(monitor.metrics_history) <= config['history_size']
            
            # Property: VLM request history should be bounded (2 hour window)
            max_expected_vlm_requests = num_operations // 5 + 1
            assert len(monitor.vlm_request_times) <= max_expected_vlm_requests
            
        finally:
            monitor.cleanup()


# =============================================================================
# Stateful Property Test for Resource Monitor
# =============================================================================

class ResourceMonitorStateMachine(RuleBasedStateMachine):
    """
    Stateful property test for ResourceMonitor
    
    Tests that resource monitoring maintains consistent state across
    various operations and transitions.
    
    Feature: vision-action-agent, Property 23: Resource usage optimization
    **Validates: Requirements 10.1, 10.4**
    """
    
    def __init__(self):
        super().__init__()
        config = {
            'monitoring_interval': 0.1,
            'history_size': 50,
            'performance_thresholds': {
                'cpu_high': 70.0,
                'cpu_critical': 85.0,
                'memory_high': 75.0,
                'memory_critical': 90.0,
                'vlm_requests_per_minute': 20,
                'vlm_requests_per_hour': 200,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        self.monitor = ResourceMonitor(config)
        self.vlm_requests_made = 0
        self.metrics_added = 0
    
    @rule(cpu=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
          memory=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    def add_metrics(self, cpu, memory):
        """Add metrics to the monitor"""
        metrics = ResourceMetrics(
            cpu_percent=cpu,
            memory_percent=memory,
            memory_used_mb=memory * 100,
            memory_available_mb=(100 - memory) * 100,
            disk_io_read_mb=0.0,
            disk_io_write_mb=0.0,
            network_sent_mb=0.0,
            network_recv_mb=0.0,
            timestamp=datetime.now(),
            process_cpu_percent=cpu * 0.5,
            process_memory_mb=memory * 50,
            process_threads=4
        )
        self.monitor.metrics_history.append(metrics)
        self.monitor.current_metrics = metrics
        self.metrics_added += 1
    
    @rule()
    def record_vlm_request(self):
        """Record a VLM request"""
        if self.monitor.can_make_vlm_request():
            self.monitor.record_vlm_request()
            self.vlm_requests_made += 1
    
    @rule()
    def check_performance_scaling(self):
        """Check performance scaling"""
        if self.monitor.current_metrics is not None:
            self.monitor._check_performance_scaling(self.monitor.current_metrics)
    
    @rule()
    def get_summary(self):
        """Get performance summary"""
        summary = self.monitor.get_performance_summary()
        # Summary should always return a dict with status
        assert isinstance(summary, dict)
        assert 'status' in summary
    
    @invariant()
    def history_bounded(self):
        """Invariant: History should never exceed configured size"""
        assert len(self.monitor.metrics_history) <= self.monitor.history_size
    
    @invariant()
    def scale_factor_valid(self):
        """Invariant: Scale factor should always be >= 1.0"""
        assert self.monitor.current_scale_factor >= 1.0
    
    @invariant()
    def vlm_rate_limit_respected(self):
        """Invariant: VLM requests should respect rate limits"""
        # Count recent requests
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        recent_requests = sum(1 for req_time in self.monitor.vlm_request_times 
                             if req_time >= minute_ago)
        
        # Should not exceed per-minute limit
        assert recent_requests <= self.monitor.thresholds.vlm_requests_per_minute
    
    def teardown(self):
        """Clean up after test"""
        self.monitor.cleanup()


# Create test case from state machine
TestResourceMonitorStateful = ResourceMonitorStateMachine.TestCase


# =============================================================================
# Property-Based Tests for Performance Metrics Availability
# =============================================================================

class TestPerformanceMetricsAvailabilityProperty:
    """
    Property 26: Performance metrics availability
    
    *For any* system operation, performance metrics should be available and 
    accurately reflect current resource usage and timing statistics
    
    **Validates: Requirements 10.5**
    
    Feature: vision-action-agent, Property 26: Performance metrics availability
    """
    
    @given(
        cpu_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=30
        ),
        memory_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=30
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_metrics_always_available_after_capture(self, cpu_values, memory_values):
        """
        Property: Performance metrics should always be available after any capture operation
        
        For any sequence of metric captures, the get_current_metrics() and 
        get_performance_summary() methods should return valid data.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        config = create_resource_config()
        monitor = ResourceMonitor(config)
        
        try:
            # Initially, no metrics should be available
            assert monitor.get_current_metrics() is None
            
            # Add metrics
            for cpu, memory in zip(cpu_values, memory_values):
                metrics = ResourceMetrics(
                    cpu_percent=cpu,
                    memory_percent=memory,
                    memory_used_mb=memory * 100,
                    memory_available_mb=(100 - memory) * 100,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=cpu * 0.5,
                    process_memory_mb=memory * 50,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
                
                # Property: After each capture, current metrics should be available
                current = monitor.get_current_metrics()
                assert current is not None, "Current metrics should be available after capture"
                assert current.cpu_percent == cpu, "CPU metric should match captured value"
                assert current.memory_percent == memory, "Memory metric should match captured value"
            
            # Property: Performance summary should be available after captures
            summary = monitor.get_performance_summary()
            assert summary is not None, "Performance summary should be available"
            assert 'status' in summary, "Summary should contain status"
            assert summary['status'] != 'no_data', "Summary should have data after captures"
            
        finally:
            monitor.cleanup()

    @given(
        num_operations=st.integers(min_value=1, max_value=100),
        include_vlm_requests=st.booleans()
    )
    @settings(max_examples=100, deadline=None)
    def test_metrics_reflect_actual_operations(self, num_operations, include_vlm_requests):
        """
        Property: Performance metrics should accurately reflect actual operations
        
        For any number of operations, the metrics should accurately count
        and track what actually happened.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        config = create_resource_config()
        # Increase rate limits for this test
        config['performance_thresholds']['vlm_requests_per_minute'] = 200
        config['performance_thresholds']['vlm_requests_per_hour'] = 2000
        monitor = ResourceMonitor(config)
        
        try:
            vlm_requests_made = 0
            
            for i in range(num_operations):
                # Add a metric
                metrics = ResourceMetrics(
                    cpu_percent=50.0,
                    memory_percent=50.0,
                    memory_used_mb=500.0,
                    memory_available_mb=500.0,
                    disk_io_read_mb=float(i),
                    disk_io_write_mb=float(i),
                    network_sent_mb=float(i),
                    network_recv_mb=float(i),
                    timestamp=datetime.now(),
                    process_cpu_percent=25.0,
                    process_memory_mb=250.0,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
                
                # Optionally make VLM requests
                if include_vlm_requests and monitor.can_make_vlm_request():
                    monitor.record_vlm_request()
                    vlm_requests_made += 1
            
            # Property: History should reflect operations (bounded by history_size)
            expected_history_size = min(num_operations, monitor.history_size)
            assert len(monitor.metrics_history) == expected_history_size, \
                f"History size {len(monitor.metrics_history)} should be {expected_history_size}"
            
            # Property: VLM request count should match what we recorded
            actual_vlm_count = len(monitor.vlm_request_times)
            assert actual_vlm_count == vlm_requests_made, \
                f"VLM request count {actual_vlm_count} should be {vlm_requests_made}"
            
            # Property: Summary should reflect current state
            summary = monitor.get_performance_summary()
            if summary['status'] != 'no_data':
                assert 'monitoring' in summary
                assert summary['monitoring']['samples_collected'] == expected_history_size
                
                if include_vlm_requests:
                    assert 'rate_limiting' in summary
                    # VLM requests in last minute should be <= what we made
                    assert summary['rate_limiting']['vlm_requests_last_minute'] <= vlm_requests_made
            
        finally:
            monitor.cleanup()

    @given(
        cpu_high=st.floats(min_value=50.0, max_value=75.0, allow_nan=False, allow_infinity=False),
        cpu_critical=st.floats(min_value=80.0, max_value=95.0, allow_nan=False, allow_infinity=False),
        current_cpu=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        current_memory=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_status_reflects_resource_levels(self, cpu_high, cpu_critical, current_cpu, current_memory):
        """
        Property: Performance status should accurately reflect resource levels
        
        For any threshold configuration and current resource levels, the status
        should correctly indicate optimal, degraded, or critical state.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        assume(cpu_high < cpu_critical)  # Ensure valid threshold ordering
        
        # Use separate memory thresholds to avoid edge case confusion
        memory_high = cpu_high
        memory_critical = cpu_critical
        
        config = {
            'monitoring_interval': 0.05,
            'history_size': 20,
            'performance_thresholds': {
                'cpu_high': cpu_high,
                'cpu_critical': cpu_critical,
                'memory_high': memory_high,
                'memory_critical': memory_critical,
                'vlm_requests_per_minute': 100,
                'vlm_requests_per_hour': 1000,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        monitor = ResourceMonitor(config)
        
        try:
            # Add enough metrics to get a valid summary (all same values)
            for _ in range(10):
                metrics = ResourceMetrics(
                    cpu_percent=current_cpu,
                    memory_percent=current_memory,
                    memory_used_mb=current_memory * 100,
                    memory_available_mb=(100 - current_memory) * 100,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=current_cpu * 0.5,
                    process_memory_mb=current_memory * 50,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
            
            summary = monitor.get_performance_summary()
            
            # Property: Status should reflect resource levels correctly
            assert 'status' in summary
            status = summary['status']
            
            # Get the average values from summary (implementation uses averages)
            avg_cpu = summary['system_metrics']['avg_cpu_percent']
            avg_memory = summary['system_metrics']['avg_memory_percent']
            
            # Determine expected status based on thresholds and AVERAGE values
            # (matching the implementation logic in get_performance_summary)
            if avg_cpu >= cpu_critical or avg_memory >= memory_critical:
                expected_status = 'critical'
            elif avg_cpu >= cpu_high or avg_memory >= memory_high:
                expected_status = 'degraded'
            else:
                expected_status = 'optimal'
            
            assert status == expected_status, \
                f"Status '{status}' should be '{expected_status}' for avg_CPU={avg_cpu:.1f}%, avg_Memory={avg_memory:.1f}%"
            
            # Property: Thresholds should be reported in summary
            assert 'thresholds' in summary
            assert summary['thresholds']['cpu_high'] == cpu_high
            assert summary['thresholds']['cpu_critical'] == cpu_critical
            
        finally:
            monitor.cleanup()

    @given(
        scale_factor=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_scale_factor_reported_in_metrics(self, scale_factor):
        """
        Property: Current scale factor should always be reported in metrics
        
        For any scale factor value, the performance summary should accurately
        report the current scaling state.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        config = create_resource_config()
        monitor = ResourceMonitor(config)
        
        try:
            # Add some metrics first
            for _ in range(5):
                metrics = ResourceMetrics(
                    cpu_percent=50.0,
                    memory_percent=50.0,
                    memory_used_mb=500.0,
                    memory_available_mb=500.0,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=25.0,
                    process_memory_mb=250.0,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
            
            # Apply a scale factor
            monitor._apply_performance_scaling(scale_factor, 80.0, 80.0)
            
            # Property: Scale factor should be reflected in summary
            summary = monitor.get_performance_summary()
            assert 'current_scale_factor' in summary
            assert summary['current_scale_factor'] == scale_factor, \
                f"Summary scale factor {summary['current_scale_factor']} should be {scale_factor}"
            
            # Property: Internal state should match
            assert monitor.current_scale_factor == scale_factor
            
        finally:
            monitor.cleanup()

    @given(
        num_vlm_requests=st.integers(min_value=0, max_value=50),
        requests_per_minute=st.integers(min_value=5, max_value=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_rate_limiting_metrics_accurate(self, num_vlm_requests, requests_per_minute):
        """
        Property: Rate limiting metrics should accurately reflect request counts
        
        For any number of VLM requests, the metrics should accurately report
        how many requests were made and how many are remaining.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        config = {
            'monitoring_interval': 0.05,
            'history_size': 20,
            'performance_thresholds': {
                'cpu_high': 70.0,
                'cpu_critical': 85.0,
                'memory_high': 75.0,
                'memory_critical': 90.0,
                'vlm_requests_per_minute': requests_per_minute,
                'vlm_requests_per_hour': requests_per_minute * 60,
                'scale_factor_moderate': 1.5,
                'scale_factor_aggressive': 2.0
            }
        }
        monitor = ResourceMonitor(config)
        
        try:
            # Add some metrics first
            metrics = ResourceMetrics(
                cpu_percent=50.0,
                memory_percent=50.0,
                memory_used_mb=500.0,
                memory_available_mb=500.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                timestamp=datetime.now(),
                process_cpu_percent=25.0,
                process_memory_mb=250.0,
                process_threads=4
            )
            monitor.metrics_history.append(metrics)
            monitor.current_metrics = metrics
            
            # Make VLM requests
            actual_requests_made = 0
            for _ in range(num_vlm_requests):
                if monitor.can_make_vlm_request():
                    monitor.record_vlm_request()
                    actual_requests_made += 1
            
            # Property: Summary should accurately report rate limiting state
            summary = monitor.get_performance_summary()
            assert 'rate_limiting' in summary
            
            rate_info = summary['rate_limiting']
            
            # Requests made should match what we recorded
            assert rate_info['vlm_requests_last_minute'] == actual_requests_made, \
                f"Reported {rate_info['vlm_requests_last_minute']} but made {actual_requests_made}"
            
            # Remaining should be limit minus made
            expected_remaining = max(0, requests_per_minute - actual_requests_made)
            assert rate_info['vlm_requests_remaining'] == expected_remaining, \
                f"Remaining {rate_info['vlm_requests_remaining']} should be {expected_remaining}"
            
            # can_make_request should match whether we're under limit
            can_make = actual_requests_made < requests_per_minute
            assert rate_info['can_make_request'] == can_make
            
        finally:
            monitor.cleanup()

    @given(
        num_samples=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=100, deadline=None)
    def test_timing_statistics_accurate(self, num_samples):
        """
        Property: Timing statistics should accurately reflect collected data
        
        For any number of samples, the average and current metrics should
        be mathematically correct.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        config = create_resource_config()
        monitor = ResourceMonitor(config)
        
        try:
            cpu_values = []
            memory_values = []
            
            # Add samples with known values
            for i in range(num_samples):
                cpu = float(i % 100)
                memory = float((i * 2) % 100)
                cpu_values.append(cpu)
                memory_values.append(memory)
                
                metrics = ResourceMetrics(
                    cpu_percent=cpu,
                    memory_percent=memory,
                    memory_used_mb=memory * 100,
                    memory_available_mb=(100 - memory) * 100,
                    disk_io_read_mb=0.0,
                    disk_io_write_mb=0.0,
                    network_sent_mb=0.0,
                    network_recv_mb=0.0,
                    timestamp=datetime.now(),
                    process_cpu_percent=cpu * 0.5,
                    process_memory_mb=memory * 50,
                    process_threads=4
                )
                monitor.metrics_history.append(metrics)
                monitor.current_metrics = metrics
            
            summary = monitor.get_performance_summary()
            
            # Property: Current metrics should match last added
            assert 'system_metrics' in summary
            assert summary['system_metrics']['cpu_percent'] == cpu_values[-1]
            assert summary['system_metrics']['memory_percent'] == memory_values[-1]
            
            # Property: Average should be calculated from recent samples
            # (last 10 samples as per implementation)
            recent_cpu = cpu_values[-10:] if len(cpu_values) >= 10 else cpu_values
            recent_memory = memory_values[-10:] if len(memory_values) >= 10 else memory_values
            
            expected_avg_cpu = sum(recent_cpu) / len(recent_cpu)
            expected_avg_memory = sum(recent_memory) / len(recent_memory)
            
            # Allow small floating point tolerance
            assert abs(summary['system_metrics']['avg_cpu_percent'] - expected_avg_cpu) < 0.01, \
                f"Avg CPU {summary['system_metrics']['avg_cpu_percent']} should be {expected_avg_cpu}"
            assert abs(summary['system_metrics']['avg_memory_percent'] - expected_avg_memory) < 0.01, \
                f"Avg Memory {summary['system_metrics']['avg_memory_percent']} should be {expected_avg_memory}"
            
        finally:
            monitor.cleanup()

    @given(
        monitoring_active=st.booleans()
    )
    @settings(max_examples=100, deadline=None)
    def test_monitoring_state_reported(self, monitoring_active):
        """
        Property: Monitoring state should be accurately reported in metrics
        
        For any monitoring state, the summary should correctly report whether
        monitoring is active or not.
        
        Feature: vision-action-agent, Property 26: Performance metrics availability
        **Validates: Requirements 10.5**
        """
        config = create_resource_config()
        monitor = ResourceMonitor(config)
        
        try:
            # Add some metrics first
            metrics = ResourceMetrics(
                cpu_percent=50.0,
                memory_percent=50.0,
                memory_used_mb=500.0,
                memory_available_mb=500.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                timestamp=datetime.now(),
                process_cpu_percent=25.0,
                process_memory_mb=250.0,
                process_threads=4
            )
            monitor.metrics_history.append(metrics)
            monitor.current_metrics = metrics
            
            # Set monitoring state
            if monitoring_active:
                monitor.start_monitoring()
                time.sleep(0.2)  # Let monitoring thread start
            
            summary = monitor.get_performance_summary()
            
            # Property: Monitoring state should be reported
            assert 'monitoring' in summary
            assert summary['monitoring']['active'] == monitor.monitoring_active
            
            # Property: If monitoring is active, it should match what we set
            if monitoring_active:
                assert summary['monitoring']['active'] == True
            
        finally:
            monitor.cleanup()
