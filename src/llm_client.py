"""
LLM Client for Ollama API integration
This module handles communication with the local Ollama service
把人设什么的都放在这了，不好，之后为了可以定制化是要放在图形界面的！
"""

import asyncio
import json
import logging
import re
from typing import Optional, Dict, Any, Protocol, runtime_checkable
import aiohttp
import requests
from .llm.base import BaseLLMClient, StreamHandler
from dataclasses import dataclass


@dataclass
class ChatMessage:
    """Chat message data model"""
    role: str  # "user" or "assistant"
    content: str


@runtime_checkable
class StreamHandler(Protocol):
    """Protocol interface for handling streaming responses."""
    
    def on_emotion_detected(self, emotion: str) -> None:
        """Called when an emotion tag is detected at the start of the response."""
        ...
    
    def on_token_received(self, token: str) -> None:
        """Called when a new token is received from the stream."""
        ...
    
    def on_stream_complete(self) -> None:
        """Called when the stream is complete."""
        ...


class LLMClient:
    """Backward-compatible LLM client.

    Delegates to the appropriate backend (Ollama / KoboldCpp) via the
    ``src.llm`` adapter layer.  Use *config* to choose the backend;
    defaults to Ollama when *config* is ``None``.
    """
    
    # VTuber character system prompt for structured JSON responses (legacy)
    VTUBER_SYSTEM_PROMPT = """你是一个名叫娜娜的 VTuber。你活泼、可爱，有点傲娇。

响应格式：你必须使用以下模式以严格的 JSON 格式响应：
{
  "emotion": "neutral, happy, angry, sad, surprised 中的一个",
  "text": "你的口语响应内容"
}

重要规则：
1. 只能使用这5种情感标签：neutral, happy, angry, sad, surprised
2. 不要在 JSON 对象外输出任何文本
3. 确保 JSON 格式正确，使用双引号
4. text 字段应该包含你作为娜娜的自然对话回应

示例：
{"emotion": "happy", "text": "哇！你好呀！我是娜娜，很高兴见到你！"}
{"emotion": "neutral", "text": "嗯，我明白了。还有什么我可以帮助你的吗？"}
{"emotion": "surprised", "text": "诶？！真的吗？这太令人惊讶了！"}"""

    # VTuber character system prompt for Tag-based streaming responses (new)
    VTUBER_STREAM_PROMPT = """你是一个名叫娜娜的 VTuber。你活泼、可爱，有点傲娇。

响应格式：使用 [emotion] 标签开头，然后是你的回复内容。
可用情绪标签：[neutral], [happy], [angry], [sad], [surprised]

示例：
[happy] 哇！你好呀！我是娜娜，很高兴见到你！
[neutral] 嗯，我明白了。还有什么我可以帮助你的吗？
[surprised] 诶？！真的吗？这太令人惊讶了！

重要：必须以情绪标签开头，标签后直接跟文字内容。"""

    # Valid emotion tags
    VALID_EMOTIONS = {'neutral', 'happy', 'angry', 'sad', 'surprised'}
    
    # Regex pattern for extracting emotion tags
    EMOTION_TAG_PATTERN = re.compile(r'^\s*\[(\w+)\]\s*')
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3", *, config=None):
        if config is not None:
            from .llm.factory import create_llm_client
            self._backend: BaseLLMClient = create_llm_client(config)
            base_url = self._backend.base_url
            model = self._backend.model
        else:
            from .llm.ollama import OllamaClient
            self._backend: BaseLLMClient = OllamaClient(base_url, model)
        """
        Initialize LLM Client
        
        Args:
            base_url: Ollama service URL
            model: Model name to use for generation
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.is_connected_flag = False
        self.logger = logging.getLogger(__name__)
        self.use_structured_responses = True  # Flag to enable/disable structured responses
        self.enable_streaming = True  # Flag to enable/disable streaming mode
    
    def validate_system_prompt(self, streaming: bool = False) -> bool:
        """
        Validate that the system prompt contains required elements
        
        Args:
            streaming: If True, validate the streaming prompt; otherwise validate JSON prompt
        
        Returns:
            bool: True if prompt is valid, False otherwise
        """
        if streaming:
            # Validate streaming prompt
            required_elements = [
                "[neutral]",
                "[happy]", 
                "[angry]",
                "[sad]",
                "[surprised]"
            ]
            prompt = self.VTUBER_STREAM_PROMPT
        else:
            # Validate JSON prompt
            required_elements = [
                "JSON",
                "emotion",
                "text",
                "neutral",
                "happy", 
                "angry",
                "sad",
                "surprised"
            ]
            prompt = self.VTUBER_SYSTEM_PROMPT
        
        prompt_lower = prompt.lower()
        for element in required_elements:
            if element.lower() not in prompt_lower:
                self.logger.error(f"System prompt missing required element: {element}")
                return False
        
        return True
        
    async def connect(self) -> bool:
        """
        Test connection to Ollama service
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Test connection with a simple request to the API
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=5) as response:
                    if response.status == 200:
                        self.is_connected_flag = True
                        self.logger.info(f"Successfully connected to Ollama at {self.base_url}")
                        return True
                    else:
                        self.is_connected_flag = False
                        self.logger.error(f"Failed to connect to Ollama: HTTP {response.status}")
                        return False
        except Exception as e:
            self.is_connected_flag = False
            self.logger.error(f"Connection to Ollama failed: {str(e)}")
            return False
    
    def is_connected(self) -> bool:
        """
        Check if client is connected to Ollama service
        
        Returns:
            bool: Connection status
        """
        return self.is_connected_flag
    
    async def generate_response(self, message: str, return_structured: bool = False) -> str | Dict[str, str]:
        """
        Generate response from Ollama API
        
        Args:
            message: User input message
            return_structured: If True, returns structured dict; if False, returns plain text for backward compatibility
            
        Returns:
            str or Dict[str, str]: Generated response text or structured response with text and emotion
            
        Raises:
            Exception: If request fails or service unavailable
        """
        if not message.strip():
            raise ValueError("Message cannot be empty")
        
        # Prepare messages with system prompt for structured responses
        messages = []
        if self.use_structured_responses and return_structured:
            messages.append({"role": "system", "content": self.VTUBER_SYSTEM_PROMPT})
        
        messages.append({"role": "user", "content": message})
            
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=120  # Increased timeout for larger models like qwen14b
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        # Extract response content
                        if "message" in result and "content" in result["message"]:
                            response_text = result["message"]["content"]
                            self.logger.info(f"Generated response: {response_text[:100]}...")
                            
                            # Return structured response if requested and enabled
                            if self.use_structured_responses and return_structured:
                                structured_response = self._parse_structured_response(response_text)
                                return structured_response
                            else:
                                # Backward compatibility: return plain text
                                return response_text
                        else:
                            raise Exception("Invalid response format from Ollama API")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: HTTP {response.status} - {error_text}")
                        
        except asyncio.TimeoutError:
            self.logger.error("Request to Ollama API timed out")
            raise Exception("Request to Ollama API timed out")
        except Exception as e:
            self.logger.error(f"Failed to generate response: {str(e)}")
            raise
    
    async def generate_response_stream(
        self, 
        message: str, 
        handler: StreamHandler
    ) -> str:
        """
        Generate response from Ollama API using streaming mode.
        
        This method streams tokens as they are generated, allowing for:
        1. Immediate emotion tag detection and VTS trigger
        2. Real-time text display
        3. Early sentence detection for TTS pipeline
        
        Args:
            message: User input message
            handler: StreamHandler implementation for callbacks
            
        Returns:
            str: Complete response text (without emotion tag)
            
        Raises:
            Exception: If request fails or service unavailable
        """
        if not message.strip():
            raise ValueError("Message cannot be empty")
        
        # Prepare messages with streaming system prompt
        messages = [
            {"role": "system", "content": self.VTUBER_STREAM_PROMPT},
            {"role": "user", "content": message}
        ]
        
        # Prepare request payload with streaming enabled
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        
        full_response = ""
        emotion_detected = False
        emotion_buffer = ""  # Buffer for detecting emotion tag at start
        
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: HTTP {response.status} - {error_text}")
                    
                    # Process streaming response
                    async for line in response.content:
                        if not line:
                            continue
                        
                        # Check if handler wants to stop streaming
                        if hasattr(handler, 'should_stop') and handler.should_stop:
                            self.logger.info("Stream stopped by handler request")
                            break
                        
                        try:
                            # Parse JSON from each line
                            data = json.loads(line.decode('utf-8'))
                            
                            if "message" in data and "content" in data["message"]:
                                token = data["message"]["content"]
                                full_response += token
                                
                                # Try to detect emotion tag at the start
                                if not emotion_detected:
                                    emotion_buffer += token
                                    emotion, remaining_text = self._extract_emotion_tag(emotion_buffer)
                                    
                                    if emotion:
                                        # Emotion tag found
                                        emotion_detected = True
                                        handler.on_emotion_detected(emotion)
                                        self.logger.info(f"Detected emotion tag: [{emotion}]")
                                        
                                        # Send remaining text after tag as tokens
                                        if remaining_text:
                                            handler.on_token_received(remaining_text)
                                    elif len(emotion_buffer) > 20:
                                        # No emotion tag found after 20 chars, use default
                                        emotion_detected = True
                                        handler.on_emotion_detected('neutral')
                                        self.logger.warning("No emotion tag found, using default 'neutral'")
                                        handler.on_token_received(emotion_buffer)
                                else:
                                    # Emotion already detected, just forward tokens
                                    handler.on_token_received(token)
                                
                                # Check again after token processing in case handler set stop flag
                                if hasattr(handler, 'should_stop') and handler.should_stop:
                                    self.logger.info("Stream stopped by handler after token processing")
                                    break
                            
                            # Check if stream is done
                            if data.get("done", False):
                                break
                                
                        except json.JSONDecodeError:
                            # Skip invalid JSON lines
                            continue
                    
                    # Handle case where no emotion was detected at all
                    if not emotion_detected and emotion_buffer:
                        handler.on_emotion_detected('neutral')
                        handler.on_token_received(emotion_buffer)
                    
                    # Signal stream completion
                    handler.on_stream_complete()
                    
                    self.logger.info(f"Stream complete, total length: {len(full_response)}")
                    
                    # Return text without emotion tag
                    _, clean_text = self._extract_emotion_tag(full_response)
                    return clean_text if clean_text else full_response
                    
        except asyncio.TimeoutError:
            self.logger.error("Streaming request to Ollama API timed out")
            raise Exception("Streaming request to Ollama API timed out")
        except Exception as e:
            self.logger.error(f"Failed to generate streaming response: {str(e)}")
            raise
    
    def _extract_emotion_tag(self, text: str) -> tuple[Optional[str], str]:
        """
        Extract emotion tag from the beginning of text.
        
        Args:
            text: Text that may start with [emotion] tag
            
        Returns:
            Tuple of (emotion, remaining_text) where emotion is None if not found
        """
        match = self.EMOTION_TAG_PATTERN.match(text)
        if match:
            emotion = match.group(1).lower()
            if emotion in self.VALID_EMOTIONS:
                remaining_text = text[match.end():]
                return emotion, remaining_text
            else:
                self.logger.warning(f"Invalid emotion tag '{emotion}', ignoring")
                return None, text
        return None, text

    def _parse_structured_response(self, raw_response: str) -> Dict[str, str]:
        """
        Parse structured response with fallback to plain text
        
        Args:
            raw_response: Raw response text from LLM
            
        Returns:
            Dict with keys 'text' and 'emotion'
        """
        try:
            # First try to extract JSON from the response
            json_data = self._extract_json_from_text(raw_response)
            
            if json_data:
                # Validate required fields
                text = json_data.get('text', '')
                emotion = json_data.get('emotion', 'neutral')
                
                # Validate emotion tag
                valid_emotions = {'neutral', 'happy', 'angry', 'sad', 'surprised'}
                if emotion not in valid_emotions:
                    self.logger.warning(f"Invalid emotion '{emotion}', defaulting to 'neutral'")
                    emotion = 'neutral'
                
                return {
                    'text': text,
                    'emotion': emotion
                }
            else:
                # Fallback to plain text with neutral emotion
                self.logger.info("No JSON found in response, using plain text fallback")
                return {
                    'text': raw_response.strip(),
                    'emotion': 'neutral'
                }
                
        except Exception as e:
            self.logger.warning(f"Error parsing structured response: {e}, using fallback")
            return {
                'text': raw_response.strip(),
                'emotion': 'neutral'
            }
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict]:
        """
        Extract JSON blocks from conversational text using regex
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Parsed JSON dict or None if no valid JSON found
        """
        try:
            # Pattern 1: Try to find JSON in markdown code blocks
            markdown_pattern = r"```json\s*(\{.*?\})\s*```"
            match = re.search(markdown_pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                json_str = match.group(1)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            # Pattern 2: Try to find the outermost {} block with content
            brace_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
            matches = re.findall(brace_pattern, text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    # Only return if it's a non-empty dict
                    if isinstance(parsed, dict) and parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue
            
            # Pattern 3: Try to find any JSON-like structure with quotes
            json_pattern = r'\{[^{}]*"[^"]*"[^{}]*:[^{}]*"[^"]*"[^{}]*\}'
            matches = re.findall(json_pattern, text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict) and parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error extracting JSON: {e}")
            return None
    
    async def generate_response_stream_with_fallback(
        self, 
        message: str, 
        handler: StreamHandler
    ) -> str:
        """
        Generate response using streaming mode with automatic fallback to non-streaming.
        
        This method attempts to use streaming mode first. If streaming fails for any reason,
        it automatically falls back to the non-streaming generate_response method.
        
        Args:
            message: User input message
            handler: StreamHandler implementation for callbacks
            
        Returns:
            str: Complete response text (without emotion tag)
        """
        if not self.enable_streaming:
            # Streaming disabled, use non-streaming mode directly
            self.logger.info("Streaming disabled, using non-streaming mode")
            return await self._fallback_to_non_streaming(message, handler)
        
        try:
            # Try streaming mode first
            return await self.generate_response_stream(message, handler)
            
        except Exception as e:
            self.logger.warning(f"Streaming failed: {e}, falling back to non-streaming mode")
            return await self._fallback_to_non_streaming(message, handler)
    
    async def _fallback_to_non_streaming(
        self, 
        message: str, 
        handler: StreamHandler
    ) -> str:
        """
        Fallback method that uses non-streaming response and simulates streaming callbacks.
        
        Args:
            message: User input message
            handler: StreamHandler implementation for callbacks
            
        Returns:
            str: Complete response text (without emotion tag)
        """
        try:
            # Use non-streaming mode with structured response
            response = await self.generate_response(message, return_structured=True)
            
            if isinstance(response, dict):
                emotion = response.get('emotion', 'neutral')
                text = response.get('text', '')
            else:
                # Plain text response
                emotion = 'neutral'
                text = str(response)
            
            # Simulate streaming callbacks
            handler.on_emotion_detected(emotion)
            handler.on_token_received(text)
            handler.on_stream_complete()
            
            return text
            
        except Exception as e:
            self.logger.error(f"Fallback to non-streaming also failed: {e}")
            # Last resort: return error message
            handler.on_emotion_detected('neutral')
            handler.on_token_received("抱歉，我现在无法回应。请稍后再试。")
            handler.on_stream_complete()
            raise

    def generate_response_sync(self, message: str, return_structured: bool = False) -> str | Dict[str, str]:
        """
        Synchronous wrapper for generate_response
        
        Args:
            message: User input message
            return_structured: If True, returns structured dict; if False, returns plain text for backward compatibility
            
        Returns:
            str or Dict[str, str]: Generated response text or structured response
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.generate_response(message, return_structured))
