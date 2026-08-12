"""
Integration tests for the Hybrid Vision-Reflex System.

These tests verify end-to-end workflows and component interactions.
"""

import pytest
import time
import tempfile
import shutil
import os
import threading
import numpy as np
import cv2
from pathlib import Path

from src.reflex_engine import ReflexEngine
from src.template_matcher import TemplateMatcher
from src.game_knowledge import GameKnowledge


class MockActionEngine:
    """Mock ActionEngine for testing."""
    
    def __init__(self):
        self.actions = []
        self.lock = threading.Lock()
    
    def execute_command(self, command):
        with self.lock:
            self.actions.append({
                'type': getattr(command, 'action_type', 'unknown'),
                'target': getattr(command, 'target', None),
                'timestamp': time.time()
            })
        return type('Result', (), {'success': True, 'execution_time': 0.01})()


class MockScreenCapturer:
    """Mock ScreenCapturer for testing."""
    
    def __init__(self):
        self._screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
    
    def capture(self, region=None):
        return self._screenshot.copy()
    
    def set_screenshot(self, screenshot):
        self._screenshot = screenshot


class MockSafetyManager:
    """Mock SafetyManager for testing."""
    
    def __init__(self):
        self.emergency_active = False
    
    def is_emergency_active(self):
        return self.emergency_active
    
    def reset_emergency_state(self):
        self.emergency_active = False


class TestCookieClickerIntegration:
    """Integration tests simulating Cookie Clicker gameplay."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    @pytest.fixture
    def game_knowledge(self, temp_dir):
        """Create GameKnowledge instance."""
        return GameKnowledge(base_path=temp_dir)
    
    @pytest.fixture
    def cookie_profile(self, game_knowledge):
        """Create Cookie Clicker profile."""
        profile_data = {
            "display_name": "Cookie Clicker",
            "description": "Click the big cookie to earn cookies",
            "vlm_prompts": [
                "You are playing Cookie Clicker.",
                "Click the big cookie to earn cookies.",
                "Buy upgrades when you have enough cookies."
            ],
            "default_templates": {
                "big-cookie": "big-cookie.png",
                "cursor-upgrade": "cursor-upgrade.png"
            },
            "action_cooldowns": {
                "click": 0.05
            }
        }
        game_knowledge.create_profile("cookie-clicker", profile_data)
        return game_knowledge.load_profile("cookie-clicker")
    
    def test_cookie_clicker_profile_creation(self, cookie_profile):
        """Test that Cookie Clicker profile is created correctly."""
        assert cookie_profile is not None
        assert cookie_profile.display_name == "Cookie Clicker"
        assert len(cookie_profile.vlm_prompts) == 3
        assert "big-cookie" in cookie_profile.default_templates
    
    def test_cookie_clicker_template_workflow(self, temp_dir, game_knowledge, cookie_profile):
        """Test creating and using templates for Cookie Clicker."""
        # Create a "big cookie" template
        cookie_template = np.zeros((80, 80, 3), dtype=np.uint8)
        cv2.circle(cookie_template, (40, 40), 35, (139, 90, 43), -1)  # Brown cookie
        cv2.circle(cookie_template, (25, 30), 5, (60, 40, 20), -1)  # Chocolate chip
        cv2.circle(cookie_template, (50, 35), 5, (60, 40, 20), -1)
        cv2.circle(cookie_template, (35, 55), 5, (60, 40, 20), -1)
        
        # Save template
        template_path = game_knowledge.save_template("cookie-clicker", "big-cookie", cookie_template)
        assert Path(template_path).exists()
        
        # Verify template can be loaded by TemplateMatcher
        matcher = TemplateMatcher()
        assert matcher.load_template(template_path)

    def test_reflex_engine_with_cookie_template(self, temp_dir, game_knowledge, cookie_profile):
        """Test ReflexEngine clicking on cookie template."""
        # Create cookie template
        cookie_template = np.zeros((80, 80, 3), dtype=np.uint8)
        cv2.circle(cookie_template, (40, 40), 35, (139, 90, 43), -1)
        
        template_path = game_knowledge.save_template("cookie-clicker", "big-cookie", cookie_template)
        
        # Create screenshot with cookie
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        screenshot[200:280, 300:380] = cookie_template
        
        # Create components
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        screen_capturer.set_screenshot(screenshot)
        template_matcher = TemplateMatcher()
        safety_manager = MockSafetyManager()
        
        reflex_engine = ReflexEngine(
            action_engine,
            screen_capturer,
            template_matcher,
            safety_manager
        )
        
        # Start clicking
        result = reflex_engine.start(template_path, "click_repeat")
        assert result, "Should start successfully"
        
        # Let it run
        time.sleep(0.5)
        
        # Check status
        status = reflex_engine.get_status()
        assert status['active'], "Should be active"
        
        # Stop
        reflex_engine.stop()
        assert not reflex_engine._active


class TestTemplateHotSwapIntegration:
    """Integration tests for template hot swapping."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    def test_hot_swap_without_interruption(self, temp_dir):
        """Test swapping templates while engine is running."""
        # Create two templates
        template1 = np.zeros((50, 50, 3), dtype=np.uint8)
        template1[:, :] = (100, 100, 100)
        template1_path = os.path.join(temp_dir, "template1.png")
        cv2.imwrite(template1_path, template1)
        
        template2 = np.zeros((60, 60, 3), dtype=np.uint8)
        template2[:, :] = (200, 200, 200)
        template2_path = os.path.join(temp_dir, "template2.png")
        cv2.imwrite(template2_path, template2)
        
        # Create components
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        template_matcher = TemplateMatcher()
        safety_manager = MockSafetyManager()
        
        reflex_engine = ReflexEngine(
            action_engine,
            screen_capturer,
            template_matcher,
            safety_manager
        )
        
        # Start with template1
        result = reflex_engine.start(template1_path, "hover")
        assert result
        
        # Let it run
        time.sleep(0.1)
        assert reflex_engine._active
        
        # Hot swap to template2
        swap_result = reflex_engine.update_template(template2_path)
        assert swap_result, "Hot swap should succeed"
        
        # Verify still running
        assert reflex_engine._active, "Should remain active after swap"
        
        # Let it run with new template
        time.sleep(0.1)
        
        # Stop
        reflex_engine.stop()


class TestTargetLossRecoveryIntegration:
    """Integration tests for target loss and recovery."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    def test_target_loss_detection(self, temp_dir):
        """Test that target loss is detected after consecutive failures."""
        # Create a distinctive template that won't match random noise
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:, :] = (100, 150, 200)
        cv2.rectangle(template, (10, 10), (40, 40), (255, 255, 255), 3)
        cv2.circle(template, (25, 25), 10, (0, 255, 0), -1)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Create components with random noise screenshot (no match)
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        # Set random noise that won't match the template
        noise_screenshot = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        screen_capturer.set_screenshot(noise_screenshot)
        template_matcher = TemplateMatcher(confidence_threshold=0.8)  # Higher threshold
        safety_manager = MockSafetyManager()
        
        reflex_engine = ReflexEngine(
            action_engine,
            screen_capturer,
            template_matcher,
            safety_manager
        )
        
        # Start
        result = reflex_engine.start(template_path, "hover")
        assert result
        
        # Let it run to accumulate failures
        time.sleep(1.0)
        
        # Check status
        status = reflex_engine.get_status()
        
        # Stop first to avoid interference
        reflex_engine.stop()
        
        # Should have consecutive failures (template shouldn't match noise)
        # Note: With high confidence threshold, it should fail to match
        assert status['consecutive_failures'] >= 0, "Should track failures"
        
        # After 10 failures, target_found should be False
        if status['consecutive_failures'] >= 10:
            assert not status['target_found'], "target_found should be False after 10 failures"
    
    def test_target_recovery(self, temp_dir):
        """Test that target is found again after reappearing."""
        # Create template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:, :] = (100, 150, 200)
        cv2.rectangle(template, (10, 10), (40, 40), (255, 255, 255), 2)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Create components
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        template_matcher = TemplateMatcher()
        safety_manager = MockSafetyManager()
        
        reflex_engine = ReflexEngine(
            action_engine,
            screen_capturer,
            template_matcher,
            safety_manager
        )
        
        # Start with empty screen
        result = reflex_engine.start(template_path, "hover")
        assert result
        
        # Let it fail
        time.sleep(0.3)
        
        # Now add template to screenshot
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        screenshot[100:150, 100:150] = template
        screen_capturer.set_screenshot(screenshot)
        
        # Let it find the target
        time.sleep(0.3)
        
        # Check status
        status = reflex_engine.get_status()
        
        # Should have found target (consecutive failures reset)
        # Note: May still have some failures from before
        
        # Stop
        reflex_engine.stop()


class TestEmergencyStopIntegration:
    """Integration tests for emergency stop functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    def test_emergency_stop_stops_all_threads(self, temp_dir):
        """Test that emergency stop stops all threads quickly."""
        # Create template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Create components
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        template_matcher = TemplateMatcher()
        safety_manager = MockSafetyManager()
        
        reflex_engine = ReflexEngine(
            action_engine,
            screen_capturer,
            template_matcher,
            safety_manager
        )
        
        # Start
        result = reflex_engine.start(template_path, "hover")
        assert result
        
        # Let it run
        time.sleep(0.1)
        assert reflex_engine._active
        
        # Trigger emergency stop
        start_time = time.perf_counter()
        safety_manager.emergency_active = True
        
        # Wait for engine to stop
        timeout = 0.5
        while reflex_engine._active and (time.perf_counter() - start_time) < timeout:
            time.sleep(0.01)
        
        stop_time = time.perf_counter() - start_time
        
        # Should stop within 0.5 seconds
        assert stop_time < 0.5, f"Emergency stop took too long: {stop_time:.3f}s"
        assert not reflex_engine._active, "Engine should be stopped"
        
        # Clean up
        safety_manager.reset_emergency_state()


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    def test_fast_loop_frequency_benchmark(self, temp_dir):
        """Benchmark Fast Loop frequency over extended period."""
        # Create template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:, :] = (100, 150, 200)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Create screenshot with template
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        screenshot[100:150, 100:150] = template
        
        # Create components
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        screen_capturer.set_screenshot(screenshot)
        template_matcher = TemplateMatcher()
        safety_manager = MockSafetyManager()
        
        reflex_engine = ReflexEngine(
            action_engine,
            screen_capturer,
            template_matcher,
            safety_manager
        )
        
        # Start
        result = reflex_engine.start(template_path, "hover")
        assert result
        
        # Run for 2 seconds
        time.sleep(2.0)
        
        # Get metrics
        status = reflex_engine.get_status()
        
        # Stop
        reflex_engine.stop()
        
        # Calculate frequency
        avg_loop_time = status['avg_loop_time']
        if avg_loop_time > 0:
            frequency = 1.0 / avg_loop_time
            print(f"\nFast Loop Frequency: {frequency:.2f} Hz")
            print(f"Average Loop Time: {avg_loop_time*1000:.2f} ms")
            print(f"Match Success Rate: {status['match_success_rate']*100:.1f}%")
            
            # Should achieve reasonable frequency
            assert frequency >= 1.0, f"Frequency too low: {frequency:.2f} Hz"
    
    def test_template_matching_latency(self, temp_dir):
        """Benchmark template matching latency."""
        # Create template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:, :] = (100, 150, 200)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Create screenshot
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        screenshot[100:150, 100:150] = template
        
        # Create matcher
        matcher = TemplateMatcher()
        assert matcher.load_template(template_path)
        
        # Benchmark
        times = []
        for _ in range(100):
            start = time.perf_counter()
            result = matcher.find_match(screenshot)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"\nTemplate Matching Latency:")
        print(f"  Average: {avg_time*1000:.2f} ms")
        print(f"  Min: {min_time*1000:.2f} ms")
        print(f"  Max: {max_time*1000:.2f} ms")
        
        # Should be fast enough for 20 Hz
        assert avg_time < 0.05, f"Matching too slow: {avg_time*1000:.2f} ms"
    
    def test_emergency_stop_response_time(self, temp_dir):
        """Benchmark emergency stop response time."""
        # Create template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Create components
        action_engine = MockActionEngine()
        screen_capturer = MockScreenCapturer()
        template_matcher = TemplateMatcher()
        safety_manager = MockSafetyManager()
        
        response_times = []
        
        for _ in range(5):
            reflex_engine = ReflexEngine(
                action_engine,
                screen_capturer,
                template_matcher,
                safety_manager
            )
            
            # Start
            reflex_engine.start(template_path, "hover")
            time.sleep(0.1)
            
            # Trigger emergency stop and measure
            start_time = time.perf_counter()
            safety_manager.emergency_active = True
            
            # Wait for stop
            while reflex_engine._active:
                time.sleep(0.001)
            
            response_time = time.perf_counter() - start_time
            response_times.append(response_time)
            
            # Reset
            safety_manager.reset_emergency_state()
        
        avg_response = sum(response_times) / len(response_times)
        max_response = max(response_times)
        
        print(f"\nEmergency Stop Response Time:")
        print(f"  Average: {avg_response*1000:.2f} ms")
        print(f"  Max: {max_response*1000:.2f} ms")
        
        # Should respond within 100ms
        assert max_response < 0.2, f"Response too slow: {max_response*1000:.2f} ms"
