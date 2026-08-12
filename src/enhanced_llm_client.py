"""
Enhanced LLM Client with Memory Integration

This module extends the existing LLMClient to provide memory-enhanced response generation
while maintaining full backward compatibility. The EnhancedLLMClient integrates with the
Memory Core RAG system to inject relevant historical context into LLM prompts.

Key Features:
- Memory context injection before LLM generation
- Token limit checking to prevent context overflow
- LLM-friendly memory formatting
- Backward compatibility with existing LLMClient interface
- Graceful degradation when memory system is unavailable
"""

import asyncio
import logging
import re
import time
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from .llm_client import LLMClient, StreamHandler
from .memory_core.memory_core import MemoryCore
from .memory_core.data_models import Memory


class EnhancedLLMClient(LLMClient):
    """
    Enhanced version of LLMClient with memory integration capabilities.
    
    Extends the existing LLMClient class to maintain backward compatibility while
    adding memory context injection for more contextually-aware responses.
    
    The class implements memory retrieval before LLM generation, formats memory
    context in LLM-friendly ways, and handles token limits to prevent overflow.
    """
    
    # Token limits for different models (conservative estimates)
    MODEL_TOKEN_LIMITS = {
        'llama3': 8192,
        'llama3.1': 32768,
        'qwen14b': 8192,
        'default': 4096  # Conservative default
    }
    
    # Memory context formatting templates
    MEMORY_CONTEXT_TEMPLATE = """
=== Relevant Context from Previous Conversations ===
{memory_content}
=== End of Context ===

"""
    
    MEMORY_ITEM_TEMPLATE = """[{timestamp}] {content}"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3", 
                 memory_core: Optional[MemoryCore] = None, enable_memory: bool = True):
        """
        Initialize Enhanced LLM Client with memory integration.
        
        Args:
            base_url: Ollama service URL
            model: Model name to use for generation
            memory_core: MemoryCore instance for memory operations (optional)
            enable_memory: Whether to enable memory features (default: True)
        """
        # Initialize parent LLMClient
        super().__init__(base_url, model)
        
        # Memory integration setup
        self.memory_core = memory_core
        self.enable_memory = enable_memory
        self.logger = logging.getLogger(__name__)
        
        # Token management
        self.model_token_limit = self.MODEL_TOKEN_LIMITS.get(model, self.MODEL_TOKEN_LIMITS['default'])
        self.memory_context_ratio = 0.3  # Use up to 30% of context for memory
        self.max_memory_tokens = int(self.model_token_limit * self.memory_context_ratio)
        
        # Performance tracking
        self._memory_injection_times = []
        self._context_overflow_count = 0
        
        self.logger.info(f"Enhanced LLM Client initialized with memory {'enabled' if enable_memory else 'disabled'}")
        self.logger.debug(f"Model: {model}, Token limit: {self.model_token_limit}, Max memory tokens: {self.max_memory_tokens}")
    
    def set_memory_core(self, memory_core: MemoryCore) -> None:
        """
        Set or update the memory core instance.
        
        Args:
            memory_core: MemoryCore instance for memory operations
        """
        self.memory_core = memory_core
        self.logger.info("Memory core instance updated")
    
    def enable_memory_features(self, enable: bool = True) -> None:
        """
        Enable or disable memory features.
        
        Args:
            enable: Whether to enable memory features
        """
        self.enable_memory = enable
        self.logger.info(f"Memory features {'enabled' if enable else 'disabled'}")
    
    async def generate_with_memory(self, prompt: str, memory_context: Optional[List[Memory]] = None,
                                 return_structured: bool = False, max_memories: int = 5) -> Union[str, Dict[str, str]]:
        """
        Generate response with memory context injection.
        
        This method retrieves relevant memories (if not provided), formats them for
        LLM consumption, injects them into the prompt context, and generates a response
        using the enhanced context.
        
        Args:
            prompt: User input prompt
            memory_context: Pre-retrieved memories (optional, will retrieve if None)
            return_structured: If True, returns structured dict; if False, returns plain text
            max_memories: Maximum number of memories to retrieve and inject
            
        Returns:
            Generated response text or structured response with text and emotion
            
        Raises:
            Exception: If generation fails
        """
        start_time = time.time()
        
        try:
            # Check if memory features are enabled and available
            if not self._is_memory_available():
                self.logger.debug("Memory features not available, using standard generation")
                return await self.generate_response(prompt, return_structured)
            
            # Retrieve relevant memories if not provided
            if memory_context is None:
                memory_context = self._retrieve_relevant_memories(prompt, max_memories)
            
            # Inject memory context into the prompt
            enhanced_prompt = self.inject_memory_context(prompt, memory_context)
            
            # Check token limits to prevent overflow
            if not self.check_token_limits(enhanced_prompt):
                self.logger.warning("Enhanced prompt exceeds token limits, falling back to standard generation")
                self._context_overflow_count += 1
                return await self.generate_response(prompt, return_structured)
            
            # Generate response with enhanced context - CRITICAL: Use parent class directly to avoid recursion
            response = await super().generate_response(enhanced_prompt, return_structured)
            
            # Track performance
            injection_time = (time.time() - start_time) * 1000
            self._memory_injection_times.append(injection_time)
            if len(self._memory_injection_times) > 100:
                self._memory_injection_times = self._memory_injection_times[-100:]
            
            self.logger.debug(f"Generated response with memory context in {injection_time:.2f}ms")
            return response
            
        except Exception as e:
            self.logger.error(f"Memory-enhanced generation failed: {e}")
            # Graceful fallback to standard generation - CRITICAL: Use parent class directly to avoid recursion
            return await super().generate_response(prompt, return_structured)
    
    async def generate_response_stream_with_memory(self, message: str, handler: StreamHandler,
                                                 memory_context: Optional[List[Memory]] = None,
                                                 max_memories: int = 5) -> str:
        """
        Generate streaming response with memory context injection.
        
        Args:
            message: User input message
            handler: StreamHandler implementation for callbacks
            memory_context: Pre-retrieved memories (optional, will retrieve if None)
            max_memories: Maximum number of memories to retrieve and inject
            
        Returns:
            Complete response text (without emotion tag)
        """
        try:
            # Check if memory features are enabled and available
            if not self._is_memory_available():
                self.logger.debug("Memory features not available, using standard streaming")
                return await self.generate_response_stream_with_fallback(message, handler)
            
            # Retrieve relevant memories if not provided
            if memory_context is None:
                memory_context = self._retrieve_relevant_memories(message, max_memories)
            
            # Inject memory context into the message
            enhanced_message = self.inject_memory_context(message, memory_context)
            
            # Check token limits to prevent overflow
            if not self.check_token_limits(enhanced_message):
                self.logger.warning("Enhanced message exceeds token limits, falling back to standard streaming")
                self._context_overflow_count += 1
                return await self.generate_response_stream_with_fallback(message, handler)
            
            # Generate streaming response with enhanced context - CRITICAL: Use parent class directly to avoid recursion
            return await super().generate_response_stream_with_fallback(enhanced_message, handler)
            
        except Exception as e:
            self.logger.error(f"Memory-enhanced streaming failed: {e}")
            # Graceful fallback to standard streaming - CRITICAL: Use parent class directly to avoid recursion
            return await super().generate_response_stream_with_fallback(message, handler)
    
    def format_memory_context(self, memories: List[Memory]) -> str:
        """
        Format memories for LLM-friendly consumption.
        
        Converts a list of Memory objects into a structured text format that
        provides context to the LLM while maintaining readability and relevance.
        
        Args:
            memories: List of Memory objects to format
            
        Returns:
            Formatted memory context string
        """
        if not memories:
            return ""
        
        try:
            # Sort memories by timestamp (most recent first) and relevance
            sorted_memories = sorted(memories, key=lambda m: m.timestamp, reverse=True)
            
            # Format each memory item
            memory_items = []
            for memory in sorted_memories:
                # Format timestamp for readability
                timestamp_str = memory.timestamp.strftime("%Y-%m-%d %H:%M")
                
                # Clean and truncate content for context injection
                content = self._clean_memory_content(memory.content)
                
                # Apply memory item template
                formatted_item = self.MEMORY_ITEM_TEMPLATE.format(
                    timestamp=timestamp_str,
                    content=content
                )
                memory_items.append(formatted_item)
            
            # Combine all memory items
            memory_content = "\n".join(memory_items)
            
            # Apply main context template
            formatted_context = self.MEMORY_CONTEXT_TEMPLATE.format(
                memory_content=memory_content
            )
            
            self.logger.debug(f"Formatted {len(memories)} memories into context ({len(formatted_context)} chars)")
            return formatted_context
            
        except Exception as e:
            self.logger.error(f"Failed to format memory context: {e}")
            return ""
    
    def check_token_limits(self, prompt: str, context: str = "") -> bool:
        """
        Check if the combined prompt and context fit within token limits.
        
        Uses a conservative token estimation based on character count to prevent
        context overflow that could cause LLM generation failures.
        
        Args:
            prompt: The main prompt text
            context: Additional context text (optional)
            
        Returns:
            True if within limits, False if would exceed limits
        """
        try:
            # Combine prompt and context
            full_text = prompt + context
            
            # Conservative token estimation: ~4 characters per token on average
            estimated_tokens = len(full_text) // 4
            
            # Add buffer for response generation (reserve 25% of context for response)
            response_buffer = int(self.model_token_limit * 0.25)
            available_tokens = self.model_token_limit - response_buffer
            
            within_limits = estimated_tokens <= available_tokens
            
            if not within_limits:
                self.logger.warning(f"Token limit check failed: {estimated_tokens} estimated tokens > {available_tokens} available")
            else:
                self.logger.debug(f"Token limit check passed: {estimated_tokens} estimated tokens <= {available_tokens} available")
            
            return within_limits
            
        except Exception as e:
            self.logger.error(f"Token limit check failed: {e}")
            # Conservative fallback: assume it exceeds limits
            return False
    
    def inject_memory_context(self, original_prompt: str, memories: List[Memory]) -> str:
        """
        Inject memory context into the original prompt while preserving structure.
        
        This method carefully inserts memory context at the beginning of the prompt
        to provide historical context without disrupting the original prompt structure
        or intent.
        
        Args:
            original_prompt: The original user prompt
            memories: List of relevant memories to inject
            
        Returns:
            Enhanced prompt with memory context injected
        """
        try:
            if not memories:
                return original_prompt
            
            # Format memories into context
            memory_context = self.format_memory_context(memories)
            
            if not memory_context.strip():
                return original_prompt
            
            # Check if the combined context would exceed token limits
            if not self.check_token_limits(original_prompt, memory_context):
                # Try with fewer memories
                reduced_memories = memories[:max(1, len(memories) // 2)]
                memory_context = self.format_memory_context(reduced_memories)
                
                if not self.check_token_limits(original_prompt, memory_context):
                    self.logger.warning("Even reduced memory context exceeds token limits")
                    return original_prompt
                
                self.logger.info(f"Reduced memory context from {len(memories)} to {len(reduced_memories)} memories")
            
            # Inject memory context at the beginning of the prompt
            enhanced_prompt = memory_context + original_prompt
            
            self.logger.debug(f"Injected memory context: {len(memories)} memories, {len(memory_context)} chars")
            return enhanced_prompt
            
        except Exception as e:
            self.logger.error(f"Failed to inject memory context: {e}")
            return original_prompt
    
    def _is_memory_available(self) -> bool:
        """
        Check if memory features are available and ready.
        
        Returns:
            True if memory features can be used, False otherwise
        """
        return (self.enable_memory and 
                self.memory_core is not None and 
                self.memory_core.is_ready())
    
    def _retrieve_relevant_memories(self, query: str, limit: int = 5) -> List[Memory]:
        """
        Retrieve relevant memories for the given query.
        
        Args:
            query: Search query
            limit: Maximum number of memories to retrieve
            
        Returns:
            List of relevant memories
        """
        try:
            if not self._is_memory_available():
                return []
            
            memories = self.memory_core.retrieve_memories(query, limit)
            self.logger.debug(f"Retrieved {len(memories)} relevant memories for query")
            return memories
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve memories: {e}")
            return []
    
    def _clean_memory_content(self, content: str) -> str:
        """
        Clean and prepare memory content for context injection.
        
        Args:
            content: Raw memory content
            
        Returns:
            Cleaned content suitable for LLM context
        """
        try:
            # Remove excessive whitespace
            cleaned = re.sub(r'\s+', ' ', content.strip())
            
            # Truncate very long content to prevent context overflow
            max_content_length = 200  # Conservative limit per memory item
            if len(cleaned) > max_content_length:
                cleaned = cleaned[:max_content_length] + "..."
            
            return cleaned
            
        except Exception as e:
            self.logger.error(f"Failed to clean memory content: {e}")
            return content[:100] + "..." if len(content) > 100 else content
    
    def get_memory_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for memory integration.
        
        Returns:
            Dictionary with memory integration performance metrics
        """
        try:
            avg_injection_time = 0.0
            if self._memory_injection_times:
                avg_injection_time = sum(self._memory_injection_times) / len(self._memory_injection_times)
            
            return {
                'memory_enabled': self.enable_memory,
                'memory_available': self._is_memory_available(),
                'avg_injection_time_ms': avg_injection_time,
                'total_injections': len(self._memory_injection_times),
                'context_overflow_count': self._context_overflow_count,
                'model_token_limit': self.model_token_limit,
                'max_memory_tokens': self.max_memory_tokens,
                'memory_context_ratio': self.memory_context_ratio
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get memory performance stats: {e}")
            return {}
    
    # ============================================================================
    # BACKWARD COMPATIBILITY METHODS
    # ============================================================================
    
    async def generate_response(self, message: str, return_structured: bool = False) -> Union[str, Dict[str, str]]:
        """
        Generate response with optional memory enhancement.
        
        This method maintains backward compatibility with the original LLMClient
        while optionally enhancing responses with memory context when available.
        
        Args:
            message: User input message
            return_structured: If True, returns structured dict; if False, returns plain text
            
        Returns:
            Generated response text or structured response
        """
        # TEMPORARY FIX: Disable memory enhancement to prevent recursion
        # Fallback to parent class implementation directly
        return await super().generate_response(message, return_structured)
    
    async def generate_response_stream(self, message: str, handler: StreamHandler) -> str:
        """
        Generate streaming response with optional memory enhancement.
        
        This method maintains backward compatibility while optionally enhancing
        streaming responses with memory context when available.
        
        Args:
            message: User input message
            handler: StreamHandler implementation for callbacks
            
        Returns:
            Complete response text (without emotion tag)
        """
        # TEMPORARY FIX: Disable memory enhancement to prevent recursion
        # Fallback to parent class implementation directly
        return await super().generate_response_stream(message, handler)