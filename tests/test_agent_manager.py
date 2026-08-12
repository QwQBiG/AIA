"""
Tests for AgentManager - Vision-Action Agent orchestration

Tests dual-mode operation, chat priority system, and agent loop management.
"""

import asyncio
import pytest
import threading
import time
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from hypothesis import given, strategies as st, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from src.agent_manager import AgentManager, AgentState
from src.vision_client import AgentCommand
from src.action_engine import ActionResult


class TestAgentManagerBasic:
    """Basic unit tests for AgentManager functionality"""
    
    @pytest.fixture
    def mock_tts_pipeline(self):
        """Mock TTS pipeline with put_text method"""
        mock = AsyncMock()
        mock.put_text = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_gui_controller(self):
        """Mock GUI controller"""
        return Mock()
    
    @pytest.fixture
    def agent_config(self):
        """Basic agent configuration"""
        return {
            'vision': {
                'model_name': 'llava',
                'capture_region': None
            },
            'actions': {
                'use_directinput': True,
                'action_delay': 0.1
            },
            'loop_interval': 0.5,
            'cooldown_period': 0.2
        }
    
    @pytest.fixture
    def agent_manager(self, agent_config, mock_tts_pipeline, mock_gui_controller):
        """Create AgentManager instance with mocked dependencies"""
        with patch('src.agent_manager.VisionClient'), \
             patch('src.agent_manager.ActionEngine'):
            manager = AgentManager(agent_config, mock_tts_pipeline, mock_gui_controller)
            yield manager
            # Cleanup
            manager.cleanup()
    
    def test_initialization(self, agent_manager):
        """Test AgentManager initializes correctly"""
        assert agent_manager.loop_active is False
        assert agent_manager.agent_state.mode == "idle"
        assert agent_manager.chat_priority_event.is_set()  # Should start allowing operations
    
    def test_configuration_update(self, agent_manager):
        """Test dynamic configuration updates"""
        new_config = {
            'loop_interval': 1.0,
            'cooldown_period': 0.5
        }
        
        agent_manager.update_configuration(new_config)
        
        assert agent_manager.loop_interval == 1.0
        assert agent_manager.cooldown_period == 0.5
    
    def test_chat_priority_control(self, agent_manager):
        """Test chat priority pause and resume"""
        # Initially should allow agent operations
        assert agent_manager.chat_priority_event.is_set()
        
        # Pause for chat
        agent_manager.pause_for_chat()
        assert not agent_manager.chat_priority_event.is_set()
        
        # Resume after chat
        agent_manager.resume_agent_loop()
        assert agent_manager.chat_priority_event.is_set()
    
    def test_emergency_stop(self, agent_manager):
        """Test emergency stop functionality"""
        agent_manager.emergency_stop()
        
        assert agent_manager.agent_state.mode == "emergency"
        agent_manager.action_engine.emergency_stop.assert_called_once()
    
    def test_state_tracking(self, agent_manager):
        """Test agent state tracking and updates"""
        state = agent_manager.get_agent_state()
        
        assert isinstance(state, AgentState)
        assert state.mode == "idle"
        assert state.loop_count == 0
        assert 'total_cycles' in state.performance_metrics


class TestAgentManagerStateful(RuleBasedStateMachine):
    """
    Stateful property-based testing for AgentManager
    
    Tests complex interactions between agent loop, chat priority,
    and emergency stop mechanisms.
    """
    
    def __init__(self):
        super().__init__()
        self.agent_manager = None
        self.mock_tts = None
        self.mock_gui = None
        self.chat_events = []
        self.agent_events = []
    
    @initialize()
    def setup_agent_manager(self):
        """Initialize AgentManager with mocked dependencies"""
        self.mock_tts = AsyncMock()
        self.mock_tts.put_text = AsyncMock()
        self.mock_gui = Mock()
        
        config = {
            'vision': {'model_name': 'llava'},
            'actions': {'use_directinput': True},
            'loop_interval': 0.1,  # Fast for testing
            'cooldown_period': 0.05
        }
        
        with patch('src.agent_manager.VisionClient') as mock_vision, \
             patch('src.agent_manager.ActionEngine') as mock_action:
            
            # Configure mocks
            mock_vision.return_value.capture_screen = AsyncMock(return_value="fake_image")
            mock_vision.return_value.analyze_scene = AsyncMock(
                return_value=AgentCommand(
                    thought="Test thought",
                    commentary="Test commentary",
                    action_type="wait",
                    target=None,
                    key=None,
                    confidence=0.8,
                    timestamp=None
                )
            )
            mock_action.return_value.execute_command = Mock(
                return_value=ActionResult(
                    success=True,
                    action_type="wait",
                    target=None,
                    error_message=None,
                    execution_time=0.1,
                    timestamp=datetime.now()
                )
            )
            mock_action.return_value.is_safety_active = Mock(return_value=False)
            mock_action.return_value.get_action_history = Mock(return_value=[])
            
            self.agent_manager = AgentManager(config, self.mock_tts, self.mock_gui)
    
    @rule()
    def start_agent_mode(self):
        """Start agent mode"""
        if not self.agent_manager.loop_active:
            asyncio.run(self.agent_manager.start_agent_loop())
            self.agent_events.append("started")
            time.sleep(0.1)  # Allow loop to start
    
    @rule()
    def stop_agent_mode(self):
        """Stop agent mode"""
        if self.agent_manager.loop_active:
            self.agent_manager.stop_agent_loop()
            self.agent_events.append("stopped")
    
    @rule()
    def pause_for_chat(self):
        """Simulate chat interaction"""
        self.agent_manager.pause_for_chat()
        self.chat_events.append("paused")
        time.sleep(0.05)  # Simulate chat processing time
    
    @rule()
    def resume_after_chat(self):
        """Resume after chat interaction"""
        self.agent_manager.resume_agent_loop()
        self.chat_events.append("resumed")
    
    @rule()
    def trigger_emergency_stop(self):
        """Trigger emergency stop"""
        self.agent_manager.emergency_stop()
        self.agent_events.append("emergency")
    
    @rule()
    def reset_emergency(self):
        """Reset emergency state"""
        self.agent_manager.reset_emergency_state()
        self.agent_events.append("reset")
    
    @invariant()
    def agent_state_is_consistent(self):
        """Agent state should always be consistent"""
        state = self.agent_manager.get_agent_state()
        
        # State should be one of the valid modes
        assert state.mode in ["idle", "active", "paused", "emergency"]
        
        # Performance metrics should be non-negative
        assert state.performance_metrics.get('total_cycles', 0) >= 0
        assert state.performance_metrics.get('successful_actions', 0) >= 0
        assert state.performance_metrics.get('failed_actions', 0) >= 0
    
    @invariant()
    def chat_priority_consistency(self):
        """Chat priority system should be consistent"""
        # If agent is active and not in emergency, chat priority should control pause state
        if (self.agent_manager.loop_active and 
            self.agent_manager.agent_state.mode != "emergency"):
            
            if not self.agent_manager.chat_priority_event.is_set():
                # When chat has priority, agent should be paused or pausing
                assert self.agent_manager.agent_state.mode in ["paused", "active"]
    
    def teardown(self):
        """Clean up after testing"""
        if self.agent_manager:
            self.agent_manager.cleanup()


# Feature: vision-action-agent, Property 2: Priority-based pause and resume
@given(
    chat_events=st.integers(min_value=1, max_value=4),
    chat_intervals=st.lists(st.floats(min_value=0.1, max_value=0.5), min_size=1, max_size=4),
    auto_resume_timeout=st.floats(min_value=0.5, max_value=2.0)
)
@settings(max_examples=8, deadline=None)
def test_priority_based_pause_and_resume_property(chat_events, chat_intervals, auto_resume_timeout):
    """
    Property 2: Priority-based pause and resume
    For any active agent loop, when a chat event occurs, the loop should pause 
    immediately and resume automatically when the chat interaction completes
    
    Validates: Requirements 1.2, 1.3
    """
    # Setup
    mock_tts = AsyncMock()
    mock_tts.put_text = AsyncMock()
    mock_gui = Mock()
    
    config = {
        'vision': {'model_name': 'llava'},
        'actions': {'use_directinput': True},
        'loop_interval': 0.2,
        'cooldown_period': 0.1,
        'chat_detection_enabled': True,
        'chat_timeout': auto_resume_timeout
    }
    
    with patch('src.agent_manager.VisionClient') as mock_vision, \
         patch('src.agent_manager.ActionEngine') as mock_action:
        
        # Configure mocks for successful operation
        mock_vision.return_value.capture_screen = AsyncMock(return_value="fake_image")
        mock_vision.return_value.analyze_scene = AsyncMock(
            return_value=AgentCommand(
                thought="Test thought",
                commentary="Test commentary",
                action_type="wait",
                target=None,
                key=None,
                confidence=0.8,
                timestamp=None
            )
        )
        mock_action.return_value.execute_command = Mock(
            return_value=ActionResult(
                success=True,
                action_type="wait",
                target=None,
                error_message=None,
                execution_time=0.1,
                timestamp=datetime.now()
            )
        )
        mock_action.return_value.is_safety_active = Mock(return_value=False)
        mock_action.return_value.get_action_history = Mock(return_value=[])
        
        agent_manager = AgentManager(config, mock_tts, mock_gui)
        
        try:
            # Start agent mode
            asyncio.run(agent_manager.start_agent_loop())
            time.sleep(0.2)  # Allow agent to start
            
            # Verify agent is initially active
            initial_state = agent_manager.get_agent_state()
            assert initial_state.mode in ["active", "idle"]
            assert agent_manager.chat_priority_event.is_set()
            
            # Test multiple chat events with priority-based pause/resume
            for i in range(min(chat_events, len(chat_intervals))):
                chat_interval = chat_intervals[i]
                
                # Trigger chat activity (should pause immediately)
                pre_chat_state = agent_manager.get_agent_state()
                chat_start_time = time.time()
                
                agent_manager.notify_chat_activity()
                
                # Verify immediate pause
                time.sleep(0.1)  # Small delay to allow pause to take effect
                paused_state = agent_manager.get_agent_state()
                
                # Agent should be paused immediately
                assert not agent_manager.chat_priority_event.is_set(), \
                    "Agent should pause immediately when chat activity is detected"
                assert paused_state.mode == "paused", \
                    f"Agent mode should be 'paused', got '{paused_state.mode}'"
                assert paused_state.chat_mode_active == True, \
                    "Chat mode should be active when paused for chat"
                
                # Verify state preservation during pause
                assert paused_state.previous_mode is not None, \
                    "Previous mode should be saved during pause"
                
                # Simulate chat processing time
                time.sleep(chat_interval)
                
                # Verify agent remains paused during chat
                during_chat_state = agent_manager.get_agent_state()
                assert during_chat_state.mode == "paused"
                assert not agent_manager.chat_priority_event.is_set()
                
                # Wait for automatic resume (timeout-based)
                resume_start_time = time.time()
                max_wait_time = auto_resume_timeout + 1.0  # Add buffer
                
                resumed = False
                while (time.time() - resume_start_time) < max_wait_time:
                    if agent_manager.chat_priority_event.is_set():
                        resumed = True
                        break
                    time.sleep(0.1)
                
                # Verify automatic resume occurred
                assert resumed, \
                    f"Agent should auto-resume within {auto_resume_timeout}s timeout"
                
                resume_time = time.time()
                actual_resume_delay = resume_time - chat_start_time - chat_interval
                
                # Resume should happen within reasonable time of timeout
                assert actual_resume_delay <= auto_resume_timeout + 0.5, \
                    f"Auto-resume took too long: {actual_resume_delay:.2f}s vs timeout {auto_resume_timeout:.2f}s"
                
                # Verify state after resume
                resumed_state = agent_manager.get_agent_state()
                assert resumed_state.chat_mode_active == False, \
                    "Chat mode should be inactive after resume"
                assert resumed_state.mode in ["active", "idle"], \
                    f"Agent should be active after resume, got '{resumed_state.mode}'"
                assert agent_manager.chat_priority_event.is_set(), \
                    "Chat priority event should be set after resume"
                
                # Brief pause between chat events
                time.sleep(0.1)
            
            # Final verification - agent should be operational
            final_state = agent_manager.get_agent_state()
            assert final_state.mode in ["active", "idle"]
            assert not final_state.chat_mode_active
            assert agent_manager.chat_priority_event.is_set()
            
            # Test chat priority status
            priority_status = agent_manager.get_chat_priority_status()
            assert priority_status['chat_detection_enabled'] == True
            assert priority_status['chat_timeout'] == auto_resume_timeout
            assert priority_status['chat_mode_active'] == False
            
        finally:
            agent_manager.cleanup()


# Feature: vision-action-agent, Property 3: State preservation across mode transitions
@given(
    mode_transitions=st.integers(min_value=2, max_value=5),
    pause_duration=st.floats(min_value=0.1, max_value=0.5),
    initial_loop_count=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=10, deadline=5000)
def test_state_preservation_across_mode_transitions_property(mode_transitions, pause_duration, initial_loop_count):
    """
    Property 3: State preservation across mode transitions
    For any system state, switching between Chat Mode and Agent Mode should 
    preserve the internal state of both modes
    
    Validates: Requirements 1.5
    """
    # Setup
    mock_tts = AsyncMock()
    mock_tts.put_text = AsyncMock()
    mock_gui = Mock()
    
    config = {
        'vision': {'model_name': 'llava'},
        'actions': {'use_directinput': True},
        'loop_interval': 0.2,
        'cooldown_period': 0.1
    }
    
    with patch('src.agent_manager.VisionClient') as mock_vision, \
         patch('src.agent_manager.ActionEngine') as mock_action:
        
        # Configure mocks for successful operation
        mock_vision.return_value.capture_screen = AsyncMock(return_value="fake_image")
        mock_vision.return_value.analyze_scene = AsyncMock(
            return_value=AgentCommand(
                thought="Test thought",
                commentary="Test commentary",
                action_type="wait",
                target=None,
                key=None,
                confidence=0.8,
                timestamp=None
            )
        )
        mock_action.return_value.execute_command = Mock(
            return_value=ActionResult(
                success=True,
                action_type="wait",
                target=None,
                error_message=None,
                execution_time=0.1,
                timestamp=datetime.now()
            )
        )
        mock_action.return_value.is_safety_active = Mock(return_value=False)
        mock_action.return_value.get_action_history = Mock(return_value=[])
        
        agent_manager = AgentManager(config, mock_tts, mock_gui)
        
        try:
            # Set initial state
            agent_manager.agent_state.loop_count = initial_loop_count
            agent_manager.agent_state.current_objective = "Initial test objective"
            agent_manager.performance_metrics['successful_actions'] = initial_loop_count
            
            # Start agent mode
            asyncio.run(agent_manager.start_agent_loop())
            time.sleep(0.2)  # Allow agent to start
            
            # Record initial state before transitions
            initial_state = agent_manager.get_agent_state()
            initial_objective = initial_state.current_objective
            initial_metrics = agent_manager.performance_metrics.copy()
            initial_config = {
                'loop_interval': agent_manager.loop_interval,
                'cooldown_period': agent_manager.cooldown_period
            }
            
            # Perform multiple mode transitions
            for i in range(mode_transitions):
                # Transition to Chat Mode (pause agent)
                pre_pause_state = agent_manager.get_agent_state()
                pre_pause_metrics = agent_manager.performance_metrics.copy()
                
                agent_manager.pause_for_chat()
                
                # Verify state during pause
                paused_state = agent_manager.get_agent_state()
                assert paused_state.mode == "paused"
                assert paused_state.chat_mode_active == True
                assert paused_state.previous_mode is not None
                
                # Verify state is preserved in saved_context
                assert len(agent_manager.agent_state.saved_context) > 0
                saved_context = agent_manager.agent_state.saved_context
                assert 'current_objective' in saved_context
                assert 'loop_count' in saved_context
                assert 'performance_metrics' in saved_context
                
                # Simulate chat processing
                time.sleep(pause_duration)
                
                # Transition back to Agent Mode (resume agent)
                agent_manager.resume_agent_loop()
                
                # Verify state after resume
                resumed_state = agent_manager.get_agent_state()
                assert resumed_state.chat_mode_active == False
                assert resumed_state.previous_mode is None
                
                # Verify state preservation
                # Core state should be preserved
                assert resumed_state.current_objective == pre_pause_state.current_objective
                assert resumed_state.loop_count == pre_pause_state.loop_count
                
                # Configuration should be preserved
                assert agent_manager.loop_interval == initial_config['loop_interval']
                assert agent_manager.cooldown_period == initial_config['cooldown_period']
                
                # Performance metrics should be preserved (non-time-sensitive ones)
                for key in ['successful_actions', 'failed_actions', 'total_cycles']:
                    if key in pre_pause_metrics:
                        current_value = agent_manager.performance_metrics.get(key, 0)
                        expected_value = pre_pause_metrics.get(key, 0)
                        # Allow for small increases due to continued operation
                        assert current_value >= expected_value, \
                            f"Metric {key} decreased: {current_value} < {expected_value}"
                
                # Saved context should be cleared after restore
                assert len(agent_manager.agent_state.saved_context) == 0
                assert len(agent_manager.agent_state.pending_actions) == 0
                
                # Brief pause between transitions
                time.sleep(0.1)
            
            # Final verification - overall state should be consistent
            final_state = agent_manager.get_agent_state()
            
            # Mode should be active (not paused)
            assert final_state.mode in ["active", "idle"]
            assert final_state.chat_mode_active == False
            
            # Core state elements should be preserved from initial state
            # (allowing for natural progression during operation)
            assert final_state.loop_count >= initial_state.loop_count
            
            # Configuration should remain unchanged
            assert agent_manager.loop_interval == initial_config['loop_interval']
            assert agent_manager.cooldown_period == initial_config['cooldown_period']
            
        finally:
            agent_manager.cleanup()


# Feature: vision-action-agent, Property 1: Dual-mode concurrency
@given(
    chat_count=st.integers(min_value=1, max_value=3),
    chat_duration=st.floats(min_value=0.1, max_value=0.3)
)
@settings(max_examples=10, deadline=None)  # Disable deadline for async tests
def test_dual_mode_concurrency_property(chat_count, chat_duration):
    """
    Property 1: Dual-mode concurrency
    For any system state, when Agent Mode is activated, chat inputs should 
    continue to be processed without interruption or delay
    
    Validates: Requirements 1.1, 1.4
    """
    # Setup
    mock_tts = AsyncMock()
    mock_tts.put_text = AsyncMock()
    mock_gui = Mock()
    
    config = {
        'vision': {'model_name': 'llava'},
        'actions': {'use_directinput': True},
        'loop_interval': 0.2,  # Slower for more predictable timing
        'cooldown_period': 0.1
    }
    
    with patch('src.agent_manager.VisionClient') as mock_vision, \
         patch('src.agent_manager.ActionEngine') as mock_action:
        
        # Configure mocks for successful operation
        mock_vision.return_value.capture_screen = AsyncMock(return_value="fake_image")
        mock_vision.return_value.analyze_scene = AsyncMock(
            return_value=AgentCommand(
                thought="Test thought",
                commentary="Test commentary", 
                action_type="wait",
                target=None,
                key=None,
                confidence=0.8,
                timestamp=None
            )
        )
        mock_action.return_value.execute_command = Mock(
            return_value=ActionResult(
                success=True,
                action_type="wait",
                target=None,
                error_message=None,
                execution_time=0.1,
                timestamp=datetime.now()
            )
        )
        mock_action.return_value.is_safety_active = Mock(return_value=False)
        mock_action.return_value.get_action_history = Mock(return_value=[])
        
        agent_manager = AgentManager(config, mock_tts, mock_gui)
        
        try:
            # Start agent mode
            asyncio.run(agent_manager.start_agent_loop())
            time.sleep(0.2)  # Allow agent to start
            
            # Test chat interactions
            for i in range(chat_count):
                # Record initial state
                initial_state = agent_manager.get_agent_state()
                
                # Simulate chat input (pause agent)
                start_time = time.time()
                agent_manager.pause_for_chat()
                
                # Verify agent is paused
                assert not agent_manager.chat_priority_event.is_set()
                
                # Simulate chat processing time
                time.sleep(chat_duration)
                
                # Resume agent
                agent_manager.resume_agent_loop()
                end_time = time.time()
                
                # Verify agent is resumed
                assert agent_manager.chat_priority_event.is_set()
                
                # Response time should be reasonable (chat_duration + small overhead)
                response_time = end_time - start_time
                assert response_time <= chat_duration + 0.1, \
                    f"Chat response delayed: {response_time:.3f}s vs expected {chat_duration:.3f}s"
                
                # Brief pause between interactions
                time.sleep(0.1)
            
            # Verify agent is still operational after chat interactions
            final_state = agent_manager.get_agent_state()
            assert final_state.mode in ["active", "paused"]
            
        finally:
            agent_manager.cleanup()


# Feature: vision-action-agent, Property 17: Error resilience and logging
@given(
    error_count=st.integers(min_value=1, max_value=3),
    error_type=st.sampled_from(['vision_error', 'action_error', 'tts_error'])
)
@settings(max_examples=5, deadline=None)  # Disable deadline for async tests
def test_error_resilience_and_logging_property(error_count, error_type):
    """
    Property 17: Error resilience and logging
    For any error condition in the agent loop, the system should log the error 
    and continue operation without crashing
    
    Validates: Requirements 6.3, 6.4
    """
    # Setup
    mock_tts = AsyncMock()
    mock_tts.put_text = AsyncMock()
    mock_gui = Mock()
    
    config = {
        'vision': {'model_name': 'llava'},
        'actions': {'use_directinput': True},
        'loop_interval': 0.2,
        'cooldown_period': 0.1
    }
    
    with patch('src.agent_manager.VisionClient') as mock_vision, \
         patch('src.agent_manager.ActionEngine') as mock_action:
        
        # Configure mocks to simulate specific error types
        error_counter = {'count': 0}
        
        def maybe_raise_vision_error(*args, **kwargs):
            if error_type == 'vision_error' and error_counter['count'] < error_count:
                error_counter['count'] += 1
                raise Exception(f"Simulated vision error #{error_counter['count']}")
            return "fake_image"
        
        def maybe_raise_action_error(command):
            if error_type == 'action_error' and error_counter['count'] < error_count:
                error_counter['count'] += 1
                return ActionResult(
                    success=False,
                    action_type=command.action_type,
                    target=command.target,
                    error_message=f"Simulated action error #{error_counter['count']}",
                    execution_time=0.1,
                    timestamp=datetime.now()
                )
            return ActionResult(
                success=True,
                action_type=command.action_type,
                target=command.target,
                error_message=None,
                execution_time=0.1,
                timestamp=datetime.now()
            )
        
        async def maybe_raise_tts_error(text):
            if error_type == 'tts_error' and error_counter['count'] < error_count:
                error_counter['count'] += 1
                raise Exception(f"Simulated TTS error #{error_counter['count']}")
        
        # Configure mocks
        mock_vision.return_value.capture_screen = AsyncMock(side_effect=maybe_raise_vision_error)
        mock_vision.return_value.analyze_scene = AsyncMock(
            return_value=AgentCommand(
                thought="Test thought",
                commentary="Test commentary",
                action_type="wait",
                target=None,
                key=None,
                confidence=0.8,
                timestamp=None
            )
        )
        mock_action.return_value.execute_command = Mock(side_effect=maybe_raise_action_error)
        mock_action.return_value.is_safety_active = Mock(return_value=False)
        mock_action.return_value.get_action_history = Mock(return_value=[])
        
        # Configure TTS to sometimes fail
        mock_tts.put_text.side_effect = maybe_raise_tts_error
        
        agent_manager = AgentManager(config, mock_tts, mock_gui)
        
        # Capture log messages
        import logging
        log_messages = []
        
        class TestLogHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record.getMessage())
        
        test_handler = TestLogHandler()
        test_handler.setLevel(logging.WARNING)  # Capture both WARNING and ERROR
        agent_manager.logger.addHandler(test_handler)
        
        try:
            # Start agent mode
            asyncio.run(agent_manager.start_agent_loop())
            
            # Let it run briefly to encounter errors
            time.sleep(0.5)
            
            # Stop agent
            agent_manager.stop_agent_loop()
            
            # Verify system resilience
            state = agent_manager.get_agent_state()
            health = agent_manager.get_system_health()
            
            # System should still be operational (not crashed)
            assert state.mode in ["idle", "active", "paused", "emergency"]
            
            # Error tracking should work
            assert health['error_count'] >= 0
            
            # If we injected errors, they should be tracked
            if error_counter['count'] > 0:
                # Check that errors were logged (this is the main requirement)
                error_logs = [msg for msg in log_messages if 'error' in msg.lower() or 'failed' in msg.lower()]
                assert len(error_logs) > 0, f"Errors should be logged. Got {len(log_messages)} total messages"
                
                # System should continue operating despite errors (resilience)
                assert state.mode in ["idle", "active", "paused"], f"System should remain operational, got mode: {state.mode}"
                
                # At least one cycle should have completed (showing the system didn't crash)
                assert health['total_cycles'] > 0, "System should complete at least one cycle"
            
            # Performance metrics should be valid
            assert health['success_rate'] >= 0.0 and health['success_rate'] <= 1.0
            
        finally:
            agent_manager.logger.removeHandler(test_handler)
            agent_manager.cleanup()


# Run the stateful test
TestAgentManagerStatefulTest = TestAgentManagerStateful.TestCase


if __name__ == "__main__":
    pytest.main([__file__])