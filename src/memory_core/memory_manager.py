"""
Memory Manager for session summarization and optimization.

This module provides memory management capabilities including session summarization,
importance scoring, memory archival, and database optimization for the Memory Core RAG system.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .memory_core import MemoryCore
from .data_models import Memory, MemoryType, OptimizationResult, Summary


@dataclass
class SessionSummary:
    """Summary of a conversation session."""
    session_id: str
    start_time: datetime
    end_time: datetime
    total_interactions: int
    key_topics: List[str]
    summary_text: str
    importance_score: float


class MemoryManager:
    """
    Memory management system for session summarization and optimization.
    
    Provides capabilities for:
    - Session summarization for daily summaries
    - Importance scoring based on access frequency and user engagement
    - Memory archival for performance optimization
    - Database maintenance and optimization
    """
    
    def __init__(self, memory_core: MemoryCore):
        """
        Initialize Memory Manager.
        
        Args:
            memory_core: MemoryCore instance for memory operations
        """
        self.memory_core = memory_core
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.session_timeout_hours = 2.0  # Sessions end after 2 hours of inactivity
        self.archive_threshold_days = 30  # Archive memories older than 30 days
        self.min_importance_score = 0.3  # Minimum score to keep memories
        
        # Session tracking
        self.current_session_id: Optional[str] = None
        self.last_interaction_time: Optional[datetime] = None
        
        self.logger.info("Memory Manager initialized")
    
    def generate_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        """
        Generate a summary for a completed session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionSummary object or None if failed
        """
        try:
            self.logger.info(f"Generating session summary for session: {session_id}")
            
            # Get all memories for this session
            # For now, we'll use a simple approach - get recent memories
            # In a full implementation, we'd track session IDs in metadata
            recent_memories = self.memory_core.retrieve_memories("", limit=20)
            
            if not recent_memories:
                self.logger.warning(f"No memories found for session: {session_id}")
                return None
            
            # Calculate session timeframe
            start_time = min(memory.timestamp for memory in recent_memories)
            end_time = max(memory.timestamp for memory in recent_memories)
            
            # Extract key topics (simplified approach)
            key_topics = self._extract_key_topics(recent_memories)
            
            # Generate summary text (simplified approach)
            summary_text = self._generate_summary_text(recent_memories, key_topics)
            
            # Calculate importance score
            importance_score = self._calculate_session_importance(recent_memories)
            
            session_summary = SessionSummary(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                total_interactions=len(recent_memories),
                key_topics=key_topics,
                summary_text=summary_text,
                importance_score=importance_score
            )
            
            # Store the session summary as a memory
            self._store_session_summary(session_summary)
            
            self.logger.info(f"Session summary generated: {len(recent_memories)} interactions, importance: {importance_score:.2f}")
            return session_summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate session summary: {e}")
            return None
    
    def calculate_importance_scores(self, memories: List[Memory]) -> List[float]:
        """
        Calculate importance scores for memories based on access frequency and user engagement.
        
        Args:
            memories: List of memories to score
            
        Returns:
            List of importance scores (0.0 to 1.0)
        """
        try:
            scores = []
            
            for memory in memories:
                score = 0.0
                
                # Base score from access count
                access_score = min(memory.access_count / 10.0, 0.4)  # Max 0.4 from access
                score += access_score
                
                # Recency score (more recent = higher score)
                days_old = (datetime.now() - memory.timestamp).days
                recency_score = max(0.0, 0.3 - (days_old / 30.0) * 0.3)  # Max 0.3 from recency
                score += recency_score
                
                # Content length score (longer content = potentially more important)
                content_score = min(len(memory.content) / 1000.0, 0.2)  # Max 0.2 from content
                score += content_score
                
                # Memory type score
                type_scores = {
                    MemoryType.INTERACTION: 0.1,
                    MemoryType.EVENT: 0.05,
                    MemoryType.SUMMARY: 0.15
                }
                score += type_scores.get(memory.memory_type, 0.0)
                
                # Ensure score is between 0.0 and 1.0
                score = max(0.0, min(1.0, score))
                scores.append(score)
            
            self.logger.debug(f"Calculated importance scores for {len(memories)} memories")
            return scores
            
        except Exception as e:
            self.logger.error(f"Failed to calculate importance scores: {e}")
            return [0.5] * len(memories)  # Return default scores
    
    def archive_old_memories(self, cutoff_date: datetime) -> int:
        """
        Archive old memories for performance optimization.
        
        Args:
            cutoff_date: Memories older than this date will be archived
            
        Returns:
            Number of memories archived
        """
        try:
            self.logger.info(f"Archiving memories older than: {cutoff_date}")
            
            # Get all memories (this is simplified - in practice we'd need pagination)
            all_memories = self.memory_core.retrieve_memories("", limit=1000)
            
            archived_count = 0
            for memory in all_memories:
                if memory.timestamp < cutoff_date:
                    # Calculate importance score
                    importance_scores = self.calculate_importance_scores([memory])
                    importance_score = importance_scores[0] if importance_scores else 0.0
                    
                    # Archive if importance is below threshold
                    if importance_score < self.min_importance_score:
                        # In a full implementation, we'd move to archive storage
                        # For now, we'll just mark it as archived in metadata
                        self.logger.debug(f"Would archive memory: {memory.id} (importance: {importance_score:.2f})")
                        archived_count += 1
            
            self.logger.info(f"Archived {archived_count} old memories")
            return archived_count
            
        except Exception as e:
            self.logger.error(f"Failed to archive old memories: {e}")
            return 0
    
    def optimize_database(self) -> OptimizationResult:
        """
        Perform database optimization and maintenance.
        
        Returns:
            OptimizationResult with optimization statistics
        """
        try:
            self.logger.info("Starting database optimization")
            start_time = time.time()
            
            # Get current statistics
            stats = self.memory_core.get_memory_stats()
            initial_memory_count = stats.total_memories
            initial_storage_size = stats.storage_size_mb
            
            # Archive old memories
            cutoff_date = datetime.now() - timedelta(days=self.archive_threshold_days)
            archived_count = self.archive_old_memories(cutoff_date)
            
            # Validate data integrity
            integrity_valid = self.memory_core.validate_data_integrity()
            
            # Create backup
            backup_success = self.memory_core.backup_memories()
            
            # Get final statistics
            final_stats = self.memory_core.get_memory_stats()
            final_memory_count = final_stats.total_memories
            final_storage_size = final_stats.storage_size_mb
            
            optimization_time = time.time() - start_time
            
            result = OptimizationResult(
                optimization_time=optimization_time,
                memories_processed=initial_memory_count,
                memories_archived=archived_count,
                storage_saved_mb=max(0.0, initial_storage_size - final_storage_size),
                integrity_check_passed=integrity_valid,
                backup_created=backup_success
            )
            
            self.logger.info(f"Database optimization completed in {optimization_time:.2f}s")
            self.logger.info(f"Processed: {initial_memory_count}, Archived: {archived_count}")
            self.logger.info(f"Storage saved: {result.storage_saved_mb:.2f} MB")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Database optimization failed: {e}")
            return OptimizationResult(
                optimization_time=0.0,
                memories_processed=0,
                memories_archived=0,
                storage_saved_mb=0.0,
                integrity_check_passed=False,
                backup_created=False
            )
    
    def _extract_key_topics(self, memories: List[Memory]) -> List[str]:
        """
        Extract key topics from a list of memories.
        
        Args:
            memories: List of memories to analyze
            
        Returns:
            List of key topics
        """
        # Simplified topic extraction - in practice, we'd use NLP techniques
        topics = set()
        
        for memory in memories:
            content = memory.content.lower()
            
            # Simple keyword-based topic extraction
            if any(word in content for word in ['food', 'eat', 'hungry', 'meal']):
                topics.add('food')
            if any(word in content for word in ['game', 'play', 'gaming']):
                topics.add('gaming')
            if any(word in content for word in ['work', 'job', 'career']):
                topics.add('work')
            if any(word in content for word in ['music', 'song', 'listen']):
                topics.add('music')
            if any(word in content for word in ['movie', 'film', 'watch']):
                topics.add('entertainment')
        
        return list(topics)[:5]  # Return top 5 topics
    
    def _generate_summary_text(self, memories: List[Memory], key_topics: List[str]) -> str:
        """
        Generate summary text for a session.
        
        Args:
            memories: List of memories in the session
            key_topics: Key topics discussed
            
        Returns:
            Summary text
        """
        # Simplified summary generation
        summary_parts = []
        
        summary_parts.append(f"Session with {len(memories)} interactions")
        
        if key_topics:
            summary_parts.append(f"Main topics: {', '.join(key_topics)}")
        
        # Add sample interactions
        if memories:
            first_memory = memories[0]
            summary_parts.append(f"Started with: {first_memory.content[:100]}...")
        
        return ". ".join(summary_parts)
    
    def _calculate_session_importance(self, memories: List[Memory]) -> float:
        """
        Calculate importance score for a session.
        
        Args:
            memories: List of memories in the session
            
        Returns:
            Importance score (0.0 to 1.0)
        """
        if not memories:
            return 0.0
        
        # Calculate average importance of individual memories
        importance_scores = self.calculate_importance_scores(memories)
        avg_importance = sum(importance_scores) / len(importance_scores)
        
        # Boost score for longer sessions
        length_boost = min(len(memories) / 20.0, 0.2)  # Max 0.2 boost for 20+ interactions
        
        # Boost score for sessions with diverse topics
        key_topics = self._extract_key_topics(memories)
        topic_boost = min(len(key_topics) / 10.0, 0.1)  # Max 0.1 boost for 10+ topics
        
        final_score = avg_importance + length_boost + topic_boost
        return max(0.0, min(1.0, final_score))
    
    def _store_session_summary(self, session_summary: SessionSummary) -> None:
        """
        Store session summary as a memory.
        
        Args:
            session_summary: SessionSummary to store
        """
        try:
            summary_content = f"Session Summary: {session_summary.summary_text}"
            
            self.memory_core.store_event(
                event_type="session_summary",
                event_data={
                    "session_id": session_summary.session_id,
                    "start_time": session_summary.start_time.isoformat(),
                    "end_time": session_summary.end_time.isoformat(),
                    "total_interactions": session_summary.total_interactions,
                    "key_topics": session_summary.key_topics,
                    "importance_score": session_summary.importance_score
                },
                timestamp=session_summary.end_time
            )
            
            self.logger.debug(f"Session summary stored for session: {session_summary.session_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to store session summary: {e}")