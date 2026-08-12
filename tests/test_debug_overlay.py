"""
Unit tests for the Debug Overlay module

Tests overlay creation, coordinate display, and cleanup functionality.
"""

import unittest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.debug_overlay import DebugOverlay, OverlayTarget, create_debug_overlay


class TestDebugOverlay(unittest.TestCase):
    """Test cases for DebugOverlay functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'enabled': True,
            'circle_radius': 15,
            'circle_color': 'red',
            'circle_width': 3,
            'display_duration': 0.5,
            'fade_effect': True
        }
        
    def tearDown(self):
        """Clean up after tests"""
        # Ensure any overlay instances are cleaned up
        pass
    
    def test_overlay_initialization(self):
        """Test overlay initialization with configuration"""
        overlay = DebugOverlay(self.config)
        
        self.assertEqual(overlay.enabled, True)
        self.assertEqual(overlay.circle_radius, 15)
        self.assertEqual(overlay.circle_color, 'red')
        self.assertEqual(overlay.circle_width, 3)
        self.assertEqual(overlay.display_duration, 0.5)
        self.assertEqual(overlay.fade_effect, True)
        self.assertFalse(overlay.running)
        self.assertEqual(len(overlay.active_targets), 0)
    
    def test_overlay_initialization_with_defaults(self):
        """Test overlay initialization with default configuration"""
        overlay = DebugOverlay()
        
        self.assertTrue(overlay.enabled)
        self.assertEqual(overlay.circle_radius, 15)
        self.assertEqual(overlay.circle_color, 'red')
        self.assertEqual(overlay.display_duration, 0.5)
        self.assertFalse(overlay.running)
    
    def test_overlay_disabled_initialization(self):
        """Test overlay initialization when disabled"""
        config = {'enabled': False}
        overlay = DebugOverlay(config)
        
        self.assertFalse(overlay.enabled)
        self.assertFalse(overlay.running)
    
    @patch('src.debug_overlay.tk.Tk')
    def test_start_overlay_disabled(self, mock_tk):
        """Test starting overlay when disabled does nothing"""
        config = {'enabled': False}
        overlay = DebugOverlay(config)
        
        overlay.start_overlay()
        
        self.assertFalse(overlay.running)
        mock_tk.assert_not_called()
    
    @patch('src.debug_overlay.tk.Tk')
    def test_start_overlay_already_running(self, mock_tk):
        """Test starting overlay when already running"""
        overlay = DebugOverlay(self.config)
        overlay.running = True  # Simulate already running
        
        overlay.start_overlay()
        
        # Should not create new thread or window
        mock_tk.assert_not_called()
    
    def test_show_target_when_disabled(self):
        """Test showing target when overlay is disabled"""
        config = {'enabled': False}
        overlay = DebugOverlay(config)
        
        overlay.show_target(100, 200, "click")
        
        # Should not add any targets
        self.assertEqual(len(overlay.active_targets), 0)
    
    def test_show_target_when_not_running(self):
        """Test showing target when overlay is not running"""
        overlay = DebugOverlay(self.config)
        
        overlay.show_target(100, 200, "click")
        
        # Should not add any targets when not running
        self.assertEqual(len(overlay.active_targets), 0)
    
    def test_show_target_functionality(self):
        """Test showing target adds to active targets"""
        overlay = DebugOverlay(self.config)
        overlay.running = True  # Simulate running state
        
        overlay.show_target(100, 200, "click", 1.0)
        
        self.assertEqual(len(overlay.active_targets), 1)
        target = overlay.active_targets[0]
        self.assertEqual(target.x, 100)
        self.assertEqual(target.y, 200)
        self.assertEqual(target.action_type, "click")
        self.assertEqual(target.duration, 1.0)
        self.assertIsInstance(target.timestamp, datetime)
    
    def test_show_target_with_default_duration(self):
        """Test showing target with default duration"""
        overlay = DebugOverlay(self.config)
        overlay.running = True
        
        overlay.show_target(150, 250, "keypress")
        
        self.assertEqual(len(overlay.active_targets), 1)
        target = overlay.active_targets[0]
        self.assertEqual(target.duration, 0.5)  # Default from config
    
    def test_show_drag_path(self):
        """Test showing drag path creates multiple targets"""
        overlay = DebugOverlay(self.config)
        overlay.running = True
        
        overlay.show_drag_path(100, 200, 300, 400, 1.0)
        
        # Should create 3 targets: start, end, and line
        self.assertEqual(len(overlay.active_targets), 3)
        
        # Check target types
        action_types = [target.action_type for target in overlay.active_targets]
        self.assertIn("drag_start", action_types)
        self.assertIn("drag_end", action_types)
        self.assertIn("drag_line", action_types)
    
    def test_clear_targets(self):
        """Test clearing all active targets"""
        overlay = DebugOverlay(self.config)
        overlay.running = True
        
        # Add some targets
        overlay.show_target(100, 200, "click")
        overlay.show_target(300, 400, "scroll")
        
        self.assertEqual(len(overlay.active_targets), 2)
        
        overlay.clear_targets()
        
        self.assertEqual(len(overlay.active_targets), 0)
    
    def test_is_running_status(self):
        """Test is_running method returns correct status"""
        overlay = DebugOverlay(self.config)
        
        self.assertFalse(overlay.is_running())
        
        overlay.running = True
        self.assertTrue(overlay.is_running())
        
        overlay.running = False
        self.assertFalse(overlay.is_running())
    
    def test_update_config(self):
        """Test updating overlay configuration"""
        overlay = DebugOverlay(self.config)
        
        new_config = {
            'circle_radius': 20,
            'circle_color': 'blue',
            'display_duration': 1.0
        }
        
        overlay.update_config(new_config)
        
        self.assertEqual(overlay.circle_radius, 20)
        self.assertEqual(overlay.circle_color, 'blue')
        self.assertEqual(overlay.display_duration, 1.0)
        # Original values should be preserved if not updated
        self.assertEqual(overlay.circle_width, 3)
    
    def test_get_action_color(self):
        """Test action color mapping"""
        overlay = DebugOverlay(self.config)
        
        self.assertEqual(overlay._get_action_color('click'), 'red')
        self.assertEqual(overlay._get_action_color('drag'), 'blue')
        self.assertEqual(overlay._get_action_color('scroll'), 'green')
        self.assertEqual(overlay._get_action_color('keypress'), 'yellow')
        self.assertEqual(overlay._get_action_color('wait'), 'gray')
        self.assertEqual(overlay._get_action_color('unknown'), 'red')  # Default
    
    def test_overlay_target_dataclass(self):
        """Test OverlayTarget dataclass functionality"""
        timestamp = datetime.now()
        target = OverlayTarget(
            x=100,
            y=200,
            action_type="click",
            timestamp=timestamp,
            duration=1.0
        )
        
        self.assertEqual(target.x, 100)
        self.assertEqual(target.y, 200)
        self.assertEqual(target.action_type, "click")
        self.assertEqual(target.timestamp, timestamp)
        self.assertEqual(target.duration, 1.0)
    
    def test_overlay_target_default_duration(self):
        """Test OverlayTarget with default duration"""
        target = OverlayTarget(
            x=100,
            y=200,
            action_type="click",
            timestamp=datetime.now()
        )
        
        self.assertEqual(target.duration, 0.5)  # Default value
    
    def test_create_debug_overlay_function(self):
        """Test convenience function for creating overlay"""
        overlay = create_debug_overlay(self.config)
        
        self.assertIsInstance(overlay, DebugOverlay)
        self.assertEqual(overlay.circle_radius, 15)
        self.assertEqual(overlay.circle_color, 'red')
    
    def test_create_debug_overlay_with_none_config(self):
        """Test convenience function with None config"""
        overlay = create_debug_overlay(None)
        
        self.assertIsInstance(overlay, DebugOverlay)
        self.assertTrue(overlay.enabled)  # Should use defaults
    
    @patch('src.debug_overlay.tk.Tk')
    def test_stop_overlay_when_not_running(self, mock_tk):
        """Test stopping overlay when not running"""
        overlay = DebugOverlay(self.config)
        
        overlay.stop_overlay()
        
        # Should not cause any errors
        self.assertFalse(overlay.running)
        mock_tk.assert_not_called()
    
    def test_cleanup_calls_stop_overlay(self):
        """Test cleanup method calls stop_overlay"""
        overlay = DebugOverlay(self.config)
        
        # Mock the stop_overlay method
        overlay.stop_overlay = Mock()
        
        overlay.cleanup()
        
        overlay.stop_overlay.assert_called_once()
    
    def test_thread_safety_of_target_operations(self):
        """Test thread safety of target operations"""
        overlay = DebugOverlay(self.config)
        overlay.running = True
        
        # Function to add targets from multiple threads
        def add_targets():
            for i in range(10):
                overlay.show_target(i * 10, i * 20, "click")
                time.sleep(0.001)  # Small delay to increase chance of race conditions
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=add_targets)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have 30 targets total (3 threads * 10 targets each)
        self.assertEqual(len(overlay.active_targets), 30)
        
        # Clear targets should also be thread-safe
        overlay.clear_targets()
        self.assertEqual(len(overlay.active_targets), 0)


class TestDebugOverlayIntegration(unittest.TestCase):
    """Integration tests for debug overlay with other components"""
    
    def test_overlay_integration_with_mock_canvas(self):
        """Test overlay drawing functionality with mocked canvas"""
        overlay = DebugOverlay({'enabled': True})
        overlay.running = True
        
        # Mock canvas
        mock_canvas = Mock()
        overlay.canvas = mock_canvas
        overlay.screen_width = 1920
        overlay.screen_height = 1080
        
        # Add a target
        overlay.show_target(100, 200, "click")
        
        # Simulate update call
        current_time = datetime.now()
        overlay._update_overlay()
        
        # Verify canvas operations were called
        mock_canvas.delete.assert_called_with("all")
        # Canvas drawing methods should be called for the target
        self.assertTrue(mock_canvas.create_oval.called or mock_canvas.create_text.called)


if __name__ == '__main__':
    unittest.main()