"""
Unit and property tests for LLM Client

Feature: ai-vtuber-system
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from hypothesis import given, strategies as st
import aiohttp
from aioresponses import aioresponses

from src.llm_client import LLMClient, ChatMessage


class TestLLMClientPropertyTests:
    """Property-based tests for LLMClient."""
    
    @given(st.text(min_size=1, max_size=1000))
    def test_network_request_processing_property(self, user_message):
        """
        Property 1: Network Request Processing
        For any user input message, the LLM_Client should send a POST request 
        to the Ollama API and return the generated response text.
        
        Feature: ai-vtuber-system, Property 1: Network Request Processing
        Validates: Requirements 1.4, 1.5
        """
        # Filter out problematic characters that might cause issues
        safe_message = user_message.strip()
        if not safe_message:
            safe_message = "test message"
        
        client = LLMClient()
        
        # Mock response from Ollama API
        mock_response = {
            "message": {
                "role": "assistant",
                "content": f"Response to: {safe_message}"
            }
        }
        
        async def run_test():
            with aioresponses() as m:
                # Mock the API endpoint
                m.post(
                    f"{client.base_url}/api/chat",
                    payload=mock_response,
                    status=200
                )
                
                # Test the request processing
                response = await client.generate_response(safe_message, return_structured=False)
                
                # Verify response is returned
                assert isinstance(response, str)
                assert len(response) > 0
                assert "Response to:" in response
                
                # Verify the request was made
                assert len(m.requests) == 1
                
                # Get the request details - aioresponses stores requests differently
                request_calls = list(m.requests.keys())
                assert len(request_calls) == 1
                
                # Verify the URL was called
                method, url = request_calls[0]
                assert method == 'POST'
                assert url.path == '/api/chat'
                assert str(url).startswith(client.base_url)
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(st.text(min_size=1, max_size=1000))
    def test_structured_response_parsing_resilience_property(self, raw_response):
        """
        Property 1: Structured Response Parsing Resilience
        For any LLM response text, the Emotional Intelligence System should always 
        produce a valid structured response with text content and a valid emotion tag, 
        defaulting to "neutral" when parsing fails.
        
        Feature: ai-vtuber-emotional-intelligence, Property 1: Structured Response Parsing Resilience
        Validates: Requirements 1.1, 1.2, 1.5, 6.3
        """
        client = LLMClient()
        
        # Parse the response using the structured response parser
        structured_response = client._parse_structured_response(raw_response)
        
        # Verify the response always has the required structure
        assert isinstance(structured_response, dict)
        assert 'text' in structured_response
        assert 'emotion' in structured_response
        
        # Verify text is always a string
        assert isinstance(structured_response['text'], str)
        
        # Verify emotion is always a valid emotion tag
        valid_emotions = {'neutral', 'happy', 'angry', 'sad', 'surprised'}
        assert structured_response['emotion'] in valid_emotions
        
        # Verify that if parsing fails, we get neutral emotion and the original text
        if not any(char in raw_response for char in '{}'):
            # If no JSON-like structure, should fallback to neutral
            assert structured_response['emotion'] == 'neutral'
            assert structured_response['text'] == raw_response.strip()
    
    @given(st.text(min_size=1, max_size=200).filter(lambda x: '{' not in x and '}' not in x))
    def test_json_extraction_robustness_property(self, surrounding_text):
        """
        Property 2: JSON Extraction Robustness
        For any text containing JSON blocks (even embedded in conversational text), 
        the regex extraction should successfully identify and parse the JSON content.
        
        Feature: ai-vtuber-emotional-intelligence, Property 2: JSON Extraction Robustness
        Validates: Requirements 1.5
        """
        client = LLMClient()
        
        # Create valid JSON structures to embed in text
        valid_json_examples = [
            '{"emotion": "happy", "text": "Hello world!"}',
            '{"emotion": "neutral", "text": "This is a test"}',
            '{"emotion": "sad", "text": "Goodbye"}',
        ]
        
        for json_str in valid_json_examples:
            # Test 1: JSON in markdown code blocks
            markdown_text = f"{surrounding_text}\n```json\n{json_str}\n```\n{surrounding_text}"
            extracted = client._extract_json_from_text(markdown_text)
            assert extracted is not None
            assert isinstance(extracted, dict)
            assert 'emotion' in extracted
            assert 'text' in extracted
            
            # Test 2: JSON embedded in conversational text
            embedded_text = f"{surrounding_text} {json_str} {surrounding_text}"
            extracted = client._extract_json_from_text(embedded_text)
            assert extracted is not None
            assert isinstance(extracted, dict)
            assert 'emotion' in extracted
            assert 'text' in extracted
            
            # Test 3: JSON with extra whitespace
            whitespace_text = f"{surrounding_text}\n\n  {json_str}  \n\n{surrounding_text}"
            extracted = client._extract_json_from_text(whitespace_text)
            assert extracted is not None
            assert isinstance(extracted, dict)
        
        # Test 4: Text with no JSON should return None
        no_json_text = surrounding_text
        extracted = client._extract_json_from_text(no_json_text)
        assert extracted is None
    
    @given(st.sampled_from(['neutral', 'happy', 'angry', 'sad', 'surprised', 'invalid', 'unknown', '']))
    def test_emotion_tag_validation_property(self, emotion_tag):
        """
        Property 3: Emotion Tag Validation
        For any emotion tag input, the system should only accept valid emotions 
        ("neutral", "happy", "angry", "sad", "surprised") and handle invalid emotions gracefully.
        
        Feature: ai-vtuber-emotional-intelligence, Property 3: Emotion Tag Validation
        Validates: Requirements 1.3
        """
        client = LLMClient()
        
        # Create a JSON response with the given emotion tag
        json_response = f'{{"emotion": "{emotion_tag}", "text": "Test message"}}'
        
        # Parse the structured response
        structured_response = client._parse_structured_response(json_response)
        
        # Verify the response structure
        assert isinstance(structured_response, dict)
        assert 'text' in structured_response
        assert 'emotion' in structured_response
        
        # Valid emotions should be preserved
        valid_emotions = {'neutral', 'happy', 'angry', 'sad', 'surprised'}
        if emotion_tag in valid_emotions:
            assert structured_response['emotion'] == emotion_tag
        else:
            # Invalid emotions should default to 'neutral'
            assert structured_response['emotion'] == 'neutral'
        
        # Text should always be preserved
        assert structured_response['text'] == "Test message"


class TestLLMClientUnitTests:
    """Unit tests for LLMClient."""
    
    def test_client_initialization(self):
        """Test LLMClient initialization with default and custom parameters."""
        # Test default initialization
        client = LLMClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model == "llama3"
        assert client.is_connected() is False
        
        # Test custom initialization
        custom_client = LLMClient(
            base_url="http://custom:8080",
            model="custom_model"
        )
        assert custom_client.base_url == "http://custom:8080"
        assert custom_client.model == "custom_model"
    
    def test_base_url_normalization(self):
        """Test that base URL is properly normalized."""
        client = LLMClient(base_url="http://localhost:11434/")
        assert client.base_url == "http://localhost:11434"
    
    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test successful connection to Ollama service."""
        client = LLMClient()
        
        with aioresponses() as m:
            m.get(f"{client.base_url}/api/tags", status=200, payload={"models": []})
            
            result = await client.connect()
            
            assert result is True
            assert client.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_connection_failure_http_error(self):
        """Test connection failure due to HTTP error."""
        client = LLMClient()
        
        with aioresponses() as m:
            m.get(f"{client.base_url}/api/tags", status=500)
            
            result = await client.connect()
            
            assert result is False
            assert client.is_connected() is False
    
    @pytest.mark.asyncio
    async def test_connection_failure_network_error(self):
        """Test connection failure due to network error."""
        client = LLMClient()
        
        with aioresponses() as m:
            m.get(f"{client.base_url}/api/tags", exception=aiohttp.ClientError("Network error"))
            
            result = await client.connect()
            
            assert result is False
            assert client.is_connected() is False
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test successful response generation."""
        client = LLMClient()
        
        mock_response = {
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you?"
            }
        }
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", payload=mock_response, status=200)
            
            response = await client.generate_response("Hello")
            
            assert response == "Hello! How can I help you?"
    
    @pytest.mark.asyncio
    async def test_generate_response_empty_message(self):
        """Test response generation with empty message."""
        client = LLMClient()
        
        with pytest.raises(ValueError, match="Message cannot be empty"):
            await client.generate_response("")
        
        with pytest.raises(ValueError, match="Message cannot be empty"):
            await client.generate_response("   ")
    
    @pytest.mark.asyncio
    async def test_generate_response_api_error(self):
        """Test response generation with API error."""
        client = LLMClient()
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", status=500, payload={"error": "Internal server error"})
            
            with pytest.raises(Exception, match="Ollama API error: HTTP 500"):
                await client.generate_response("Hello")
    
    @pytest.mark.asyncio
    async def test_generate_response_invalid_format(self):
        """Test response generation with invalid response format."""
        client = LLMClient()
        
        # Response missing required fields
        invalid_response = {"invalid": "format"}
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", payload=invalid_response, status=200)
            
            with pytest.raises(Exception, match="Invalid response format from Ollama API"):
                await client.generate_response("Hello")
    
    @pytest.mark.asyncio
    async def test_generate_response_timeout(self):
        """Test response generation with timeout."""
        client = LLMClient()
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", exception=asyncio.TimeoutError())
            
            with pytest.raises(Exception, match="Request to Ollama API timed out"):
                await client.generate_response("Hello")
    
    def test_generate_response_sync(self):
        """Test synchronous wrapper for generate_response."""
        client = LLMClient()
        
        mock_response = {
            "message": {
                "role": "assistant", 
                "content": "Sync response"
            }
        }
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", payload=mock_response, status=200)
            
            response = client.generate_response_sync("Hello")
            
            assert response == "Sync response"


class TestChatMessage:
    """Unit tests for ChatMessage data model."""
    
    def test_chat_message_creation(self):
        """Test ChatMessage creation."""
        message = ChatMessage(role="user", content="Hello world")
        
        assert message.role == "user"
        assert message.content == "Hello world"
    
    def test_chat_message_validation(self):
        """Test ChatMessage with different roles."""
        user_msg = ChatMessage(role="user", content="User message")
        assistant_msg = ChatMessage(role="assistant", content="Assistant message")
        
        assert user_msg.role == "user"
        assert assistant_msg.role == "assistant"


class TestLLMClientEmotionalIntelligence:
    """Unit tests for emotional intelligence features."""
    
    def test_system_prompt_validation(self):
        """Test system prompt contains required elements."""
        client = LLMClient()
        
        # Test that validation passes for the default prompt
        assert client.validate_system_prompt() is True
        
        # Test that the prompt contains required elements
        prompt = client.VTUBER_SYSTEM_PROMPT.lower()
        required_elements = ["json", "emotion", "text", "neutral", "happy", "angry", "sad", "surprised"]
        for element in required_elements:
            assert element in prompt
    
    def test_structured_response_parsing_valid_json(self):
        """Test parsing of valid JSON responses."""
        client = LLMClient()
        
        # Test valid JSON response
        json_response = '{"emotion": "happy", "text": "Hello world!"}'
        result = client._parse_structured_response(json_response)
        
        assert result['emotion'] == 'happy'
        assert result['text'] == 'Hello world!'
    
    def test_structured_response_parsing_invalid_emotion(self):
        """Test parsing with invalid emotion defaults to neutral."""
        client = LLMClient()
        
        # Test invalid emotion
        json_response = '{"emotion": "excited", "text": "Hello world!"}'
        result = client._parse_structured_response(json_response)
        
        assert result['emotion'] == 'neutral'
        assert result['text'] == 'Hello world!'
    
    def test_structured_response_parsing_fallback(self):
        """Test fallback to plain text when JSON parsing fails."""
        client = LLMClient()
        
        # Test plain text response
        plain_response = "Hello, this is a plain text response!"
        result = client._parse_structured_response(plain_response)
        
        assert result['emotion'] == 'neutral'
        assert result['text'] == 'Hello, this is a plain text response!'
    
    def test_json_extraction_markdown_blocks(self):
        """Test JSON extraction from markdown code blocks."""
        client = LLMClient()
        
        # Test markdown JSON block
        markdown_text = '''Here's the response:
        
```json
{"emotion": "happy", "text": "Great!"}
```

Hope that helps!'''
        
        result = client._extract_json_from_text(markdown_text)
        assert result is not None
        assert result['emotion'] == 'happy'
        assert result['text'] == 'Great!'
    
    def test_json_extraction_embedded_json(self):
        """Test JSON extraction from embedded JSON in text."""
        client = LLMClient()
        
        # Test embedded JSON
        embedded_text = 'Sure! {"emotion": "neutral", "text": "Here you go"} Let me know if you need more help.'
        
        result = client._extract_json_from_text(embedded_text)
        assert result is not None
        assert result['emotion'] == 'neutral'
        assert result['text'] == 'Here you go'
    
    def test_json_extraction_no_json(self):
        """Test JSON extraction returns None when no JSON present."""
        client = LLMClient()
        
        # Test text with no JSON
        no_json_text = "This is just plain text with no JSON structure at all."
        
        result = client._extract_json_from_text(no_json_text)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_response_structured_mode(self):
        """Test generate_response with structured response mode."""
        client = LLMClient()
        
        # Mock structured JSON response
        mock_response = {
            "message": {
                "role": "assistant",
                "content": '{"emotion": "happy", "text": "Hello! Nice to meet you!"}'
            }
        }
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", payload=mock_response, status=200)
            
            response = await client.generate_response("Hello", return_structured=True)
            
            assert isinstance(response, dict)
            assert response['emotion'] == 'happy'
            assert response['text'] == 'Hello! Nice to meet you!'
    
    @pytest.mark.asyncio
    async def test_generate_response_backward_compatibility(self):
        """Test generate_response maintains backward compatibility."""
        client = LLMClient()
        
        # Mock plain text response
        mock_response = {
            "message": {
                "role": "assistant",
                "content": "Hello! Nice to meet you!"
            }
        }
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", payload=mock_response, status=200)
            
            response = await client.generate_response("Hello", return_structured=False)
            
            assert isinstance(response, str)
            assert response == "Hello! Nice to meet you!"
    
    def test_generate_response_sync_structured(self):
        """Test synchronous wrapper with structured responses."""
        client = LLMClient()
        
        # Mock structured JSON response
        mock_response = {
            "message": {
                "role": "assistant",
                "content": '{"emotion": "neutral", "text": "Sync response test"}'
            }
        }
        
        with aioresponses() as m:
            m.post(f"{client.base_url}/api/chat", payload=mock_response, status=200)
            
            response = client.generate_response_sync("Hello", return_structured=True)
            
            assert isinstance(response, dict)
            assert response['emotion'] == 'neutral'
            assert response['text'] == 'Sync response test'