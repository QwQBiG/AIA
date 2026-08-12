"""
Unit and property tests for configuration and data models.

Feature: ai-vtuber-system
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
from hypothesis import given, strategies as st

from src.config import SystemConfig, ChatMessage, SystemState, load_config, create_default_config


class TestSystemConfig:
    """Unit tests for SystemConfig class."""
    
    def test_default_config_creation(self):
        """Test creating SystemConfig with default values."""
        config = SystemConfig()
        
        assert config.ollama_url == "http://localhost:11434"
        assert config.ollama_model == "llama3"
        assert config.tts_voice == "zh-CN-XiaoxiaoNeural"
        assert config.vts_port == 8001
        assert config.log_level == "INFO"
        
        # Test new emotional intelligence defaults
        assert config.enable_emotional_intelligence is False
        assert config.enable_voice_cloning is False
        assert config.enable_expression_control is False
        
        # Test GPT-SoVITS defaults
        assert config.sovits_url == "http://127.0.0.1:9880"
        assert config.sovits_timeout == 10.0
        assert config.sovits_language == "zh"
        assert config.fallback_to_edge_tts is True
        
        # Test emotion configuration defaults
        assert config.default_emotion == "neutral"
        assert config.expression_timeout == 0.5
        assert isinstance(config.emotion_hotkey_map, dict)
        assert "neutral" in config.emotion_hotkey_map
        assert "happy" in config.emotion_hotkey_map
        assert "angry" in config.emotion_hotkey_map
        assert "sad" in config.emotion_hotkey_map
        assert "surprised" in config.emotion_hotkey_map
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = SystemConfig()
        config.validate()  # Should not raise any exception
    
    def test_config_validation_failures(self):
        """Test configuration validation with invalid values."""
        # Test invalid ollama_url
        config = SystemConfig(ollama_url="")
        with pytest.raises(ValueError, match="ollama_url must be a non-empty string"):
            config.validate()
        
        # Test invalid vts_port
        config = SystemConfig(vts_port=-1)
        with pytest.raises(ValueError, match="vts_port must be a positive integer"):
            config.validate()
        
        # Test invalid log_level
        config = SystemConfig(log_level="INVALID")
        with pytest.raises(ValueError, match="log_level must be one of"):
            config.validate()
    
    def test_emotional_intelligence_validation(self):
        """Test validation of emotional intelligence settings."""
        # Test invalid enable_emotional_intelligence
        config = SystemConfig(enable_emotional_intelligence="invalid")
        with pytest.raises(ValueError, match="enable_emotional_intelligence must be a boolean"):
            config.validate()
        
        # Test invalid sovits_timeout
        config = SystemConfig(sovits_timeout=-1)
        with pytest.raises(ValueError, match="sovits_timeout must be a positive number"):
            config.validate()
        
        # Test invalid emotion_hotkey_map
        config = SystemConfig(emotion_hotkey_map="invalid")
        with pytest.raises(ValueError, match="emotion_hotkey_map must be a dictionary"):
            config.validate()
        
        # Test invalid emotion in mapping
        config = SystemConfig(emotion_hotkey_map={"invalid_emotion": "hotkey1"})
        with pytest.raises(ValueError, match="Invalid emotion 'invalid_emotion'"):
            config.validate()
        
        # Test invalid default_emotion
        config = SystemConfig(default_emotion="invalid")
        with pytest.raises(ValueError, match="default_emotion must be one of"):
            config.validate()
    
    def test_backward_compatibility_with_old_config(self):
        """Test that old configuration files without new fields work correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Old config format without emotional intelligence fields
            old_config_data = {
                "ollama_url": "http://test:11434",
                "ollama_model": "test_model",
                "tts_voice": "test_voice",
                "vts_port": 9001,
                "log_level": "DEBUG"
            }
            json.dump(old_config_data, f)
            temp_path = f.name
        
        try:
            config = SystemConfig.load_from_file(temp_path)
            
            # Verify old fields are loaded correctly
            assert config.ollama_url == "http://test:11434"
            assert config.ollama_model == "test_model"
            assert config.tts_voice == "test_voice"
            assert config.vts_port == 9001
            assert config.log_level == "DEBUG"
            
            # Verify new fields have default values
            assert config.enable_emotional_intelligence is False
            assert config.enable_voice_cloning is False
            assert config.enable_expression_control is False
            assert config.sovits_url == "http://127.0.0.1:9880"
            assert config.sovits_timeout == 10.0
            assert config.sovits_language == "zh"
            assert config.fallback_to_edge_tts is True
            assert config.default_emotion == "neutral"
            assert config.expression_timeout == 0.5
            assert isinstance(config.emotion_hotkey_map, dict)
            
            # Validation should pass
            config.validate()
            
        finally:
            os.unlink(temp_path)
    
    def test_full_config_loading_with_new_fields(self):
        """Test loading configuration with all new emotional intelligence fields."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            full_config_data = {
                "ollama_url": "http://localhost:11434",
                "ollama_model": "llama3",
                "tts_voice": "zh-CN-XiaoxiaoNeural",
                "vts_port": 8001,
                "log_level": "INFO",
                "enable_emotional_intelligence": True,
                "enable_voice_cloning": True,
                "enable_expression_control": True,
                "sovits_url": "http://127.0.0.1:9880",
                "sovits_timeout": 15.0,
                "sovits_language": "en",
                "fallback_to_edge_tts": False,
                "emotion_hotkey_map": {
                    "neutral": "hotkey1",
                    "happy": "hotkey2",
                    "angry": "hotkey3",
                    "sad": "hotkey4",
                    "surprised": "hotkey5"
                },
                "default_emotion": "happy",
                "expression_timeout": 1.0
            }
            json.dump(full_config_data, f)
            temp_path = f.name
        
        try:
            config = SystemConfig.load_from_file(temp_path)
            
            # Verify all fields are loaded correctly
            assert config.enable_emotional_intelligence is True
            assert config.enable_voice_cloning is True
            assert config.enable_expression_control is True
            assert config.sovits_url == "http://127.0.0.1:9880"
            assert config.sovits_timeout == 15.0
            assert config.sovits_language == "en"
            assert config.fallback_to_edge_tts is False
            assert config.default_emotion == "happy"
            assert config.expression_timeout == 1.0
            assert config.emotion_hotkey_map["neutral"] == "hotkey1"
            assert config.emotion_hotkey_map["happy"] == "hotkey2"
            
            # Validation should pass
            config.validate()
            
        finally:
            os.unlink(temp_path)
    
    def test_config_error_handling_with_invalid_json(self):
        """Test error handling when configuration file contains invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json content")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid configuration file"):
                SystemConfig.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_config_with_unknown_fields(self):
        """Test that unknown fields in config file are ignored gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_with_unknown = {
                "ollama_url": "http://localhost:11434",
                "unknown_field": "should_be_ignored",
                "another_unknown": 123,
                "enable_emotional_intelligence": True
            }
            json.dump(config_with_unknown, f)
            temp_path = f.name
        
        try:
            config = SystemConfig.load_from_file(temp_path)
            
            # Known fields should be loaded
            assert config.ollama_url == "http://localhost:11434"
            assert config.enable_emotional_intelligence is True
            
            # Unknown fields should not cause errors
            assert not hasattr(config, 'unknown_field')
            assert not hasattr(config, 'another_unknown')
            
            # Validation should pass
            config.validate()
            
        finally:
            os.unlink(temp_path)


class TestChatMessage:
    """Unit tests for ChatMessage class."""
    
    def test_valid_message_creation(self):
        """Test creating valid ChatMessage."""
        timestamp = datetime.now()
        message = ChatMessage(role="user", content="Hello", timestamp=timestamp)
        
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.timestamp == timestamp
    
    def test_invalid_role(self):
        """Test ChatMessage with invalid role."""
        with pytest.raises(ValueError, match="role must be either 'user' or 'assistant'"):
            ChatMessage(role="invalid", content="Hello", timestamp=datetime.now())
    
    def test_empty_content(self):
        """Test ChatMessage with empty content."""
        with pytest.raises(ValueError, match="content must be a non-empty string"):
            ChatMessage(role="user", content="", timestamp=datetime.now())
    
    def test_message_serialization(self):
        """Test message to/from dictionary conversion."""
        timestamp = datetime.now()
        message = ChatMessage(role="assistant", content="Hi there!", timestamp=timestamp)
        
        # Test to_dict
        data = message.to_dict()
        assert data["role"] == "assistant"
        assert data["content"] == "Hi there!"
        assert data["timestamp"] == timestamp.isoformat()
        
        # Test from_dict
        restored = ChatMessage.from_dict(data)
        assert restored.role == message.role
        assert restored.content == message.content
        assert restored.timestamp == message.timestamp


class TestSystemState:
    """Unit tests for SystemState class."""
    
    def test_default_state(self):
        """Test default SystemState values."""
        state = SystemState()
        
        assert state.ollama_connected is False
        assert state.vts_connected is False
        assert state.is_speaking is False
        assert state.current_audio_file is None
    
    def test_reset_connections(self):
        """Test resetting connection states."""
        state = SystemState(ollama_connected=True, vts_connected=True)
        state.reset_connections()
        
        assert state.ollama_connected is False
        assert state.vts_connected is False
    
    def test_audio_state_management(self):
        """Test audio state management."""
        state = SystemState()
        
        # Start speaking
        state.set_audio_state(True, "/path/to/audio.mp3")
        assert state.is_speaking is True
        assert state.current_audio_file == "/path/to/audio.mp3"
        
        # Stop speaking
        state.set_audio_state(False)
        assert state.is_speaking is False
        assert state.current_audio_file is None


class TestFilePathConsistency:
    """Property-based tests for file path consistency."""
    
    @given(st.text(min_size=1, max_size=100))
    def test_file_path_consistency_property(self, filename):
        """
        Property 4: File Path Consistency
        For any file operation in the system, absolute paths should be used 
        to ensure reliability across different execution contexts.
        
        Feature: ai-vtuber-system, Property 4: File Path Consistency
        Validates: Requirements 3.4, 7.2
        """
        # Filter out invalid filename characters for cross-platform compatibility
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        if not safe_filename:
            safe_filename = "test_config"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test relative path input
            relative_path = f"{safe_filename}.json"
            
            # Create config and save to relative path
            config = SystemConfig()
            
            # Change to temp directory to test relative path handling
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Save config using relative path
                config.save_to_file(relative_path)
                
                # Verify file was created with absolute path handling
                expected_abs_path = os.path.abspath(relative_path)
                assert os.path.exists(expected_abs_path)
                
                # Load config using relative path
                loaded_config = SystemConfig.load_from_file(relative_path)
                
                # Verify loaded config matches original
                assert loaded_config.ollama_url == config.ollama_url
                assert loaded_config.ollama_model == config.ollama_model
                assert loaded_config.tts_voice == config.tts_voice
                assert loaded_config.vts_port == config.vts_port
                assert loaded_config.log_level == config.log_level
                
            finally:
                os.chdir(original_cwd)
    
    def test_absolute_path_handling(self):
        """Test that absolute paths are handled correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with absolute path
            abs_path = os.path.join(temp_dir, "absolute_config.json")
            
            config = SystemConfig(ollama_model="test_model")
            config.save_to_file(abs_path)
            
            # Verify file exists at absolute path
            assert os.path.exists(abs_path)
            
            # Load and verify
            loaded_config = SystemConfig.load_from_file(abs_path)
            assert loaded_config.ollama_model == "test_model"
    
    def test_nonexistent_file_handling(self):
        """Test handling of nonexistent configuration files."""
        nonexistent_path = "/nonexistent/path/config.json"
        
        # Should return default config for nonexistent file
        config = SystemConfig.load_from_file(nonexistent_path)
        default_config = SystemConfig()
        
        assert config.ollama_url == default_config.ollama_url
        assert config.ollama_model == default_config.ollama_model
        assert config.tts_voice == default_config.tts_voice
        assert config.vts_port == default_config.vts_port
        assert config.log_level == default_config.log_level


class TestConfigUtilityFunctions:
    """Unit tests for utility functions."""
    
    def test_load_config_function(self):
        """Test load_config utility function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "ollama_url": "http://test:11434",
                "ollama_model": "test_model",
                "tts_voice": "test_voice",
                "vts_port": 9001,
                "log_level": "DEBUG"
            }
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert config.ollama_url == "http://test:11434"
            assert config.ollama_model == "test_model"
            assert config.log_level == "DEBUG"
        finally:
            os.unlink(temp_path)
    
    def test_create_default_config_function(self):
        """Test create_default_config utility function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "default_config.json")
            
            config = create_default_config(config_path)
            
            # Verify file was created
            assert os.path.exists(config_path)
            
            # Verify config has default values
            assert config.ollama_url == "http://localhost:11434"
            assert config.ollama_model == "llama3"
            
            # Verify file content
            with open(config_path, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data["ollama_url"] == "http://localhost:11434"
            assert saved_data["ollama_model"] == "llama3"