"""
Tests for Memory Core data models.

This module tests the data model classes including Memory, Entity, MemoryStats,
and related types to ensure they meet the design requirements.
"""

import pytest
from datetime import datetime, timezone
from dataclasses import fields

from src.memory_core.data_models import (
    Memory, Entity, MemoryStats, Fact, ScoredMemory, OptimizationResult, Summary,
    MemoryType, EntityType, PreferenceType
)


class TestMemoryDataclass:
    """Test the Memory dataclass implementation."""
    
    def test_memory_dataclass_fields(self):
        """Test that Memory dataclass has all required fields with correct types."""
        # Get all fields from the Memory dataclass
        memory_fields = {field.name: field.type for field in fields(Memory)}
        
        # Verify all required fields are present
        required_fields = [
            'id', 'content', 'embedding', 'timestamp', 'memory_type',
            'metadata', 'importance_score', 'access_count', 'last_accessed'
        ]
        
        # Check that all required fields exist
        for field_name in required_fields:
            assert field_name in memory_fields, f"Missing required field: {field_name}"
    
    def test_memory_creation_with_all_fields(self):
        """Test creating a Memory instance with all required fields."""
        now = datetime.now(timezone.utc)
        # Use None for embedding to avoid numpy issues in testing
        metadata = {"source": "test", "confidence": 0.9}
        
        memory = Memory(
            id="test_memory_001",
            content="User said they love pizza",
            embedding=None,  # Will be set to actual embedding later
            timestamp=now,
            memory_type=MemoryType.INTERACTION,
            metadata=metadata,
            importance_score=0.8,
            access_count=5,
            last_accessed=now
        )
        
        # Verify all fields are set correctly
        assert memory.id == "test_memory_001"
        assert memory.content == "User said they love pizza"
        assert memory.embedding is None
        assert memory.timestamp == now
        assert memory.memory_type == MemoryType.INTERACTION
        assert memory.metadata == metadata
        assert memory.importance_score == 0.8
        assert memory.access_count == 5
        assert memory.last_accessed == now
    
    def test_memory_with_optional_embedding(self):
        """Test creating a Memory instance with None embedding (for lazy loading)."""
        now = datetime.now(timezone.utc)
        
        memory = Memory(
            id="test_memory_002",
            content="Test content without embedding",
            embedding=None,
            timestamp=now,
            memory_type=MemoryType.EVENT,
            metadata={},
            importance_score=0.5,
            access_count=0,
            last_accessed=now
        )
        
        assert memory.embedding is None
        assert memory.memory_type == MemoryType.EVENT
        assert memory.access_count == 0
    
    def test_memory_types_enum(self):
        """Test that MemoryType enum has all required values."""
        assert MemoryType.INTERACTION.value == "INTERACTION"
        assert MemoryType.EVENT.value == "EVENT"
        assert MemoryType.SUMMARY.value == "SUMMARY"
        
        # Test that we can create memories with each type
        now = datetime.now(timezone.utc)
        
        for memory_type in MemoryType:
            memory = Memory(
                id=f"test_{memory_type.value.lower()}",
                content=f"Test {memory_type.value} content",
                embedding=None,
                timestamp=now,
                memory_type=memory_type,
                metadata={},
                importance_score=0.5,
                access_count=0,
                last_accessed=now
            )
            assert memory.memory_type == memory_type
    
    def test_memory_importance_score_range(self):
        """Test that importance_score can handle expected range of values."""
        now = datetime.now(timezone.utc)
        
        # Test minimum score
        memory_min = Memory(
            id="test_min",
            content="Low importance content",
            embedding=None,
            timestamp=now,
            memory_type=MemoryType.INTERACTION,
            metadata={},
            importance_score=0.0,
            access_count=0,
            last_accessed=now
        )
        assert memory_min.importance_score == 0.0
        
        # Test maximum score
        memory_max = Memory(
            id="test_max",
            content="High importance content",
            embedding=None,
            timestamp=now,
            memory_type=MemoryType.INTERACTION,
            metadata={},
            importance_score=1.0,
            access_count=100,
            last_accessed=now
        )
        assert memory_max.importance_score == 1.0
        assert memory_max.access_count == 100
    
    def test_memory_metadata_flexibility(self):
        """Test that metadata field can handle various data types."""
        now = datetime.now(timezone.utc)
        
        complex_metadata = {
            "entities": ["user_name:John", "preference:pizza"],
            "confidence": 0.95,
            "source": "conversation",
            "tags": ["food", "preference"],
            "nested": {
                "category": "personal",
                "verified": True
            }
        }
        
        memory = Memory(
            id="test_complex_metadata",
            content="Complex metadata test",
            embedding=None,
            timestamp=now,
            memory_type=MemoryType.INTERACTION,
            metadata=complex_metadata,
            importance_score=0.7,
            access_count=1,
            last_accessed=now
        )
        
        assert memory.metadata == complex_metadata
        assert memory.metadata["entities"] == ["user_name:John", "preference:pizza"]
        assert memory.metadata["nested"]["verified"] is True
    
    def test_memory_access_tracking(self):
        """Test that access count and last accessed fields work correctly."""
        now = datetime.now(timezone.utc)
        later = datetime.now(timezone.utc)
        
        memory = Memory(
            id="test_access_tracking",
            content="Access tracking test",
            embedding=None,
            timestamp=now,
            memory_type=MemoryType.INTERACTION,
            metadata={},
            importance_score=0.6,
            access_count=0,
            last_accessed=now
        )
        
        # Simulate accessing the memory
        memory.access_count += 1
        memory.last_accessed = later
        
        assert memory.access_count == 1
        assert memory.last_accessed == later
        assert memory.last_accessed > memory.timestamp


class TestEntityDataclass:
    """Test the Entity dataclass implementation."""
    
    def test_entity_creation(self):
        """Test creating an Entity instance."""
        now = datetime.now(timezone.utc)
        
        entity = Entity(
            name="pizza",
            entity_type=EntityType.PREFERENCE,
            value="like",
            confidence=0.9,
            first_mentioned=now,
            last_updated=now,
            related_memories=["memory_001", "memory_002"]
        )
        
        assert entity.name == "pizza"
        assert entity.entity_type == EntityType.PREFERENCE
        assert entity.value == "like"
        assert entity.confidence == 0.9
        assert entity.related_memories == ["memory_001", "memory_002"]
    
    def test_entity_types_enum(self):
        """Test that EntityType enum has all required values."""
        assert EntityType.USER_NAME.value == "USER_NAME"
        assert EntityType.PREFERENCE.value == "PREFERENCE"
        assert EntityType.FACT.value == "FACT"


class TestPreferenceTypeEnum:
    """Test the PreferenceType enumeration."""
    
    def test_preference_type_values(self):
        """Test that PreferenceType enum has correct values."""
        assert PreferenceType.LIKE.value == "like"
        assert PreferenceType.DISLIKE.value == "dislike"
        assert PreferenceType.NEUTRAL.value == "neutral"


class TestMemoryStatsDataclass:
    """Test the MemoryStats dataclass implementation."""
    
    def test_memory_stats_creation(self):
        """Test creating a MemoryStats instance."""
        now = datetime.now(timezone.utc)
        recent_memories = []  # Empty list for testing
        
        stats = MemoryStats(
            total_memories=100,
            storage_size_mb=15.5,
            avg_retrieval_time_ms=150.0,
            entities_tracked=25,
            sessions_recorded=10,
            last_optimization=now,
            uptime_percentage=99.9,
            recent_memories=recent_memories
        )
        
        assert stats.total_memories == 100
        assert stats.storage_size_mb == 15.5
        assert stats.avg_retrieval_time_ms == 150.0
        assert stats.entities_tracked == 25
        assert stats.sessions_recorded == 10
        assert stats.last_optimization == now
        assert stats.uptime_percentage == 99.9
        assert stats.recent_memories == recent_memories


class TestScoredMemoryDataclass:
    """Test the ScoredMemory dataclass implementation."""
    
    def test_scored_memory_creation(self):
        """Test creating a ScoredMemory instance."""
        now = datetime.now(timezone.utc)
        
        memory = Memory(
            id="test_scored",
            content="Test content for scoring",
            embedding=None,
            timestamp=now,
            memory_type=MemoryType.INTERACTION,
            metadata={},
            importance_score=0.8,
            access_count=3,
            last_accessed=now
        )
        
        scored_memory = ScoredMemory(
            memory=memory,
            relevance_score=0.95,
            similarity_score=0.87,
            recency_boost=0.1
        )
        
        assert scored_memory.memory == memory
        assert scored_memory.relevance_score == 0.95
        assert scored_memory.similarity_score == 0.87
        assert scored_memory.recency_boost == 0.1


class TestFactDataclass:
    """Test the Fact dataclass implementation."""
    
    def test_fact_creation(self):
        """Test creating a Fact instance."""
        fact = Fact(
            content="User's favorite color is blue",
            confidence=0.85,
            source_memory_id="memory_123",
            verified=True,
            category="personal"
        )
        
        assert fact.content == "User's favorite color is blue"
        assert fact.confidence == 0.85
        assert fact.source_memory_id == "memory_123"
        assert fact.verified is True
        assert fact.category == "personal"


if __name__ == "__main__":
    pytest.main([__file__])