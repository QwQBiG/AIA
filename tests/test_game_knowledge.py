"""
Tests for GameKnowledge - profile and template management.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
import numpy as np
import cv2

from src.game_knowledge import GameKnowledge, GameProfile


class TestGameKnowledge:
    """Test suite for GameKnowledge class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def game_knowledge(self, temp_dir):
        """Create a GameKnowledge instance with temporary directory."""
        return GameKnowledge(base_path=temp_dir)
    
    @pytest.fixture
    def sample_profile_data(self):
        """Sample profile data for testing."""
        return {
            "display_name": "Test Game",
            "description": "A test game for unit testing",
            "vlm_prompts": [
                "You are playing Test Game.",
                "Your goal is to test the system."
            ],
            "default_templates": {
                "target": "target.png",
                "button": "button.png"
            },
            "action_cooldowns": {
                "click": 0.5
            }
        }
    
    def test_create_profile_success(self, game_knowledge, sample_profile_data):
        """Test creating a new game profile."""
        result = game_knowledge.create_profile("test-game", sample_profile_data)
        
        assert result is True
        
        # Verify directory structure
        game_path = Path(game_knowledge.base_path) / "test-game"
        assert game_path.exists()
        assert (game_path / "profile.json").exists()
        assert (game_path / "templates").exists()
        
        # Verify profile.json content
        with open(game_path / "profile.json", 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["display_name"] == "Test Game"
        assert saved_data["description"] == "A test game for unit testing"
        assert len(saved_data["vlm_prompts"]) == 2
    
    def test_create_profile_already_exists(self, game_knowledge, sample_profile_data):
        """Test creating a profile that already exists."""
        game_knowledge.create_profile("test-game", sample_profile_data)
        result = game_knowledge.create_profile("test-game", sample_profile_data)
        
        assert result is False
    
    def test_create_profile_missing_required_field(self, game_knowledge):
        """Test creating a profile with missing required fields."""
        incomplete_data = {
            "display_name": "Test Game",
            "description": "Missing other fields"
        }
        
        result = game_knowledge.create_profile("incomplete-game", incomplete_data)
        assert result is False
    
    def test_save_template(self, game_knowledge, sample_profile_data):
        """Test saving a template image."""
        # Create profile first
        game_knowledge.create_profile("test-game", sample_profile_data)
        
        # Create a test image
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        test_image[10:40, 10:40] = [255, 0, 0]  # Blue square
        
        # Save template
        template_path = game_knowledge.save_template("test-game", "test-template", test_image)
        
        assert Path(template_path).exists()
        assert template_path.endswith("test-template.png")
        
        # Verify image can be loaded
        loaded_image = cv2.imread(template_path)
        assert loaded_image is not None
        assert loaded_image.shape == test_image.shape
    
    def test_load_profile_success(self, game_knowledge, sample_profile_data):
        """Test loading a game profile."""
        # Create profile first
        game_knowledge.create_profile("test-game", sample_profile_data)
        
        # Load profile
        profile = game_knowledge.load_profile("test-game")
        
        assert profile is not None
        assert isinstance(profile, GameProfile)
        assert profile.game_name == "test-game"
        assert profile.display_name == "Test Game"
        assert profile.description == "A test game for unit testing"
        assert len(profile.vlm_prompts) == 2
        assert "target" in profile.default_templates
        assert profile.action_cooldowns["click"] == 0.5
    
    def test_load_profile_not_found(self, game_knowledge):
        """Test loading a non-existent profile."""
        profile = game_knowledge.load_profile("non-existent-game")
        assert profile is None
    
    def test_load_profile_invalid_json(self, game_knowledge, temp_dir):
        """Test loading a profile with invalid JSON."""
        # Create directory and invalid JSON file
        game_path = Path(temp_dir) / "invalid-game"
        game_path.mkdir(parents=True)
        
        with open(game_path / "profile.json", 'w') as f:
            f.write("{ invalid json }")
        
        profile = game_knowledge.load_profile("invalid-game")
        assert profile is None
    
    def test_list_templates(self, game_knowledge, sample_profile_data):
        """Test listing all templates for a game."""
        # Create profile
        game_knowledge.create_profile("test-game", sample_profile_data)
        
        # Create test images
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        game_knowledge.save_template("test-game", "template1", test_image)
        game_knowledge.save_template("test-game", "template2", test_image)
        game_knowledge.save_template("test-game", "template3", test_image)
        
        # List templates
        templates = game_knowledge.list_templates("test-game")
        
        assert len(templates) == 3
        assert all(t.endswith(".png") for t in templates)
        assert any("template1" in t for t in templates)
        assert any("template2" in t for t in templates)
        assert any("template3" in t for t in templates)
    
    def test_list_templates_empty(self, game_knowledge, sample_profile_data):
        """Test listing templates when none exist."""
        game_knowledge.create_profile("test-game", sample_profile_data)
        templates = game_knowledge.list_templates("test-game")
        assert templates == []
    
    def test_list_templates_nonexistent_game(self, game_knowledge):
        """Test listing templates for non-existent game."""
        templates = game_knowledge.list_templates("non-existent-game")
        assert templates == []
    
    def test_get_template_path(self, game_knowledge, sample_profile_data):
        """Test getting path to a specific template."""
        # Create profile and template
        game_knowledge.create_profile("test-game", sample_profile_data)
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        saved_path = game_knowledge.save_template("test-game", "my-template", test_image)
        
        # Get template path
        retrieved_path = game_knowledge.get_template_path("test-game", "my-template")
        
        assert retrieved_path == saved_path
        assert Path(retrieved_path).exists()
    
    def test_get_template_path_with_extension(self, game_knowledge, sample_profile_data):
        """Test getting template path when .png extension is provided."""
        game_knowledge.create_profile("test-game", sample_profile_data)
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        game_knowledge.save_template("test-game", "my-template", test_image)
        
        # Get template path with extension
        retrieved_path = game_knowledge.get_template_path("test-game", "my-template.png")
        
        assert retrieved_path is not None
        assert Path(retrieved_path).exists()
    
    def test_profile_hot_reload(self, game_knowledge, sample_profile_data):
        """Test that profile can be reloaded after modification (Requirement 5.4)."""
        # Create initial profile
        game_knowledge.create_profile("test-game", sample_profile_data)
        profile1 = game_knowledge.load_profile("test-game")
        
        # Modify profile.json
        game_path = Path(game_knowledge.base_path) / "test-game"
        modified_data = sample_profile_data.copy()
        modified_data["display_name"] = "Modified Test Game"
        
        with open(game_path / "profile.json", 'w') as f:
            json.dump(modified_data, f, indent=2)
        
        # Reload profile
        profile2 = game_knowledge.load_profile("test-game")
        
        assert profile2 is not None
        assert profile2.display_name == "Modified Test Game"
        assert profile2.display_name != profile1.display_name
