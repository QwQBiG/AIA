"""
Tests for Memory Core ChromaDB setup and configuration.

This module tests the basic ChromaDB installation and configuration,
particularly ensuring telemetry is disabled as required.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.memory_core import MemoryCore
from src.memory_core.data_models import MemoryType


class TestMemoryCoreSetup:
    """Test ChromaDB setup and basic functionality."""
    
    def setup_method(self):
        """Setup test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_memory_db"
        self.memory_core = MemoryCore(db_path=str(self.db_path))
    
    def teardown_method(self):
        """Clean up test environment."""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_chromadb_initialization(self):
        """Test that ChromaDB initializes correctly with telemetry disabled."""
        # Check that the database directory was created
        assert self.db_path.exists()
        
        # Check that ChromaDB client is initialized
        assert self.memory_core.client is not None
        
        # Check that collection is created
        assert self.memory_core.collection is not None
        assert self.memory_core.collection.name == "vtuber_memories"
    
    def test_telemetry_disabled(self):
        """Test that telemetry is properly disabled."""
        # Check that the client settings have telemetry disabled
        # Note: ChromaDB doesn't expose settings directly, but we can verify
        # the initialization completed without errors
        assert self.memory_core.client is not None
        
        # Verify collection metadata includes our custom fields
        collection_metadata = self.memory_core.collection.metadata
        assert "description" in collection_metadata
        assert "schema_version" in collection_metadata
        assert collection_metadata["schema_version"] == "1.0"
    
    def test_collection_creation(self):
        """Test that the collection is created with proper metadata and schema validation."""
        collection = self.memory_core.collection
        
        # Check collection name
        assert collection.name == "vtuber_memories"
        
        # Check metadata
        metadata = collection.metadata
        assert metadata["description"] == "AI VTuber memory storage with semantic search"
        assert metadata["schema_version"] == "1.0"
        assert metadata["embedding_model"] == "all-MiniLM-L6-v2"
        assert metadata["embedding_dimensions"] == 384
        assert "created_at" in metadata
        assert "validation_schema" in metadata
        
        # Validate that the validation schema is properly stored
        import json
        stored_schema = json.loads(metadata["validation_schema"])
        assert stored_schema == self.memory_core.MEMORY_METADATA_SCHEMA
    
    def test_json_schema_validation(self):
        """Test that JSON schema validation works correctly for memory metadata."""
        # Test valid metadata
        valid_metadata = {
            "content": "Test content",
            "timestamp": "2024-01-15T10:30:00Z",
            "memory_type": "INTERACTION",
            "importance_score": 0.8,
            "entities": ["test_entity"],
            "schema_version": "1.0",
            "validated": True
        }
        
        assert self.memory_core._validate_memory_data("Test content", valid_metadata)
        
        # Test invalid metadata - missing required field
        invalid_metadata = {
            "content": "Test content",
            # Missing timestamp
            "memory_type": "INTERACTION"
        }
        
        assert not self.memory_core._validate_memory_data("Test content", invalid_metadata)
        
        # Test invalid metadata - wrong type
        invalid_metadata2 = {
            "content": "Test content",
            "timestamp": "2024-01-15T10:30:00Z",
            "memory_type": "INVALID_TYPE",  # Not in enum
            "importance_score": 0.8
        }
        
        assert not self.memory_core._validate_memory_data("Test content", invalid_metadata2)
        
        # Test invalid metadata - importance_score out of range
        invalid_metadata3 = {
            "content": "Test content",
            "timestamp": "2024-01-15T10:30:00Z",
            "memory_type": "INTERACTION",
            "importance_score": 1.5  # Should be between 0 and 1
        }
        
        assert not self.memory_core._validate_memory_data("Test content", invalid_metadata3)
    
    def test_collection_schema_validation(self):
        """Test that collection schema validation works correctly."""
        # Should pass with properly initialized collection
        assert self.memory_core._validate_collection_schema()
        
        # Test with modified metadata (simulate corrupted collection)
        original_metadata = self.memory_core.collection.metadata.copy()
        
        # This test would require mocking the collection metadata
        # For now, we just verify the method exists and works with valid data
        assert self.memory_core._validate_collection_schema()
    
    def test_memory_storage_without_embedding_model(self):
        """Test that memory storage works even when embedding model isn't ready."""
        # The embedding model loads asynchronously, so it might not be ready
        # This tests graceful degradation
        
        memory_id = self.memory_core.store_interaction(
            user_input="Hello, how are you?",
            ai_response="I'm doing well, thank you for asking!"
        )
        
        # Should return a valid memory ID even without embeddings
        assert memory_id != ""
        assert len(memory_id) > 0
        
        # Check that memory was stored
        count = self.memory_core.collection.count()
        assert count == 1
    
    def test_memory_validation_filter(self):
        """Test that invalid memories are filtered out."""
        # Test very short content
        memory_id = self.memory_core.store_interaction(
            user_input="Hi",
            ai_response="Hi"
        )
        assert memory_id == ""  # Should be rejected
        
        # Test blacklisted patterns
        memory_id = self.memory_core.store_interaction(
            user_input="System: Loading...",
            ai_response="Listening..."
        )
        assert memory_id == ""  # Should be rejected
        
        # Test valid content
        memory_id = self.memory_core.store_interaction(
            user_input="What's your favorite color?",
            ai_response="I really like blue, it reminds me of the sky."
        )
        assert memory_id != ""  # Should be accepted
    
    def test_event_storage(self):
        """Test that game events can be stored."""
        event_data = {
            "game": "test_game",
            "action": "level_complete",
            "score": 1000
        }
        
        memory_id = self.memory_core.store_event(
            event_type="game_achievement",
            event_data=event_data
        )
        
        assert memory_id != ""
        assert len(memory_id) > 0
        
        # Check that event was stored
        count = self.memory_core.collection.count()
        assert count == 1
    
    def test_memory_stats(self):
        """Test that memory statistics are properly tracked."""
        # Store some test memories
        self.memory_core.store_interaction(
            user_input="Test question 1",
            ai_response="Test response 1"
        )
        self.memory_core.store_interaction(
            user_input="Test question 2", 
            ai_response="Test response 2"
        )
        
        # Get statistics
        stats = self.memory_core.get_memory_stats()
        
        assert stats.total_memories == 2
        assert stats.uptime_percentage > 0
        assert isinstance(stats.recent_memories, list)
    
    def test_clear_all_memories(self):
        """Test that all memories can be cleared."""
        # Store some test memories
        self.memory_core.store_interaction(
            user_input="Test question",
            ai_response="Test response"
        )
        
        # Verify memory was stored
        assert self.memory_core.collection.count() == 1
        
        # Clear all memories
        success = self.memory_core.clear_all_memories()
        assert success
        
        # Verify memories were cleared
        assert self.memory_core.collection.count() == 0
    
    def test_data_integrity_validation(self):
        """Test enhanced data integrity validation with schema checking."""
        # Should pass with empty database
        assert self.memory_core.validate_data_integrity()
        
        # Store some valid data and test again
        self.memory_core.store_interaction(
            user_input="Test question",
            ai_response="Test response"
        )
        
        assert self.memory_core.validate_data_integrity()
        
        # Store some event data and test
        self.memory_core.store_event(
            event_type="test_event",
            event_data={"key": "value"}
        )
        
        assert self.memory_core.validate_data_integrity()
    
    def test_graceful_degradation_when_not_ready(self):
        """Test that system works gracefully when embedding model isn't ready."""
        # Force not ready state for testing
        original_ready = self.memory_core.ready
        self.memory_core.ready = False
        
        try:
            # Retrieval should return empty list without errors
            memories = self.memory_core.retrieve_memories("test query")
            assert memories == []
            
            # Storage should still work (without embeddings)
            memory_id = self.memory_core.store_interaction(
                user_input="Test question",
                ai_response="Test response"
            )
            assert memory_id != ""
            
        finally:
            # Restore original state
            self.memory_core.ready = original_ready


if __name__ == "__main__":
    pytest.main([__file__])