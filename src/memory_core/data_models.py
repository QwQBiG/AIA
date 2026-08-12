"""
Data models for the Memory Core RAG system.

This module defines the core data structures used throughout the memory system,
including Memory, Entity, MemoryStats, and related types.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import numpy as np


class MemoryType(Enum):
    """Types of memories that can be stored."""
    INTERACTION = "INTERACTION"
    EVENT = "EVENT"
    SUMMARY = "SUMMARY"


class EntityType(Enum):
    """Types of entities that can be tracked."""
    USER_NAME = "USER_NAME"
    PREFERENCE = "PREFERENCE"
    FACT = "FACT"


class PreferenceType(Enum):
    """User preference categorization."""
    LIKE = "like"
    DISLIKE = "dislike"
    NEUTRAL = "neutral"


@dataclass
class Memory:
    """Core data structure for stored memories."""
    id: str
    content: str
    embedding: Optional[np.ndarray]
    timestamp: datetime
    memory_type: MemoryType
    metadata: Dict[str, Any]
    importance_score: float
    access_count: int
    last_accessed: datetime


@dataclass
class Entity:
    """Represents tracked entities and user preferences."""
    name: str
    entity_type: EntityType
    value: str
    confidence: float
    first_mentioned: datetime
    last_updated: datetime
    related_memories: List[str]  # Memory IDs


@dataclass
class Fact:
    """Structure for storing factual information about users."""
    content: str
    confidence: float
    source_memory_id: str
    verified: bool
    category: str  # e.g., "personal", "professional", "hobby"


@dataclass
class MemoryStats:
    """System statistics for monitoring and user interface."""
    total_memories: int
    storage_size_mb: float
    avg_retrieval_time_ms: float
    entities_tracked: int
    sessions_recorded: int
    last_optimization: Optional[datetime]
    uptime_percentage: float
    recent_memories: List[Memory]  # For UI display
    avg_storage_time_ms: float = 0.0  # Average storage operation time
    last_backup: Optional[datetime] = None  # Last backup timestamp
    backup_count: int = 0  # Total number of backups created
    last_integrity_check: Optional[datetime] = None  # Last integrity check
    integrity_issues: List[str] = None  # Current integrity issues
    
    def __post_init__(self):
        if self.integrity_issues is None:
            self.integrity_issues = []


@dataclass
class ScoredMemory:
    """Memory with relevance score for ranking."""
    memory: Memory
    relevance_score: float
    similarity_score: float
    recency_boost: float


@dataclass
class OptimizationResult:
    """Result of database optimization operations."""
    memories_archived: int
    memories_deleted: int
    storage_freed_mb: float
    optimization_time_ms: float
    success: bool
    message: str


@dataclass
class Summary:
    """Session summary data structure."""
    session_id: str
    start_time: datetime
    end_time: datetime
    summary_text: str
    key_entities: List[str]
    memory_count: int
    importance_score: float