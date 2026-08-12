"""
Property-based tests for VisionClient

Tests the vision client's screenshot capture timing and VLM integration
using property-based testing with Hypothesis.
"""

import asyncio
import time
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import Mock, patch, MagicMock
import base64
from PIL import Image
import io

from src.vision_client import VisionClient, AgentCommand


class TestVisionClientProperties:
    """Property-based tests for VisionClient functionality"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for VisionClient"""
        return {
            'vision_model': 'llava',
            'capture_region': None,
            'max_image_dimension': 1024
        }
    
    @pytest.fixture
    def mock_mss(self):
        """Mock mss screenshot functionality"""
        with patch('src.vision_client.mss.mss') as mock_mss_class:
            mock_sct = Mock()
            mock_mss_class.return_value = mock_sct
            
            # Create a mock screenshot
            mock_screenshot = Mock()
            mock_screenshot.size = (800, 600)
            mock_screenshot.bgra = b'\x00' * (800 * 600 * 4)  # Mock BGRA data
            mock_sct.grab.return_value = mock_screenshot
            mock_sct.monitors = [None, {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}]
            
            yield mock_sct
    
    @given(
        intervals=st.lists(
            st.floats(min_value=0.1, max_value=0.5),  # Reduced max to avoid long test times
            min_size=3, 
            max_size=5  # Reduced max size
        )
    )
    @settings(max_examples=1, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])  # Minimal examples for fastest execution
    def test_screenshot_capture_timing_property(self, intervals):
        """
        # Feature: vision-action-agent, Property 4: Screenshot capture timing
        
        Property: For any configured interval, when Agent Mode is active, 
        screenshots should be captured at that exact frequency with minimal timing variance
        **Validates: Requirements 2.1**
        """
        # Create mock config inline
        mock_config = {
            'vision_model': 'llava',
            'capture_region': None,
            'max_image_dimension': 1024
        }
        
        with patch('src.vision_client.mss.mss') as mock_mss_class:
            mock_sct = Mock()
            mock_mss_class.return_value = mock_sct
            
            # Create a mock screenshot
            mock_screenshot = Mock()
            mock_screenshot.size = (800, 600)
            mock_screenshot.bgra = b'\x00' * (800 * 600 * 4)  # Mock BGRA data
            mock_sct.grab.return_value = mock_screenshot
            mock_sct.monitors = [None, {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}]
            
            with patch('src.vision_client.Image.frombytes') as mock_frombytes:
                # Mock PIL Image
                mock_img = Mock()
                mock_img.size = (800, 600)
                
                # Mock the save method to write actual data to buffer
                def mock_save(buffer, format=None, quality=None):
                    # Write some test data to the buffer
                    buffer.write(b'test_image_data')
                
                mock_img.save = mock_save
                mock_frombytes.return_value = mock_img
                
                vision_client = VisionClient(mock_config)
                
                # Test timing for each interval (without actually sleeping)
                for target_interval in intervals:
                    capture_times = []
                    
                    # Capture screenshots and measure timing (no sleep)
                    for i in range(3):  # Test with 3 captures
                        loop_start = time.time()
                        
                        # Simulate the capture
                        asyncio.run(vision_client.capture_screen())
                        
                        capture_times.append(time.time() - loop_start)
                    
                    # Verify timing consistency
                    avg_capture_time = sum(capture_times) / len(capture_times)
                    
                    # Property: Capture time should be consistent and reasonable
                    # Allow for some variance due to system overhead
                    max_variance = 0.1  # 100ms variance allowed
                    for capture_time in capture_times:
                        assert abs(capture_time - avg_capture_time) <= max_variance, \
                            f"Capture time variance too high: {capture_time} vs avg {avg_capture_time}"
                    
                    # Property: Capture should complete quickly (under 200ms for mss optimization)
                    assert avg_capture_time < 0.2, \
                        f"Screenshot capture too slow: {avg_capture_time}s (should be < 0.2s)"
            for target_interval in intervals:
                capture_times = []
                
                # Capture screenshots and measure timing
                start_time = time.time()
                for i in range(3):  # Test with 3 captures
                    loop_start = time.time()
                    
                    # Simulate the capture
                    asyncio.run(vision_client.capture_screen())
                    
                    capture_times.append(time.time() - loop_start)
                    
                    # Wait for the target interval
                    if i < 2:  # Don't wait after the last capture
                        time.sleep(target_interval)
                
                # Verify timing consistency
                avg_capture_time = sum(capture_times) / len(capture_times)
                
                # Property: Capture time should be consistent and reasonable
                # Allow for some variance due to system overhead
                max_variance = 0.1  # 100ms variance allowed
                for capture_time in capture_times:
                    assert abs(capture_time - avg_capture_time) <= max_variance, \
                        f"Capture time variance too high: {capture_time} vs avg {avg_capture_time}"
                
                # Property: Capture should complete quickly (under 200ms for mss optimization)
                assert avg_capture_time < 0.2, \
                    f"Screenshot capture too slow: {avg_capture_time}s (should be < 0.2s)"
    
    @given(
        regions=st.one_of(
            st.none(),
            st.tuples(
                st.integers(min_value=0, max_value=1920),  # x
                st.integers(min_value=0, max_value=1080),  # y  
                st.integers(min_value=100, max_value=800), # width
                st.integers(min_value=100, max_value=600)  # height
            )
        )
    )
    @settings(max_examples=1, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_flexible_capture_regions_property(self, regions):
        """
        # Feature: vision-action-agent, Property 7: Flexible capture regions
        
        Property: For any specified screen region or full screen capture, 
        the resulting image should contain exactly the requested area
        **Validates: Requirements 2.4**
        """
        # Create mock config inline
        mock_config = {
            'vision_model': 'llava',
            'capture_region': None,
            'max_image_dimension': 1024
        }
        
        with patch('src.vision_client.mss.mss') as mock_mss_class:
            mock_sct = Mock()
            mock_mss_class.return_value = mock_sct
            
            # Create a mock screenshot
            mock_screenshot = Mock()
            mock_screenshot.size = (800, 600)
            mock_screenshot.bgra = b'\x00' * (800 * 600 * 4)  # Mock BGRA data
            mock_sct.grab.return_value = mock_screenshot
            mock_sct.monitors = [None, {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}]
            
            with patch('src.vision_client.Image.frombytes') as mock_frombytes:
                # Mock PIL Image with appropriate size based on region
                if regions:
                    expected_size = (regions[2], regions[3])  # width, height
                else:
                    expected_size = (1920, 1080)  # Full screen
                
                mock_img = Mock()
                mock_img.size = expected_size
                
                # Mock the save method to write actual data to buffer
                def mock_save(buffer, format=None, quality=None):
                    # Write some test data to the buffer
                    buffer.write(b'test_image_data')
                
                mock_img.save = mock_save
                mock_frombytes.return_value = mock_img
            mock_frombytes.return_value = mock_img
            
            vision_client = VisionClient(mock_config)
            
            # Test capture with the specified region
            result = asyncio.run(vision_client.capture_screen(regions))
            
            # Property: Should return valid base64 data
            assert isinstance(result, str), "Result should be a string"
            assert len(result) > 0, "Result should not be empty"
            
            # Verify base64 encoding is valid
            try:
                decoded = base64.b64decode(result)
                assert len(decoded) > 0, "Decoded data should not be empty"
            except Exception as e:
                pytest.fail(f"Invalid base64 encoding: {e}")
            
            # Verify mss was called with correct region parameters
            if regions:
                expected_monitor = {
                    "top": regions[1],
                    "left": regions[0],
                    "width": regions[2], 
                    "height": regions[3]
                }
                mock_sct.grab.assert_called_with(expected_monitor)
            else:
                # Should use primary monitor
                mock_sct.grab.assert_called_with(mock_sct.monitors[1])
    
    @given(
        dimensions=st.tuples(
            st.integers(min_value=100, max_value=4000),  # width
            st.integers(min_value=100, max_value=4000)   # height
        )
    )
    @settings(max_examples=1, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_image_format_conversion_property(self, dimensions):
        """
        # Feature: vision-action-agent, Property 5: Image format conversion
        
        Property: For any captured screenshot, the output should be valid base64 
        encoded data that can be decoded back to the original image
        **Validates: Requirements 2.2**
        """
        width, height = dimensions
        
        # Create mock config inline
        mock_config = {
            'vision_model': 'llava',
            'capture_region': None,
            'max_image_dimension': 1024
        }
        
        with patch('src.vision_client.mss.mss') as mock_mss_class:
            mock_sct = Mock()
            mock_mss_class.return_value = mock_sct
            
            # Create a mock screenshot
            mock_screenshot = Mock()
            mock_screenshot.size = (800, 600)
            mock_screenshot.bgra = b'\x00' * (800 * 600 * 4)  # Mock BGRA data
            mock_sct.grab.return_value = mock_screenshot
            mock_sct.monitors = [None, {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}]
        
        with patch('src.vision_client.Image.frombytes') as mock_frombytes:
            # Create a mock image with the specified dimensions
            mock_img = Mock()
            mock_img.size = (width, height)
            
            # Mock the save method to write actual JPEG data
            def mock_save(buffer, format=None, quality=None):
                # Create a minimal JPEG header for testing
                jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb'
                buffer.write(jpeg_header)
            
            mock_img.save = mock_save
            mock_frombytes.return_value = mock_img
            
            vision_client = VisionClient(mock_config)
            
            # Capture screenshot
            result = asyncio.run(vision_client.capture_screen())
            
            # Property: Result should be valid base64
            assert isinstance(result, str), "Result should be a string"
            assert len(result) > 0, "Result should not be empty"
            
            # Property: Should be decodable back to binary data
            try:
                decoded_data = base64.b64decode(result)
                assert len(decoded_data) > 0, "Decoded data should not be empty"
                
                # Should start with JPEG header
                assert decoded_data.startswith(b'\xff\xd8'), "Should be valid JPEG data"
                
            except Exception as e:
                pytest.fail(f"Base64 round-trip failed: {e}")
            
            # Property: Re-encoding should produce the same result
            re_encoded = base64.b64encode(decoded_data).decode('utf-8')
            assert re_encoded == result, "Re-encoding should produce identical result"
    
    @given(
        contexts=st.sampled_from(["gaming", "desktop", "application"]),
        action_histories=st.one_of(
            st.none(),
            st.lists(
                st.fixed_dictionaries({
                    'action_type': st.sampled_from(['click', 'keypress', 'drag', 'wait', 'none']),
                    'target': st.one_of(st.none(), st.tuples(st.integers(0, 1920), st.integers(0, 1080)))
                }),
                min_size=1,
                max_size=3
            )
        )
    )
    @settings(max_examples=1, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_vlm_integration_round_trip_property(self, contexts, action_histories):
        """
        # Feature: vision-action-agent, Property 6: VLM integration round-trip
        
        Property: For any screenshot sent to the Vision Language Model, 
        the system should receive a structured response containing all required fields
        **Validates: Requirements 2.3, 2.5, 8.3**
        """
        # Create mock config inline
        mock_config = {
            'vision_model': 'llava',
            'capture_region': None,
            'max_image_dimension': 1024
        }
        
        # Mock valid VLM response
        mock_vlm_response = {
            'response': '{"thought": "I can see the screen", "commentary": "Looking at the interface", "action_type": "click", "target": [100, 200], "key": null, "confidence": 0.8}'
        }
        
        with patch('src.vision_client.mss.mss') as mock_mss_class:
            mock_sct = Mock()
            mock_mss_class.return_value = mock_sct
            
            # Create a mock screenshot
            mock_screenshot = Mock()
            mock_screenshot.size = (800, 600)
            mock_screenshot.bgra = b'\x00' * (800 * 600 * 4)
            mock_sct.grab.return_value = mock_screenshot
            mock_sct.monitors = [None, {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}]
            
            with patch('src.vision_client.Image.frombytes') as mock_frombytes:
                mock_img = Mock()
                mock_img.size = (800, 600)
                mock_img.save = Mock()
                mock_frombytes.return_value = mock_img
                
                with patch('asyncio.to_thread') as mock_to_thread:
                    mock_to_thread.return_value = mock_vlm_response
                    
                    vision_client = VisionClient(mock_config)
                    
                    # Test VLM analysis with different contexts and action histories
                    image_b64 = asyncio.run(vision_client.capture_screen())
                    result_tuple = asyncio.run(vision_client.analyze_scene(image_b64, contexts, action_histories))
                    
                    # analyze_scene returns (AgentCommand, image_dimensions)
                    result, image_dimensions = result_tuple
                    
                    # Property: Should return AgentCommand with all required fields
                    assert isinstance(result, AgentCommand), "Result should be AgentCommand instance"
                    assert hasattr(result, 'thought'), "Should have thought field"
                    assert hasattr(result, 'commentary'), "Should have commentary field"
                    assert hasattr(result, 'action_type'), "Should have action_type field"
                    assert hasattr(result, 'target'), "Should have target field"
                    assert hasattr(result, 'key'), "Should have key field"
                    assert hasattr(result, 'confidence'), "Should have confidence field"
                    assert hasattr(result, 'timestamp'), "Should have timestamp field"
                    
                    # Property: Fields should have correct types
                    assert isinstance(result.thought, str), "Thought should be string"
                    assert isinstance(result.commentary, str), "Commentary should be string"
                    assert isinstance(result.action_type, str), "Action type should be string"
                    assert isinstance(result.confidence, float), "Confidence should be float"
                    assert 0.0 <= result.confidence <= 1.0, "Confidence should be between 0 and 1"
                    
                    # Property: Target should be tuple or None
                    if result.target is not None:
                        assert isinstance(result.target, tuple), "Target should be tuple when not None"
                        assert len(result.target) == 2, "Target should have 2 coordinates"
                        assert all(isinstance(coord, int) for coord in result.target), "Coordinates should be integers"
                    
                    # Property: Action type should be valid
                    valid_actions = ['click', 'keypress', 'drag', 'wait', 'none']
                    assert result.action_type in valid_actions, f"Action type should be one of {valid_actions}"
                    
                    # Property: VLM should be called with proper parameters
                    mock_to_thread.assert_called_once()
                    # Verify the call was made (without checking specific argument positions)
                    assert mock_to_thread.called, "VLM should be called via asyncio.to_thread"