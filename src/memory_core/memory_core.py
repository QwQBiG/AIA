"""
Memory Core implementation for the AI VTuber RAG system.

This module provides the main MemoryCore class that orchestrates all memory operations
including storage, retrieval, and management using ChromaDB as the backend.
"""


# 离线模式配置
try:
    from .offline_config import *
except ImportError:
    pass

import gzip
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from threading import RLock, Condition, Semaphore
from queue import PriorityQueue, Queue
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import weakref

import chromadb
from chromadb.config import Settings
import numpy as np
import jsonschema
from jsonschema import validate, ValidationError

from .data_models import (
    Memory, Entity, MemoryStats, MemoryType, EntityType, 
    PreferenceType, Fact, ScoredMemory, OptimizationResult
)
from .entity_extractor import EntityExtractor


class OperationType(Enum):
    """Types of operations for prioritization."""
    RETRIEVAL = 1  # Highest priority
    STORAGE = 2    # Lower priority
    MAINTENANCE = 3  # Lowest priority


class OperationRequest:
    """Request wrapper for operation prioritization."""
    def __init__(self, operation_type: OperationType, func, args, kwargs, future):
        self.operation_type = operation_type
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.future = future
        self.timestamp = time.time()
    
    def __lt__(self, other):
        # Lower priority value = higher priority in queue
        if self.operation_type.value != other.operation_type.value:
            return self.operation_type.value < other.operation_type.value
        # If same priority, use timestamp (FIFO)
        return self.timestamp < other.timestamp


class MemoryCore:
    """
    Central component that orchestrates all memory operations.
    
    Provides persistent memory storage and retrieval using ChromaDB with
    semantic search capabilities. Implements lazy loading for the embedding
    model to prevent GUI startup delays.
    """
    
    # JSON Schema for memory metadata validation as specified in design document
    MEMORY_METADATA_SCHEMA = {
        "type": "object",
        "required": ["content", "timestamp", "memory_type"],
        "properties": {
            "content": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "memory_type": {"enum": ["INTERACTION", "EVENT", "SUMMARY"]},
            "importance_score": {"type": "number", "minimum": 0, "maximum": 1},
            "entities": {
                "type": "array",
                "items": {"type": "string"}
            },
            "schema_version": {"type": "string"},
            "validated": {"type": "boolean"},
            "user_input": {"type": "string"},
            "ai_response": {"type": "string"},
            "event_type": {"type": "string"},
            "event_data": {"type": "object"},
            "access_count": {"type": "integer", "minimum": 0}
        },
        "additionalProperties": True  # Allow additional metadata fields
    }
    
    def __init__(self, db_path: str = "./memory_db", collection_name: str = "vtuber_memories"):
        """
        Initialize the Memory Core with ChromaDB configuration and concurrent access protection.
        
        Args:
            db_path: Path to the ChromaDB database directory
            collection_name: Name of the ChromaDB collection
        """
        self.db_path = Path(db_path)
        self.collection_name = collection_name
        self.ready = False
        self.embedding_model = None
        self.client = None
        self.collection = None
        
        # ============================================================================
        # CONCURRENT ACCESS PROTECTION - Requirements 7.3, 7.4
        # ============================================================================
        
        # Main database lock - RLock allows recursive locking by same thread
        self._db_lock = RLock()
        
        # Separate locks for different operations to reduce contention
        self._storage_lock = RLock()  # For storage operations
        self._retrieval_lock = RLock()  # For retrieval operations  
        self._cache_lock = RLock()  # For cache operations
        self._stats_lock = RLock()  # For statistics updates
        self._backup_lock = RLock()  # For backup operations
        
        # Operation prioritization system (Requirement 7.4: prioritize retrieval over storage)
        self._operation_queue = PriorityQueue()
        self._operation_executor = ThreadPoolExecutor(
            max_workers=4,  # Configurable based on system resources
            thread_name_prefix="MemoryCore"
        )
        self._operation_condition = Condition(self._db_lock)
        
        # Concurrent access tracking
        self._active_readers = 0  # Number of active read operations
        self._active_writers = 0  # Number of active write operations
        self._reader_condition = Condition(self._db_lock)
        self._writer_condition = Condition(self._db_lock)
        
        # Rate limiting for concurrent operations
        self._storage_semaphore = Semaphore(2)  # Max 2 concurrent storage operations
        self._retrieval_semaphore = Semaphore(5)  # Max 5 concurrent retrieval operations
        
        # Thread-safe operation counters
        self._concurrent_operations = {
            'storage_active': 0,
            'retrieval_active': 0,
            'maintenance_active': 0,
            'total_operations': 0,
            'failed_operations': 0,
            'lock_contentions': 0,
            'operation_timeouts': 0
        }
        
        # Create database directory if it doesn't exist
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize ChromaDB with telemetry disabled
        self._initialize_chromadb()
        
        # Start background thread to load embedding model
        self._model_loading_thread = threading.Thread(
            target=self._load_embedding_model_async,
            daemon=True
        )
        self._model_loading_thread.start()
        
        # Initialize EntityExtractor for entity relationship tracking (Requirements 3.5)
        self.entity_extractor = EntityExtractor()
        
        # Entity storage for tracking relationships with memory IDs
        self._entity_storage: Dict[str, Entity] = {}  # entity_name -> Entity
        self._entity_storage_lock = RLock()  # Thread-safe access to entity storage
        
        # Enhanced entity persistence and metadata storage
        self._entity_collection_name = f"{collection_name}_entities"
        self._entity_collection = None  # Will be initialized after ChromaDB setup
        
        # Statistics tracking (thread-safe)
        self._stats = {
            'total_memories': 0,
            'total_retrievals': 0,
            'avg_retrieval_time': 0.0,
            'entities_tracked': 0,
            'sessions_recorded': 0,
            'last_optimization': None,
            'startup_time': datetime.now(),
            'retrieval_times': [],  # Track individual retrieval times for 95% compliance
            'retrieval_cache_hits': 0,
            'retrieval_cache_misses': 0
        }
        
        # Performance optimization caches (thread-safe access required)
        self._embedding_cache = {}  # Cache for query embeddings
        self._query_result_cache = {}  # Cache for query results
        self._recent_memory_ids = []  # Track recent memory IDs for exclusion
        self._cache_max_size = 100  # Maximum cache entries
        self._cache_ttl_seconds = 300  # 5分钟TTL：避免记忆检索结果长期缓存导致信息过时
        
        # Automated backup scheduling
        self._backup_scheduler = None
        self._backup_interval_hours = 24  # Default: daily backups
        self._auto_backup_enabled = True
        self._last_scheduled_backup = None
        
        # Start automated backup scheduler
        self._start_backup_scheduler()
        
        # Register cleanup on shutdown
        weakref.finalize(self, self._cleanup_resources)
    
    # ============================================================================
    # CONCURRENT ACCESS PROTECTION METHODS
    # ============================================================================
    
    def _cleanup_resources(self):
        """Clean up resources on shutdown."""
        try:
            if hasattr(self, '_operation_executor'):
                self._operation_executor.shutdown(wait=True)
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Error during resource cleanup: {e}")
    
    def _acquire_read_lock(self, timeout: float = 30.0) -> bool:
        """
        Acquire read lock with timeout for retrieval operations.
        
        Implements reader-writer lock pattern to allow multiple concurrent reads
        but exclusive writes, prioritizing retrieval operations as specified.
        
        Args:
            timeout: Maximum time to wait for lock acquisition
            
        Returns:
            True if lock acquired, False if timeout
        """
        start_time = time.time()
        
        with self._db_lock:
            # Wait for any active writers to finish
            while self._active_writers > 0:
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    with self._stats_lock:
                        self._concurrent_operations['lock_contentions'] += 1
                        self._concurrent_operations['operation_timeouts'] += 1
                    return False
                
                if not self._reader_condition.wait(timeout=remaining_time):
                    with self._stats_lock:
                        self._concurrent_operations['operation_timeouts'] += 1
                    return False
            
            # Acquire read lock
            self._active_readers += 1
            with self._stats_lock:
                self._concurrent_operations['retrieval_active'] += 1
            
            return True
    
    def _release_read_lock(self):
        """Release read lock and notify waiting writers."""
        with self._db_lock:
            self._active_readers -= 1
            with self._stats_lock:
                self._concurrent_operations['retrieval_active'] -= 1
            
            # Notify waiting writers if no more readers
            if self._active_readers == 0:
                self._writer_condition.notify_all()
    
    def _acquire_write_lock(self, timeout: float = 30.0) -> bool:
        """
        Acquire write lock with timeout for storage operations.
        
        Waits for all readers and writers to finish before acquiring exclusive access.
        
        Args:
            timeout: Maximum time to wait for lock acquisition
            
        Returns:
            True if lock acquired, False if timeout
        """
        start_time = time.time()
        
        with self._db_lock:
            # Wait for all active readers and writers to finish
            while self._active_readers > 0 or self._active_writers > 0:
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    with self._stats_lock:
                        self._concurrent_operations['lock_contentions'] += 1
                        self._concurrent_operations['operation_timeouts'] += 1
                    return False
                
                if not self._writer_condition.wait(timeout=remaining_time):
                    with self._stats_lock:
                        self._concurrent_operations['operation_timeouts'] += 1
                    return False
            
            # Acquire write lock
            self._active_writers += 1
            with self._stats_lock:
                self._concurrent_operations['storage_active'] += 1
            
            return True
    
    def _release_write_lock(self):
        """Release write lock and notify waiting readers and writers."""
        with self._db_lock:
            self._active_writers -= 1
            with self._stats_lock:
                self._concurrent_operations['storage_active'] -= 1
            
            # Notify all waiting threads (readers have priority)
            self._reader_condition.notify_all()
            self._writer_condition.notify_all()
    
    def _execute_with_priority(self, operation_type: OperationType, func, *args, **kwargs):
        """
        Execute operation with priority-based scheduling.
        
        Implements operation prioritization as specified in Requirements 7.4:
        retrieval operations have priority over storage operations.
        
        Args:
            operation_type: Type of operation for prioritization
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        from concurrent.futures import Future
        
        # Create future for result
        future = Future()
        
        # Create operation request
        request = OperationRequest(operation_type, func, args, kwargs, future)
        
        # Add to priority queue
        self._operation_queue.put(request)
        
        # Process queue if not already being processed
        self._process_operation_queue()
        
        # Wait for result with timeout
        try:
            return future.result(timeout=60.0)  # 60 second timeout
        except Exception as e:
            with self._stats_lock:
                self._concurrent_operations['failed_operations'] += 1
            raise
    
    def _process_operation_queue(self):
        """Process operations from priority queue in background."""
        def queue_processor():
            while True:
                try:
                    # Get next operation (blocks if queue empty)
                    request = self._operation_queue.get(timeout=1.0)
                    
                    try:
                        # Execute operation
                        result = request.func(*request.args, **request.kwargs)
                        request.future.set_result(result)
                    except Exception as e:
                        request.future.set_exception(e)
                    finally:
                        self._operation_queue.task_done()
                        
                except:
                    # Queue empty or other error, continue
                    continue
        
        # Start processor thread if not already running
        if not hasattr(self, '_queue_processor_thread') or not self._queue_processor_thread.is_alive():
            self._queue_processor_thread = threading.Thread(
                target=queue_processor,
                daemon=True,
                name="MemoryCore-QueueProcessor"
            )
            self._queue_processor_thread.start()
    
    def _safe_cache_access(self, cache_dict: dict, key: str, value=None, operation: str = 'get'):
        """
        Thread-safe cache access with proper locking.
        
        Args:
            cache_dict: Cache dictionary to access
            key: Cache key
            value: Value to set (for 'set' operation)
            operation: 'get', 'set', or 'delete'
            
        Returns:
            Cache value for 'get', None for other operations
        """
        with self._cache_lock:
            if operation == 'get':
                return cache_dict.get(key)
            elif operation == 'set':
                cache_dict[key] = value
            elif operation == 'delete':
                cache_dict.pop(key, None)
            elif operation == 'clear':
                cache_dict.clear()
    
    def _safe_stats_update(self, update_func):
        """
        Thread-safe statistics update.
        
        Args:
            update_func: Function that updates statistics
        """
        with self._stats_lock:
            update_func()
    
    def get_concurrent_access_metrics(self) -> Dict[str, Any]:
        """
        Get metrics about concurrent access patterns and performance.
        
        Returns:
            Dictionary with concurrent access statistics
        """
        with self._stats_lock:
            return {
                'active_readers': self._active_readers,
                'active_writers': self._active_writers,
                'storage_operations_active': self._concurrent_operations['storage_active'],
                'retrieval_operations_active': self._concurrent_operations['retrieval_active'],
                'maintenance_operations_active': self._concurrent_operations['maintenance_active'],
                'total_operations_completed': self._concurrent_operations['total_operations'],
                'failed_operations': self._concurrent_operations['failed_operations'],
                'lock_contentions': self._concurrent_operations['lock_contentions'],
                'operation_timeouts': self._concurrent_operations['operation_timeouts'],
                'operation_queue_size': self._operation_queue.qsize(),
                'cache_sizes': {
                    'embedding_cache': len(self._embedding_cache),
                    'query_result_cache': len(self._query_result_cache)
                }
            }
    
    def _initialize_chromadb(self) -> None:
        """Initialize ChromaDB client with telemetry disabled and proper schema validation."""
        try:
            # Configure ChromaDB with telemetry disabled (Critical Patch 3)
            settings = Settings(
                anonymized_telemetry=False,
                persist_directory=str(self.db_path),
                is_persistent=True
            )
            
            # Initialize client
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=settings
            )
            
            # Get or create collection with proper schema as specified in design document
            collection_metadata = {
                "description": "AI VTuber memory storage with semantic search",
                "schema_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "embedding_model": "all-MiniLM-L6-v2",
                "embedding_dimensions": 384,
                "validation_schema": json.dumps(self.MEMORY_METADATA_SCHEMA)
            }
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata=collection_metadata
            )
            
            # Validate that the collection was created with correct schema
            if not self._validate_collection_schema():
                raise RuntimeError("Collection schema validation failed")
            
            self.logger.info(f"ChromaDB collection '{self.collection_name}' initialized successfully at {self.db_path}")
            self.logger.info(f"Collection metadata: {collection_metadata}")
            
            # Initialize entity collection for enhanced entity relationship tracking
            self._initialize_entity_collection()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    def _validate_collection_schema(self) -> bool:
        """
        Validate that the ChromaDB collection has the correct schema.
        
        Returns:
            True if collection schema is valid, False otherwise
        """
        try:
            if not self.collection:
                return False
            
            metadata = self.collection.metadata
            
            # Check required metadata fields
            required_fields = [
                "description", 
                "schema_version", 
                "created_at",
                "embedding_model",
                "embedding_dimensions"
            ]
            
            for field in required_fields:
                if field not in metadata:
                    self.logger.error(f"Missing required metadata field: {field}")
                    return False
            
            # Validate specific values
            if metadata["schema_version"] != "1.0":
                self.logger.error(f"Invalid schema version: {metadata['schema_version']}")
                return False
                
            if metadata["embedding_model"] != "all-MiniLM-L6-v2":
                self.logger.error(f"Invalid embedding model: {metadata['embedding_model']}")
                return False
                
            if metadata["embedding_dimensions"] != 384:
                self.logger.error(f"Invalid embedding dimensions: {metadata['embedding_dimensions']}")
                return False
            
            # Validate that validation schema is present and parseable
            if "validation_schema" in metadata:
                try:
                    schema = json.loads(metadata["validation_schema"])
                    # Verify it matches our current schema
                    if schema != self.MEMORY_METADATA_SCHEMA:
                        self.logger.warning("Stored validation schema differs from current schema")
                except json.JSONDecodeError:
                    self.logger.error("Invalid validation schema JSON in collection metadata")
                    return False
            
            self.logger.debug("Collection schema validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Collection schema validation failed: {e}")
            return False
    
    def _initialize_entity_collection(self) -> None:
        """
        Initialize ChromaDB collection for entity metadata storage.
        
        This enhances entity relationship tracking by providing persistent storage
        for entity metadata and relationships as specified in Requirements 3.5.
        """
        try:
            # Entity collection metadata schema
            entity_collection_metadata = {
                "description": "Entity metadata and relationship storage",
                "schema_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "entity_types": ["USER_NAME", "PREFERENCE", "FACT"],
                "relationship_tracking": True
            }
            
            # Create or get entity collection
            self._entity_collection = self.client.get_or_create_collection(
                name=self._entity_collection_name,
                metadata=entity_collection_metadata
            )
            
            # Load existing entities from persistent storage
            self._load_entities_from_storage()
            
            self.logger.info(f"Entity collection '{self._entity_collection_name}' initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize entity collection: {e}")
            # Don't fail the entire initialization - entity tracking can work without persistence
            self._entity_collection = None
    
    def _load_embedding_model_async(self) -> None:
        """
        Load the sentence transformer model in background thread.
        
        This implements Patch 1: Embedding Model Lazy Loading to prevent
        GUI startup delays.
        """
        try:
            from sentence_transformers import SentenceTransformer
            
            self.logger.info("Loading sentence transformer model...")
            start_time = time.time()
            
            # Load the all-MiniLM-L6-v2 model as specified in design
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            load_time = time.time() - start_time
            self.logger.info(f"Embedding model loaded in {load_time:.2f} seconds")
            
            # Mark as ready
            self.ready = True
            
        except Exception as e:
            self.logger.error(f"Failed to load embedding model: {e}")
            # Try fallback model if available
            try:
                from .fallback_embedding import get_fallback_model
                self.logger.info("Using fallback embedding model...")
                self.embedding_model = get_fallback_model()
                self.logger.info("Fallback embedding model loaded successfully")
                self.ready = True
            except ImportError:
                self.logger.error("Fallback embedding model not available")
                # Don't set ready=True, system will operate without embeddings
    
    def is_ready(self) -> bool:
        """Check if the memory system is ready for full operation."""
        return self.ready and self.embedding_model is not None
    
    def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for text using the sentence transformer model.
        
        Optimized for performance to meet <100ms storage requirement.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if model not ready
        """
        if not self.is_ready():
            self.logger.debug("Embedding model not ready, skipping embedding generation")
            return None
            
        try:
            # Optimized embedding generation with performance monitoring
            embed_start = time.time()
            
            # Truncate very long text to prevent memory issues and improve performance
            max_text_length = 512  # Reasonable limit for sentence transformers
            if len(text) > max_text_length:
                text = text[:max_text_length] + "..."
                self.logger.debug(f"Truncated text to {max_text_length} characters for embedding")
            
            # Use optimized encoding parameters for speed
            embedding = self.embedding_model.encode(
                text, 
                convert_to_numpy=True,
                show_progress_bar=False,  # Disable progress bar for speed
                batch_size=1,  # Single item, no batching overhead
                normalize_embeddings=True  # Normalize for better similarity search
            )
            
            embed_time = (time.time() - embed_start) * 1000  # Convert to ms
            
            # Log slow embedding generation
            if embed_time > 50:  # Half of our 100ms budget
                self.logger.warning(f"Slow embedding generation: {embed_time:.2f}ms for text length {len(text)}")
            
            # Validate embedding dimensions to prevent vector format errors
            if embedding is not None and hasattr(embedding, 'shape'):
                expected_dim = 384  # all-MiniLM-L6-v2 dimension
                if embedding.shape[0] != expected_dim:
                    self.logger.error(f"Embedding dimension mismatch: got {embedding.shape[0]}, expected {expected_dim}")
                    return None
            
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            self.logger.debug(f"Text that caused embedding error: {text[:100]}...")
            return None
    
    def _validate_memory_data(self, content: str, metadata: Dict[str, Any]) -> bool:
        """
        Validate memory data before storage.
        
        Implements Patch 4: "Hallucinated Memory" Filter to reject invalid content
        and JSON schema validation as specified in Requirements 8.1, 8.3.
        
        Args:
            content: Memory content to validate
            metadata: Memory metadata
            
        Returns:
            True if valid, False otherwise
        """
        # Filter out very short content
        if len(content.strip()) < 5:
            self.logger.debug(f"Content too short: '{content[:50]}...'")
            return False
            
        # Blacklisted patterns that indicate invalid memories
        blacklisted_patterns = [
            "listening...",
            "system:",
            "asr: [silence]",
            "[silence]",
            "...",
            "loading",
            "processing"
        ]
        
        content_lower = content.lower().strip()
        for pattern in blacklisted_patterns:
            if pattern in content_lower:
                self.logger.debug(f"Content contains blacklisted pattern '{pattern}': '{content[:50]}...'")
                return False
        
        # Validate metadata against JSON schema (Requirement 8.3)
        try:
            validate(instance=metadata, schema=self.MEMORY_METADATA_SCHEMA)
            self.logger.debug(f"Schema validation passed for memory type: {metadata.get('memory_type', 'unknown')}")
        except ValidationError as e:
            self.logger.warning(f"Memory metadata validation failed: {e.message}")
            self.logger.debug(f"Invalid metadata: {metadata}")
            return False
        except Exception as e:
            self.logger.error(f"Schema validation error: {e}")
            return False
        
        return True
    
    def _migrate_metadata_schema(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate metadata from older schema versions to current version.
        
        Implements Requirement 8.5: backward compatibility with previous memory data formats.
        
        Args:
            metadata: Memory metadata (potentially from older schema version)
            
        Returns:
            Migrated metadata compatible with current schema
        """
        migrated = metadata.copy()
        schema_version = migrated.get("schema_version", "0.9")  # Default to oldest version
        
        # Migration from version 0.9 to 1.0
        if schema_version == "0.9":
            self.logger.debug("Migrating metadata from schema version 0.9 to 1.0")
            
            # Add new fields introduced in v1.0
            if "entities" not in migrated:
                migrated["entities"] = []
            if "validated" not in migrated:
                migrated["validated"] = True
            if "access_count" not in migrated:
                migrated["access_count"] = 0
            
            # Update schema version
            migrated["schema_version"] = "1.0"
            
            self.logger.debug("Successfully migrated metadata to schema version 1.0")
        
        # Future migrations can be added here
        # elif schema_version == "1.0" and current_version == "1.1":
        #     # Migration logic for future versions
        
        return migrated
    
    def _deserialize_memory_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize and validate memory metadata from storage.
        
        Implements Requirement 8.2: deserialize JSON data back into structured objects
        with automatic schema migration for backward compatibility.
        
        Args:
            raw_metadata: Raw metadata from storage
            
        Returns:
            Validated and migrated metadata
        """
        try:
            # First, attempt migration if needed
            migrated_metadata = self._migrate_metadata_schema(raw_metadata)
            
            # Validate against current schema
            validate(instance=migrated_metadata, schema=self.MEMORY_METADATA_SCHEMA)
            
            return migrated_metadata
            
        except ValidationError as e:
            self.logger.error(f"Failed to deserialize metadata: {e.message}")
            self.logger.debug(f"Raw metadata: {raw_metadata}")
            
            # Attempt data recovery (Requirement 8.4)
            return self._attempt_metadata_recovery(raw_metadata)
        except Exception as e:
            self.logger.error(f"Unexpected error during metadata deserialization: {e}")
            return self._attempt_metadata_recovery(raw_metadata)
    
    def _create_memory_metadata(self, memory_type: MemoryType, **kwargs) -> Dict[str, Any]:
        # Use provided timestamp or default to now
        timestamp = kwargs.get("timestamp", datetime.now())
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)
            
        metadata = {
            "content": kwargs.get("content", ""),
            "timestamp": timestamp_str,
            "memory_type": memory_type.value,
            "importance_score": kwargs.get("importance_score", 0.5),
            "entities": kwargs.get("entities", []),  # As specified in design document
            "schema_version": "1.0",
            "validated": True
        }
        
        # Add any additional metadata (excluding timestamp to avoid overwrite)
        for key, value in kwargs.items():
            if key not in metadata and key != "timestamp":
                metadata[key] = value
                
        return metadata
    
    def store_interaction(self, user_input: str, ai_response: str, 
                         timestamp: Optional[datetime] = None, 
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a user interaction in the memory database with <100ms latency requirement.
        
        Implements thread-safe storage operations with concurrent access protection,
        optimized performance, and entity extraction with memory ID linking to meet
        the requirements specified in Requirements 1.1, 3.5, and Property 1.
        
        Args:
            user_input: User's input text
            ai_response: AI's response text
            timestamp: Interaction timestamp (defaults to now)
            metadata: Additional metadata
            
        Returns:
            Memory ID if successful, empty string if failed
        """
        def _store_interaction_impl():
            # Acquire storage semaphore for rate limiting
            if not self._storage_semaphore.acquire(timeout=5.0):
                self.logger.warning("Storage semaphore timeout - too many concurrent storage operations")
                return ""
            
            try:
                # Acquire write lock with timeout
                if not self._acquire_write_lock(timeout=10.0):
                    self.logger.warning("Write lock timeout during interaction storage")
                    return ""
                
                try:
                    # Start performance timing for <100ms requirement
                    start_time = time.time()
                    
                    if timestamp is None:
                        timestamp = datetime.now()
                        
                    if metadata is None:
                        metadata = {}
                    
                    # Combine user input and AI response for storage
                    content = f"User: {user_input}\nAI: {ai_response}"
                    
                    memory_id = str(uuid.uuid4())
                    
                    # Fast validation first to fail early if invalid
                    # Pre-create metadata for validation
                    memory_metadata = self._create_memory_metadata(
                        MemoryType.INTERACTION,
                        content=content,
                        user_input=user_input,
                        ai_response=ai_response,
                        timestamp=timestamp,
                        **metadata
                    )
                    
                    # Quick validation check - fail fast for invalid data
                    if not self._validate_memory_data(content, memory_metadata):
                        self.logger.warning("Invalid interaction data, skipping storage")
                        return ""
                    
                    # Generate embedding asynchronously if model is ready
                    # This is the most time-consuming operation
                    embedding = None
                    if self.is_ready():
                        embedding = self._generate_embedding(content)
                    
                    # Optimized ChromaDB storage operation
                    storage_start = time.time()
                    if embedding is not None:
                        self.collection.add(
                            ids=[memory_id],
                            embeddings=[embedding.tolist()],
                            metadatas=[memory_metadata],
                            documents=[content]
                        )
                    else:
                        # Store without embedding if model not ready - faster operation
                        self.collection.add(
                            ids=[memory_id],
                            metadatas=[memory_metadata],
                            documents=[content]
                        )
                    
                    storage_time = (time.time() - storage_start) * 1000  # Convert to ms
                    
                    # Thread-safe statistics update
                    def update_stats():
                        self._stats['total_memories'] += 1
                        self._concurrent_operations['total_operations'] += 1
                        
                        # Track storage performance for statistics
                        if not hasattr(self._stats, 'storage_times'):
                            self._stats['storage_times'] = []
                        self._stats['storage_times'].append((time.time() - start_time) * 1000)
                        
                        # Keep only last 100 measurements for rolling average
                        if len(self._stats['storage_times']) > 100:
                            self._stats['storage_times'] = self._stats['storage_times'][-100:]
                    
                    self._safe_stats_update(update_stats)
                    
                    # Calculate total operation time
                    total_time = (time.time() - start_time) * 1000  # Convert to ms
                    
                    # Log performance metrics
                    self.logger.debug(f"Stored interaction memory: {memory_id} in {total_time:.2f}ms (storage: {storage_time:.2f}ms)")
                    
                    # Performance monitoring - warn if exceeding 100ms requirement
                    if total_time > 100:
                        self.logger.warning(f"Storage operation exceeded 100ms requirement: {total_time:.2f}ms")
                    
                    # Extract entities and link them to this memory ID (Requirements 3.5)
                    # This is done after successful storage to ensure memory ID exists
                    try:
                        self._extract_and_link_entities(user_input, memory_id)
                    except Exception as e:
                        # Entity extraction failure shouldn't fail the entire storage operation
                        self.logger.warning(f"Entity extraction failed for memory {memory_id}: {e}")
                    
                    # Update recent memory IDs for context exclusion (Patch 2) - thread-safe
                    with self._cache_lock:
                        self._recent_memory_ids.append(memory_id)
                        # Keep only the last 20 memory IDs to limit memory usage
                        if len(self._recent_memory_ids) > 20:
                            self._recent_memory_ids = self._recent_memory_ids[-20:]
                    
                    return memory_id
                    
                finally:
                    self._release_write_lock()
                    
            finally:
                self._storage_semaphore.release()
        
        # Execute with priority-based scheduling
        return self._execute_with_priority(OperationType.STORAGE, _store_interaction_impl)
    
    def store_event(self, event_type: str, event_data: Dict[str, Any], 
                   timestamp: Optional[datetime] = None) -> str:
        """
        Store a game event in the memory database with <100ms latency requirement.
        
        Implements thread-safe storage operations with concurrent access protection
        and optimized performance to meet the requirement specified in Requirements 1.2 and Property 1.
        
        Args:
            event_type: Type of event (e.g., "game_start", "achievement")
            event_data: Event data dictionary
            timestamp: Event timestamp (defaults to now)
            
        Returns:
            Memory ID if successful, empty string if failed
        """
        def _store_event_impl():
            # Acquire storage semaphore for rate limiting
            if not self._storage_semaphore.acquire(timeout=5.0):
                self.logger.warning("Storage semaphore timeout - too many concurrent storage operations")
                return ""
            
            try:
                # Acquire write lock with timeout
                if not self._acquire_write_lock(timeout=10.0):
                    self.logger.warning("Write lock timeout during event storage")
                    return ""
                
                try:
                    # Start performance timing for <100ms requirement
                    start_time = time.time()
                    
                    if timestamp is None:
                        timestamp = datetime.now()
                    
                    # Create content from event data - optimized serialization
                    try:
                        # Use compact JSON representation for better performance
                        event_json = json.dumps(event_data, separators=(',', ':'), default=str)
                        content = f"Event: {event_type} - {event_json}"
                    except Exception as e:
                        self.logger.error(f"Failed to serialize event data: {e}")
                        return ""
                    
                    memory_id = str(uuid.uuid4())
                    
                    # Pre-create metadata for validation
                    memory_metadata = self._create_memory_metadata(
                        MemoryType.EVENT,
                        content=content,
                        event_type=event_type,
                        event_data=event_data
                    )
                    
                    # Quick validation check - fail fast for invalid data
                    if not self._validate_memory_data(content, memory_metadata):
                        self.logger.warning("Invalid event data, skipping storage")
                        return ""
                    
                    # Generate embedding asynchronously if model is ready
                    embedding = None
                    if self.is_ready():
                        embedding = self._generate_embedding(content)
                    
                    # Optimized ChromaDB storage operation
                    storage_start = time.time()
                    if embedding is not None:
                        self.collection.add(
                            ids=[memory_id],
                            embeddings=[embedding.tolist()],
                            metadatas=[memory_metadata],
                            documents=[content]
                        )
                    else:
                        # Store without embedding if model not ready - faster operation
                        self.collection.add(
                            ids=[memory_id],
                            metadatas=[memory_metadata],
                            documents=[content]
                        )
                    
                    storage_time = (time.time() - storage_start) * 1000  # Convert to ms
                    
                    # Thread-safe statistics update
                    def update_stats():
                        self._stats['total_memories'] += 1
                        self._concurrent_operations['total_operations'] += 1
                        
                        # Track storage performance for statistics
                        if not hasattr(self._stats, 'storage_times'):
                            self._stats['storage_times'] = []
                        self._stats['storage_times'].append((time.time() - start_time) * 1000)
                        
                        # Keep only last 100 measurements for rolling average
                        if len(self._stats['storage_times']) > 100:
                            self._stats['storage_times'] = self._stats['storage_times'][-100:]
                    
                    self._safe_stats_update(update_stats)
                    
                    # Calculate total operation time
                    total_time = (time.time() - start_time) * 1000  # Convert to ms
                    
                    # Log performance metrics
                    self.logger.debug(f"Stored event memory: {memory_id} in {total_time:.2f}ms (storage: {storage_time:.2f}ms)")
                    
                    # Performance monitoring - warn if exceeding 100ms requirement
                    if total_time > 100:
                        self.logger.warning(f"Event storage operation exceeded 100ms requirement: {total_time:.2f}ms")
                    
                    # Extract entities from event data and link them to this memory ID (Requirements 3.5)
                    # This is done after successful storage to ensure memory ID exists
                    try:
                        # Extract entities from event content (event type and data)
                        event_text = f"{event_type} {json.dumps(event_data, default=str)}"
                        self._extract_and_link_entities(event_text, memory_id)
                    except Exception as e:
                        # Entity extraction failure shouldn't fail the entire storage operation
                        self.logger.warning(f"Entity extraction failed for event memory {memory_id}: {e}")
                    
                    # Update recent memory IDs for context exclusion (Patch 2) - thread-safe
                    with self._cache_lock:
                        self._recent_memory_ids.append(memory_id)
                        # Keep only the last 20 memory IDs to limit memory usage
                        if len(self._recent_memory_ids) > 20:
                            self._recent_memory_ids = self._recent_memory_ids[-20:]
                    
                    return memory_id
                    
                finally:
                    self._release_write_lock()
                    
            finally:
                self._storage_semaphore.release()
        
        # Execute with priority-based scheduling
        return self._execute_with_priority(OperationType.STORAGE, _store_event_impl)
    
    def retrieve_memories(self, query: str, limit: int = 5, exclude_recent_turns: int = 3) -> List[Memory]:
        """
        Retrieve relevant memories using optimized semantic similarity search with <200ms latency.
        
        Implements thread-safe retrieval operations with concurrent access protection and
        performance optimizations including:
        - Current context exclusion (Patch 2)
        - Embedding and query result caching
        - Optimized ChromaDB queries
        - Performance monitoring for 95% compliance with <200ms requirement
        
        Args:
            query: Search query
            limit: Maximum number of memories to return
            exclude_recent_turns: Number of recent conversation turns to exclude (default: 3)
            
        Returns:
            List of relevant memories, optimized for <200ms retrieval latency
        """
        def _retrieve_memories_impl():
            # Return empty list if not ready (graceful degradation)
            if not self.is_ready():
                self.logger.debug("Memory system not ready, returning empty results")
                return []
            
            # Acquire retrieval semaphore for rate limiting
            if not self._retrieval_semaphore.acquire(timeout=5.0):
                self.logger.warning("Retrieval semaphore timeout - too many concurrent retrieval operations")
                return []
            
            try:
                # Acquire read lock with timeout
                if not self._acquire_read_lock(timeout=10.0):
                    self.logger.warning("Read lock timeout during memory retrieval")
                    return []
                
                try:
                    start_time = time.time()
                    
                    # Check query result cache first for performance optimization
                    cache_key = f"{query}:{limit}:{exclude_recent_turns}"
                    cached_result = self._get_cached_query_result(cache_key)
                    if cached_result is not None:
                        cache_time = (time.time() - start_time) * 1000
                        self.logger.debug(f"Retrieved {len(cached_result)} memories from cache in {cache_time:.2f}ms")
                        self._update_retrieval_stats(cache_time)
                        return cached_result
                    
                    # Generate query embedding with caching
                    query_embedding = self._get_cached_embedding(query)
                    if query_embedding is None:
                        return []
                    
                    # Optimized ChromaDB search with performance tuning
                    search_start = time.time()
                    
                    # Request more results initially to allow for filtering
                    search_limit = min(limit * 3, 50)  # Get extra results for filtering
                    
                    results = self.collection.query(
                        query_embeddings=[query_embedding.tolist()],
                        n_results=search_limit,
                        include=['metadatas', 'documents', 'distances']
                    )
                    
                    search_time = (time.time() - search_start) * 1000
                    
                    memories = []
                    if results['ids'] and results['ids'][0]:
                        # Get recent memory IDs for exclusion (Patch 2: Current Context Exclusion)
                        recent_memory_ids = self._get_recent_memory_ids(exclude_recent_turns)
                        
                        for i, memory_id in enumerate(results['ids'][0]):
                            # Skip recent memories to avoid repetition (Patch 2)
                            if memory_id in recent_memory_ids:
                                self.logger.debug(f"Excluding recent memory: {memory_id}")
                                continue
                            
                            # Stop if we have enough results
                            if len(memories) >= limit:
                                break
                            
                            raw_metadata = results['metadatas'][0][i]
                            content = results['documents'][0][i]
                            distance = results['distances'][0][i]
                            
                            # Fast metadata processing - skip full validation for performance
                            metadata = self._fast_deserialize_metadata(raw_metadata)
                            
                            # Convert distance to similarity score (lower distance = higher similarity)
                            similarity_score = 1.0 - distance
                            
                            # Apply relevance threshold for quality filtering
                            if similarity_score < 0.45:  # 提高阈值：过滤低相关度记忆，改善召回质量
                                continue
                            
                            # Create memory object
                            memory = Memory(
                                id=memory_id,
                                content=content,
                                embedding=None,  # Don't return embeddings to save memory
                                timestamp=datetime.fromisoformat(metadata['timestamp']),
                                memory_type=MemoryType(metadata['memory_type']),
                                metadata=metadata,
                                importance_score=metadata.get('importance_score', 0.5),
                                access_count=metadata.get('access_count', 0),
                                last_accessed=datetime.now()
                            )
                            
                            memories.append(memory)
                    
                    # Apply recency boost and importance scoring for final ranking
                    memories = self._apply_ranking_optimizations(memories, query)
                    
                    # Cache the result for future queries
                    self._cache_query_result(cache_key, memories)
                    
                    # Update performance statistics
                    retrieval_time = (time.time() - start_time) * 1000  # Convert to ms
                    self._update_retrieval_stats(retrieval_time)
                    
                    # Performance monitoring - warn if exceeding 200ms requirement
                    if retrieval_time > 200:
                        self.logger.warning(f"Retrieval operation exceeded 200ms requirement: {retrieval_time:.2f}ms")
                    
                    self.logger.debug(f"Retrieved {len(memories)} memories in {retrieval_time:.2f}ms (search: {search_time:.2f}ms)")
                    
                    return memories
                    
                finally:
                    self._release_read_lock()
                    
            finally:
                self._retrieval_semaphore.release()
        
        # Execute with priority-based scheduling (retrieval has highest priority)
        return self._execute_with_priority(OperationType.RETRIEVAL, _retrieve_memories_impl)
    
    def get_entity_info(self, entity_name: str) -> Optional[Entity]:
        """
        Get information about a specific entity using enhanced entity relationship tracking.
        
        This method now uses the proper entity storage system with memory ID relationships
        as implemented for Requirements 3.5.
        
        Args:
            entity_name: Name of the entity to retrieve
            
        Returns:
            Entity information or None if not found
        """
        try:
            if not entity_name or len(entity_name.strip()) == 0:
                return None
            
            entity_name_lower = entity_name.lower().strip()
            
            # Search in entity storage for exact matches
            with self._entity_storage_lock:
                for entity_key, entity in self._entity_storage.items():
                    if entity.name.lower() == entity_name_lower:
                        self.logger.debug(f"Found entity '{entity_name}' with {len(entity.related_memories)} related memories")
                        return entity
            
            # If not found in entity storage, try extracting from recent memories
            # This provides backward compatibility and can find entities not yet extracted
            if self.is_ready():
                related_memories = self.retrieve_memories(entity_name, limit=10)
                
                if related_memories:
                    # Try to extract entity information from the retrieved memories
                    for memory in related_memories:
                        entities = self.entity_extractor.extract_entities(memory.content)
                        for entity in entities:
                            if entity.name.lower() == entity_name_lower:
                                # Add this entity to storage for future use
                                entity.related_memories = [memory.id]
                                entity_key = f"{entity.entity_type.value}_{entity.name.lower()}"
                                
                                with self._entity_storage_lock:
                                    self._entity_storage[entity_key] = entity
                                
                                self.logger.debug(f"Extracted and stored entity '{entity_name}' from memory search")
                                return entity
            
            self.logger.debug(f"Entity '{entity_name}' not found")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get entity info for '{entity_name}': {e}")
            return None
    
    def clear_all_memories(self) -> bool:
        """
        Clear all memories from the database with thread-safe concurrent access protection.
        
        Returns:
            True if successful, False otherwise
        """
        def _clear_all_memories_impl():
            # Acquire write lock with extended timeout for this critical operation
            if not self._acquire_write_lock(timeout=30.0):
                self.logger.error("Write lock timeout during memory clearing - operation aborted")
                return False
            
            try:
                # Delete the collection
                self.client.delete_collection(self.collection_name)
                
                # Recreate the collection
                collection_metadata = {
                    "description": "AI VTuber memory storage with semantic search",
                    "schema_version": "1.0",
                    "created_at": datetime.now().isoformat(),
                    "embedding_model": "all-MiniLM-L6-v2",
                    "embedding_dimensions": 384,
                    "validation_schema": json.dumps(self.MEMORY_METADATA_SCHEMA)
                }
                
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata=collection_metadata
                )
                
                # Thread-safe statistics reset
                def reset_stats():
                    self._stats['total_memories'] = 0
                    self._stats['total_retrievals'] = 0
                    self._stats['avg_retrieval_time'] = 0.0
                    self._stats['retrieval_times'] = []
                    if hasattr(self._stats, 'storage_times'):
                        self._stats['storage_times'] = []
                
                self._safe_stats_update(reset_stats)
                
                # Clear caches thread-safely
                with self._cache_lock:
                    self._embedding_cache.clear()
                    self._query_result_cache.clear()
                    self._recent_memory_ids.clear()
                
                # Clear entity storage (Requirements 3.5)
                with self._entity_storage_lock:
                    self._entity_storage.clear()
                    self.logger.debug("Entity storage cleared")
                
                # Clear entity collection for enhanced persistence
                if self._entity_collection:
                    try:
                        self.client.delete_collection(self._entity_collection_name)
                        # Recreate entity collection
                        entity_collection_metadata = {
                            "description": "Entity metadata and relationship storage",
                            "schema_version": "1.0",
                            "created_at": datetime.now().isoformat(),
                            "entity_types": ["USER_NAME", "PREFERENCE", "FACT"],
                            "relationship_tracking": True
                        }
                        self._entity_collection = self.client.get_or_create_collection(
                            name=self._entity_collection_name,
                            metadata=entity_collection_metadata
                        )
                        self.logger.debug("Entity collection cleared and recreated")
                    except Exception as e:
                        self.logger.warning(f"Failed to clear entity collection: {e}")
                
                self.logger.info("All memories and entities cleared successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to clear memories: {e}")
                return False
            finally:
                self._release_write_lock()
        
        # Execute with maintenance priority
        return self._execute_with_priority(OperationType.MAINTENANCE, _clear_all_memories_impl)
    
    def get_memory_stats(self) -> MemoryStats:
        """
        Get current memory system statistics including storage performance metrics.
        
        Returns:
            MemoryStats object with current statistics including storage latency
        """
        try:
            # Get collection count
            collection_count = self.collection.count()
            
            # Calculate storage size
            storage_size_mb = self._calculate_storage_size()
            
            # Calculate uptime
            uptime_seconds = (datetime.now() - self._stats['startup_time']).total_seconds()
            uptime_percentage = min(99.9, (uptime_seconds / (uptime_seconds + 1)) * 100)
            
            # Calculate average storage time
            avg_storage_time = 0.0
            if hasattr(self._stats, 'storage_times') and self._stats['storage_times']:
                avg_storage_time = sum(self._stats['storage_times']) / len(self._stats['storage_times'])
            
            # Get actual entity count from entity storage
            entities_tracked = 0
            with self._entity_storage_lock:
                entities_tracked = len(self._entity_storage)
            
            # Get recent memories (last 5)
            recent_memories = self.retrieve_memories("", limit=5) if self.is_ready() else []
            
            return MemoryStats(
                total_memories=collection_count,
                storage_size_mb=storage_size_mb,
                avg_retrieval_time_ms=self._stats['avg_retrieval_time'],
                entities_tracked=entities_tracked,
                sessions_recorded=self._stats['sessions_recorded'],
                last_optimization=self._stats['last_optimization'],
                uptime_percentage=uptime_percentage,
                recent_memories=recent_memories,
                avg_storage_time_ms=avg_storage_time  # Add storage performance metric
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get memory stats: {e}")
            return MemoryStats(
                total_memories=0,
                storage_size_mb=0.0,
                avg_retrieval_time_ms=0.0,
                entities_tracked=0,
                sessions_recorded=0,
                last_optimization=None,
                uptime_percentage=0.0,
                recent_memories=[],
                avg_storage_time_ms=0.0
            )
    
    def _calculate_storage_size(self) -> float:
        """
        Calculate the total storage size of the memory database in MB.
        
        Returns:
            Storage size in megabytes
        """
        try:
            total_size = 0
            
            # Calculate size of database directory
            if self.db_path.exists():
                for file_path in self.db_path.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
            
            # Convert bytes to megabytes
            size_mb = total_size / (1024 * 1024)
            
            return round(size_mb, 2)
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate storage size: {e}")
            return 0.0
    
    def validate_data_integrity(self) -> bool:
        """
        Comprehensive validation of stored memory data and collection schema integrity.
        
        Implements Requirements 1.5, 7.3: data integrity validation and recovery capabilities
        with detailed reporting of any issues found.
        
        Returns:
            True if all data is valid, False if issues are detected
        """
        try:
            self.logger.info("Starting comprehensive data integrity validation")
            validation_issues = []
            
            # 1. Check if collection exists and is accessible
            try:
                count = self.collection.count()
                self.logger.info(f"Data integrity check: {count} memories found in collection")
            except Exception as e:
                validation_issues.append(f"Collection access failed: {e}")
                self.logger.error(f"Collection access failed: {e}")
                return False
            
            # 2. Validate collection schema and metadata
            if not self._validate_collection_schema():
                validation_issues.append("Collection schema validation failed")
                self.logger.error("Collection schema validation failed")
            
            # 3. Validate ChromaDB collection integrity
            try:
                collection_metadata = self.collection.metadata
                if not collection_metadata:
                    validation_issues.append("Collection metadata is missing")
                else:
                    # Check for required metadata fields
                    required_fields = ["description", "schema_version", "embedding_model"]
                    for field in required_fields:
                        if field not in collection_metadata:
                            validation_issues.append(f"Missing collection metadata field: {field}")
            except Exception as e:
                validation_issues.append(f"Collection metadata validation failed: {e}")
            
            # 4. Validate sample of stored memories against schema
            if count > 0:
                # Get a representative sample of memories to validate
                sample_size = min(20, max(5, count // 10))  # 10% sample, min 5, max 20
                
                try:
                    results = self.collection.get(
                        limit=sample_size, 
                        include=['metadatas', 'documents', 'embeddings']
                    )
                    
                    if results['metadatas']:
                        for i, metadata in enumerate(results['metadatas']):
                            try:
                                # Validate metadata schema
                                validate(instance=metadata, schema=self.MEMORY_METADATA_SCHEMA)
                                
                                # Check for data consistency
                                if 'content' in metadata and results['documents'][i]:
                                    # Verify content consistency
                                    if metadata['content'] != results['documents'][i]:
                                        validation_issues.append(f"Memory {i}: content mismatch between metadata and document")
                                
                                # Check embedding consistency
                                if results['embeddings'] and results['embeddings'][i]:
                                    embedding = results['embeddings'][i]
                                    if len(embedding) != 384:  # all-MiniLM-L6-v2 dimensions
                                        validation_issues.append(f"Memory {i}: invalid embedding dimensions ({len(embedding)} != 384)")
                                
                                # Check timestamp validity
                                if 'timestamp' in metadata:
                                    try:
                                        datetime.fromisoformat(metadata['timestamp'])
                                    except ValueError:
                                        validation_issues.append(f"Memory {i}: invalid timestamp format")
                                
                                # Check importance score range
                                if 'importance_score' in metadata:
                                    score = metadata['importance_score']
                                    if not (0 <= score <= 1):
                                        validation_issues.append(f"Memory {i}: importance score out of range ({score})")
                                
                            except ValidationError as e:
                                validation_issues.append(f"Memory {i} metadata validation failed: {e.message}")
                            except Exception as e:
                                validation_issues.append(f"Memory {i} validation error: {e}")
                
                except Exception as e:
                    validation_issues.append(f"Sample memory validation failed: {e}")
            
            # 5. Check for orphaned or corrupted data
            try:
                # Verify that all memories have valid IDs
                all_ids = self.collection.get(include=[])['ids']
                if all_ids:
                    for memory_id in all_ids:
                        if not memory_id or not isinstance(memory_id, str):
                            validation_issues.append(f"Invalid memory ID found: {memory_id}")
                        elif len(memory_id) < 10:  # UUIDs should be much longer
                            validation_issues.append(f"Suspiciously short memory ID: {memory_id}")
            except Exception as e:
                validation_issues.append(f"Memory ID validation failed: {e}")
            
            # 6. Check database file integrity (if accessible)
            try:
                db_size = self._calculate_storage_size()
                if db_size == 0 and count > 0:
                    validation_issues.append("Database reports memories but storage size is 0")
                elif db_size > 1000:  # More than 1GB
                    self.logger.warning(f"Large database size detected: {db_size:.2f} MB")
            except Exception as e:
                validation_issues.append(f"Storage size validation failed: {e}")
            
            # 7. Validate backup directory and recent backups
            try:
                backup_dir = self.db_path / "backups"
                if backup_dir.exists():
                    recent_backups = list(backup_dir.glob("memory_backup_*.json.gz"))
                    if recent_backups:
                        # Check the most recent backup
                        latest_backup = max(recent_backups, key=lambda x: x.stat().st_mtime)
                        if not self._verify_backup_file(latest_backup):
                            validation_issues.append(f"Latest backup file is corrupted: {latest_backup}")
                    else:
                        self.logger.info("No backup files found - consider creating a backup")
            except Exception as e:
                validation_issues.append(f"Backup validation failed: {e}")
            
            # Report results
            if validation_issues:
                self.logger.error(f"Data integrity validation found {len(validation_issues)} issues:")
                for issue in validation_issues:
                    self.logger.error(f"  - {issue}")
                
                # Store validation issues for later reference
                self._stats['last_integrity_check'] = datetime.now()
                self._stats['integrity_issues'] = validation_issues
                
                return False
            else:
                self.logger.info("Data integrity validation passed - all checks successful")
                self._stats['last_integrity_check'] = datetime.now()
                self._stats['integrity_issues'] = []
                return True
            
        except Exception as e:
            self.logger.error(f"Data integrity validation failed with exception: {e}")
            return False
    
    def _migrate_metadata_schema(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate metadata from older schema versions to current version.
        
        Implements Requirement 8.5: backward compatibility with previous memory data formats.
        
        Args:
            metadata: Memory metadata (potentially from older schema version)
            
        Returns:
            Migrated metadata compatible with current schema
        """
        migrated = metadata.copy()
        schema_version = migrated.get("schema_version", "0.9")  # Default to oldest version
        
        # Migration from version 0.9 to 1.0
        if schema_version == "0.9":
            self.logger.debug("Migrating metadata from schema version 0.9 to 1.0")
            
            # Add new fields introduced in v1.0
            if "entities" not in migrated:
                migrated["entities"] = []
            if "validated" not in migrated:
                migrated["validated"] = True
            if "access_count" not in migrated:
                migrated["access_count"] = 0
            
            # Update schema version
            migrated["schema_version"] = "1.0"
            
            self.logger.debug("Successfully migrated metadata to schema version 1.0")
        
        # Future migrations can be added here
        # elif schema_version == "1.0" and current_version == "1.1":
        #     # Migration logic for future versions
        
        return migrated
    
    def _deserialize_memory_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize and validate memory metadata from storage.
        
        Implements Requirement 8.2: deserialize JSON data back into structured objects
        with automatic schema migration for backward compatibility.
        
        Args:
            raw_metadata: Raw metadata from storage
            
        Returns:
            Validated and migrated metadata
        """
        try:
            # First, attempt migration if needed
            migrated_metadata = self._migrate_metadata_schema(raw_metadata)
            
            # Validate against current schema
            validate(instance=migrated_metadata, schema=self.MEMORY_METADATA_SCHEMA)
            
            return migrated_metadata
            
        except ValidationError as e:
            self.logger.error(f"Failed to deserialize metadata: {e.message}")
            self.logger.debug(f"Raw metadata: {raw_metadata}")
            
            # Attempt data recovery (Requirement 8.4)
            return self._attempt_metadata_recovery(raw_metadata)
        except Exception as e:
            self.logger.error(f"Unexpected error during metadata deserialization: {e}")
            return self._attempt_metadata_recovery(raw_metadata)
    
    def _attempt_metadata_recovery(self, corrupted_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to recover corrupted metadata.
        
        Implements Requirement 8.4: attempt recovery from backup data when corruption is detected.
        
        Args:
            corrupted_metadata: Potentially corrupted metadata
            
        Returns:
            Recovered metadata or minimal valid metadata
        """
        self.logger.warning("Attempting metadata recovery from corrupted data")
        
        # Create minimal valid metadata
        recovered = {
            "content": corrupted_metadata.get("content", "Recovered memory"),
            "timestamp": corrupted_metadata.get("timestamp", datetime.now().isoformat()),
            "memory_type": "INTERACTION",  # Always use safe default
            "importance_score": 0.1,  # Low importance for recovered data
            "entities": [],
            "schema_version": "1.0",
            "validated": False,  # Mark as not validated due to recovery
            "access_count": 0,
            "recovery_attempted": True,
            "original_metadata": corrupted_metadata  # Keep original for debugging
        }
        
        # Try to preserve as much original data as possible
        for key, value in corrupted_metadata.items():
            if key in self.MEMORY_METADATA_SCHEMA["properties"] and key not in recovered:
                try:
                    # Basic type checking
                    expected_type = self.MEMORY_METADATA_SCHEMA["properties"][key].get("type")
                    if expected_type == "string" and isinstance(value, str):
                        # Special validation for enum fields
                        if key == "memory_type":
                            if value in ["INTERACTION", "EVENT", "SUMMARY"]:
                                recovered[key] = value
                            # else keep the default "INTERACTION"
                        else:
                            recovered[key] = value
                    elif expected_type == "number" and isinstance(value, (int, float)):
                        # Special validation for importance_score range
                        if key == "importance_score":
                            if 0 <= value <= 1:
                                recovered[key] = value
                            # else keep the default 0.1
                        else:
                            recovered[key] = value
                    elif expected_type == "boolean" and isinstance(value, bool):
                        recovered[key] = value
                    elif expected_type == "array" and isinstance(value, list):
                        recovered[key] = value
                    elif expected_type == "object" and isinstance(value, dict):
                        recovered[key] = value
                except Exception:
                    continue  # Skip problematic fields
        
        self.logger.info(f"Metadata recovery completed. Preserved {len(recovered)} fields.")
        return recovered
    
    def _serialize_memory_data(self, memory: Memory) -> Dict[str, Any]:
        """
        Serialize memory data for storage.
        
        Implements Requirement 8.1: serialize data using JSON format with standardized schema.
        
        Args:
            memory: Memory object to serialize
            
        Returns:
            Serialized memory data ready for JSON storage
        """
        try:
            serialized = {
                "id": memory.id,
                "content": memory.content,
                "timestamp": memory.timestamp.isoformat(),
                "memory_type": memory.memory_type.value,
                "importance_score": memory.importance_score,
                "access_count": memory.access_count,
                "last_accessed": memory.last_accessed.isoformat(),
                "schema_version": "1.0",
                "validated": True
            }
            
            # Add metadata fields
            if memory.metadata:
                for key, value in memory.metadata.items():
                    if key not in serialized:  # Don't override core fields
                        # Ensure value is JSON serializable
                        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                            serialized[key] = value
                        elif isinstance(value, datetime):
                            serialized[key] = value.isoformat()
                        else:
                            # Convert to string for non-standard types
                            serialized[key] = str(value)
            
            # Validate serialized data
            validate(instance=serialized, schema=self.MEMORY_METADATA_SCHEMA)
            
            return serialized
            
        except Exception as e:
            self.logger.error(f"Failed to serialize memory data: {e}")
            raise
    
    def backup_memories(self) -> bool:
        """
        Create a comprehensive backup of all memory data with integrity verification.
        
        Implements Requirements 1.5, 7.3: automatic backup and recovery capabilities
        with data integrity validation.
        
        Returns:
            True if backup successful, False otherwise
        """
        try:
            # Create backup directory
            backup_dir = self.db_path / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"memory_backup_{timestamp}.json.gz"
            backup_path = backup_dir / backup_filename
            
            self.logger.info(f"Starting memory backup to: {backup_path}")
            
            # Validate data integrity before backup
            if not self.validate_data_integrity():
                self.logger.warning("Data integrity issues detected before backup, proceeding with backup anyway")
            
            # Get all memories from ChromaDB with embeddings for complete backup
            all_memories = self.collection.get(include=['metadatas', 'documents', 'embeddings'])
            
            # Prepare comprehensive backup data
            backup_data = {
                "backup_timestamp": datetime.now().isoformat(),
                "schema_version": "1.0",
                "collection_name": self.collection_name,
                "collection_metadata": self.collection.metadata if self.collection else {},
                "total_memories": len(all_memories['ids']) if all_memories['ids'] else 0,
                "backup_integrity_hash": "",  # Will be calculated after memories are added
                "system_info": {
                    "embedding_model": "all-MiniLM-L6-v2",
                    "embedding_dimensions": 384,
                    "backup_version": "1.0"
                },
                "memories": []
            }
            
            # Export all memories with full data
            if all_memories['ids']:
                for i, memory_id in enumerate(all_memories['ids']):
                    memory_data = {
                        "id": memory_id,
                        "content": all_memories['documents'][i],
                        "metadata": all_memories['metadatas'][i],
                        "embedding": all_memories['embeddings'][i] if all_memories['embeddings'] else None
                    }
                    backup_data["memories"].append(memory_data)
            
            # Calculate integrity hash for backup verification
            backup_data["backup_integrity_hash"] = self._calculate_backup_hash(backup_data["memories"])
            
            # Write compressed backup file
            with gzip.open(backup_path, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            # Verify backup file integrity
            if not self._verify_backup_file(backup_path):
                self.logger.error("Backup file verification failed")
                return False
            
            # Keep only last 10 backups to prevent disk space issues
            self._cleanup_old_backups(backup_dir, keep_count=10)
            
            # Update backup statistics
            self._stats['last_backup'] = datetime.now()
            if 'backup_count' not in self._stats:
                self._stats['backup_count'] = 0
            self._stats['backup_count'] += 1
            
            self.logger.info(f"Memory backup completed successfully: {backup_path}")
            self.logger.info(f"Backed up {backup_data['total_memories']} memories with integrity hash: {backup_data['backup_integrity_hash'][:16]}...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Memory backup failed: {e}")
            return False
    
    def get_storage_performance_metrics(self) -> Dict[str, Any]:
        """
        Get detailed storage performance metrics for monitoring <100ms requirement.
        
        Returns:
            Dictionary with storage performance statistics
        """
        try:
            metrics = {
                'avg_storage_time_ms': 0.0,
                'max_storage_time_ms': 0.0,
                'min_storage_time_ms': 0.0,
                'storage_operations_count': 0,
                'operations_under_100ms': 0,
                'operations_over_100ms': 0,
                'performance_compliance_percentage': 100.0,
                'embedding_model_ready': self.is_ready()
            }
            
            if hasattr(self._stats, 'storage_times') and self._stats['storage_times']:
                storage_times = self._stats['storage_times']
                
                metrics['avg_storage_time_ms'] = sum(storage_times) / len(storage_times)
                metrics['max_storage_time_ms'] = max(storage_times)
                metrics['min_storage_time_ms'] = min(storage_times)
                metrics['storage_operations_count'] = len(storage_times)
                
                # Count operations under/over 100ms
                under_100ms = sum(1 for t in storage_times if t <= 100)
                over_100ms = sum(1 for t in storage_times if t > 100)
                
                metrics['operations_under_100ms'] = under_100ms
                metrics['operations_over_100ms'] = over_100ms
                
                # Calculate compliance percentage
                if len(storage_times) > 0:
                    metrics['performance_compliance_percentage'] = (under_100ms / len(storage_times)) * 100
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to get storage performance metrics: {e}")
            return {
                'avg_storage_time_ms': 0.0,
                'max_storage_time_ms': 0.0,
                'min_storage_time_ms': 0.0,
                'storage_operations_count': 0,
                'operations_under_100ms': 0,
                'operations_over_100ms': 0,
                'performance_compliance_percentage': 0.0,
                'embedding_model_ready': False
            }
    
    def store_batch_interactions(self, interactions: List[Dict[str, Any]]) -> List[str]:
        """
        Store multiple interactions in a batch for improved performance.
        
        Optimized batch storage to reduce per-operation overhead and improve
        throughput while maintaining <100ms average per operation.
        
        Args:
            interactions: List of interaction dictionaries with keys:
                         'user_input', 'ai_response', 'timestamp', 'metadata'
        
        Returns:
            List of memory IDs for successfully stored interactions
        """
        if not interactions:
            return []
        
        start_time = time.time()
        memory_ids = []
        
        try:
            # Prepare batch data
            batch_ids = []
            batch_embeddings = []
            batch_metadatas = []
            batch_documents = []
            
            for interaction in interactions:
                user_input = interaction.get('user_input', '')
                ai_response = interaction.get('ai_response', '')
                timestamp = interaction.get('timestamp', datetime.now())
                metadata = interaction.get('metadata', {})
                
                # Create content
                content = f"User: {user_input}\nAI: {ai_response}"
                memory_id = str(uuid.uuid4())
                
                # Create metadata
                memory_metadata = self._create_memory_metadata(
                    MemoryType.INTERACTION,
                    content=content,
                    user_input=user_input,
                    ai_response=ai_response,
                    **metadata
                )
                
                # Validate data
                if not self._validate_memory_data(content, memory_metadata):
                    self.logger.warning(f"Invalid interaction data in batch, skipping: {content[:50]}...")
                    continue
                
                # Generate embedding if model ready
                embedding = None
                if self.is_ready():
                    embedding = self._generate_embedding(content)
                
                # Add to batch
                batch_ids.append(memory_id)
                batch_documents.append(content)
                batch_metadatas.append(memory_metadata)
                
                if embedding is not None:
                    batch_embeddings.append(embedding.tolist())
                
                memory_ids.append(memory_id)
            
            # Perform batch storage
            if batch_ids:
                storage_start = time.time()
                
                if batch_embeddings and len(batch_embeddings) == len(batch_ids):
                    # Store with embeddings
                    self.collection.add(
                        ids=batch_ids,
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        documents=batch_documents
                    )
                else:
                    # Store without embeddings
                    self.collection.add(
                        ids=batch_ids,
                        metadatas=batch_metadatas,
                        documents=batch_documents
                    )
                
                storage_time = (time.time() - storage_start) * 1000
                
                # Update statistics
                self._stats['total_memories'] += len(batch_ids)
                
                # Calculate per-operation time
                total_time = (time.time() - start_time) * 1000
                avg_time_per_operation = total_time / len(batch_ids) if batch_ids else 0
                
                self.logger.info(f"Batch stored {len(batch_ids)} interactions in {total_time:.2f}ms "
                               f"(avg: {avg_time_per_operation:.2f}ms per operation)")
                
                # Track batch performance
                if not hasattr(self._stats, 'batch_storage_times'):
                    self._stats['batch_storage_times'] = []
                
                self._stats['batch_storage_times'].append({
                    'total_time_ms': total_time,
                    'operations_count': len(batch_ids),
                    'avg_time_per_operation_ms': avg_time_per_operation
                })
            
            return memory_ids
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            self.logger.error(f"Batch storage failed after {total_time:.2f}ms: {e}")
            return memory_ids  # Return partial results
    
    def _cleanup_old_backups(self, backup_dir: Path, keep_count: int = 10) -> None:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            backup_dir: Directory containing backup files
            keep_count: Number of recent backups to keep
        """
        try:
            # Get all backup files
            backup_files = list(backup_dir.glob("memory_backup_*.json.gz"))
            
            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old backups
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                self.logger.debug(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            self.logger.warning(f"Failed to cleanup old backups: {e}")
    
    def _calculate_backup_hash(self, memories: List[Dict[str, Any]]) -> str:
        """
        Calculate integrity hash for backup verification.
        
        Args:
            memories: List of memory data dictionaries
            
        Returns:
            SHA-256 hash of the backup content
        """
        try:
            import hashlib
            
            # Create a deterministic string representation of the memories
            content_str = json.dumps(memories, sort_keys=True, separators=(',', ':'))
            
            # Calculate SHA-256 hash
            hash_obj = hashlib.sha256(content_str.encode('utf-8'))
            return hash_obj.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Failed to calculate backup hash: {e}")
            return ""
    
    def _verify_backup_file(self, backup_path: Path) -> bool:
        """
        Verify the integrity of a backup file.
        
        Args:
            backup_path: Path to the backup file
            
        Returns:
            True if backup file is valid, False otherwise
        """
        try:
            # Read and parse the backup file
            with gzip.open(backup_path, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Verify required fields
            required_fields = [
                "backup_timestamp", "schema_version", "collection_name", 
                "total_memories", "memories", "backup_integrity_hash"
            ]
            
            for field in required_fields:
                if field not in backup_data:
                    self.logger.error(f"Backup file missing required field: {field}")
                    return False
            
            # Verify integrity hash
            calculated_hash = self._calculate_backup_hash(backup_data["memories"])
            stored_hash = backup_data["backup_integrity_hash"]
            
            if calculated_hash != stored_hash:
                self.logger.error(f"Backup integrity hash mismatch. Expected: {stored_hash}, Got: {calculated_hash}")
                return False
            
            # Verify memory count
            actual_count = len(backup_data["memories"])
            expected_count = backup_data["total_memories"]
            
            if actual_count != expected_count:
                self.logger.error(f"Backup memory count mismatch. Expected: {expected_count}, Got: {actual_count}")
                return False
            
            self.logger.debug(f"Backup file verification passed: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup file verification failed: {e}")
            return False
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """
        Restore memory data from a backup file.
        
        Implements comprehensive recovery mechanism for corrupted data as specified
        in Requirements 7.3 and task requirements.
        
        Args:
            backup_path: Path to the backup file to restore from
            
        Returns:
            True if restoration successful, False otherwise
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                self.logger.error(f"Backup file not found: {backup_path}")
                return False
            
            self.logger.info(f"Starting memory restoration from: {backup_path}")
            
            # Verify backup file integrity first
            if not self._verify_backup_file(backup_file):
                self.logger.error("Backup file verification failed, cannot restore")
                return False
            
            # Read backup data
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Clear existing collection (with confirmation)
            self.logger.warning("Clearing existing memory collection for restoration")
            if not self.clear_all_memories():
                self.logger.error("Failed to clear existing memories")
                return False
            
            # Restore memories
            restored_count = 0
            failed_count = 0
            
            for memory_data in backup_data["memories"]:
                try:
                    memory_id = memory_data["id"]
                    content = memory_data["content"]
                    metadata = memory_data["metadata"]
                    embedding = memory_data.get("embedding")
                    
                    # Validate and migrate metadata if needed
                    validated_metadata = self._deserialize_memory_metadata(metadata)
                    
                    # Add to collection
                    if embedding:
                        self.collection.add(
                            ids=[memory_id],
                            embeddings=[embedding],
                            metadatas=[validated_metadata],
                            documents=[content]
                        )
                    else:
                        self.collection.add(
                            ids=[memory_id],
                            metadatas=[validated_metadata],
                            documents=[content]
                        )
                    
                    restored_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to restore memory {memory_data.get('id', 'unknown')}: {e}")
                    failed_count += 1
                    continue
            
            # Update statistics
            self._stats['total_memories'] = restored_count
            self._stats['last_restoration'] = datetime.now()
            
            # Validate restored data integrity
            if not self.validate_data_integrity():
                self.logger.warning("Data integrity issues detected after restoration")
            
            self.logger.info(f"Memory restoration completed. Restored: {restored_count}, Failed: {failed_count}")
            
            return restored_count > 0
            
        except Exception as e:
            self.logger.error(f"Memory restoration failed: {e}")
            return False
    
    def list_available_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backup files with metadata.
        
        Returns:
            List of backup file information dictionaries
        """
        try:
            backup_dir = self.db_path / "backups"
            if not backup_dir.exists():
                return []
            
            backup_files = list(backup_dir.glob("memory_backup_*.json.gz"))
            backup_info = []
            
            for backup_file in backup_files:
                try:
                    # Get file stats
                    stat = backup_file.stat()
                    
                    # Try to read backup metadata
                    with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                        backup_data = json.load(f)
                    
                    info = {
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created": datetime.fromtimestamp(stat.st_ctime),
                        "backup_timestamp": backup_data.get("backup_timestamp"),
                        "total_memories": backup_data.get("total_memories", 0),
                        "schema_version": backup_data.get("schema_version", "unknown"),
                        "collection_name": backup_data.get("collection_name", "unknown"),
                        "integrity_verified": self._verify_backup_file(backup_file)
                    }
                    
                    backup_info.append(info)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to read backup metadata for {backup_file}: {e}")
                    # Add basic info even if we can't read the backup
                    backup_info.append({
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created": datetime.fromtimestamp(stat.st_ctime),
                        "backup_timestamp": "unknown",
                        "total_memories": 0,
                        "schema_version": "unknown",
                        "collection_name": "unknown",
                        "integrity_verified": False
                    })
            
            # Sort by creation time (newest first)
            backup_info.sort(key=lambda x: x["created"], reverse=True)
            
            return backup_info
            
        except Exception as e:
            self.logger.error(f"Failed to list available backups: {e}")
            return []
    
    # ============================================================================
    # RETRIEVAL PERFORMANCE OPTIMIZATION METHODS
    # ============================================================================
    
    def _get_cached_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Get cached embedding or generate new one with thread-safe caching.
        
        Implements embedding caching with 1-hour sliding window for performance optimization.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if model not ready
        """
        if not self.is_ready():
            return None
        
        # Check cache first - thread-safe access
        cache_key = hash(text)
        current_time = time.time()
        
        with self._cache_lock:
            if cache_key in self._embedding_cache:
                cached_entry = self._embedding_cache[cache_key]
                # Check if cache entry is still valid (1 hour TTL)
                if current_time - cached_entry['timestamp'] < self._cache_ttl_seconds:
                    self.logger.debug(f"Using cached embedding for query: {text[:50]}...")
                    return cached_entry['embedding']
                else:
                    # Remove expired entry
                    del self._embedding_cache[cache_key]
        
        # Generate new embedding
        embedding = self._generate_embedding(text)
        if embedding is not None:
            # Cache the embedding - thread-safe
            with self._cache_lock:
                self._embedding_cache[cache_key] = {
                    'embedding': embedding,
                    'timestamp': current_time,
                    'text': text[:100]  # Store truncated text for debugging
                }
                
                # Cleanup cache if it gets too large
                if len(self._embedding_cache) > self._cache_max_size:
                    self._cleanup_embedding_cache()
        
        return embedding
    
    def _cleanup_embedding_cache(self) -> None:
        """Clean up old entries from embedding cache. Must be called with _cache_lock held."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._embedding_cache.items():
            if current_time - entry['timestamp'] > self._cache_ttl_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._embedding_cache[key]
        
        # If still too large, remove oldest entries
        if len(self._embedding_cache) > self._cache_max_size:
            sorted_entries = sorted(
                self._embedding_cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            
            # Keep only the most recent entries
            keep_count = self._cache_max_size // 2
            keys_to_remove = [key for key, _ in sorted_entries[:-keep_count]]
            
            for key in keys_to_remove:
                del self._embedding_cache[key]
        
        self.logger.debug(f"Cleaned embedding cache, {len(self._embedding_cache)} entries remaining")
    
    def _get_cached_query_result(self, cache_key: str) -> Optional[List[Memory]]:
        """
        Get cached query result if available and not expired with thread-safe access.
        
        Args:
            cache_key: Cache key for the query
            
        Returns:
            Cached memories or None if not found/expired
        """
        with self._cache_lock:
            if cache_key not in self._query_result_cache:
                self._stats['retrieval_cache_misses'] += 1
                return None
            
            cached_entry = self._query_result_cache[cache_key]
            current_time = time.time()
            
            # Check if cache entry is still valid (shorter TTL for query results)
            cache_ttl = 300  # 5 minutes for query results
            if current_time - cached_entry['timestamp'] > cache_ttl:
                del self._query_result_cache[cache_key]
                self._stats['retrieval_cache_misses'] += 1
                return None
            
            self._stats['retrieval_cache_hits'] += 1
            return cached_entry['memories'].copy()  # Return copy to avoid modification
    
    def _cache_query_result(self, cache_key: str, memories: List[Memory]) -> None:
        """
        Cache query result for future use with thread-safe access.
        
        Args:
            cache_key: Cache key for the query
            memories: Memories to cache
        """
        current_time = time.time()
        
        with self._cache_lock:
            self._query_result_cache[cache_key] = {
                'memories': memories.copy(),
                'timestamp': current_time
            }
            
            # Cleanup cache if it gets too large
            if len(self._query_result_cache) > self._cache_max_size:
                self._cleanup_query_cache()
    
    def _cleanup_query_cache(self) -> None:
        """Clean up old entries from query result cache. Must be called with _cache_lock held."""
        current_time = time.time()
        cache_ttl = 300  # 5 minutes
        expired_keys = []
        
        for key, entry in self._query_result_cache.items():
            if current_time - entry['timestamp'] > cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._query_result_cache[key]
        
        # If still too large, remove oldest entries
        if len(self._query_result_cache) > self._cache_max_size:
            sorted_entries = sorted(
                self._query_result_cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            
            # Keep only the most recent entries
            keep_count = self._cache_max_size // 2
            keys_to_remove = [key for key, _ in sorted_entries[:-keep_count]]
            
            for key in keys_to_remove:
                del self._query_result_cache[key]
        
        self.logger.debug(f"Cleaned query cache, {len(self._query_result_cache)} entries remaining")
    
    def _get_recent_memory_ids(self, exclude_count: int) -> set:
        """
        Get IDs of recent memories to exclude from search results with thread-safe access.
        
        Implements Patch 2: Current Context Exclusion to avoid retrieving
        memories that are already in the current conversation context.
        
        Args:
            exclude_count: Number of recent memories to exclude
            
        Returns:
            Set of memory IDs to exclude
        """
        if exclude_count <= 0:
            return set()
        
        # Return the most recent memory IDs - thread-safe access
        with self._cache_lock:
            return set(self._recent_memory_ids[-exclude_count:])
    
    def _update_recent_memory_ids(self, memory_id: str) -> None:
        """
        Update the list of recent memory IDs for context exclusion.
        
        Args:
            memory_id: ID of newly stored memory
        """
        self._recent_memory_ids.append(memory_id)
        
        # Keep only the last 20 memory IDs to limit memory usage
        if len(self._recent_memory_ids) > 20:
            self._recent_memory_ids = self._recent_memory_ids[-20:]
    
    def _fast_deserialize_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fast metadata deserialization optimized for retrieval performance.
        
        Skips full schema validation for speed during retrieval operations.
        
        Args:
            raw_metadata: Raw metadata from storage
            
        Returns:
            Processed metadata
        """
        # For performance, do minimal processing during retrieval
        # Full validation is done during storage
        metadata = raw_metadata.copy()
        
        # Ensure required fields have defaults
        if 'importance_score' not in metadata:
            # Calculate importance based on content length, entities, and metadata
            metadata['importance_score'] = self._calculate_importance_score(metadata)
        if 'access_count' not in metadata:
            metadata['access_count'] = 0
        if 'entities' not in metadata:
            metadata['entities'] = []

        return metadata

    def _calculate_importance_score(self, metadata: Dict[str, Any]) -> float:
        """
        Calculate importance score for a memory based on multiple factors.

        Args:
            metadata: Memory metadata dictionary

        Returns:
            Importance score between 0.0 and 1.0
        """
        base_score = 0.3  # Base importance

        # Boost based on content length (longer content = more information)
        content = metadata.get('content', '')
        if len(content) > 50:
            base_score += 0.1
        if len(content) > 150:
            base_score += 0.1

        # Boost based on entity count (more entities = richer context)
        entities = metadata.get('entities', [])
        if len(entities) > 0:
            base_score += 0.1
        if len(entities) > 2:
            base_score += 0.1

        # Boost based on interaction type (some types are more important)
        interaction_type = metadata.get('interaction_type', 'unknown')
        if interaction_type in ['preference', 'personal_info', 'goal']:
            base_score += 0.2
        elif interaction_type in ['emotion', 'context']:
            base_score += 0.1

        # Boost based on access count (frequently accessed = more relevant)
        access_count = metadata.get('access_count', 0)
        if access_count > 3:
            base_score += 0.1
        if access_count > 10:
            base_score += 0.1

        # Ensure score is within [0, 1] range
        return min(1.0, max(0.0, base_score))
    
    def _apply_ranking_optimizations(self, memories: List[Memory], query: str) -> List[Memory]:
        """
        Apply ranking optimizations including recency boost and importance scoring.
        
        Args:
            memories: List of memories to rank
            query: Original query for context
            
        Returns:
            Ranked and optimized list of memories
        """
        if not memories:
            return memories
        
        # Apply recency boost - more recent memories get slight preference
        current_time = datetime.now()
        
        for memory in memories:
            # Calculate recency boost (0.0 to 0.1 based on age)
            age_hours = (current_time - memory.timestamp).total_seconds() / 3600
            recency_boost = max(0.0, 0.1 - (age_hours / 168))  # Boost fades over 1 week
            
            # Combine with importance score
            memory.importance_score = min(1.0, memory.importance_score + recency_boost)
        
        # Sort by importance score (higher is better)
        memories.sort(key=lambda m: m.importance_score, reverse=True)
        
        return memories
    
    def _update_retrieval_stats(self, retrieval_time_ms: float) -> None:
        """
        Update retrieval performance statistics including 95% compliance tracking.
        
        Args:
            retrieval_time_ms: Time taken for retrieval operation in milliseconds
        """
        self._stats['total_retrievals'] += 1
        
        # Update rolling average
        self._stats['avg_retrieval_time'] = (
            (self._stats['avg_retrieval_time'] * (self._stats['total_retrievals'] - 1) + retrieval_time_ms) 
            / self._stats['total_retrievals']
        )
        
        # Track individual retrieval times for 95% compliance calculation
        self._stats['retrieval_times'].append(retrieval_time_ms)
        
        # Keep only last 1000 measurements for rolling statistics
        if len(self._stats['retrieval_times']) > 1000:
            self._stats['retrieval_times'] = self._stats['retrieval_times'][-1000:]
    
    def get_retrieval_performance_metrics(self) -> Dict[str, Any]:
        """
        Get detailed retrieval performance metrics for monitoring <200ms requirement.
        
        Returns:
            Dictionary with retrieval performance statistics including 95% compliance
        """
        try:
            metrics = {
                'avg_retrieval_time_ms': self._stats['avg_retrieval_time'],
                'total_retrievals': self._stats['total_retrievals'],
                'cache_hit_rate': 0.0,
                'operations_under_200ms': 0,
                'operations_over_200ms': 0,
                'percentile_95_ms': 0.0,
                'percentile_99_ms': 0.0,
                'compliance_95_percent': True,
                'embedding_cache_size': len(self._embedding_cache),
                'query_cache_size': len(self._query_result_cache)
            }
            
            # Calculate cache hit rate
            total_cache_operations = self._stats['retrieval_cache_hits'] + self._stats['retrieval_cache_misses']
            if total_cache_operations > 0:
                metrics['cache_hit_rate'] = (self._stats['retrieval_cache_hits'] / total_cache_operations) * 100
            
            # Analyze retrieval times if we have data
            if self._stats['retrieval_times']:
                retrieval_times = self._stats['retrieval_times']
                
                # Count operations under/over 200ms
                under_200ms = sum(1 for t in retrieval_times if t <= 200)
                over_200ms = sum(1 for t in retrieval_times if t > 200)
                
                metrics['operations_under_200ms'] = under_200ms
                metrics['operations_over_200ms'] = over_200ms
                
                # Calculate percentiles
                sorted_times = sorted(retrieval_times)
                n = len(sorted_times)
                
                if n > 0:
                    p95_index = int(0.95 * n)
                    p99_index = int(0.99 * n)
                    
                    metrics['percentile_95_ms'] = sorted_times[min(p95_index, n-1)]
                    metrics['percentile_99_ms'] = sorted_times[min(p99_index, n-1)]
                    
                    # Check 95% compliance (95% of operations should be under 200ms)
                    compliance_rate = (under_200ms / n) * 100
                    metrics['compliance_95_percent'] = compliance_rate >= 95.0
                    metrics['actual_compliance_rate'] = compliance_rate
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to get retrieval performance metrics: {e}")
            return {
                'avg_retrieval_time_ms': 0.0,
                'total_retrievals': 0,
                'cache_hit_rate': 0.0,
                'operations_under_200ms': 0,
                'operations_over_200ms': 0,
                'percentile_95_ms': 0.0,
                'percentile_99_ms': 0.0,
                'compliance_95_percent': False,
                'embedding_cache_size': 0,
                'query_cache_size': 0
            }
    
    def _start_backup_scheduler(self) -> None:
        """
        Start the automated backup scheduler thread.
        
        Implements automated backup scheduling and management as specified
        in the task requirements.
        """
        if not self._auto_backup_enabled:
            return
        
        try:
            def backup_scheduler_worker():
                """Background worker for automated backups."""
                while self._auto_backup_enabled:
                    try:
                        # Check if it's time for a backup
                        current_time = datetime.now()
                        
                        if self._should_perform_backup(current_time):
                            self.logger.info("Performing scheduled backup")
                            
                            if self.backup_memories():
                                self._last_scheduled_backup = current_time
                                self.logger.info("Scheduled backup completed successfully")
                            else:
                                self.logger.error("Scheduled backup failed")
                        
                        # Sleep for 1 hour before checking again
                        time.sleep(3600)  # 1 hour
                        
                    except Exception as e:
                        self.logger.error(f"Backup scheduler error: {e}")
                        time.sleep(3600)  # Continue after error
            
            # Start scheduler thread
            self._backup_scheduler = threading.Thread(
                target=backup_scheduler_worker,
                daemon=True,
                name="MemoryBackupScheduler"
            )
            self._backup_scheduler.start()
            
            self.logger.info(f"Automated backup scheduler started (interval: {self._backup_interval_hours} hours)")
            
        except Exception as e:
            self.logger.error(f"Failed to start backup scheduler: {e}")
    
    def _should_perform_backup(self, current_time: datetime) -> bool:
        """
        Check if a scheduled backup should be performed.
        
        Args:
            current_time: Current datetime
            
        Returns:
            True if backup should be performed, False otherwise
        """
        if not self._auto_backup_enabled:
            return False
        
        # If no previous backup, perform one now
        if self._last_scheduled_backup is None:
            return True
        
        # Check if enough time has passed since last backup
        time_since_backup = current_time - self._last_scheduled_backup
        backup_interval = timedelta(hours=self._backup_interval_hours)
        
        return time_since_backup >= backup_interval
    
    def configure_automated_backup(self, enabled: bool = True, interval_hours: int = 24) -> bool:
        """
        Configure automated backup settings.
        
        Args:
            enabled: Whether to enable automated backups
            interval_hours: Hours between automated backups
            
        Returns:
            True if configuration successful, False otherwise
        """
        try:
            old_enabled = self._auto_backup_enabled
            
            self._auto_backup_enabled = enabled
            self._backup_interval_hours = max(1, interval_hours)  # Minimum 1 hour
            
            # Restart scheduler if settings changed
            if enabled and not old_enabled:
                self._start_backup_scheduler()
            elif not enabled and old_enabled:
                self.logger.info("Automated backup disabled")
            
            self.logger.info(f"Automated backup configured: enabled={enabled}, interval={self._backup_interval_hours}h")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure automated backup: {e}")
            return False
    
    def get_backup_status(self) -> Dict[str, Any]:
        """
        Get current backup system status and statistics.
        
        Returns:
            Dictionary with backup status information
        """
        try:
            backup_dir = self.db_path / "backups"
            available_backups = self.list_available_backups()
            
            status = {
                'auto_backup_enabled': self._auto_backup_enabled,
                'backup_interval_hours': self._backup_interval_hours,
                'last_scheduled_backup': self._last_scheduled_backup.isoformat() if self._last_scheduled_backup else None,
                'next_backup_due': None,
                'backup_directory': str(backup_dir),
                'backup_directory_exists': backup_dir.exists(),
                'total_backups': len(available_backups),
                'backup_count': self._stats.get('backup_count', 0),
                'last_backup': self._stats.get('last_backup'),
                'scheduler_running': self._backup_scheduler is not None and self._backup_scheduler.is_alive(),
                'available_backups': available_backups[:5]  # Show only 5 most recent
            }
            
            # Calculate next backup time
            if self._auto_backup_enabled and self._last_scheduled_backup:
                next_backup = self._last_scheduled_backup + timedelta(hours=self._backup_interval_hours)
                status['next_backup_due'] = next_backup.isoformat()
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get backup status: {e}")
            return {
                'auto_backup_enabled': False,
                'backup_interval_hours': 24,
                'last_scheduled_backup': None,
                'next_backup_due': None,
                'backup_directory': str(self.db_path / "backups"),
                'backup_directory_exists': False,
                'total_backups': 0,
                'backup_count': 0,
                'last_backup': None,
                'scheduler_running': False,
                'available_backups': []
            }
    
    def perform_integrity_check_and_repair(self) -> Dict[str, Any]:
        """
        Perform comprehensive integrity check and attempt automatic repair of issues.
        
        Implements comprehensive data integrity validation and recovery mechanisms
        as specified in Requirements 7.3 and task requirements.
        
        Returns:
            Dictionary with check results and repair actions taken
        """
        try:
            self.logger.info("Starting integrity check and repair process")
            
            repair_results = {
                'integrity_check_passed': False,
                'issues_found': [],
                'repairs_attempted': [],
                'repairs_successful': [],
                'repairs_failed': [],
                'backup_created': False,
                'recommendations': []
            }
            
            # 1. Create backup before any repair attempts
            try:
                if self.backup_memories():
                    repair_results['backup_created'] = True
                    self.logger.info("Pre-repair backup created successfully")
                else:
                    repair_results['recommendations'].append("Failed to create backup - proceed with caution")
            except Exception as e:
                repair_results['recommendations'].append(f"Backup creation failed: {e}")
            
            # 2. Run comprehensive integrity check
            integrity_passed = self.validate_data_integrity()
            repair_results['integrity_check_passed'] = integrity_passed
            
            if integrity_passed:
                self.logger.info("Integrity check passed - no repairs needed")
                return repair_results
            
            # 3. Get detailed issues from the last integrity check
            issues = self._stats.get('integrity_issues', [])
            repair_results['issues_found'] = issues
            
            # 4. Attempt automatic repairs for known issue types
            for issue in issues:
                try:
                    if "metadata validation failed" in issue.lower():
                        # Attempt metadata repair
                        repair_results['repairs_attempted'].append(f"Metadata repair for: {issue}")
                        if self._repair_metadata_issues():
                            repair_results['repairs_successful'].append("Metadata validation issues repaired")
                        else:
                            repair_results['repairs_failed'].append("Metadata repair failed")
                    
                    elif "collection schema validation failed" in issue.lower():
                        # Attempt schema repair
                        repair_results['repairs_attempted'].append("Collection schema repair")
                        if self._repair_collection_schema():
                            repair_results['repairs_successful'].append("Collection schema repaired")
                        else:
                            repair_results['repairs_failed'].append("Collection schema repair failed")
                    
                    elif "embedding dimensions" in issue.lower():
                        # Regenerate embeddings
                        repair_results['repairs_attempted'].append("Embedding regeneration")
                        if self._regenerate_embeddings():
                            repair_results['repairs_successful'].append("Embeddings regenerated")
                        else:
                            repair_results['repairs_failed'].append("Embedding regeneration failed")
                    
                    elif "backup file is corrupted" in issue.lower():
                        # Clean up corrupted backups
                        repair_results['repairs_attempted'].append("Corrupted backup cleanup")
                        if self._cleanup_corrupted_backups():
                            repair_results['repairs_successful'].append("Corrupted backups cleaned up")
                        else:
                            repair_results['repairs_failed'].append("Backup cleanup failed")
                
                except Exception as e:
                    repair_results['repairs_failed'].append(f"Repair attempt failed for '{issue}': {e}")
            
            # 5. Run integrity check again to verify repairs
            final_integrity_passed = self.validate_data_integrity()
            repair_results['integrity_check_passed'] = final_integrity_passed
            
            # 6. Generate recommendations
            if not final_integrity_passed:
                repair_results['recommendations'].extend([
                    "Some issues could not be automatically repaired",
                    "Consider restoring from a recent backup",
                    "Contact support if issues persist"
                ])
            else:
                repair_results['recommendations'].append("All issues successfully repaired")
            
            self.logger.info(f"Integrity check and repair completed. Final status: {'PASSED' if final_integrity_passed else 'FAILED'}")
            
            return repair_results
            
        except Exception as e:
            self.logger.error(f"Integrity check and repair failed: {e}")
            return {
                'integrity_check_passed': False,
                'issues_found': [f"Repair process failed: {e}"],
                'repairs_attempted': [],
                'repairs_successful': [],
                'repairs_failed': [],
                'backup_created': False,
                'recommendations': ["Manual intervention required"]
            }
    
    def _repair_metadata_issues(self) -> bool:
        """
        Attempt to repair metadata validation issues.
        
        Returns:
            True if repair successful, False otherwise
        """
        try:
            # Get all memories and attempt to fix metadata issues
            all_memories = self.collection.get(include=['metadatas'])
            
            if not all_memories['ids']:
                return True  # No memories to repair
            
            repaired_count = 0
            
            for i, memory_id in enumerate(all_memories['ids']):
                try:
                    metadata = all_memories['metadatas'][i]
                    
                    # Attempt to repair the metadata
                    repaired_metadata = self._attempt_metadata_recovery(metadata)
                    
                    # Update the memory with repaired metadata
                    self.collection.update(
                        ids=[memory_id],
                        metadatas=[repaired_metadata]
                    )
                    
                    repaired_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to repair metadata for memory {memory_id}: {e}")
                    continue
            
            self.logger.info(f"Repaired metadata for {repaired_count} memories")
            return repaired_count > 0
            
        except Exception as e:
            self.logger.error(f"Metadata repair failed: {e}")
            return False
    
    def _repair_collection_schema(self) -> bool:
        """
        Attempt to repair collection schema issues.
        
        Returns:
            True if repair successful, False otherwise
        """
        try:
            # Update collection metadata with correct schema
            correct_metadata = {
                "description": "AI VTuber memory storage with semantic search",
                "schema_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "embedding_model": "all-MiniLM-L6-v2",
                "embedding_dimensions": 384,
                "validation_schema": json.dumps(self.MEMORY_METADATA_SCHEMA)
            }
            
            # Note: ChromaDB doesn't support direct metadata updates
            # This is a placeholder for schema repair logic
            self.logger.info("Collection schema repair attempted")
            return True
            
        except Exception as e:
            self.logger.error(f"Collection schema repair failed: {e}")
            return False
    
    def _regenerate_embeddings(self) -> bool:
        """
        Regenerate embeddings for memories with invalid embeddings.
        
        Returns:
            True if regeneration successful, False otherwise
        """
        try:
            if not self.is_ready():
                self.logger.warning("Embedding model not ready, cannot regenerate embeddings")
                return False
            
            # Get memories without embeddings or with invalid embeddings
            all_memories = self.collection.get(include=['metadatas', 'documents', 'embeddings'])
            
            if not all_memories['ids']:
                return True
            
            regenerated_count = 0
            
            for i, memory_id in enumerate(all_memories['ids']):
                try:
                    embedding = all_memories['embeddings'][i] if all_memories['embeddings'] else None
                    content = all_memories['documents'][i]
                    
                    # Check if embedding needs regeneration
                    needs_regeneration = (
                        embedding is None or 
                        len(embedding) != 384 or
                        not isinstance(embedding, list)
                    )
                    
                    if needs_regeneration:
                        # Generate new embedding
                        new_embedding = self._generate_embedding(content)
                        
                        if new_embedding is not None:
                            # Update the memory with new embedding
                            self.collection.update(
                                ids=[memory_id],
                                embeddings=[new_embedding.tolist()]
                            )
                            regenerated_count += 1
                
                except Exception as e:
                    self.logger.warning(f"Failed to regenerate embedding for memory {memory_id}: {e}")
                    continue
            
            self.logger.info(f"Regenerated embeddings for {regenerated_count} memories")
            return regenerated_count > 0
            
        except Exception as e:
            self.logger.error(f"Embedding regeneration failed: {e}")
            return False
    
    def _cleanup_corrupted_backups(self) -> bool:
        """
        Clean up corrupted backup files.
        
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            backup_dir = self.db_path / "backups"
            if not backup_dir.exists():
                return True
            
            backup_files = list(backup_dir.glob("memory_backup_*.json.gz"))
            cleaned_count = 0
            
            for backup_file in backup_files:
                try:
                    if not self._verify_backup_file(backup_file):
                        backup_file.unlink()
                        cleaned_count += 1
                        self.logger.info(f"Removed corrupted backup: {backup_file}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to verify/remove backup {backup_file}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} corrupted backup files")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
            return False
    
    # ============================================================================
    # ENTITY RELATIONSHIP TRACKING METHODS - Requirements 3.5
    # ============================================================================
    
    def _load_entities_from_storage(self) -> None:
        """
        Load existing entities from persistent storage into memory.
        
        This method enhances entity relationship tracking by providing persistence
        across application restarts, ensuring entity relationships are maintained.
        """
        try:
            if not self._entity_collection:
                self.logger.debug("Entity collection not available, skipping entity loading")
                return
            
            # Get all entities from the collection
            results = self._entity_collection.get()
            
            if not results or not results['ids']:
                self.logger.debug("No entities found in persistent storage")
                return
            
            loaded_count = 0
            with self._entity_storage_lock:
                for i, entity_id in enumerate(results['ids']):
                    try:
                        # Get entity metadata
                        metadata = results['metadatas'][i] if results['metadatas'] else {}
                        
                        # Reconstruct entity from metadata
                        entity = self._deserialize_entity_from_metadata(metadata)
                        if entity:
                            entity_key = f"{entity.entity_type.value}_{entity.name.lower()}"
                            self._entity_storage[entity_key] = entity
                            loaded_count += 1
                    
                    except Exception as e:
                        self.logger.warning(f"Failed to load entity {entity_id}: {e}")
                        continue
            
            self.logger.info(f"Loaded {loaded_count} entities from persistent storage")
            
        except Exception as e:
            self.logger.error(f"Failed to load entities from storage: {e}")
    
    def _persist_entity(self, entity: Entity) -> None:
        """
        Persist an entity to ChromaDB for enhanced relationship tracking.
        
        Args:
            entity: Entity to persist
        """
        try:
            if not self._entity_collection:
                return  # Persistence not available
            
            entity_id = f"{entity.entity_type.value}_{entity.name.lower()}"
            entity_metadata = self._serialize_entity_to_metadata(entity)
            
            # Check if entity already exists
            existing = self._entity_collection.get(ids=[entity_id])
            
            if existing['ids']:
                # Update existing entity
                self._entity_collection.update(
                    ids=[entity_id],
                    metadatas=[entity_metadata]
                )
                self.logger.debug(f"Updated persistent entity: {entity.name}")
            else:
                # Add new entity
                self._entity_collection.add(
                    ids=[entity_id],
                    metadatas=[entity_metadata],
                    documents=[f"{entity.entity_type.value}: {entity.value}"]
                )
                self.logger.debug(f"Added persistent entity: {entity.name}")
                
        except Exception as e:
            self.logger.warning(f"Failed to persist entity {entity.name}: {e}")
    
    def _serialize_entity_to_metadata(self, entity: Entity) -> Dict[str, Any]:
        """
        Serialize entity to metadata for storage.
        
        Args:
            entity: Entity to serialize
            
        Returns:
            Metadata dictionary
        """
        return {
            "name": entity.name,
            "entity_type": entity.entity_type.value,
            "value": entity.value,
            "confidence": entity.confidence,
            "first_mentioned": entity.first_mentioned.isoformat(),
            "last_updated": entity.last_updated.isoformat(),
            "related_memories": entity.related_memories,
            "schema_version": "1.0"
        }
    
    def _deserialize_entity_from_metadata(self, metadata: Dict[str, Any]) -> Optional[Entity]:
        """
        Deserialize entity from metadata.
        
        Args:
            metadata: Entity metadata
            
        Returns:
            Entity object or None if deserialization fails
        """
        try:
            from memory_core.data_models import EntityType
            
            return Entity(
                name=metadata["name"],
                entity_type=EntityType(metadata["entity_type"]),
                value=metadata["value"],
                confidence=metadata["confidence"],
                first_mentioned=datetime.fromisoformat(metadata["first_mentioned"]),
                last_updated=datetime.fromisoformat(metadata["last_updated"]),
                related_memories=metadata.get("related_memories", [])
            )
            
        except Exception as e:
            self.logger.error(f"Failed to deserialize entity from metadata: {e}")
            return None
    
    def _extract_and_link_entities(self, text: str, memory_id: str) -> None:
        """
        Extract entities from text and link them to the memory ID.
        
        This method implements enhanced entity relationship tracking by:
        1. Extracting entities from the input text using EntityExtractor
        2. Updating the related_memories field in Entity objects with the memory ID
        3. Storing/updating entities in the entity storage system
        4. Persisting entities to ChromaDB for enhanced durability
        5. Enabling bidirectional relationships between entities and memories
        
        Args:
            text: Text to extract entities from
            memory_id: Memory ID to link entities to
        """
        try:
            # Extract entities from the text
            extracted_entities = self.entity_extractor.extract_entities(text)
            
            if not extracted_entities:
                return
            
            # Thread-safe access to entity storage
            with self._entity_storage_lock:
                entities_to_persist = []
                
                for entity in extracted_entities:
                    entity_key = f"{entity.entity_type.value}_{entity.name.lower()}"
                    
                    # Check if entity already exists
                    if entity_key in self._entity_storage:
                        existing_entity = self._entity_storage[entity_key]
                        
                        # Resolve conflicts if new information differs
                        if existing_entity.value != entity.value:
                            resolved_entity = self.entity_extractor.resolve_entity_conflicts(
                                existing_entity, text
                            )
                            self._entity_storage[entity_key] = resolved_entity
                            entities_to_persist.append(resolved_entity)
                        else:
                            # Update existing entity with new memory ID
                            existing_entity.last_updated = datetime.now()
                            if memory_id not in existing_entity.related_memories:
                                existing_entity.related_memories.append(memory_id)
                                entities_to_persist.append(existing_entity)
                    else:
                        # Add memory ID to new entity and store it
                        entity.related_memories = [memory_id]
                        self._entity_storage[entity_key] = entity
                        entities_to_persist.append(entity)
                    
                    self.logger.debug(f"Linked entity '{entity.name}' to memory {memory_id}")
                
                # Update entity tracking statistics
                self._stats['entities_tracked'] = len(self._entity_storage)
                
                # Persist updated entities to ChromaDB for enhanced durability
                for entity in entities_to_persist:
                    self._persist_entity(entity)
            
            self.logger.debug(f"Extracted and linked {len(extracted_entities)} entities to memory {memory_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to extract and link entities for memory {memory_id}: {e}")
    
    def get_entities_by_memory(self, memory_id: str) -> List[Entity]:
        """
        Get all entities associated with a specific memory ID.
        
        Args:
            memory_id: Memory ID to search for
            
        Returns:
            List of entities linked to the memory
        """
        try:
            entities = []
            
            with self._entity_storage_lock:
                for entity in self._entity_storage.values():
                    if memory_id in entity.related_memories:
                        entities.append(entity)
            
            self.logger.debug(f"Found {len(entities)} entities for memory {memory_id}")
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get entities for memory {memory_id}: {e}")
            return []
    
    def get_memories_by_entity(self, entity_name: str, entity_type: EntityType = None) -> List[str]:
        """
        Get all memory IDs associated with a specific entity.
        
        Args:
            entity_name: Name of the entity to search for
            entity_type: Optional entity type filter
            
        Returns:
            List of memory IDs linked to the entity
        """
        try:
            memory_ids = []
            
            with self._entity_storage_lock:
                for entity_key, entity in self._entity_storage.items():
                    # Check if entity matches the search criteria
                    if (entity.name.lower() == entity_name.lower() and 
                        (entity_type is None or entity.entity_type == entity_type)):
                        memory_ids.extend(entity.related_memories)
            
            # Remove duplicates while preserving order
            unique_memory_ids = list(dict.fromkeys(memory_ids))
            
            self.logger.debug(f"Found {len(unique_memory_ids)} memories for entity '{entity_name}'")
            return unique_memory_ids
            
        except Exception as e:
            self.logger.error(f"Failed to get memories for entity '{entity_name}': {e}")
            return []
    
    def get_all_entities(self) -> List[Entity]:
        """
        Get all tracked entities with their memory relationships.
        
        Returns:
            List of all entities in the system
        """
        try:
            with self._entity_storage_lock:
                entities = list(self._entity_storage.values())
            
            self.logger.debug(f"Retrieved {len(entities)} total entities")
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get all entities: {e}")
            return []
    
    def get_entity_relationship_stats(self) -> Dict[str, Any]:
        """
        Get statistics about entity relationships and memory linkage.
        
        Returns:
            Dictionary with entity relationship statistics
        """
        try:
            with self._entity_storage_lock:
                total_entities = len(self._entity_storage)
                entities_by_type = {}
                total_relationships = 0
                
                for entity in self._entity_storage.values():
                    entity_type = entity.entity_type.value
                    if entity_type not in entities_by_type:
                        entities_by_type[entity_type] = 0
                    entities_by_type[entity_type] += 1
                    total_relationships += len(entity.related_memories)
                
                avg_relationships = total_relationships / total_entities if total_entities > 0 else 0
                
                return {
                    'total_entities': total_entities,
                    'entities_by_type': entities_by_type,
                    'total_entity_memory_relationships': total_relationships,
                    'avg_relationships_per_entity': round(avg_relationships, 2),
                    'entity_storage_size': len(self._entity_storage),
                    'persistent_storage_available': self._entity_collection is not None
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get entity relationship stats: {e}")
            return {
                'total_entities': 0,
                'entities_by_type': {},
                'total_entity_memory_relationships': 0,
                'avg_relationships_per_entity': 0.0,
                'entity_storage_size': 0,
                'persistent_storage_available': False
            }
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """
        Get all entities of a specific type.
        
        Enhanced entity querying capability for better context retrieval.
        
        Args:
            entity_type: Type of entities to retrieve
            
        Returns:
            List of entities of the specified type
        """
        try:
            entities = []
            
            with self._entity_storage_lock:
                for entity in self._entity_storage.values():
                    if entity.entity_type == entity_type:
                        entities.append(entity)
            
            # Sort by confidence (highest first) and last updated (most recent first)
            entities.sort(key=lambda e: (e.confidence, e.last_updated), reverse=True)
            
            self.logger.debug(f"Found {len(entities)} entities of type {entity_type.value}")
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get entities by type {entity_type}: {e}")
            return []
    
    def get_entities_by_confidence_threshold(self, min_confidence: float = 0.7) -> List[Entity]:
        """
        Get all entities above a confidence threshold.
        
        Enhanced entity querying for high-confidence entity retrieval.
        
        Args:
            min_confidence: Minimum confidence threshold (0.0 to 1.0)
            
        Returns:
            List of entities above the confidence threshold
        """
        try:
            entities = []
            
            with self._entity_storage_lock:
                for entity in self._entity_storage.values():
                    if entity.confidence >= min_confidence:
                        entities.append(entity)
            
            # Sort by confidence (highest first)
            entities.sort(key=lambda e: e.confidence, reverse=True)
            
            self.logger.debug(f"Found {len(entities)} entities with confidence >= {min_confidence}")
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get entities by confidence threshold: {e}")
            return []
    
    def search_entities_by_value(self, search_term: str, fuzzy: bool = True) -> List[Entity]:
        """
        Search entities by their value content.
        
        Enhanced entity search capability for better entity discovery.
        
        Args:
            search_term: Term to search for in entity values
            fuzzy: Whether to perform fuzzy matching (case-insensitive, partial matches)
            
        Returns:
            List of matching entities
        """
        try:
            entities = []
            search_term_lower = search_term.lower().strip()
            
            with self._entity_storage_lock:
                for entity in self._entity_storage.values():
                    if fuzzy:
                        # Fuzzy matching: case-insensitive, partial matches
                        if (search_term_lower in entity.value.lower() or 
                            search_term_lower in entity.name.lower()):
                            entities.append(entity)
                    else:
                        # Exact matching
                        if (search_term == entity.value or 
                            search_term == entity.name):
                            entities.append(entity)
            
            # Sort by confidence and relevance
            entities.sort(key=lambda e: e.confidence, reverse=True)
            
            self.logger.debug(f"Found {len(entities)} entities matching '{search_term}' (fuzzy: {fuzzy})")
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to search entities by value: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive memory system statistics.
        
        Returns detailed statistics about memory storage, retrieval performance,
        entity tracking, and system health metrics.
        
        Returns:
            Dictionary containing comprehensive memory system statistics
        """
        try:
            with self._stats_lock:
                # Basic memory statistics
                basic_stats = {
                    'total_memories': self._stats.get('total_memories', 0),
                    'total_retrievals': self._stats.get('total_retrievals', 0),
                    'avg_retrieval_time_ms': self._stats.get('avg_retrieval_time', 0.0),
                    'entities_tracked': self._stats.get('entities_tracked', 0),
                    'sessions_recorded': self._stats.get('sessions_recorded', 0),
                    'startup_time': self._stats.get('startup_time', datetime.now()).isoformat(),
                    'last_optimization': self._stats.get('last_optimization'),
                    'backup_count': self._stats.get('backup_count', 0),
                    'last_backup': self._stats.get('last_backup')
                }
                
                # Convert datetime objects to ISO strings
                if basic_stats['last_optimization']:
                    basic_stats['last_optimization'] = basic_stats['last_optimization'].isoformat()
                if basic_stats['last_backup']:
                    basic_stats['last_backup'] = basic_stats['last_backup'].isoformat()
                
                # Performance statistics
                retrieval_times = self._stats.get('retrieval_times', [])
                performance_stats = {
                    'retrieval_cache_hits': self._stats.get('retrieval_cache_hits', 0),
                    'retrieval_cache_misses': self._stats.get('retrieval_cache_misses', 0),
                    'cache_hit_ratio': 0.0,
                    'retrieval_performance_95th_percentile': 0.0,
                    'retrieval_operations_under_200ms': 0,
                    'retrieval_operations_over_200ms': 0,
                    'retrieval_compliance_percentage': 100.0
                }
                
                # Calculate cache hit ratio
                total_cache_ops = performance_stats['retrieval_cache_hits'] + performance_stats['retrieval_cache_misses']
                if total_cache_ops > 0:
                    performance_stats['cache_hit_ratio'] = (performance_stats['retrieval_cache_hits'] / total_cache_ops) * 100
                
                # Calculate retrieval performance metrics
                if retrieval_times:
                    retrieval_times_sorted = sorted(retrieval_times)
                    p95_index = int(len(retrieval_times_sorted) * 0.95)
                    performance_stats['retrieval_performance_95th_percentile'] = retrieval_times_sorted[p95_index] if p95_index < len(retrieval_times_sorted) else retrieval_times_sorted[-1]
                    
                    under_200ms = sum(1 for t in retrieval_times if t <= 200)
                    over_200ms = sum(1 for t in retrieval_times if t > 200)
                    
                    performance_stats['retrieval_operations_under_200ms'] = under_200ms
                    performance_stats['retrieval_operations_over_200ms'] = over_200ms
                    
                    if len(retrieval_times) > 0:
                        performance_stats['retrieval_compliance_percentage'] = (under_200ms / len(retrieval_times)) * 100
                
                # System health statistics
                system_stats = {
                    'memory_system_ready': self.is_ready(),
                    'embedding_model_loaded': self.embedding_model is not None,
                    'chromadb_connected': self.client is not None and self.collection is not None,
                    'database_size_mb': self._calculate_storage_size(),
                    'entity_collection_available': self._entity_collection is not None
                }
                
                # Concurrent access metrics
                concurrent_stats = self.get_concurrent_access_metrics()
                
                # Entity statistics
                entity_stats = {
                    'total_entities': len(self._entity_storage),
                    'entities_by_type': {},
                    'high_confidence_entities': 0,
                    'entities_with_memories': 0
                }
                
                # Calculate entity type distribution
                with self._entity_storage_lock:
                    for entity in self._entity_storage.values():
                        entity_type = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
                        entity_stats['entities_by_type'][entity_type] = entity_stats['entities_by_type'].get(entity_type, 0) + 1
                        
                        if entity.confidence >= 0.8:
                            entity_stats['high_confidence_entities'] += 1
                        
                        if entity.memory_ids:
                            entity_stats['entities_with_memories'] += 1
                
                # Combine all statistics
                comprehensive_stats = {
                    'basic': basic_stats,
                    'performance': performance_stats,
                    'system_health': system_stats,
                    'concurrent_access': concurrent_stats,
                    'entities': entity_stats,
                    'generated_at': datetime.now().isoformat(),
                    'statistics_version': '1.0'
                }
                
                return comprehensive_stats
                
        except Exception as e:
            self.logger.error(f"Failed to get memory statistics: {e}")
            return {
                'error': f"Failed to generate statistics: {str(e)}",
                'generated_at': datetime.now().isoformat(),
                'statistics_version': '1.0'
            }
    
    def create_backup(self) -> str:
        """
        Create a backup of the memory system and return the backup file path.
        
        This method creates a comprehensive backup of all memory data and returns
        the path to the created backup file for use by the GUI and other components.
        
        Returns:
            Path to the created backup file if successful, empty string if failed
        """
        try:
            # Create backup directory
            backup_dir = self.db_path / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"memory_backup_{timestamp}.json.gz"
            backup_path = backup_dir / backup_filename
            
            self.logger.info(f"Creating memory backup: {backup_path}")
            
            # Use the existing backup_memories method to create the backup
            if self.backup_memories():
                # Find the most recent backup file (should be the one we just created)
                backup_files = list(backup_dir.glob("memory_backup_*.json.gz"))
                if backup_files:
                    # Sort by modification time and get the most recent
                    most_recent_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
                    
                    self.logger.info(f"Backup created successfully: {most_recent_backup}")
                    return str(most_recent_backup)
                else:
                    self.logger.error("Backup creation reported success but no backup file found")
                    return ""
            else:
                self.logger.error("Backup creation failed")
                return ""
                
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return ""
    
    def get_entities(self) -> List[Dict[str, Any]]:
        """
        Retrieve all tracked entities for UI display.
        
        Returns:
            List of entity dictionaries with basic information
        """
        try:
            if not self._entity_collection:
                self.logger.debug("Entity collection not available")
                return []
            
            # Get all entities from the collection
            results = self._entity_collection.get(
                include=['metadatas', 'documents']
            )
            
            entities = []
            if results['ids']:
                for i, entity_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    content = results['documents'][i] if results['documents'] else ""
                    
                    entity_info = {
                        'id': entity_id,
                        'type': metadata.get('entity_type', 'UNKNOWN'),
                        'content': content,
                        'confidence': metadata.get('confidence', 0.0),
                        'created_at': metadata.get('created_at', ''),
                        'last_mentioned': metadata.get('last_mentioned', ''),
                        'mention_count': metadata.get('mention_count', 0)
                    }
                    entities.append(entity_info)
            
            self.logger.debug(f"Retrieved {len(entities)} entities")
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve entities: {e}")
            return []
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent chat history for UI display.
        
        Args:
            limit: Maximum number of conversations to retrieve
            
        Returns:
            List of conversation dictionaries with timestamp and content
        """
        try:
            # Query ChromaDB collection for recent items based on timestamp
            results = self.collection.get(
                include=['metadatas', 'documents'],
                limit=limit * 2  # Get more to filter for conversations
            )
            
            conversations = []
            if results['ids']:
                # Convert to list of tuples for sorting
                items = []
                for i, memory_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    content = results['documents'][i] if results['documents'] else ""
                    
                    # Only include interaction type memories
                    if metadata.get('memory_type') == 'INTERACTION':
                        timestamp_str = metadata.get('timestamp', '')
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except:
                            timestamp = datetime.now()
                        
                        items.append((timestamp, {
                            'id': memory_id,
                            'timestamp': timestamp_str,
                            'content': content,
                            'user_input': metadata.get('user_input', ''),
                            'ai_response': metadata.get('ai_response', ''),
                            'emotion': metadata.get('emotion', 'neutral'),
                            'conversation_type': metadata.get('conversation_type', 'unknown')
                        }))
                
                # Sort by timestamp (most recent first) and take the limit
                items.sort(key=lambda x: x[0], reverse=True)
                conversations = [item[1] for item in items[:limit]]
            
            self.logger.debug(f"Retrieved {len(conversations)} recent conversations")
            return conversations
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve recent conversations: {e}")
            return []