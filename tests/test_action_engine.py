"""
Property-based tests for ActionEngine

Tests the action execution fidelity and coordinate boundary validation
using Hypothesis for comprehensive input coverage.
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Tuple

from src.action_engine import ActionEngine, ActionResult
from src.vision_client import AgentCommand


class TestActionEngine:
    """Test suite for ActionEngine with property-based testing"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = {
            'use_directinput': False,  # Use pyautogui for testing
            'action_delay': 0.01,  # Faster for testing
            'click_duration': 0.01,
            'clamp_region': None
        }
        
        # Mock screen bounds to avoid system dependencies
        with patch('src.action_engine.pyautogui.size', return_value=(1920, 1080)):
            self.engine = ActionEngine(self.config)
    
    @given(
        x=st.integers(min_value=2, max_value=1919),  # 确保x > 1，避免被误认为百分比
        y=st.integers(min_value=0, max_value=1079),
        confidence=st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=100, deadline=None)
    @patch('src.action_engine.pyautogui.click')
    def test_property_action_execution_fidelity_click(self, mock_click, x, y, confidence):
        """
        Property 8: Action execution fidelity
        For any valid click command, the ActionEngine should execute the corresponding operation
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Feature: vision-action-agent, Property 8: Action execution fidelity
        
        # Clear action history to avoid hallucination guard interference
        self.engine.action_history.clear()
        
        # Create a valid click command
        command = AgentCommand(
            thought="Test click",
            commentary="Testing click action",
            action_type="click",
            target=[x, y],
            key=None,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # Execute the command
        result = self.engine.execute_command(command)
        
        # Verify the action was executed successfully
        assert result.success is True
        assert result.action_type == "click"
        assert result.target == (x, y)
        assert result.error_message is None
        
        # Verify the underlying library was called with correct parameters
        mock_click.assert_called_once_with(x, y, duration=self.engine.click_duration)
    
    @given(
        key=st.sampled_from(['space', 'enter', 'tab', 'escape', 'a', 'w', 's', 'd']),
        confidence=st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=100)
    @patch('src.action_engine.pyautogui.press')
    def test_property_action_execution_fidelity_keypress(self, mock_press, key, confidence):
        """
        Property 8: Action execution fidelity (keypress variant)
        For any valid keypress command, the ActionEngine should execute the corresponding operation
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Feature: vision-action-agent, Property 8: Action execution fidelity
        
        # Create a valid keypress command
        command = AgentCommand(
            thought="Test keypress",
            commentary="Testing keypress action",
            action_type="keypress",
            target=None,
            key=key,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # Execute the command
        result = self.engine.execute_command(command)
        
        # Verify the action was executed successfully
        assert result.success is True
        assert result.action_type == "keypress"
        assert result.error_message is None
        
        # Verify the underlying library was called with correct parameters
        mock_press.assert_called_once_with(key)
    
    @given(
        x1=st.integers(min_value=0, max_value=1919),
        y1=st.integers(min_value=0, max_value=1079),
        x2=st.integers(min_value=0, max_value=1919),
        y2=st.integers(min_value=0, max_value=1079),
        confidence=st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=100)
    @patch('src.action_engine.pyautogui.drag')
    def test_property_action_execution_fidelity_drag(self, mock_drag, x1, y1, x2, y2, confidence):
        """
        Property 8: Action execution fidelity (drag variant)
        For any valid drag command, the ActionEngine should execute the corresponding operation
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Feature: vision-action-agent, Property 8: Action execution fidelity
        
        # Create a valid drag command
        command = AgentCommand(
            thought="Test drag",
            commentary="Testing drag action",
            action_type="drag",
            target=[x1, y1, x2, y2],
            key=None,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # Execute the command
        result = self.engine.execute_command(command)
        
        # Verify the action was executed successfully
        assert result.success is True
        assert result.action_type == "drag"
        assert result.target == (x1, y1, x2, y2)
        assert result.error_message is None
        
        # Verify the underlying library was called with correct parameters
        mock_drag.assert_called_once_with(x1, y1, x2, y2, duration=self.engine.click_duration)
    
    @given(
        x=st.integers(min_value=0, max_value=1919),
        y=st.integers(min_value=0, max_value=1079),
        scroll_amount=st.integers(min_value=-10, max_value=10),
        confidence=st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=100)
    @patch('src.action_engine.pyautogui.scroll')
    def test_property_action_execution_fidelity_scroll(self, mock_scroll, x, y, scroll_amount, confidence):
        """
        Property 8: Action execution fidelity (scroll variant)
        For any valid scroll command, the ActionEngine should execute the corresponding operation
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Feature: vision-action-agent, Property 8: Action execution fidelity
        
        # Create a valid scroll command
        command = AgentCommand(
            thought="Test scroll",
            commentary="Testing scroll action",
            action_type="scroll",
            target=[x, y, scroll_amount],
            key=None,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # Execute the command
        result = self.engine.execute_command(command)
        
        # Verify the action was executed successfully
        assert result.success is True
        assert result.action_type == "scroll"
        assert result.target == (x, y, scroll_amount)
        assert result.error_message is None
        
        # Verify the underlying library was called with correct parameters
        mock_scroll.assert_called_once_with(scroll_amount, x=x, y=y)
    
    def test_wait_action_execution(self):
        """Test wait action execution"""
        command = AgentCommand(
            thought="Test wait",
            commentary="Testing wait action",
            action_type="wait",
            target=None,
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        result = self.engine.execute_command(command)
        
        assert result.success is True
        assert result.action_type == "wait"
        assert result.execution_time > 0  # Should have taken some time
    
    def test_none_action_execution(self):
        """Test none action execution"""
        command = AgentCommand(
            thought="Test none",
            commentary="Testing none action",
            action_type="none",
            target=None,
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        result = self.engine.execute_command(command)
        
        assert result.success is True
        assert result.action_type == "none"
        assert result.execution_time >= 0.0  # Should be minimal but not necessarily exactly 0
    
    def test_unknown_action_type(self):
        """Test handling of unknown action types"""
        command = AgentCommand(
            thought="Test unknown",
            commentary="Testing unknown action",
            action_type="unknown_action",
            target=None,
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        result = self.engine.execute_command(command)
        
        assert result.success is False
        assert result.action_type == "unknown_action"
        assert "Unknown action type" in result.error_message
    
    @given(
        x=st.integers(min_value=-1000, max_value=3000),
        y=st.integers(min_value=-1000, max_value=3000)
    )
    @settings(max_examples=100)
    @patch('src.action_engine.pyautogui.click')
    def test_property_coordinate_boundary_validation(self, mock_click, x, y):
        """
        Property 9: Coordinate boundary validation
        For any coordinate pair, the Action Engine should reject coordinates outside screen boundaries
        and accept valid coordinates within bounds
        **Validates: Requirements 3.5, 9.1, 9.3, 9.5**
        """
        # Feature: vision-action-agent, Property 9: Coordinate boundary validation
        
        # Create a click command with the generated coordinates
        command = AgentCommand(
            thought="Test boundary validation",
            commentary="Testing coordinate boundaries",
            action_type="click",
            target=[x, y],
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        # Execute the command
        result = self.engine.execute_command(command)
        
        # Check if coordinates are within screen bounds (0-1919, 0-1079)
        is_within_bounds = (0 <= x < 1920 and 0 <= y < 1080)
        
        if is_within_bounds:
            # Valid coordinates should succeed
            assert result.success is True
            assert result.error_message is None
            mock_click.assert_called_once_with(x, y, duration=self.engine.click_duration)
        else:
            # Invalid coordinates should be rejected
            assert result.success is False
            assert "outside safe bounds" in result.error_message
            mock_click.assert_not_called()
    
    @given(
        x1=st.integers(min_value=-500, max_value=2500),
        y1=st.integers(min_value=-500, max_value=1500),
        x2=st.integers(min_value=-500, max_value=2500),
        y2=st.integers(min_value=-500, max_value=1500)
    )
    @settings(max_examples=100, deadline=None)
    @patch('src.action_engine.pyautogui.drag')
    def test_property_coordinate_boundary_validation_drag(self, mock_drag, x1, y1, x2, y2):
        """
        Property 9: Coordinate boundary validation (drag variant)
        For any drag coordinates, both start and end points should be validated
        **Validates: Requirements 3.5, 9.1, 9.3, 9.5**
        """
        # Feature: vision-action-agent, Property 9: Coordinate boundary validation
        
        # Create a drag command with the generated coordinates
        command = AgentCommand(
            thought="Test drag boundary validation",
            commentary="Testing drag coordinate boundaries",
            action_type="drag",
            target=[x1, y1, x2, y2],
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        # Execute the command
        result = self.engine.execute_command(command)
        
        # Check if both start and end coordinates are within screen bounds
        start_valid = (0 <= x1 < 1920 and 0 <= y1 < 1080)
        end_valid = (0 <= x2 < 1920 and 0 <= y2 < 1080)
        both_valid = start_valid and end_valid
        
        if both_valid:
            # Valid coordinates should succeed
            assert result.success is True
            assert result.error_message is None
            mock_drag.assert_called_once_with(x1, y1, x2, y2, duration=self.engine.click_duration)
        else:
            # Invalid coordinates should be rejected
            assert result.success is False
            assert "outside safe bounds" in result.error_message
            mock_drag.assert_not_called()
    
    def test_coordinate_clamping_configuration(self):
        """Test coordinate clamping when clamp_region is configured"""
        # Configure engine with clamp region
        config_with_clamp = self.config.copy()
        config_with_clamp['clamp_region'] = (100, 100, 800, 600)  # x, y, width, height
        
        with patch('src.action_engine.pyautogui.size', return_value=(1920, 1080)):
            clamped_engine = ActionEngine(config_with_clamp)
        
        # Test coordinate within clamp region (should succeed)
        command_valid = AgentCommand(
            thought="Test clamped valid",
            commentary="Testing valid clamped coordinate",
            action_type="click",
            target=[500, 400],  # Within clamp region
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        with patch('src.action_engine.pyautogui.click') as mock_click:
            result = clamped_engine.execute_command(command_valid)
            assert result.success is True
            mock_click.assert_called_once()
        
        # Test coordinate outside clamp region (should fail)
        command_invalid = AgentCommand(
            thought="Test clamped invalid",
            commentary="Testing invalid clamped coordinate",
            action_type="click",
            target=[50, 50],  # Outside clamp region
            key=None,
            confidence=1.0,
            timestamp=datetime.now()
        )
        
        with patch('src.action_engine.pyautogui.click') as mock_click:
            result = clamped_engine.execute_command(command_invalid)
            assert result.success is False
            assert "outside safe bounds" in result.error_message
            mock_click.assert_not_called()