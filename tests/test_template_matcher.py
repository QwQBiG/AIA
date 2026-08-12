"""
Property-based tests for TemplateMatcher.

This module tests template matching functionality using property-based
testing with Hypothesis.

Feature: hybrid-vision-reflex-system
"""

import pytest
import tempfile
import os
import cv2
import numpy as np
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, patch
import time

from src.template_matcher import TemplateMatcher, MatchResult


class TestTemplateMatcher:
    """Property-based tests for template matching."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def matcher(self):
        """Create a TemplateMatcher instance."""
        return TemplateMatcher(confidence_threshold=0.7)
    
    def create_test_template(self, width: int, height: int, color: tuple = (100, 150, 200)) -> np.ndarray:
        """Create a test template image with specific dimensions and color."""
        template = np.zeros((height, width, 3), dtype=np.uint8)
        template[:, :] = color
        # Add some pattern to make it distinctive
        cv2.rectangle(template, (5, 5), (width-5, height-5), (255, 255, 255), 2)
        cv2.circle(template, (width//2, height//2), min(width, height)//4, (0, 255, 0), -1)
        return template
    
    def create_screenshot_with_template(self, template: np.ndarray, position: tuple, 
                                       screenshot_size: tuple = (800, 600)) -> np.ndarray:
        """Create a screenshot containing the template at a specific position."""
        screenshot = np.random.randint(0, 50, (screenshot_size[1], screenshot_size[0], 3), dtype=np.uint8)
        x, y = position
        h, w = template.shape[:2]
        
        # Ensure template fits in screenshot
        if x + w <= screenshot_size[0] and y + h <= screenshot_size[1]:
            screenshot[y:y+h, x:x+w] = template
        
        return screenshot
    
    # Property 1: Template Validation
    @given(
        width=st.integers(min_value=20, max_value=200),
        height=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_template_validation_valid(self, temp_dir, matcher, width, height):
        """
        Property 1: Template Validation
        
        For any file path provided to the Template_Matcher, if the file is a valid PNG
        image with dimensions between 20x20 and 200x200 pixels, it should be accepted.
        
        **Validates: Requirements 1.1, 4.5**
        """
        # Create a valid template
        template = self.create_test_template(width, height)
        template_path = os.path.join(temp_dir, f"template_{width}x{height}.png")
        cv2.imwrite(template_path, template)
        
        # Load template
        result = matcher.load_template(template_path)
        
        # Should be accepted
        assert result is True
        assert matcher._template is not None
        assert matcher._template_width == width
        assert matcher._template_height == height
    
    @given(
        width=st.one_of(
            st.integers(min_value=1, max_value=19),
            st.integers(min_value=201, max_value=500)
        ),
        height=st.one_of(
            st.integers(min_value=1, max_value=19),
            st.integers(min_value=201, max_value=500)
        )
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_template_validation_invalid_dimensions(self, temp_dir, matcher, width, height):
        """
        Property 1: Template Validation (Invalid Dimensions)
        
        For any file path provided to the Template_Matcher, if the file has dimensions
        outside the 20x20 to 200x200 range, it should be rejected with an appropriate error.
        
        **Validates: Requirements 1.1, 4.5**
        """
        # Create a template with invalid dimensions
        template = self.create_test_template(width, height)
        template_path = os.path.join(temp_dir, f"template_{width}x{height}.png")
        cv2.imwrite(template_path, template)
        
        # Load template
        result = matcher.load_template(template_path)
        
        # Should be rejected
        assert result is False
        assert matcher._template is None
    
    def test_property_template_validation_nonexistent_file(self, matcher):
        """
        Property 1: Template Validation (Nonexistent File)
        
        For any file path that doesn't exist, the Template_Matcher should reject it.
        
        **Validates: Requirements 1.1, 4.5**
        """
        result = matcher.load_template("/nonexistent/path/template.png")
        assert result is False
        assert matcher._template is None
    
    # Property 2: Match Coordinate Accuracy
    @given(
        template_width=st.integers(min_value=30, max_value=100),
        template_height=st.integers(min_value=30, max_value=100),
        x_pos=st.integers(min_value=50, max_value=600),
        y_pos=st.integers(min_value=50, max_value=400)
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_match_coordinate_accuracy(self, temp_dir, matcher, 
                                                template_width, template_height, x_pos, y_pos):
        """
        Property 2: Match Coordinate Accuracy
        
        For any synthetic screenshot containing a known template at position (x, y),
        when the Template_Matcher finds a match with confidence >= 0.7, the returned
        center coordinates should be within 5 pixels of the actual center.
        
        **Validates: Requirements 1.3**
        """
        # Ensure template fits in screenshot
        assume(x_pos + template_width <= 800)
        assume(y_pos + template_height <= 600)
        
        # Create template
        template = self.create_test_template(template_width, template_height)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Load template
        assert matcher.load_template(template_path)
        
        # Create screenshot with template at known position
        screenshot = self.create_screenshot_with_template(template, (x_pos, y_pos))
        
        # Find match
        result = matcher.find_match(screenshot)
        
        # Calculate expected center
        expected_center_x = x_pos + template_width // 2
        expected_center_y = y_pos + template_height // 2
        
        # Verify match found
        assert result.found is True
        assert result.confidence >= 0.7
        
        # Verify coordinate accuracy (within 5 pixels)
        assert abs(result.center_x - expected_center_x) <= 5
        assert abs(result.center_y - expected_center_y) <= 5
    
    # Property 3: Low Confidence Rejection
    @given(
        template_width=st.integers(min_value=30, max_value=100),
        template_height=st.integers(min_value=30, max_value=100)
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_low_confidence_rejection(self, temp_dir, matcher, 
                                               template_width, template_height):
        """
        Property 3: Low Confidence Rejection
        
        For any screenshot where the template is not present or heavily distorted
        (confidence < 0.7), the Template_Matcher should return a "Target Lost" status
        rather than false positive coordinates.
        
        **Validates: Requirements 1.4**
        """
        # Create template
        template = self.create_test_template(template_width, template_height, color=(100, 150, 200))
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Load template
        assert matcher.load_template(template_path)
        
        # Create screenshot WITHOUT the template (just random noise)
        screenshot = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        
        # Find match
        result = matcher.find_match(screenshot)
        
        # Should return "Target Lost" status (found=False)
        if result.confidence < 0.7:
            assert result.found is False
            assert result.center_x == 0
            assert result.center_y == 0
    
    # Property 4: Highest Confidence Selection
    @given(
        template_width=st.integers(min_value=30, max_value=80),
        template_height=st.integers(min_value=30, max_value=80),
        num_instances=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_highest_confidence_selection(self, temp_dir, matcher,
                                                   template_width, template_height, num_instances):
        """
        Property 4: Highest Confidence Selection
        
        For any screenshot containing multiple instances of a template, the
        Template_Matcher should return the match with the highest confidence score.
        
        **Validates: Requirements 1.5**
        """
        # Create template
        template = self.create_test_template(template_width, template_height)
        template_path = os.path.join(temp_dir, "template.png")
        cv2.imwrite(template_path, template)
        
        # Load template
        assert matcher.load_template(template_path)
        
        # Create screenshot with multiple instances
        screenshot = np.random.randint(0, 50, (600, 800, 3), dtype=np.uint8)
        
        # Place multiple instances with varying quality
        positions = []
        for i in range(num_instances):
            x = 50 + i * 150
            y = 50 + i * 100
            
            # Ensure it fits
            if x + template_width <= 800 and y + template_height <= 600:
                # First instance is perfect match
                if i == 0:
                    screenshot[y:y+template_height, x:x+template_width] = template
                    positions.append((x, y, 1.0))  # Perfect match
                else:
                    # Other instances are slightly degraded
                    degraded = template.copy()
                    noise = np.random.randint(-20, 20, degraded.shape, dtype=np.int16)
                    degraded = np.clip(degraded.astype(np.int16) + noise, 0, 255).astype(np.uint8)
                    screenshot[y:y+template_height, x:x+template_width] = degraded
                    positions.append((x, y, 0.8))  # Degraded match
        
        # Find match
        result = matcher.find_match(screenshot)
        
        # Should find a match
        assert result.found is True
        
        # The match should be the first instance (highest confidence)
        # Allow some tolerance for coordinate matching
        first_pos = positions[0]
        expected_center_x = first_pos[0] + template_width // 2
        expected_center_y = first_pos[1] + template_height // 2
        
        # Verify it's close to the best match position
        distance = np.sqrt((result.center_x - expected_center_x)**2 + 
                          (result.center_y - expected_center_y)**2)
        
        # Should be within reasonable distance (allowing for OpenCV matching variations)
        assert distance <= 50  # Relaxed threshold for multiple instances


class TestTemplateMatcherEdgeCases:
    """Unit tests for edge cases and error handling."""
    
    @pytest.fixture
    def matcher(self):
        """Create a TemplateMatcher instance."""
        return TemplateMatcher(confidence_threshold=0.7)
    
    def test_find_match_without_loaded_template(self, matcher):
        """Test that find_match handles missing template gracefully."""
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        result = matcher.find_match(screenshot)
        
        assert result.found is False
        assert result.confidence == 0.0
    
    def test_template_larger_than_screenshot(self, matcher, tmp_path):
        """Test that template larger than screenshot is handled."""
        # Create large template
        template = np.zeros((500, 500, 3), dtype=np.uint8)
        template_path = tmp_path / "large_template.png"
        cv2.imwrite(str(template_path), template)
        
        # Load template (should fail due to size)
        result = matcher.load_template(str(template_path))
        assert result is False
    
    def test_region_of_interest_matching(self, matcher, tmp_path):
        """Test template matching within a specific region."""
        # Create template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:, :] = (100, 150, 200)
        cv2.rectangle(template, (10, 10), (40, 40), (255, 255, 255), 2)
        
        template_path = tmp_path / "template.png"
        cv2.imwrite(str(template_path), template)
        
        # Load template
        assert matcher.load_template(str(template_path))
        
        # Create screenshot with template at position (200, 200)
        screenshot = np.random.randint(0, 50, (600, 800, 3), dtype=np.uint8)
        screenshot[200:250, 200:250] = template
        
        # Search in region containing the template
        region = (150, 150, 200, 200)  # (x, y, width, height)
        result = matcher.find_match(screenshot, region=region)
        
        # Should find the template
        assert result.found is True
        
        # Coordinates should be absolute (not relative to region)
        assert 200 <= result.center_x <= 250
        assert 200 <= result.center_y <= 250
    
    def test_confidence_threshold_initialization(self):
        """Test that confidence threshold is validated on initialization."""
        # Valid thresholds
        matcher1 = TemplateMatcher(0.5)
        assert matcher1.confidence_threshold == 0.5
        
        matcher2 = TemplateMatcher(0.9)
        assert matcher2.confidence_threshold == 0.9
        
        # Invalid thresholds
        with pytest.raises(ValueError):
            TemplateMatcher(-0.1)
        
        with pytest.raises(ValueError):
            TemplateMatcher(1.5)
    
    def test_match_result_timestamp(self, matcher, tmp_path):
        """Test that MatchResult includes timestamp."""
        # Create and load template
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:, :] = (100, 150, 200)
        template_path = tmp_path / "template.png"
        cv2.imwrite(str(template_path), template)
        
        assert matcher.load_template(str(template_path))
        
        # Create screenshot
        screenshot = np.random.randint(0, 50, (600, 800, 3), dtype=np.uint8)
        screenshot[100:150, 100:150] = template
        
        # Get timestamp before matching
        before = time.time()
        result = matcher.find_match(screenshot)
        after = time.time()
        
        # Timestamp should be within the time range
        assert before <= result.timestamp <= after
