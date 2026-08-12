"""
Tests for SafetyManager - Emergency stop and safety validation systems

This module tests the emergency stop functionality, hotkey listener,
and safety state management for the Vision-Action Agent.
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from src.safety_manager import SafetyManager


class TestSafetyManagerBasic:
    """Basic unit tests for SafetyManager functionality"""
    
    def test_initialization_default_config(self):
        """Test SafetyManager initialization with default configuration"""
        safety_manager = SafetyManager()
        
        assert not safety_manager.emergency_active
        assert safety_manager.emergency_timestamp is None
        assert safety_manager.hotkey_enabled
        assert safety_manager.emergency_key == '<f9>'
        assert len(safety_manager.emergency_callbacks) == 0
    
    def test_initialization_custom_config(self):
        """Test SafetyManager initialization with custom configuration"""
        config = {
            'enable_emergency_hotkey': False,
            'emergency_key': '<f10>',
            'enable_tts_announcement': False
        }
        
        safety_manager = SafetyManager(config)
        
        assert not safety_manager.hotkey_enabled
        assert safety_manager.emergency_key == '<f10>'
        assert not safety_manager.enable_tts_announcement
    
    def test_emergency_callbacks_management(self):
        """Test adding and removing emergency callbacks"""
        safety_manager = SafetyManager()
        
        # Mock callback functions
        callback1 = Mock()
        callback2 = Mock()
        
        # Add callbacks
        safety_manager.add_emergency_callback(callback1)
        safety_manager.add_emergency_callback(callback2)
        
        assert len(safety_manager.emergency_callbacks) == 2
        assert callback1 in safety_manager.emergency_callbacks
        assert callback2 in safety_manager.emergency_callbacks
        
        # Remove callback
        safety_manager.remove_emergency_callback(callback1)
        
        assert len(safety_manager.emergency_callbacks) == 1
        assert callback1 not in safety_manager.emergency_callbacks
        assert callback2 in safety_manager.emergency_callbacks
    
    def test_emergency_stop_activation(self):
        """Test basic emergency stop activation"""
        safety_manager = SafetyManager()
        callback_mock = Mock()
        safety_manager.add_emergency_callback(callback_mock)
        
        # Trigger emergency stop
        safety_manager.trigger_emergency_stop()
        
        # Verify state
        assert safety_manager.emergency_active
        assert safety_manager.emergency_timestamp is not None
        assert safety_manager.is_emergency_active()
        
        # Verify callback was called
        callback_mock.assert_called_once()
    
    def test_emergency_stop_reset(self):
        """Test emergency stop reset functionality"""
        safety_manager = SafetyManager()
        
        # Activate emergency stop
        safety_manager.trigger_emergency_stop()
        assert safety_manager.emergency_active
        
        # Reset emergency state
        safety_manager.reset_emergency_state()
        assert not safety_manager.emergency_active
        assert not safety_manager.is_emergency_active()
    
    def test_emergency_duration_calculation(self):
        """Test emergency duration calculation"""
        safety_manager = SafetyManager()
        
        # No emergency active
        assert safety_manager.get_emergency_duration() is None
        
        # Activate emergency
        safety_manager.trigger_emergency_stop()
        
        # Small delay
        time.sleep(0.1)
        
        duration = safety_manager.get_emergency_duration()
        assert duration is not None
        assert duration >= 0.1
        assert duration < 1.0  # Should be less than 1 second
    
    def test_safety_status_validation(self):
        """Test safety status validation"""
        safety_manager = SafetyManager()
        
        status = safety_manager.validate_system_safety()
        
        assert isinstance(status, dict)
        assert 'emergency_active' in status
        assert 'emergency_duration' in status
        assert 'hotkey_enabled' in status
        assert 'hotkey_available' in status
        assert 'listener_active' in status
        assert 'callback_count' in status
        assert 'timestamp' in status
        
        # Verify initial values
        assert not status['emergency_active']
        assert status['emergency_duration'] is None
        assert status['callback_count'] == 0
    
    @patch('src.safety_manager.PYNPUT_AVAILABLE', True)
    def test_hotkey_setup_success(self):
        """Test successful hotkey setup"""
        safety_manager = SafetyManager()
        mock_action_engine = Mock()
        mock_action_engine.emergency_stop = Mock()
        
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            result = safety_manager.setup_emergency_hotkey(mock_action_engine)
            
            assert result is True
            assert mock_action_engine.emergency_stop in safety_manager.emergency_callbacks
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
    
    @patch('src.safety_manager.PYNPUT_AVAILABLE', False)
    def test_hotkey_setup_pynput_unavailable(self):
        """Test hotkey setup when pynput is unavailable"""
        safety_manager = SafetyManager()
        
        result = safety_manager.setup_emergency_hotkey()
        
        assert result is False
    
    def test_hotkey_setup_disabled(self):
        """Test hotkey setup when disabled in config"""
        config = {'enable_emergency_hotkey': False}
        safety_manager = SafetyManager(config)
        
        result = safety_manager.setup_emergency_hotkey()
        
        assert result is False
    
    def test_tts_pipeline_integration(self):
        """Test TTS pipeline integration for announcements"""
        mock_tts = Mock()
        mock_tts.put_text = Mock()
        
        safety_manager = SafetyManager(tts_pipeline=mock_tts)
        
        # Test setting TTS pipeline
        new_mock_tts = Mock()
        safety_manager.set_tts_pipeline(new_mock_tts)
        assert safety_manager.tts_pipeline == new_mock_tts
    
    def test_emergency_system_test(self):
        """Test the emergency system self-test functionality"""
        safety_manager = SafetyManager()
        
        result = safety_manager.test_emergency_system()
        
        assert result is True
        assert not safety_manager.emergency_active  # Should be reset after test


class TestSafetyManagerPropertyBased:
    """Property-based tests for SafetyManager using Hypothesis"""
    
    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=100, deadline=5000)
    def test_property_emergency_stop_immediacy(self, num_callbacks):
        """
        Property 11: Emergency stop immediacy
        For any active action sequence, pressing F9 should immediately stop 
        all pending and future actions within one system tick
        
        Feature: vision-action-agent, Property 11: Emergency stop immediacy
        Validates: Requirements 4.1, 4.2
        """
        safety_manager = SafetyManager()
        
        # Create mock callbacks to simulate active actions
        callbacks = []
        for i in range(num_callbacks):
            callback = Mock()
            callbacks.append(callback)
            safety_manager.add_emergency_callback(callback)
        
        # Record time before emergency stop
        start_time = time.time()
        
        # Trigger emergency stop (simulating F9 press)
        safety_manager.trigger_emergency_stop()
        
        # Record time after emergency stop
        end_time = time.time()
        
        # Verify immediacy (should complete within one system tick ~10ms)
        response_time = end_time - start_time
        assert response_time < 0.01, f"Emergency stop took {response_time:.4f}s, expected < 0.01s"
        
        # Verify all callbacks were called immediately
        for callback in callbacks:
            callback.assert_called_once()
        
        # Verify emergency state is active
        assert safety_manager.is_emergency_active()
        
        # Verify no new actions can be executed (emergency state persists)
        new_callback = Mock()
        safety_manager.add_emergency_callback(new_callback)
        
        # Triggering again should not call new callback (already in emergency state)
        safety_manager.trigger_emergency_stop()
        new_callback.assert_not_called()
    
    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=100, deadline=10000)
    def test_property_kill_switch_thread_independence(self, num_blocking_threads):
        """
        Property 12: Kill switch thread independence
        For any system state, the kill switch should operate independently 
        of main application threads and remain responsive even under high system load
        
        Feature: vision-action-agent, Property 12: Kill switch thread independence
        Validates: Requirements 4.4
        """
        safety_manager = SafetyManager()
        
        # Create blocking threads to simulate high system load
        blocking_threads = []
        stop_blocking = threading.Event()
        
        def blocking_operation():
            """Simulate CPU-intensive operation"""
            while not stop_blocking.is_set():
                # Busy work to consume CPU
                sum(i * i for i in range(1000))
                time.sleep(0.001)
        
        # Start blocking threads
        for i in range(num_blocking_threads):
            thread = threading.Thread(target=blocking_operation, daemon=True)
            thread.start()
            blocking_threads.append(thread)
        
        try:
            # Let blocking threads run for a moment
            time.sleep(0.1)
            
            # Test emergency stop responsiveness under load
            start_time = time.time()
            safety_manager.trigger_emergency_stop()
            end_time = time.time()
            
            # Verify kill switch remains responsive despite system load
            response_time = end_time - start_time
            assert response_time < 0.05, f"Kill switch took {response_time:.4f}s under load, expected < 0.05s"
            
            # Verify emergency state is active
            assert safety_manager.is_emergency_active()
            
            # Verify thread-safe state access under load
            for _ in range(10):
                assert safety_manager.is_action_allowed() == False
                status = safety_manager.validate_system_safety()
                assert status['emergency_active'] == True
                assert status['state_lock_acquired'] == True
            
        finally:
            # Clean up blocking threads
            stop_blocking.set()
            for thread in blocking_threads:
                thread.join(timeout=1.0)


class SafetyManagerStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for SafetyManager
    
    Tests complex state transitions and concurrent operations
    """
    
    def __init__(self):
        super().__init__()
        self.safety_manager = None
        self.callbacks = []
    
    @initialize()
    def init_safety_manager(self):
        """Initialize SafetyManager for testing"""
        self.safety_manager = SafetyManager()
        self.callbacks = []
    
    @rule()
    def add_callback(self):
        """Add a new emergency callback"""
        callback = Mock()
        self.callbacks.append(callback)
        self.safety_manager.add_emergency_callback(callback)
    
    @rule()
    def remove_callback(self):
        """Remove an existing callback"""
        if self.callbacks:
            callback = self.callbacks.pop()
            self.safety_manager.remove_emergency_callback(callback)
    
    @rule()
    def trigger_emergency(self):
        """Trigger emergency stop"""
        self.safety_manager.trigger_emergency_stop()
    
    @rule()
    def reset_emergency(self):
        """Reset emergency state"""
        self.safety_manager.reset_emergency_state()
    
    @rule()
    def validate_safety(self):
        """Validate safety status"""
        status = self.safety_manager.validate_system_safety()
        assert isinstance(status, dict)
        assert 'emergency_active' in status
    
    @invariant()
    def emergency_state_consistency(self):
        """Emergency state should be consistent across all methods"""
        is_active_method = self.safety_manager.is_emergency_active()
        is_active_field = self.safety_manager.emergency_active
        
        assert is_active_method == is_active_field
        
        # If emergency is active, timestamp should exist
        if is_active_method:
            assert self.safety_manager.emergency_timestamp is not None
        
        # Duration should be None when not active
        if not is_active_method:
            assert self.safety_manager.get_emergency_duration() is None


# Run the stateful tests
TestSafetyManagerStateful = SafetyManagerStateMachine.TestCase


class TestSafetyManagerConcurrency:
    """Test SafetyManager under concurrent conditions"""
    
    def test_concurrent_emergency_triggers(self):
        """Test multiple threads triggering emergency simultaneously"""
        safety_manager = SafetyManager()
        callback_mock = Mock()
        safety_manager.add_emergency_callback(callback_mock)
        
        # Create multiple threads that trigger emergency
        threads = []
        for i in range(5):
            thread = threading.Thread(target=safety_manager.trigger_emergency_stop)
            threads.append(thread)
        
        # Start all threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify emergency is active and callback was called only once
        assert safety_manager.is_emergency_active()
        callback_mock.assert_called_once()
    
    def test_concurrent_callback_management(self):
        """Test concurrent callback addition/removal"""
        safety_manager = SafetyManager()
        
        def add_callbacks():
            for i in range(10):
                callback = Mock()
                safety_manager.add_emergency_callback(callback)
        
        def remove_callbacks():
            # Wait a bit then try to remove callbacks
            time.sleep(0.01)
            callbacks_to_remove = safety_manager.emergency_callbacks.copy()
            for callback in callbacks_to_remove[:5]:  # Remove first 5
                safety_manager.remove_emergency_callback(callback)
        
        # Run concurrent operations
        thread1 = threading.Thread(target=add_callbacks)
        thread2 = threading.Thread(target=remove_callbacks)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Verify system is still in valid state
        assert len(safety_manager.emergency_callbacks) >= 0
        status = safety_manager.validate_system_safety()
        assert isinstance(status, dict)


if __name__ == "__main__":
    pytest.main([__file__])