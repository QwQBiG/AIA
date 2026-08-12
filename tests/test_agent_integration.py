"""
Integration tests for the Vision-Action Agent system.

This module tests the end-to-end agent workflow including:
- Screenshot capture to action execution
- Safety mechanisms under various conditions
- Dual-mode operation with chat and agent running simultaneously

Requirements covered:
- 1.1: Dual-mode operation
- 4.1: Emergency stop functionality
- 6.3: Error handling and resilience
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from src.agent_manager import AgentManager, AgentState
from src.action_engine import ActionEngine, ActionResult
from src.vision_client import VisionClient, AgentCommand
from src.safety_manager import SafetyManager


class TestAgentSystemIntegration:
    """Integration tests for the complete agent system."""
    
    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration."""
        return {
            'enabled': True,
            'loop_interval': 0.5,
            'cooldown_period': 0.1,
            'chat_detection_enabled': True,
            'chat_timeout': 5.0,
            'vision': {
                'vision_model': 'llava',
                'capture_region': None,
                'max_image_dimension': 512
            },
            'actions': {
                'use_directinput': False,
                'action_delay': 0.05,
                'click_duration': 0.05,
                'clamp_region': None,
                'debug_overlay': {'enabled': False}
            },
            'safety': {
                'enable_emergency_hotkey': False,  # Disable for testing
                'emergency_key': '<f9>',
                'enable_tts_announcement': False
            },
            'resource_monitoring': {
                'enabled': False,  # Disable for testing
                'cpu_threshold': 80.0,
                'memory_threshold': 85.0
            }
        }
    
    @pytest.fixture
    def mock_tts_pipeline(self):
        """Create mock TTS pipeline."""
        mock = AsyncMock()
        mock.put_text = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_gui_controller(self):
        """Create mock GUI controller."""
        mock = Mock()
        mock.log_message = Mock()
        return mock
    
    @pytest.fixture
    def agent_manager(self, agent_config, mock_tts_pipeline, mock_gui_controller):
        """Create AgentManager with mocked dependencies."""
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Configure VisionClient mock
            mock_vision = Mock()
            mock_vision.capture_screen = AsyncMock(return_value="base64_image_data")
            mock_vision.analyze_scene = AsyncMock(return_value=AgentCommand(
                thought="Test thought",
                commentary="Test commentary",
                action_type="wait",
                target=None,
                key=None,
                confidence=0.8,
                timestamp=datetime.now()
            ))
            mock_vision.cleanup = Mock()
            mock_vision.cleanup_temporary_data = AsyncMock()
            mock_vision_cls.return_value = mock_vision
            
            # Configure ActionEngine mock
            mock_action = Mock()
            mock_action.execute_command = Mock(return_value=ActionResult(
                success=True,
                action_type="wait",
                target=None,
                error_message=None,
                execution_time=0.1,
                timestamp=datetime.now()
            ))
            mock_action.is_safety_active = Mock(return_value=False)
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action_cls.return_value = mock_action
            
            # Configure ResourceMonitor mock
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.get_performance_summary = Mock(return_value={})
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            manager = AgentManager(agent_config, mock_tts_pipeline, mock_gui_controller)
            yield manager
            manager.cleanup()


class TestEndToEndAgentWorkflow:
    """End-to-end tests for agent workflow from screenshot to action."""
    
    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration."""
        return {
            'enabled': True,
            'loop_interval': 0.5,
            'cooldown_period': 0.1,
            'chat_detection_enabled': True,
            'chat_timeout': 5.0,
            'vision': {
                'vision_model': 'llava',
                'capture_region': None,
                'max_image_dimension': 512
            },
            'actions': {
                'use_directinput': False,
                'action_delay': 0.05,
                'click_duration': 0.05,
                'clamp_region': None,
                'debug_overlay': {'enabled': False}
            },
            'safety': {
                'enable_emergency_hotkey': False,
                'emergency_key': '<f9>',
                'enable_tts_announcement': False
            },
            'resource_monitoring': {
                'enabled': False,
                'cpu_threshold': 80.0,
                'memory_threshold': 85.0
            }
        }
    
    @pytest.mark.asyncio
    async def test_complete_agent_cycle(self, agent_config):
        """
        Test complete agent cycle: screenshot -> analysis -> action -> commentary.
        
        Validates Requirements 1.1, 6.3
        """
        mock_tts = AsyncMock()
        mock_tts.put_text = AsyncMock()
        
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Track workflow steps
            workflow_steps = []
            
            # Configure VisionClient mock
            mock_vision = Mock()
            async def capture_screen_mock(*args, **kwargs):
                workflow_steps.append('screenshot_captured')
                return "base64_image_data"
            mock_vision.capture_screen = capture_screen_mock
            
            async def analyze_scene_mock(*args, **kwargs):
                workflow_steps.append('scene_analyzed')
                return AgentCommand(
                    thought="I see a button to click",
                    commentary="Let me click that button",
                    action_type="click",
                    target=(100, 200),
                    key=None,
                    confidence=0.9,
                    timestamp=datetime.now()
                )
            mock_vision.analyze_scene = analyze_scene_mock
            mock_vision.cleanup = Mock()
            mock_vision.cleanup_temporary_data = AsyncMock()
            mock_vision_cls.return_value = mock_vision
            
            # Configure ActionEngine mock
            mock_action = Mock()
            def execute_command_mock(command):
                workflow_steps.append(f'action_executed:{command.action_type}')
                return ActionResult(
                    success=True,
                    action_type=command.action_type,
                    target=command.target,
                    error_message=None,
                    execution_time=0.1,
                    timestamp=datetime.now()
                )
            mock_action.execute_command = execute_command_mock
            mock_action.is_safety_active = Mock(return_value=False)
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action_cls.return_value = mock_action
            
            # Configure ResourceMonitor mock
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.get_performance_summary = Mock(return_value={})
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            # Create agent manager
            manager = AgentManager(agent_config, mock_tts, None)
            
            try:
                # Execute one agent cycle directly
                await manager._execute_agent_cycle()
                
                # Verify workflow steps occurred in correct order
                assert 'screenshot_captured' in workflow_steps, "Screenshot should be captured"
                assert 'scene_analyzed' in workflow_steps, "Scene should be analyzed"
                assert 'action_executed:click' in workflow_steps, "Action should be executed"
                
                # Verify TTS was called with commentary
                mock_tts.put_text.assert_called()
                
                # Verify state was updated
                assert manager.agent_state.last_action is not None
                assert manager.agent_state.loop_count == 1
                
            finally:
                manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_agent_cycle_with_vision_failure(self, agent_config):
        """
        Test agent cycle handles vision failures gracefully.
        
        Validates Requirements 6.3, 6.4
        """
        mock_tts = AsyncMock()
        mock_tts.put_text = AsyncMock()
        
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Configure VisionClient to fail
            mock_vision = Mock()
            mock_vision.capture_screen = AsyncMock(side_effect=Exception("Screen capture failed"))
            mock_vision.cleanup = Mock()
            mock_vision_cls.return_value = mock_vision
            
            # Configure ActionEngine mock
            mock_action = Mock()
            mock_action.execute_command = Mock()
            mock_action.is_safety_active = Mock(return_value=False)
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action_cls.return_value = mock_action
            
            # Configure ResourceMonitor mock
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.get_performance_summary = Mock(return_value={})
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            manager = AgentManager(agent_config, mock_tts, None)
            
            try:
                # Execute agent cycle - should handle error gracefully
                await manager._execute_agent_cycle()
                
                # Verify vision failure was tracked
                assert manager.performance_metrics['vision_failures'] > 0
                
                # Verify action was NOT executed (since vision failed)
                mock_action.execute_command.assert_not_called()
                
            finally:
                manager.cleanup()


class TestSafetyMechanisms:
    """Tests for safety mechanisms under various conditions."""
    
    @pytest.fixture
    def safety_manager(self):
        """Create SafetyManager for testing."""
        config = {
            'enable_emergency_hotkey': False,  # Disable for testing
            'emergency_key': '<f9>',
            'enable_tts_announcement': False
        }
        manager = SafetyManager(config=config)
        yield manager
        manager.shutdown()
    
    def test_emergency_stop_blocks_actions(self, safety_manager):
        """
        Test that emergency stop blocks all actions.
        
        Validates Requirements 4.1, 4.2
        """
        # Initially actions should be allowed
        assert safety_manager.is_action_allowed()
        
        # Trigger emergency stop
        safety_manager.trigger_emergency_stop()
        
        # Actions should now be blocked
        assert not safety_manager.is_action_allowed()
        assert safety_manager.is_emergency_active()
    
    def test_emergency_stop_persists_until_reset(self, safety_manager):
        """
        Test that emergency state persists until manual reset.
        
        Validates Requirements 4.5
        """
        # Trigger emergency stop
        safety_manager.trigger_emergency_stop()
        assert safety_manager.is_emergency_active()
        
        # State should persist
        time.sleep(0.1)
        assert safety_manager.is_emergency_active()
        
        # Reset should clear the state
        safety_manager.reset_emergency_state()
        assert not safety_manager.is_emergency_active()
        assert safety_manager.is_action_allowed()
    
    def test_emergency_callbacks_are_called(self, safety_manager):
        """
        Test that emergency callbacks are invoked.
        
        Validates Requirements 4.1, 4.2
        """
        callback_called = []
        
        def test_callback():
            callback_called.append(True)
        
        safety_manager.add_emergency_callback(test_callback)
        safety_manager.trigger_emergency_stop()
        
        assert len(callback_called) == 1
    
    @pytest.mark.asyncio
    async def test_agent_respects_safety_lock(self):
        """
        Test that agent manager respects safety lock.
        
        Validates Requirements 4.1, 4.2, 4.5
        """
        agent_config = {
            'enabled': True,
            'loop_interval': 0.5,
            'cooldown_period': 0.1,
            'vision': {'vision_model': 'llava'},
            'actions': {'use_directinput': False, 'debug_overlay': {'enabled': False}},
            'safety': {'enable_emergency_hotkey': False},
            'resource_monitoring': {'enabled': False}
        }
        
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Configure mocks
            mock_vision = Mock()
            mock_vision.capture_screen = AsyncMock(return_value="base64_data")
            mock_vision.analyze_scene = AsyncMock(return_value=AgentCommand(
                thought="Test", commentary="Test", action_type="click",
                target=(100, 100), key=None, confidence=0.9, timestamp=datetime.now()
            ))
            mock_vision.cleanup = Mock()
            mock_vision.cleanup_temporary_data = AsyncMock()
            mock_vision_cls.return_value = mock_vision
            
            mock_action = Mock()
            mock_action.execute_command = Mock(return_value=ActionResult(
                success=True, action_type="click", target=(100, 100),
                error_message=None, execution_time=0.1, timestamp=datetime.now()
            ))
            mock_action.is_safety_active = Mock(return_value=True)  # Safety is active
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action_cls.return_value = mock_action
            
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            manager = AgentManager(agent_config, None, None)
            
            try:
                # Start agent loop
                await manager.start_agent_loop()
                
                # Wait a bit for loop to run
                await asyncio.sleep(0.3)
                
                # Agent should be in emergency mode due to safety lock
                assert manager.agent_state.mode == "emergency"
                
            finally:
                manager.stop_agent_loop()
                manager.cleanup()


class TestDualModeOperation:
    """Tests for dual-mode operation with chat and agent."""
    
    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration."""
        return {
            'enabled': True,
            'loop_interval': 0.5,
            'cooldown_period': 0.1,
            'chat_detection_enabled': True,
            'chat_timeout': 2.0,
            'vision': {'vision_model': 'llava'},
            'actions': {'use_directinput': False, 'debug_overlay': {'enabled': False}},
            'safety': {'enable_emergency_hotkey': False},
            'resource_monitoring': {'enabled': False}
        }
    
    @pytest.mark.asyncio
    async def test_chat_pauses_agent(self, agent_config):
        """
        Test that chat activity pauses agent loop.
        
        Validates Requirements 1.2, 1.3
        """
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Configure mocks
            mock_vision = Mock()
            mock_vision.capture_screen = AsyncMock(return_value="base64_data")
            mock_vision.analyze_scene = AsyncMock(return_value=AgentCommand(
                thought="Test", commentary="Test", action_type="wait",
                target=None, key=None, confidence=0.8, timestamp=datetime.now()
            ))
            mock_vision.cleanup = Mock()
            mock_vision.cleanup_temporary_data = AsyncMock()
            mock_vision_cls.return_value = mock_vision
            
            mock_action = Mock()
            mock_action.execute_command = Mock(return_value=ActionResult(
                success=True, action_type="wait", target=None,
                error_message=None, execution_time=0.1, timestamp=datetime.now()
            ))
            mock_action.is_safety_active = Mock(return_value=False)
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action_cls.return_value = mock_action
            
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            manager = AgentManager(agent_config, None, None)
            
            try:
                # Start agent loop
                await manager.start_agent_loop()
                await asyncio.sleep(0.2)
                
                # Agent should be active
                assert manager.agent_state.mode == "active"
                
                # Pause for chat
                manager.pause_for_chat()
                
                # Agent should be paused
                assert manager.agent_state.mode == "paused"
                assert manager.agent_state.chat_mode_active
                
                # Resume after chat
                manager.resume_agent_loop()
                
                # Agent should be active again
                assert manager.agent_state.mode == "active"
                assert not manager.agent_state.chat_mode_active
                
            finally:
                manager.stop_agent_loop()
                manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_auto_resume_after_chat_timeout(self, agent_config):
        """
        Test that agent auto-resumes after chat timeout.
        
        Validates Requirements 1.3
        """
        # Use short timeout for testing
        agent_config['chat_timeout'] = 0.5
        
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Configure mocks
            mock_vision = Mock()
            mock_vision.capture_screen = AsyncMock(return_value="base64_data")
            mock_vision.analyze_scene = AsyncMock(return_value=AgentCommand(
                thought="Test", commentary="Test", action_type="wait",
                target=None, key=None, confidence=0.8, timestamp=datetime.now()
            ))
            mock_vision.cleanup = Mock()
            mock_vision.cleanup_temporary_data = AsyncMock()
            mock_vision_cls.return_value = mock_vision
            
            mock_action = Mock()
            mock_action.execute_command = Mock(return_value=ActionResult(
                success=True, action_type="wait", target=None,
                error_message=None, execution_time=0.1, timestamp=datetime.now()
            ))
            mock_action.is_safety_active = Mock(return_value=False)
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action_cls.return_value = mock_action
            
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            manager = AgentManager(agent_config, None, None)
            
            try:
                # Start agent loop
                await manager.start_agent_loop()
                await asyncio.sleep(0.2)
                
                # Pause for chat
                manager.pause_for_chat()
                assert manager.agent_state.mode == "paused"
                
                # Wait for auto-resume (timeout + some buffer)
                await asyncio.sleep(0.8)
                
                # Check auto-resume was triggered
                # Note: The actual auto-resume happens in the agent loop
                manager._check_auto_resume()
                
                # Should have resumed
                assert not manager.agent_state.chat_mode_active
                
            finally:
                manager.stop_agent_loop()
                manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_state_preservation_across_mode_transitions(self, agent_config):
        """
        Test that state is preserved across mode transitions.
        
        Validates Requirements 1.5
        """
        with patch('src.agent_manager.VisionClient') as mock_vision_cls, \
             patch('src.agent_manager.ActionEngine') as mock_action_cls, \
             patch('src.agent_manager.ResourceMonitor') as mock_resource_cls:
            
            # Configure mocks
            mock_vision = Mock()
            mock_vision.capture_screen = AsyncMock(return_value="base64_data")
            mock_vision.analyze_scene = AsyncMock(return_value=AgentCommand(
                thought="Test", commentary="Test", action_type="wait",
                target=None, key=None, confidence=0.8, timestamp=datetime.now()
            ))
            mock_vision.cleanup = Mock()
            mock_vision.cleanup_temporary_data = AsyncMock()
            mock_vision.capture_region = None
            mock_vision.model_name = 'llava'
            mock_vision_cls.return_value = mock_vision
            
            mock_action = Mock()
            mock_action.execute_command = Mock(return_value=ActionResult(
                success=True, action_type="wait", target=None,
                error_message=None, execution_time=0.1, timestamp=datetime.now()
            ))
            mock_action.is_safety_active = Mock(return_value=False)
            mock_action.emergency_stop = Mock()
            mock_action.reset_safety_lock = Mock()
            mock_action.get_action_history = Mock(return_value=[])
            mock_action.cleanup = Mock()
            mock_action.action_delay = 0.1
            mock_action_cls.return_value = mock_action
            
            mock_resource = Mock()
            mock_resource.start_monitoring = Mock()
            mock_resource.stop_monitoring = Mock()
            mock_resource.can_make_vlm_request = Mock(return_value=True)
            mock_resource.record_vlm_request = Mock()
            mock_resource.register_scale_callback = Mock()
            mock_resource.cleanup = Mock()
            mock_resource.monitoring_active = False
            mock_resource_cls.return_value = mock_resource
            
            manager = AgentManager(agent_config, None, None)
            
            try:
                # Start agent and run a few cycles
                await manager.start_agent_loop()
                await asyncio.sleep(0.3)
                
                # Record state before transition
                loop_count_before = manager.agent_state.loop_count
                objective_before = manager.agent_state.current_objective
                
                # Transition to chat mode
                manager.pause_for_chat()
                
                # State should be saved
                assert manager.agent_state.saved_context is not None
                
                # Resume
                manager.resume_agent_loop()
                
                # State should be restored
                assert manager.agent_state.loop_count == loop_count_before
                
            finally:
                manager.stop_agent_loop()
                manager.cleanup()
