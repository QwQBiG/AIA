"""
Memory Core RAG System

This module provides persistent memory capabilities for the AI VTuber application
using ChromaDB as the vector database backend with sentence-transformers for
semantic embeddings.
"""

from .memory_core import MemoryCore
from .entity_extractor import EntityExtractor
from .data_models import Memory, Entity, MemoryStats, PreferenceType, Fact

__all__ = [
    'MemoryCore',
    'EntityExtractor',
    'Memory',
    'Entity', 
    'MemoryStats',
    'PreferenceType',
    'Fact'
]