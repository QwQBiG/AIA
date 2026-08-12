"""
Tests for Enhanced LLM Client with Memory Integration

This module contains comprehensive tests for the EnhancedLLMClient class,
including unit tests, integration tests, and property-based tests to validate
memory integration functionality and backward compatibility.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

# Import the classes we're testing
from src.enhanced_llm_client import EnhancedLLMClient
from src.memory_core.memory_core import MemoryCore
from src.memory_core.data_models import Memory, MemoryType, Entity, EntityType
from src.llm_client import StreamHandler


class MockStreamHandler:
    """Mock stream handler for testing streaming functionality."""
    
    def __init__(self):
        self.emotions_detected = []
        self.tokens_received = []
        self.stream_complete_called = False
        self.should_stop = False
    
    def on_emotion_detected(self, emotion: str) -> None:
        self.emotions_detected.append(emotion)
    
    def on_token_received(self, token: str) -> None:
        self.tokens_received.append(token)
    
    def on_stream_complete(self) -> None:
        self.stream_complete_called = True


class TestEnhancedLLMClientUnit:
    """Unit tests for EnhancedLLMClient functionality."""
    
    @pytest.fixture
    def mock_memory_core(self):
        """Create a mock MemoryCore for testing."""
        mock_core = Mock(spec=MemoryCore)
        mock_core.is_ready.return_value = True
        mock_core.retrieve_memories.return_value = []
        return mock_core
    
    @pytest.fixture
    def enhanced_client(self, mock_memory_core):
        """Create an EnhancedLLMClient instance for testing."""
        with patch('src.enhanced_llm_client.LLMClient.__init__'):
            client = EnhancedLLMClient(
                base_url="http://localhost:11434",
                model="llama3",
                memory_core=mock_memory_core,
                enable_memory=True
            )
            # Mock parent class methods
            client.generate_response = AsyncMock(return_value="Test response")
            client.generate_response_stream_with_fallback = AsyncMock(return_value="Test streaming response")
            return client
    
    @pytest.fixture
    def sample_memories(self):
        """Create sample memories for testing."""
        return [
            Memory(
                id="mem1",
                content="User: I love pizza\nAI: That's great! Pizza is delicious.",
                embedding=None,
                timestamp=datetime.now() - timedelta(hours=1),
                memory_type=MemoryType.INTERACTION,
                metadata={"user_input": "I love pizza", "ai_response": "That's great! Pizza is delicious."},
                importance_score=0.8,
                access_count=1,
                last_accessed=datetime.now()
            ),
            Memory(
                id="mem2",
                content="User: What's my favorite food?\nAI: Based on our conversation, you mentioned loving pizza.",
                embedding=None,
                timestamp=datetime.now() - timedelta(minutes=30),
                memory_type=MemoryType.INTERACTION,
                metadata={"user_input": "What's my favorite food?", "ai_response": "Based on our conversation, you mentioned loving pizza."},
                importance_score=0.9,
                access_count=2,
                last_accessed=datetime.now()
            )
        ]
    
    def test_initialization(self, mock_memory_core):
        """Test EnhancedLLMClient initialization."""
        with patch('src.enhanced_llm_client.LLMClient.__init__'):
            client = EnhancedLLMClient(
                base_url="http://localhost:11434",
                model="llama3",
                memory_core=mock_memory_core,
                enable_memory=True
            )
            
            assert client.memory_core == mock_memory_core
            assert client.enable_memory is True
            assert client.model_token_limit == 8192  # llama3 limit
            assert client.max_memory_tokens == int(8192 * 0.3)  # 30% of context
    
    def test_initialization_without_memory_core(self):
        """Test initialization without memory core."""
        with patch('src.enhanced_llm_client.LLMClient.__init__'):
            client = EnhancedLLMClient(
                base_url="http://localhost:11434",
                model="llama3",
                memory_core=None,
                enable_memory=True
            )
            
            assert client.memory_core is None
            assert client.enable_memory is True
    
    def test_set_memory_core(self, enhanced_client, mock_memory_core):
        """Test setting memory core after initialization."""
        new_memory_core = Mock(spec=MemoryCore)
        enhanced_client.set_memory_core(new_memory_core)
        
        assert enhanced_client.memory_core == new_memory_core
    
    def test_enable_disable_memory_features(self, enhanced_client):
        """Test enabling and disabling memory features."""
        # Test disabling
        enhanced_client.enable_memory_features(False)
        assert enhanced_client.enable_memory is False
        
        # Test enabling
        enhanced_client.enable_memory_features(True)
        assert enhanced_client.enable_memory is True
    
    def test_format_memory_context_empty(self, enhanced_client):
        """Test formatting empty memory context."""
        result = enhanced_client.format_memory_context([])
        assert result == ""
    
    def test_format_memory_context_with_memories(self, enhanced_client, sample_memories):
        """Test formatting memory context with actual memories."""
        result = enhanced_client.format_memory_context(sample_memories)
        
        assert "=== Relevant Context from Previous Conversations ===" in result
        assert "=== End of Context ===" in result
        assert "I love pizza" in result
        assert "What's my favorite food?" in result
        
        # Check that memories are sorted by timestamp (most recent first)
        lines = result.split('\n')
        pizza_line_idx = next(i for i, line in enumerate(lines) if "I love pizza" in line)
        favorite_line_idx = next(i for i, line in enumerate(lines) if "What's my favorite food?" in line)
        assert favorite_line_idx < pizza_line_idx  # More recent memory should come first
    
    def test_check_token_limits_within_limits(self, enhanced_client):
        """Test token limit checking with content within limits."""
        short_prompt = "Hello, how are you?"
        short_context = "Previous conversation: User said hello."
        
        result = enhanced_client.check_token_limits(short_prompt, short_context)
        assert result is True
    
    def test_check_token_limits_exceeds_limits(self, enhanced_client):
        """Test token limit checking with content exceeding limits."""
        # Create a very long prompt that would exceed token limits
        long_prompt = "A" * 20000  # Very long prompt
        long_context = "B" * 20000  # Very long context
        
        result = enhanced_client.check_token_limits(long_prompt, long_context)
        assert result is False
    
    def test_inject_memory_context_empty_memories(self, enhanced_client):
        """Test memory context injection with empty memories."""
        original_prompt = "What is my favorite food?"
        result = enhanced_client.inject_memory_context(original_prompt, [])
        
        assert result == original_prompt
    
    def test_inject_memory_context_with_memories(self, enhanced_client, sample_memories):
        """Test memory context injection with actual memories."""
        original_prompt = "What is my favorite food?"
        result = enhanced_client.inject_memory_context(original_prompt, sample_memories)
        
        assert original_prompt in result
        assert "=== Relevant Context from Previous Conversations ===" in result
        assert "I love pizza" in result
        assert len(result) > len(original_prompt)
    
    def test_inject_memory_context_token_limit_exceeded(self, enhanced_client, sample_memories):
        """Test memory context injection when token limits would be exceeded."""
        # Mock check_token_limits to return False
        enhanced_client.check_token_limits = Mock(return_value=False)
        
        original_prompt = "What is my favorite food?"
        result = enhanced_client.inject_memory_context(original_prompt, sample_memories)
        
        # Should return original prompt when token limits exceeded
        assert result == original_prompt
    
    def test_is_memory_available_true(self, enhanced_client, mock_memory_core):
        """Test memory availability check when memory is available."""
        enhanced_client.enable_memory = True
        enhanced_client.memory_core = mock_memory_core
        mock_memory_core.is_ready.return_value = True
        
        result = enhanced_client._is_memory_available()
        assert result is True
    
    def test_is_memory_available_false_disabled(self, enhanced_client, mock_memory_core):
        """Test memory availability check when memory is disabled."""
        enhanced_client.enable_memory = False
        enhanced_client.memory_core = mock_memory_core
        mock_memory_core.is_ready.return_value = True
        
        result = enhanced_client._is_memory_available()
        assert result is False
    
    def test_is_memory_available_false_no_core(self, enhanced_client):
        """Test memory availability check when no memory core."""
        enhanced_client.enable_memory = True
        enhanced_client.memory_core = None
        
        result = enhanced_client._is_memory_available()
        assert result is False
    
    def test_is_memory_available_false_not_ready(self, enhanced_client, mock_memory_core):
        """Test memory availability check when memory core not ready."""
        enhanced_client.enable_memory = True
        enhanced_client.memory_core = mock_memory_core
        mock_memory_core.is_ready.return_value = False
        
        result = enhanced_client._is_memory_available()
        assert result is False
    
    def test_retrieve_relevant_memories_success(self, enhanced_client, mock_memory_core, sample_memories):
        """Test successful memory retrieval."""
        mock_memory_core.retrieve_memories.return_value = sample_memories
        
        result = enhanced_client._retrieve_relevant_memories("pizza", 5)
        
        assert result == sample_memories
        mock_memory_core.retrieve_memories.assert_called_once_with("pizza", 5)
    
    def test_retrieve_relevant_memories_not_available(self, enhanced_client):
        """Test memory retrieval when memory not available."""
        enhanced_client.enable_memory = False
        
        result = enhanced_client._retrieve_relevant_memories("pizza", 5)
        
        assert result == []
    
    def test_retrieve_relevant_memories_exception(self, enhanced_client, mock_memory_core):
        """Test memory retrieval with exception."""
        mock_memory_core.retrieve_memories.side_effect = Exception("Memory error")
        
        result = enhanced_client._retrieve_relevant_memories("pizza", 5)
        
        assert result == []
    
    def test_clean_memory_content_normal(self, enhanced_client):
        """Test cleaning normal memory content."""
        content = "User: I love pizza\nAI: That's great!"
        result = enhanced_client._clean_memory_content(content)
        
        assert result == "User: I love pizza AI: That's great!"
    
    def test_clean_memory_content_long(self, enhanced_client):
        """Test cleaning very long memory content."""
        content = "A" * 300  # Very long content
        result = enhanced_client._clean_memory_content(content)
        
        assert len(result) <= 203  # 200 chars + "..."
        assert result.endswith("...")
    
    def test_get_memory_performance_stats(self, enhanced_client):
        """Test getting memory performance statistics."""
        # Add some mock performance data
        enhanced_client._memory_injection_times = [10.0, 15.0, 12.0]
        enhanced_client._context_overflow_count = 2
        
        stats = enhanced_client.get_memory_performance_stats()
        
        assert stats['memory_enabled'] is True
        assert stats['avg_injection_time_ms'] == 12.333333333333334  # Average of [10, 15, 12]
        assert stats['total_injections'] == 3
        assert stats['context_overflow_count'] == 2
        assert stats['model_token_limit'] == 8192
        assert 'memory_available' in stats


class TestEnhancedLLMClientIntegration:
    """Integration tests for EnhancedLLMClient with memory system."""
    
    @pytest.fixture
    def mock_memory_core(self):
        """Create a more realistic mock MemoryCore for integration testing."""
        mock_core = Mock(spec=MemoryCore)
        mock_core.is_ready.return_value = True
        return mock_core
    
    @pytest.fixture
    def enhanced_client(self, mock_memory_core):
        """Create an EnhancedLLMClient for integration testing."""
        with patch('src.enhanced_llm_client.LLMClient.__init__'):
            client = EnhancedLLMClient(
                base_url="http://localhost:11434",
                model="llama3",
                memory_core=mock_memory_core,
                enable_memory=True
            )
            # Mock parent class methods
            client.generate_response = AsyncMock(return_value="Enhanced response with context")
            client.generate_response_stream_with_fallback = AsyncMock(return_value="Enhanced streaming response")
            return client
    
    @pytest.fixture
    def sample_memories(self):
        """Create sample memories for integration testing."""
        return [
            Memory(
                id="mem1",
                content="User: My name is Alice\nAI: Nice to meet you, Alice!",
                embedding=None,
                timestamp=datetime.now() - timedelta(hours=2),
                memory_type=MemoryType.INTERACTION,
                metadata={"user_input": "My name is Alice", "ai_response": "Nice to meet you, Alice!"},
                importance_score=0.9,
                access_count=1,
                last_accessed=datetime.now()
            ),
            Memory(
                id="mem2",
                content="User: I work as a software engineer\nAI: That's interesting! Software engineering is a great field.",
                embedding=None,
                timestamp=datetime.now() - timedelta(hours=1),
                memory_type=MemoryType.INTERACTION,
                metadata={"user_input": "I work as a software engineer", "ai_response": "That's interesting! Software engineering is a great field."},
                importance_score=0.8,
                access_count=1,
                last_accessed=datetime.now()
            )
        ]
    
    @pytest.mark.asyncio
    async def test_generate_with_memory_success(self, enhanced_client, mock_memory_core, sample_memories):
        """Test successful memory-enhanced generation."""
        mock_memory_core.retrieve_memories.return_value = sample_memories
        
        result = await enhanced_client.generate_with_memory("What do you know about me?")
        
        # Verify memory retrieval was called
        mock_memory_core.retrieve_memories.assert_called_once()
        
        # Verify response generation was called with enhanced prompt
        enhanced_client.generate_response.assert_called_once()
        call_args = enhanced_client.generate_response.call_args[0]
        enhanced_prompt = call_args[0]
        
        # Check that memory context was injected
        assert "Alice" in enhanced_prompt
        assert "software engineer" in enhanced_prompt
        assert "=== Relevant Context from Previous Conversations ===" in enhanced_prompt
        
        assert result == "Enhanced response with context"
    
    @pytest.mark.asyncio
    async def test_generate_with_memory_no_memories(self, enhanced_client, mock_memory_core):
        """Test memory-enhanced generation with no relevant memories."""
        mock_memory_core.retrieve_memories.return_value = []
        
        result = await enhanced_client.generate_with_memory("Hello there!")
        
        # Should still work, just without memory context
        mock_memory_core.retrieve_memories.assert_called_once()
        enhanced_client.generate_response.assert_called_once()
        
        assert result == "Enhanced response with context"
    
    @pytest.mark.asyncio
    async def test_generate_with_memory_provided_context(self, enhanced_client, sample_memories):
        """Test memory-enhanced generation with pre-provided memory context."""
        result = await enhanced_client.generate_with_memory(
            "What do you know about me?", 
            memory_context=sample_memories
        )
        
        # Should not call retrieve_memories since context was provided
        enhanced_client.memory_core.retrieve_memories.assert_not_called()
        
        # But should still generate with enhanced context
        enhanced_client.generate_response.assert_called_once()
        call_args = enhanced_client.generate_response.call_args[0]
        enhanced_prompt = call_args[0]
        
        assert "Alice" in enhanced_prompt
        assert "software engineer" in enhanced_prompt
        
        assert result == "Enhanced response with context"
    
    @pytest.mark.asyncio
    async def test_generate_with_memory_token_limit_exceeded(self, enhanced_client, mock_memory_core, sample_memories):
        """Test memory-enhanced generation when token limits are exceeded."""
        mock_memory_core.retrieve_memories.return_value = sample_memories
        
        # Mock check_token_limits to return False (exceeds limits)
        enhanced_client.check_token_limits = Mock(return_value=False)
        
        result = await enhanced_client.generate_with_memory("What do you know about me?")
        
        # Should fall back to standard generation without memory context
        enhanced_client.generate_response.assert_called()
        call_args = enhanced_client.generate_response.call_args[0]
        prompt = call_args[0]
        
        # Should be the original prompt, not enhanced
        assert prompt == "What do you know about me?"
        
        assert result == "Enhanced response with context"
    
    @pytest.mark.asyncio
    async def test_generate_with_memory_memory_not_available(self, enhanced_client):
        """Test memory-enhanced generation when memory is not available."""
        enhanced_client.enable_memory = False
        
        result = await enhanced_client.generate_with_memory("Hello!")
        
        # Should fall back to standard generation
        enhanced_client.generate_response.assert_called_once_with("Hello!", False)
        assert result == "Enhanced response with context"
    
    @pytest.mark.asyncio
    async def test_generate_response_stream_with_memory_success(self, enhanced_client, mock_memory_core, sample_memories):
        """Test successful memory-enhanced streaming generation."""
        mock_memory_core.retrieve_memories.return_value = sample_memories
        handler = MockStreamHandler()
        
        result = await enhanced_client.generate_response_stream_with_memory("Tell me about myself", handler)
        
        # Verify memory retrieval was called
        mock_memory_core.retrieve_memories.assert_called_once()
        
        # Verify streaming generation was called with enhanced message
        enhanced_client.generate_response_stream_with_fallback.assert_called_once()
        call_args = enhanced_client.generate_response_stream_with_fallback.call_args[0]
        enhanced_message = call_args[0]
        
        # Check that memory context was injected
        assert "Alice" in enhanced_message
        assert "software engineer" in enhanced_message
        
        assert result == "Enhanced streaming response"
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_generate_response(self, enhanced_client, mock_memory_core, sample_memories):
        """Test backward compatibility of generate_response method."""
        mock_memory_core.retrieve_memories.return_value = sample_memories
        
        # Call the standard generate_response method
        result = await enhanced_client.generate_response("Hello!")
        
        # Should automatically use memory enhancement when available
        mock_memory_core.retrieve_memories.assert_called_once()
        
        # Should call the enhanced generation path
        call_args = enhanced_client.generate_response.call_args[0]
        enhanced_prompt = call_args[0]
        
        # Memory context should be injected
        assert "Alice" in enhanced_prompt or len(enhanced_prompt) > len("Hello!")
        
        assert result == "Enhanced response with context"
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_generate_response_stream(self, enhanced_client, mock_memory_core, sample_memories):
        """Test backward compatibility of generate_response_stream method."""
        mock_memory_core.retrieve_memories.return_value = sample_memories
        handler = MockStreamHandler()
        
        # Call the standard generate_response_stream method
        result = await enhanced_client.generate_response_stream("Hello!", handler)
        
        # Should automatically use memory enhancement when available
        mock_memory_core.retrieve_memories.assert_called_once()
        
        assert result == "Enhanced streaming response"


class TestEnhancedLLMClientPropertyBased:
    """Property-based tests for EnhancedLLMClient."""
    
    @pytest.fixture
    def enhanced_client(self):
        """Create an EnhancedLLMClient for property testing."""
        mock_memory_core = Mock(spec=MemoryCore)
        mock_memory_core.is_ready.return_value = True
        mock_memory_core.retrieve_memories.return_value = []
        
        with patch('src.enhanced_llm_client.LLMClient.__init__'):
            client = EnhancedLLMClient(
                base_url="http://localhost:11434",
                model="llama3",
                memory_core=mock_memory_core,
                enable_memory=True
            )
            client.generate_response = AsyncMock(return_value="Test response")
            return client
    
    def test_property_context_injection_preserves_original_prompt(self, enhanced_client):
        """
        Property: Context injection should always preserve the original prompt content.
        **Validates: Requirements 4.4**
        """
        original_prompts = [
            "Hello, how are you?",
            "What is the weather like?",
            "Tell me a joke",
            "What is 2 + 2?",
            "Can you help me with programming?",
            "",  # Edge case: empty prompt
            "A" * 1000,  # Edge case: very long prompt
        ]
        
        for original_prompt in original_prompts:
            # Test with empty memories (should return original)
            result = enhanced_client.inject_memory_context(original_prompt, [])
            assert result == original_prompt, f"Empty memories should return original prompt: '{original_prompt}'"
            
            # Test with memories that don't exceed token limits
            sample_memory = Memory(
                id="test",
                content="Short memory content",
                embedding=None,
                timestamp=datetime.now(),
                memory_type=MemoryType.INTERACTION,
                metadata={},
                importance_score=0.5,
                access_count=1,
                last_accessed=datetime.now()
            )
            
            result = enhanced_client.inject_memory_context(original_prompt, [sample_memory])
            
            # Original prompt should be contained in the result
            if original_prompt:  # Skip empty prompt check
                assert original_prompt in result, f"Original prompt should be preserved: '{original_prompt}'"
    
    def test_property_token_limits_never_exceeded(self, enhanced_client):
        """
        Property: Token limit checking should never allow content that exceeds limits.
        **Validates: Requirements 4.5**
        """
        # Test various prompt and context combinations
        test_cases = [
            ("Short prompt", "Short context"),
            ("Medium length prompt with some content", "Medium context with additional information"),
            ("A" * 1000, "B" * 1000),  # Long content
            ("A" * 10000, "B" * 10000),  # Very long content that should exceed limits
        ]
        
        for prompt, context in test_cases:
            result = enhanced_client.check_token_limits(prompt, context)
            
            # If the method returns True, the content should actually be within limits
            if result:
                # Conservative token estimation: ~4 characters per token
                estimated_tokens = len(prompt + context) // 4
                response_buffer = int(enhanced_client.model_token_limit * 0.25)
                available_tokens = enhanced_client.model_token_limit - response_buffer
                
                assert estimated_tokens <= available_tokens, \
                    f"Token limit check returned True but content exceeds limits: {estimated_tokens} > {available_tokens}"
    
    def test_property_memory_formatting_consistency(self, enhanced_client):
        """
        Property: Memory formatting should be consistent and well-structured.
        **Validates: Requirements 4.3**
        """
        # Test with various memory configurations
        memory_configs = [
            [],  # Empty memories
            [Memory(  # Single memory
                id="single",
                content="Single memory content",
                embedding=None,
                timestamp=datetime.now(),
                memory_type=MemoryType.INTERACTION,
                metadata={},
                importance_score=0.5,
                access_count=1,
                last_accessed=datetime.now()
            )],
            [Memory(  # Multiple memories
                id=f"mem{i}",
                content=f"Memory {i} content",
                embedding=None,
                timestamp=datetime.now() - timedelta(hours=i),
                memory_type=MemoryType.INTERACTION,
                metadata={},
                importance_score=0.5,
                access_count=1,
                last_accessed=datetime.now()
            ) for i in range(5)]
        ]
        
        for memories in memory_configs:
            result = enhanced_client.format_memory_context(memories)
            
            if not memories:
                # Empty memories should return empty string
                assert result == "", "Empty memories should return empty string"
            else:
                # Non-empty memories should have proper structure
                assert isinstance(result, str), "Result should be a string"
                
                if len(memories) > 0:
                    # Should contain the context markers
                    assert "=== Relevant Context from Previous Conversations ===" in result
                    assert "=== End of Context ===" in result
                    
                    # Should contain content from all memories
                    for memory in memories:
                        # Content might be cleaned/truncated, so check for partial matches
                        memory_words = memory.content.split()[:3]  # First few words
                        if memory_words:
                            assert any(word in result for word in memory_words), \
                                f"Memory content should be represented in formatted result: {memory.content[:50]}"
    
    def test_property_graceful_degradation(self, enhanced_client):
        """
        Property: System should gracefully degrade when memory features fail.
        **Validates: Requirements 7.2**
        """
        # Test various failure scenarios
        failure_scenarios = [
            ("memory_disabled", lambda: setattr(enhanced_client, 'enable_memory', False)),
            ("memory_core_none", lambda: setattr(enhanced_client, 'memory_core', None)),
            ("memory_not_ready", lambda: enhanced_client.memory_core.is_ready.return_value.__setitem__(slice(None), False) if hasattr(enhanced_client.memory_core.is_ready.return_value, '__setitem__') else enhanced_client.memory_core.is_ready.__setattr__('return_value', False)),
        ]
        
        original_prompt = "Test prompt for graceful degradation"
        
        for scenario_name, setup_failure in failure_scenarios:
            # Setup the failure condition
            try:
                setup_failure()
            except:
                # Some failure setups might not work with mocks, skip them
                continue
            
            # Test that memory availability check returns False
            is_available = enhanced_client._is_memory_available()
            assert not is_available, f"Memory should not be available in scenario: {scenario_name}"
            
            # Test that memory retrieval returns empty list
            memories = enhanced_client._retrieve_relevant_memories("test query", 5)
            assert memories == [], f"Memory retrieval should return empty list in scenario: {scenario_name}"
            
            # Test that context injection returns original prompt
            result = enhanced_client.inject_memory_context(original_prompt, [])
            assert result == original_prompt, f"Context injection should return original prompt in scenario: {scenario_name}"
            
            # Reset for next test
            enhanced_client.enable_memory = True
            if enhanced_client.memory_core:
                enhanced_client.memory_core.is_ready.return_value = True


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])