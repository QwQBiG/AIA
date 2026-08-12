"""
System Workflow Integration for AI VTuber System.

This module integrates all components into a complete conversation workflow,
implementing the main system logic that coordinates user input processing,
LLM response generation, TTS playback, and VTube Studio animation control.

Supports both traditional mode and streaming pipeline mode for reduced latency.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from .config import SystemConfig, SystemState, ChatMessage
from .llm_client import LLMClient, StreamHandler
from .vts_client import VTSClient
from .tts_player import TTSPlayer
from .error_handler import ErrorHandler
from .stream_processor import StreamProcessor
from .tts_pipeline import TTSPipeline
from .text_cleaner import TextCleaner

# Import memory system components with error handling
try:
    from .memory_core.memory_core import MemoryCore
    from .enhanced_llm_client import EnhancedLLMClient
    MEMORY_SYSTEM_AVAILABLE = True
except ImportError:
    MemoryCore = None
    EnhancedLLMClient = None
    MEMORY_SYSTEM_AVAILABLE = False


class SystemWorkflow:
    """
    Main system workflow coordinator.
    
    Integrates all components to provide complete conversation workflow
    from user input to AI response with visual and audio feedback.
    """
    
    def __init__(self, config: SystemConfig):
        """
        Initialize the system workflow.
        
        Args:
            config: System configuration instance
        """
        self.config = config
        self.system_state = SystemState()
        self.error_handler = ErrorHandler()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.llm_client = LLMClient(config=config)
        
        # Memory system components (will be injected by main system)
        self.memory_core: Optional[MemoryCore] = None
        self.enhanced_llm_client: Optional[EnhancedLLMClient] = None
        
        # Initialize enhanced LLM client if memory system is available
        if MEMORY_SYSTEM_AVAILABLE:
            self.enhanced_llm_client = EnhancedLLMClient(
                base_url=config.ollama_url,
                model=config.ollama_model,
                memory_core=None,
                enable_memory=True
            )
            self.logger.info("Enhanced LLM Client initialized")
        
        self.vts_client = VTSClient(
            port=config.vts_port,
            emotion_hotkey_map=config.emotion_hotkey_map
        )
        self.tts_player = TTSPlayer(voice=config.tts_voice, config=config)
        
        # Callback for status updates (will be set by GUI)
        self.status_callback: Optional[Callable[[str, str], None]] = None
        
        # Callback for streaming text updates (will be set by GUI)
        self.streaming_text_callback: Optional[Callable[[str], None]] = None
        
        # Connection check lock to prevent concurrent checks
        self._connection_lock = threading.Lock()
        
        # Streaming pipeline components (initialize immediately for VTS integration)
        self._tts_pipeline: Optional[TTSPipeline] = None
        self._is_streaming_active = False
        
        # Initialize TTS pipeline immediately for VTS integration
        self._initialize_tts_pipeline()
        
        # Text cleaner for UX optimization (Requirements: 3.1, 3.4)
        self._text_cleaner: Optional[TextCleaner] = None
        
        # Full-duplex engine components (injected by main system)
        self.duplex_manager: Optional[Any] = None
        self.streaming_ears: Optional[Any] = None
        self.text_processor: Optional[Any] = None
        self.configuration_manager: Optional[Any] = None
        
        self.logger.info("System workflow initialized")
    
    def _initialize_tts_pipeline(self) -> None:
        """
        Initialize TTS pipeline immediately for VTS integration.
        
        This ensures the pipeline is available for dependency verification
        and VTS client injection during system startup.
        """
        try:
            self._tts_pipeline = TTSPipeline(
                self.tts_player,
                vts_client=self.vts_client,  # Inject VTSClient for lip-sync
                max_queue_size=self.config.performance.max_queue_size,
                ux_config=self.config.ux
            )
            self.logger.info("TTS Pipeline initialized for VTS integration")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TTS Pipeline: {e}")
            self._tts_pipeline = None
    
    def optimize_performance(self) -> None:
        """
        优化系统性能，防止资源泄漏和延迟累积
        """
        try:
            # 清理LLM客户端缓存
            if hasattr(self.llm_client, 'clear_cache'):
                self.llm_client.clear_cache()
            
            if self.enhanced_llm_client and hasattr(self.enhanced_llm_client, 'clear_cache'):
                self.enhanced_llm_client.clear_cache()
            
            # 清理TTS播放器缓存
            if hasattr(self.tts_player, 'clear_cache'):
                self.tts_player.clear_cache()
            
            # 清理流式处理管道
            if self._tts_pipeline:
                if hasattr(self._tts_pipeline, 'clear_cache'):
                    self._tts_pipeline.clear_cache()
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            self.logger.info("系统性能优化完成")
            
        except Exception as e:
            self.logger.warning(f"性能优化失败: {e}")
    
    def set_memory_core(self, memory_core: MemoryCore) -> None:
        """
        Set the memory core for enhanced conversations.
        
        Args:
            memory_core: MemoryCore instance for memory operations
        """
        self.memory_core = memory_core
        
        if self.enhanced_llm_client:
            self.enhanced_llm_client.set_memory_core(memory_core)
            self.logger.info("Memory core connected to Enhanced LLM Client")
        
        self.logger.info("Memory core integrated into SystemWorkflow")
    
    def get_active_llm_client(self):
        """
        Get the active LLM client (enhanced if memory is available, otherwise standard).
        
        Returns:
            Active LLM client instance
        """
        # CRITICAL FIX: Re-enable enhanced client now that recursion is fixed
        if self.enhanced_llm_client and self.memory_core and self.memory_core.is_ready():
            return self.enhanced_llm_client
        else:
            return self.llm_client
    
    def set_status_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        Set callback function for status updates.
        
        Args:
            callback: Function to call with (message, level) for status updates
        """
        self.status_callback = callback
    
    def set_streaming_text_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback function for streaming text updates.
        
        Args:
            callback: Function to call with partial text during streaming
        """
        self.streaming_text_callback = callback
    
    def _log_status(self, message: str, level: str = "INFO") -> None:
        """
        Log status message and send to callback if available.
        
        Args:
            message: Status message
            level: Log level (INFO, WARNING, ERROR, SUCCESS)
        """
        # Log to system logger
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "SUCCESS":
            self.logger.info(message)
        else:
            self.logger.info(message)
        
        # Send to GUI callback if available
        if self.status_callback:
            self.status_callback(message, level)
    
    async def initialize_connections(self) -> Dict[str, bool]:
        """
        Initialize connections to all external services.
        
        Returns:
            Dictionary with connection status for each service
        """
        self._log_status("正在初始化系统连接...", "INFO")
        connection_results = {}
        
        # Initialize Ollama connection
        try:
            self._log_status("连接到 Ollama 服务...", "INFO")
            ollama_connected = await self.llm_client.connect()
            self.system_state.llm_connected = ollama_connected
            connection_results["ollama"] = ollama_connected
            
            if ollama_connected:
                self._log_status(f"Ollama 连接成功 (模型: {self.config.ollama_model})", "SUCCESS")
            else:
                self._log_status("Ollama 连接失败", "ERROR")
                
        except Exception as e:
            self.error_handler.handle_network_error("ollama_connection", e)
            self.system_state.ollama_connected = False
            connection_results["ollama"] = False
            self._log_status(f"Ollama 连接异常: {str(e)}", "ERROR")
        
        # Initialize VTube Studio connection
        try:
            self._log_status("连接到 VTube Studio...", "INFO")
            
            # Ensure we're in the correct event loop context
            vts_connected = await self.vts_client.connect()
            
            if vts_connected:
                # Attempt authentication
                vts_authenticated = await self.vts_client.authenticate()
                self.system_state.vts_connected = vts_authenticated
                connection_results["vts"] = vts_authenticated
                
                if vts_authenticated:
                    self._log_status("VTube Studio 连接并认证成功", "SUCCESS")
                else:
                    self._log_status("VTube Studio 认证失败", "ERROR")
            else:
                self.system_state.vts_connected = False
                connection_results["vts"] = False
                self._log_status("VTube Studio 连接失败", "ERROR")
                
        except Exception as e:
            # More detailed error logging
            self.error_handler.handle_network_error("vts_connection", e)
            self.system_state.vts_connected = False
            connection_results["vts"] = False
            self._log_status(f"VTube Studio 连接异常: {str(e)}", "ERROR")
            connection_results["vts"] = False
            self._log_status(f"VTube Studio 连接异常: {str(e)}", "ERROR")
        
        # Log overall connection status
        connected_services = sum(connection_results.values())
        total_services = len(connection_results)
        self._log_status(
            f"系统初始化完成: {connected_services}/{total_services} 服务已连接",
            "SUCCESS" if connected_services > 0 else "WARNING"
        )
        
        return connection_results
    
    def check_connections(self) -> Dict[str, bool]:
        """
        Check current connection status for all services.
        
        Returns:
            Dictionary with current connection status
        """
        with self._connection_lock:
            return {
                "ollama": self.llm_client.is_connected(),
                "vts": self.vts_client.is_connected()
            }
    
    async def process_user_input(self, user_input: str, on_subtitle: Callable[[str], None] = None) -> None:
        """
        Process user input through the conversation workflow.
        
        This is the main workflow function that coordinates all components.
        When streaming is enabled, uses the streaming pipeline for reduced latency.
        Otherwise, uses the traditional workflow.
        
        Args:
            user_input: User's input message
            on_subtitle: Optional callback for subtitle updates (thread-safe)
        """
        if not user_input.strip():
            self._log_status("用户输入为空，跳过处理", "WARNING")
            return
        
        # Check if streaming pipeline should be used
        use_streaming = (
            self.config.performance.enable_streaming and
            self.config.performance.enable_sentence_chunking and
            not self.error_handler.is_feature_disabled("streaming")
        )
        
        if use_streaming:
            await self._process_user_input_streaming(user_input, on_subtitle)
        else:
            await self._process_user_input_traditional(user_input, on_subtitle)
    
    async def _process_user_input_streaming(self, user_input: str, on_subtitle: Callable[[str], None] = None) -> None:
        """
        Process user input using the streaming pipeline for reduced latency.
        
        This method implements:
        - Filler audio for latency masking (plays immediately)
        - Tag-based streaming LLM responses
        - Immediate emotion detection and VTS trigger
        - Sentence-by-sentence TTS generation
        - Producer-consumer audio playback
        - Synchronized subtitle display
        
        Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 5.3
        
        Args:
            user_input: User's input message
            on_subtitle: Optional callback for subtitle updates (thread-safe)
        """
        workflow_start_time = time.time()
        self._is_streaming_active = True
        
        # Track accumulated text for display
        accumulated_text = ""
        detected_emotion = None
        
        try:
            self._log_status(f"处理用户输入 (流式模式): {user_input}", "INFO")
            
            # Initialize TTS pipeline if not already running
            if self._tts_pipeline is None:
                self._initialize_tts_pipeline()
            
            # Ensure pipeline is not already running
            if not self._tts_pipeline.is_running:
                await self._tts_pipeline.start(on_subtitle)
            
            # Initialize TextCleaner if not already created (Requirements: 3.1, 3.4)
            if self._text_cleaner is None:
                self._text_cleaner = TextCleaner(
                    remove_emoji=self.config.ux.remove_emoji,
                    remove_markdown=self.config.ux.remove_markdown,
                    remove_parenthetical=self.config.ux.remove_parenthetical
                )
            # Note: _tts_pipeline.start() already called above (L373), removed duplicate
            
            # Play filler audio immediately to mask latency while waiting for LLM response
            # Requirements: 2.1 (extended) - Latency masking
            if self.config.ux.enable_cache:
                filler_played = self._tts_pipeline.play_filler()
                if filler_played:
                    self._log_status("播放填充音频以掩盖延迟", "INFO")
            
            # Create stream processor with sentence callback
            def on_sentence(sentence: str):
                """Callback when a complete sentence is detected."""
                self.logger.debug(f"Sentence detected: {sentence[:50]}...")

                # Clean text for TTS while preserving original for subtitles (Requirements: 3.1, 3.4)
                clean_text = self._text_cleaner.clean(sentence)

                # Queue sentence for TTS generation with both original and cleaned text
                # Use asyncio.run_coroutine_threadsafe to avoid RuntimeError in non-async context
                try:
                    current_loop = asyncio.get_running_loop()
                    if current_loop.is_running():
                        current_loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(self._tts_pipeline.put_text(sentence, clean_text))
                        )
                except RuntimeError:
                    # No running loop, this will be called from async context, safe to use create_task
                    asyncio.create_task(self._tts_pipeline.put_text(sentence, clean_text))
            
            stream_processor = StreamProcessor(
                on_sentence=on_sentence,
                min_sentence_length=self.config.performance.stream_chunk_min_size,
                aggressive_split=self.config.ux.aggressive_split,
                aggressive_min_length=self.config.ux.aggressive_min_length
            )
            
            # Create stream handler for LLM callbacks
            class WorkflowStreamHandler:
                def __init__(handler_self, workflow: 'SystemWorkflow'):
                    handler_self.workflow = workflow
                    handler_self.emotion_triggered = False
                    handler_self.token_count = 0
                    handler_self.max_tokens = 300  # Reduced to prevent overly long responses
                    handler_self.emotion_count = {}  # Track emotion repetition
                    handler_self.last_tokens = []  # Track for repetition detection
                    handler_self.should_stop = False  # Flag to stop streaming
                    handler_self.sentence_count = 0  # Track number of sentences generated
                    handler_self.max_sentences = 5  # Maximum sentences before auto-stop
                
                def on_emotion_detected(handler_self, emotion: str) -> None:
                    """Called when emotion tag is detected - trigger VTS immediately."""
                    nonlocal detected_emotion
                    detected_emotion = emotion
                    
                    # Track emotion repetition
                    handler_self.emotion_count[emotion] = handler_self.emotion_count.get(emotion, 0) + 1
                    
                    # Stop if same emotion appears too many times
                    if handler_self.emotion_count[emotion] > 2:  # Reduced threshold
                        handler_self.workflow.logger.warning(f"Emotion '{emotion}' repeated {handler_self.emotion_count[emotion]} times, stopping stream")
                        handler_self.should_stop = True
                        return
                    
                    handler_self.workflow.logger.info(f"Emotion detected: {emotion}")
                    handler_self.workflow._log_status(f"检测到情绪: {emotion}", "INFO")
                    
                    # Trigger VTS expression immediately (don't wait) - only if expression control is enabled
                    if (not handler_self.emotion_triggered and 
                        handler_self.workflow.config.enable_expression_control):
                        handler_self.emotion_triggered = True
                        asyncio.create_task(
                            handler_self.workflow._trigger_expression_async(emotion)
                        )
                
                def on_token_received(handler_self, token: str) -> None:
                    """Called when a new token is received."""
                    nonlocal accumulated_text
                    
                    # Check if we should stop
                    if handler_self.should_stop:
                        return
                    
                    # Check token limit to prevent infinite responses
                    handler_self.token_count += 1
                    if handler_self.token_count > handler_self.max_tokens:
                        handler_self.workflow.logger.warning(f"Token limit reached ({handler_self.max_tokens}), stopping stream")
                        handler_self.should_stop = True
                        return
                    
                    # Skip emotion tags and control tokens for display
                    if token.startswith('[') and token.endswith(']'):
                        # This is likely an emotion tag, don't add to display text
                        return
                    
                    # Track recent tokens for repetition detection
                    handler_self.last_tokens.append(token)
                    if len(handler_self.last_tokens) > 20:  # Keep last 20 tokens
                        handler_self.last_tokens.pop(0)
                    
                    # Check for repetitive patterns (more strict)
                    if len(handler_self.last_tokens) >= 8:
                        # Check if last 4 tokens are repeating
                        last_4 = handler_self.last_tokens[-4:]
                        prev_4 = handler_self.last_tokens[-8:-4]
                        if last_4 == prev_4:
                            handler_self.workflow.logger.warning("Repetitive pattern detected, stopping stream")
                            handler_self.should_stop = True
                            return
                    
                    # Check for sentence completion patterns that might indicate end
                    if token in ['。', '！', '？', '.', '!', '?']:
                        handler_self.sentence_count += 1
                        handler_self.workflow.logger.debug(f"Sentence {handler_self.sentence_count} completed")
                        
                        # Stop after reasonable number of sentences
                        if handler_self.sentence_count >= handler_self.max_sentences:
                            handler_self.workflow.logger.info(f"Reached max sentences ({handler_self.max_sentences}), stopping stream")
                            handler_self.should_stop = True
                            return
                        
                        # Also stop if we've generated enough content
                        if handler_self.token_count > 100 and len(accumulated_text) > 150:
                            handler_self.workflow.logger.info("Generated sufficient content, stopping stream")
                            handler_self.should_stop = True
                            return
                    
                    accumulated_text += token
                    
                    # Feed token to stream processor for sentence detection
                    stream_processor.feed(token)
                    
                    # Update GUI with streaming text - only show clean text without repetition
                    if handler_self.workflow.streaming_text_callback:
                        # Clean the text for display (remove emotion tags and excessive repetition)
                        clean_display_text = handler_self._clean_display_text(accumulated_text)
                        handler_self.workflow.streaming_text_callback(clean_display_text)
                
                def _clean_display_text(handler_self, text: str) -> str:
                    """Clean text for display by removing emotion tags and excessive repetition."""
                    import re
                    
                    # Remove emotion tags like [neutral], [happy], etc.
                    cleaned = re.sub(r'\[[\w\s]+\]', '', text)
                    
                    # Remove excessive whitespace
                    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                    
                    # Detect and remove repetitive patterns
                    sentences = cleaned.split('。')
                    if len(sentences) > 1:
                        # Check for repeated sentences
                        unique_sentences = []
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if sentence and sentence not in unique_sentences:
                                unique_sentences.append(sentence)
                        cleaned = '。'.join(unique_sentences)
                        if cleaned and not cleaned.endswith('。'):
                            cleaned += '。'
                    
                    return cleaned
                
                def on_stream_complete(handler_self) -> None:
                    """Called when stream is complete."""
                    # Flush any remaining text in the buffer
                    stream_processor.flush()
                    handler_self.workflow.logger.info("Stream complete")
            
            handler = WorkflowStreamHandler(self)
            
            # Generate streaming response
            self._log_status("正在生成 AI 回复 (流式)...", "INFO")
            
            try:
                # Use memory-enhanced LLM client if available
                active_llm_client = self.get_active_llm_client()
                
                if active_llm_client == self.enhanced_llm_client:
                    self._log_status("使用内存增强的流式响应生成...", "INFO")
                    response_text = await active_llm_client.generate_response_stream_with_memory(
                        user_input, handler, max_memories=5
                    )
                else:
                    self._log_status("使用标准流式响应生成...", "INFO")
                    response_text = await active_llm_client.generate_response_stream_with_fallback(
                        user_input, handler
                    )
                
                # Store conversation in memory if memory system is available
                if self.memory_core and self.memory_core.is_ready():
                    try:
                        # Create timestamp for memory storage
                        interaction_timestamp = datetime.now()
                        
                        memory_id = self.memory_core.store_interaction(
                            user_input=user_input,
                            ai_response=response_text,
                            timestamp=interaction_timestamp,
                            metadata={
                                'source': 'system_workflow',
                                'conversation_type': 'streaming',
                                'workflow_time': time.time() - workflow_start_time,
                                'emotion': detected_emotion or 'neutral'
                            }
                        )
                        
                        if memory_id:
                            self.logger.debug(f"Streaming conversation stored in memory: {memory_id}")
                        else:
                            self.logger.warning("Failed to store streaming conversation in memory")
                            
                    except Exception as e:
                        self.logger.error(f"Failed to store streaming conversation in memory: {e}")
                        # Continue without memory storage - don't fail the conversation
            except Exception as e:
                self.logger.error(f"Streaming response failed: {e}")
                self._log_status(f"流式响应失败: {e}", "ERROR")
                # Fall back to traditional mode
                await self._process_user_input_traditional(user_input)
                return
            
            # Log the response
            emotion_str = detected_emotion or 'neutral'
            self._log_status(
                f"AI 回复 (情感: {emotion_str}): {response_text[:100]}{'...' if len(response_text) > 100 else ''}", 
                "SUCCESS"
            )
            
            # Wait for TTS pipeline to finish playing all audio
            self._log_status("等待语音播放完成...", "INFO")
            timeout_seconds = 60.0  # 60秒超时保护
            start_wait = time.time()
            while not self._tts_pipeline.is_idle():
                if time.time() - start_wait > timeout_seconds:
                    self.logger.warning(f"TTS pipeline idle wait timeout after {timeout_seconds}s, forcing continue")
                    break
                await asyncio.sleep(0.1)
            
            # Stop TTS pipeline
            await self._tts_pipeline.stop()
            
            # Log completion
            workflow_duration = time.time() - workflow_start_time
            self._log_status(
                f"流式对话完成 (总耗时: {workflow_duration:.2f}秒)",
                "SUCCESS"
            )
            
        except Exception as e:
            self.error_handler.handle_thread_error("streaming_conversation_workflow", e)
            self._log_status(f"流式对话流程出错: {str(e)}", "ERROR")
            
        finally:
            self._is_streaming_active = False
            self.system_state.set_audio_state(False)
            
            # Ensure pipeline is stopped
            if self._tts_pipeline:
                try:
                    await self._tts_pipeline.stop()
                except Exception:
                    pass
            
            # 每次流式对话后进行性能优化
            try:
                self.optimize_performance()
            except Exception as e:
                self.logger.warning(f"流式对话后性能优化失败: {e}")
    
    async def _trigger_expression_async(self, emotion: str) -> None:
        """
        Trigger VTS expression asynchronously.
        
        This is called immediately when emotion is detected during streaming,
        ensuring expression appears before audio starts.
        
        Requirements: 1.2, 1.3 - Emotion priority response
        
        Args:
            emotion: Emotion tag to trigger
        """
        try:
            await self._coordinate_expression_timing(emotion)
        except Exception as e:
            self.logger.warning(f"Failed to trigger expression: {e}")
    
    def interrupt_streaming(self) -> None:
        """
        Interrupt current streaming playback.
        
        Called when user sends a new message while previous response
        is still playing. Stops current audio and clears the queue.
        
        Requirements: 1.4 (extended) - Graceful interruption
        """
        if self._is_streaming_active and self._tts_pipeline:
            self._log_status("中断当前播放...", "INFO")
            self._tts_pipeline.interrupt()
            self._is_streaming_active = False
    
    def enable_full_duplex_mode(self) -> bool:
        """
        Enable full-duplex conversational mode.
        
        Returns:
            bool: True if successfully enabled, False otherwise
        """
        if not self.streaming_ears:
            self.logger.warning("StreamingEars not available - cannot enable full-duplex mode")
            return False
        
        # Check if already enabled
        if self.is_full_duplex_enabled():
            self.logger.info("Full-duplex mode is already enabled")
            return True
        
        try:
            # Start streaming ears for real-time speech recognition
            self.streaming_ears.start_streaming()
            
            # Enable duplex manager if available
            if self.duplex_manager:
                self.duplex_manager.set_ai_speaking_state(False)  # Initialize as idle
            
            self._log_status("全双工模式已启用", "SUCCESS")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable full-duplex mode: {e}")
            self._log_status(f"启用全双工模式失败: {str(e)}", "ERROR")
            return False
    
    def disable_full_duplex_mode(self) -> None:
        """Disable full-duplex conversational mode."""
        try:
            # Stop streaming ears
            if self.streaming_ears:
                self.streaming_ears.stop_streaming()
            
            self._log_status("全双工模式已禁用", "INFO")
            
        except Exception as e:
            self.logger.error(f"Failed to disable full-duplex mode: {e}")
            self._log_status(f"禁用全双工模式失败: {str(e)}", "ERROR")
    
    def is_full_duplex_enabled(self) -> bool:
        """Check if full-duplex mode is currently enabled."""
        return (self.streaming_ears is not None and 
                hasattr(self.streaming_ears, '_streaming_active') and
                self.streaming_ears._streaming_active)
    
    async def _process_user_input_traditional(self, user_input: str, on_subtitle: Callable[[str], None] = None) -> None:
        """
        Process user input through the traditional (non-streaming) workflow.
        
        This is the original workflow that waits for complete LLM response
        before processing TTS.
        
        Args:
            user_input: User's input message
            on_subtitle: Optional callback for subtitle updates (thread-safe)
        """
        workflow_start_time = time.time()
        
        try:
            # Step 1: Log user input
            self._log_status(f"处理用户输入: {user_input}", "INFO")
            user_message = ChatMessage(
                role="user",
                content=user_input,
                timestamp=datetime.now()
            )
            
            # Step 2: Generate LLM response (structured or plain text based on configuration)
            self._log_status("正在生成 AI 回复...", "INFO")
            structured_response = await self._generate_structured_response(user_input)
            
            if not structured_response:
                self._log_status("AI 回复生成失败", "ERROR")
                return
            
            # Extract text and emotion from structured response
            response_text = structured_response.get('text', '')
            emotion = structured_response.get('emotion', 'neutral')
            
            ai_message = ChatMessage(
                role="assistant",
                content=response_text,
                timestamp=datetime.now()
            )
            
            # Check if emotional intelligence is enabled for logging and processing
            use_emotional_intelligence = (
                self.config.enable_emotional_intelligence and 
                not self.error_handler.is_feature_disabled("emotional_intelligence")
            )
            
            if use_emotional_intelligence:
                # Log with emotional intelligence information
                self._log_status(f"AI 回复 (情感: {emotion}): {response_text[:100]}{'...' if len(response_text) > 100 else ''}", "SUCCESS")
                
                # Step 3: Process emotional response with coordinated timing
                await self._process_emotional_response(structured_response)
                
                # Step 4: Log emotional intelligence completion
                workflow_duration = time.time() - workflow_start_time
                self._log_status(
                    f"情感对话流程完成 (总耗时: {workflow_duration:.2f}秒)",
                    "SUCCESS"
                )
            else:
                # Log without emotional intelligence information (backward compatibility)
                self._log_status(f"AI 回复: {response_text[:100]}{'...' if len(response_text) > 100 else ''}", "SUCCESS")
                
                # Step 3: Process basic response without emotional features
                await self._process_basic_response(response_text)
                
                # Step 4: Log basic completion
                workflow_duration = time.time() - workflow_start_time
                self._log_status(
                    f"对话完成 (总耗时: {workflow_duration:.2f}秒)",
                    "SUCCESS"
                )
            
            # Store conversation in memory if memory system is available
            if self.memory_core and self.memory_core.is_ready():
                try:
                    # Create timestamp for memory storage
                    interaction_timestamp = datetime.now()
                    
                    memory_id = self.memory_core.store_interaction(
                        user_input=user_input,
                        ai_response=response_text,
                        timestamp=interaction_timestamp,
                        metadata={
                            'source': 'system_workflow',
                            'conversation_type': 'traditional',
                            'emotion': emotion,
                            'workflow_time': time.time() - workflow_start_time,
                            'use_emotional_intelligence': use_emotional_intelligence
                        }
                    )
                    
                    if memory_id:
                        self.logger.debug(f"Traditional conversation stored in memory: {memory_id}")
                    else:
                        self.logger.warning("Failed to store traditional conversation in memory")
                        
                except Exception as e:
                    self.logger.error(f"Failed to store traditional conversation in memory: {e}")
                    # Continue without memory storage - don't fail the conversation
            
        except Exception as e:
            self.error_handler.handle_thread_error("enhanced_conversation_workflow", e)
            self._log_status(f"情感对话流程出错: {str(e)}", "ERROR")
            
        finally:
            # Ensure system state is reset on error
            self.system_state.set_audio_state(False)
            
            # 每次对话后进行性能优化，防止资源累积
            try:
                self.optimize_performance()
            except Exception as e:
                self.logger.warning(f"对话后性能优化失败: {e}")
    
    async def _generate_structured_response(self, user_input: str) -> Optional[Dict[str, str]]:
        """
        Generate structured response from LLM with emotion metadata.
        
        Args:
            user_input: User's input message
            
        Returns:
            Dictionary with 'text' and 'emotion' keys, or None if failed
        """
        if not self.system_state.llm_connected:
            self._log_status("Ollama 未连接，尝试重新连接...", "WARNING")
            
            # Attempt reconnection
            try:
                connected = await self.llm_client.connect()
                self.system_state.llm_connected = connected
                
                if not connected:
                    self._log_status("Ollama 重连失败", "ERROR")
                    return None
                    
            except Exception as e:
                self.error_handler.handle_network_error("ollama_reconnection", e)
                self._log_status(f"Ollama 重连异常: {str(e)}", "ERROR")
                return None
        
        try:
            # Check if emotional intelligence is enabled and not disabled due to failures
            use_emotional_intelligence = (
                self.config.enable_emotional_intelligence and 
                not self.error_handler.is_feature_disabled("emotional_intelligence") and
                hasattr(self.llm_client, 'generate_response')
            )
            
            if use_emotional_intelligence:
                # Use memory-enhanced LLM client if available
                active_llm_client = self.get_active_llm_client()
                
                if active_llm_client == self.enhanced_llm_client:
                    self._log_status("使用内存增强的结构化响应生成...", "INFO")
                    response = await asyncio.wait_for(
                        active_llm_client.generate_with_memory(user_input, return_structured=True, max_memories=5),
                        timeout=120.0
                    )
                else:
                    # Generate structured response with emotion metadata
                    response = await asyncio.wait_for(
                        active_llm_client.generate_response(user_input, return_structured=True),
                        timeout=120.0
                    )
                
                # Ensure response is a dictionary with required keys
                if isinstance(response, dict) and 'text' in response and 'emotion' in response:
                    # Reset basic functionality errors on success
                    self.error_handler.reset_basic_functionality_errors()
                    return response
                else:
                    # Handle structured response parsing failure
                    self.error_handler.handle_feature_failure(
                        "structured_response_parsing",
                        Exception(f"Invalid structured response format: {type(response)}"),
                        "response_parsing"
                    )
                    
                    # Fallback to plain text response
                    self._log_status("结构化响应格式无效，使用纯文本回退", "WARNING")
                    text_response = response if isinstance(response, str) else str(response)
                    return {'text': text_response, 'emotion': 'neutral'}
            else:
                # Use memory-enhanced LLM client if available for plain text response
                active_llm_client = self.get_active_llm_client()
                
                if active_llm_client == self.enhanced_llm_client:
                    self._log_status("使用内存增强的纯文本响应生成...", "INFO")
                    response = await asyncio.wait_for(
                        active_llm_client.generate_with_memory(user_input, return_structured=False, max_memories=5),
                        timeout=120.0
                    )
                else:
                    # Use plain text response when emotional intelligence is disabled
                    if self.error_handler.is_feature_disabled("emotional_intelligence"):
                        self._log_status("情感智能功能已禁用，使用纯文本模式", "INFO")
                    
                    response = await asyncio.wait_for(
                        active_llm_client.generate_response(user_input, return_structured=False),
                        timeout=120.0
                    )
                
                # Reset basic functionality errors on success
                self.error_handler.reset_basic_functionality_errors()
                return {'text': response, 'emotion': 'neutral'}
            
        except asyncio.TimeoutError:
            self._log_status("LLM 响应超时", "ERROR")
            
            # Handle as basic functionality error
            timeout_error = Exception("LLM response timeout")
            self.error_handler.handle_basic_functionality_error("llm_generation", timeout_error)
            return None
            
        except Exception as e:
            # Determine if this is a basic functionality error or feature-specific error
            if use_emotional_intelligence:
                # This is an emotional intelligence feature failure
                feature_disabled = self.error_handler.handle_feature_failure(
                    "emotional_intelligence", e, "structured_response_generation"
                )
                
                if feature_disabled:
                    self._log_status("情感智能功能因错误过多被临时禁用", "WARNING")
                
                # Try fallback to plain text
                try:
                    self._log_status("尝试纯文本回退...", "INFO")
                    response = await asyncio.wait_for(
                        self.llm_client.generate_response(user_input, return_structured=False),
                        timeout=120.0
                    )
                    return {'text': response, 'emotion': 'neutral'}
                except Exception as fallback_error:
                    self.error_handler.handle_basic_functionality_error("llm_fallback", fallback_error)
                    self._log_status(f"纯文本回退也失败: {str(fallback_error)}", "ERROR")
            else:
                # This is a basic functionality error
                self.error_handler.handle_basic_functionality_error("llm_generation", e)
                self._log_status(f"基础 LLM 生成失败: {str(e)}", "ERROR")
            
            # Mark as disconnected if it's a connection error
            if "connection" in str(e).lower() or "network" in str(e).lower():
                self.system_state.llm_connected = False
            
            return None
    
    def _extract_primary_emotion(self, structured_response: Dict[str, str]) -> str:
        """
        Extract the primary emotion from structured response, handling multiple emotions.
        
        According to requirement 5.4, when multiple emotions are detected,
        the system should use the first valid emotion tag.
        
        Args:
            structured_response: Dictionary containing emotion metadata
            
        Returns:
            str: Primary emotion tag (defaults to 'neutral' if invalid)
        """
        emotion = structured_response.get('emotion', 'neutral')
        
        # Valid emotion tags as defined in requirements
        valid_emotions = {'neutral', 'happy', 'angry', 'sad', 'surprised'}
        
        # Handle multiple emotions by taking the first valid one
        if isinstance(emotion, str):
            # Split by common separators and take first valid emotion
            emotion_candidates = [e.strip().lower() for e in emotion.replace(',', ' ').split()]
            for candidate in emotion_candidates:
                if candidate in valid_emotions:
                    self.logger.debug(f"Selected primary emotion '{candidate}' from candidates: {emotion_candidates}")
                    return candidate
        
        # Fallback to neutral if no valid emotion found
        if emotion not in valid_emotions:
            self.logger.warning(f"Invalid emotion '{emotion}', defaulting to 'neutral'")
            return 'neutral'
        
        return emotion
    
    async def _coordinate_expression_timing(self, emotion: str) -> bool:
        """
        Coordinate expression timing to ensure expressions appear before audio.
        
        This method implements the timing coordination requirement 5.4 and 2.4,
        ensuring expressions are triggered with proper timing constraints.
        
        Args:
            emotion: Primary emotion tag to trigger
            
        Returns:
            bool: True if expression was triggered successfully, False otherwise
        """
        # Check if expression control is enabled and not disabled due to failures
        if not (self.config.enable_expression_control and 
                self.system_state.vts_connected and 
                not self.error_handler.is_feature_disabled("expression_control") and
                hasattr(self.vts_client, 'trigger_expression')):
            
            if self.error_handler.is_feature_disabled("expression_control"):
                self.logger.info("Expression control disabled due to failures - skipping expression timing coordination")
            else:
                self.logger.info("Expression control not available - skipping expression timing coordination")
            return False
        
        try:
            expression_start_time = time.time()
            self._log_status(f"协调表情时序: {emotion}", "INFO")
            
            # Trigger expression with strict timing constraint (500ms max)
            expression_triggered = await asyncio.wait_for(
                self.vts_client.trigger_expression(emotion),
                timeout=self.config.expression_timeout
            )
            
            expression_duration = (time.time() - expression_start_time) * 1000
            
            if expression_triggered:
                self._log_status(f"表情时序协调成功: {emotion} ({expression_duration:.1f}ms)", "SUCCESS")
                
                # Small delay to ensure expression is visible before audio starts
                if expression_duration < 100:  # If very fast, add small delay
                    await asyncio.sleep(0.05)  # 50ms delay
                    
                return True
            else:
                # Handle expression failure
                self.error_handler.handle_feature_failure(
                    "expression_control",
                    Exception(f"Expression trigger returned False for emotion: {emotion}"),
                    "expression_timing"
                )
                self._log_status(f"表情时序协调失败: {emotion} ({expression_duration:.1f}ms)", "WARNING")
                return False
                
        except asyncio.TimeoutError:
            expression_duration = (time.time() - expression_start_time) * 1000
            timeout_error = Exception(f"Expression timing timeout for emotion: {emotion}")
            
            self.error_handler.handle_feature_failure(
                "expression_control", timeout_error, "expression_timing_timeout"
            )
            self._log_status(f"表情时序协调超时: {emotion} ({expression_duration:.1f}ms)", "WARNING")
            return False
        except Exception as e:
            expression_duration = (time.time() - expression_start_time) * 1000
            
            # Handle expression control failure
            feature_disabled = self.error_handler.handle_feature_failure(
                "expression_control", e, "expression_timing_coordination"
            )
            
            if feature_disabled:
                self._log_status("表情控制功能因错误过多被临时禁用", "WARNING")
            
            self._log_status(f"表情时序协调异常: {emotion} ({expression_duration:.1f}ms) - {str(e)}", "WARNING")
            return False
    async def _process_emotional_response(self, structured_response: Dict[str, str]) -> None:
        """
        Process emotional response with coordinated timing for expression and voice generation.
        
        This method implements the timing coordination according to requirements 5.2 and 5.4,
        ensuring expressions are triggered before or simultaneously with audio playback.
        
        Args:
            structured_response: Dictionary containing 'text' and 'emotion' keys
        """
        text = structured_response.get('text', '')
        raw_emotion = structured_response.get('emotion', 'neutral')
        
        if not text.strip():
            self._log_status("响应文本为空，跳过处理", "WARNING")
            return
        
        # Extract primary emotion (handles multiple emotions by using first valid one)
        emotion = self._extract_primary_emotion(structured_response)
        
        if emotion != raw_emotion:
            self._log_status(f"情感标签处理: '{raw_emotion}' -> '{emotion}'", "INFO")
        
        audio_file = None
        expression_triggered = False
        
        try:
            # Step 1: Coordinate expression timing (trigger before audio generation)
            expression_triggered = await self._coordinate_expression_timing(emotion)
            
            # Step 2: Generate TTS audio with voice cloning error handling
            self._log_status("生成语音...", "INFO")
            
            try:
                audio_file = await self.tts_player.generate_audio(text)
            except Exception as tts_error:
                # Handle voice cloning failure
                if (self.config.enable_voice_cloning and 
                    "sovits" in str(tts_error).lower()):
                    
                    feature_disabled = self.error_handler.handle_feature_failure(
                        "voice_cloning", tts_error, "audio_generation"
                    )
                    
                    if feature_disabled:
                        self._log_status("语音克隆功能因错误过多被临时禁用", "WARNING")
                else:
                    # This is a basic TTS functionality error
                    self.error_handler.handle_basic_functionality_error("tts_generation", tts_error)
                
                raise  # Re-raise to be handled by outer try-catch
            
            # Update system state
            self.system_state.set_audio_state(True, audio_file)
            
            # Step 3: Start dynamic mouth animation if VTS is connected
            # Use ensure_connected to auto-reconnect if needed
            vts_available = await self.vts_client.ensure_connected()
            mouth_animation_task = None
            
            if vts_available:
                try:
                    # Start dynamic mouth animation in background
                    mouth_animation_task = asyncio.create_task(
                        self.vts_client.animate_mouth_speaking()
                    )
                    self._log_status("开始动态嘴型动画", "INFO")
                except Exception as e:
                    self.error_handler.handle_network_error("vts_animation_start", e)
                    self._log_status(f"嘴型动画启动失败: {str(e)}", "WARNING")
            else:
                self._log_status("VTS 未连接，跳过嘴型动画", "WARNING")
            
            # Step 4: Play audio (expressions should already be visible by now)
            self._log_status("播放语音...", "INFO")
            
            # Run audio playback in thread to avoid blocking
            playback_complete = threading.Event()
            playback_error = [None]  # Use list to allow modification in nested function
            
            def play_audio_sync():
                try:
                    self.tts_player.play_audio(audio_file)
                except Exception as e:
                    playback_error[0] = e
                    self.error_handler.handle_file_error(audio_file, e, "audio_playback")
                    self._log_status(f"音频播放失败: {str(e)}", "ERROR")
                finally:
                    playback_complete.set()
            
            # Start audio playback in background thread
            audio_thread = threading.Thread(target=play_audio_sync, daemon=True)
            audio_thread.start()
            
            # Wait for audio to complete while keeping event loop responsive
            while not playback_complete.is_set():
                await asyncio.sleep(0.1)
            
            # Stop mouth animation when audio completes
            if mouth_animation_task and not mouth_animation_task.done():
                mouth_animation_task.cancel()
                try:
                    await mouth_animation_task
                except asyncio.CancelledError:
                    pass
            
            # Ensure mouth is closed
            if vts_available:
                await self.vts_client.stop_mouth_animation()
            
            timing_status = "成功" if expression_triggered else "仅语音"
            self._log_status(f"情感语音播放完成 (时序协调: {timing_status})", "SUCCESS")
            
        except Exception as e:
            self.error_handler.handle_file_error(
                audio_file or "unknown", e, "emotional_tts_processing"
            )
            self._log_status(f"情感 TTS 处理失败: {str(e)}", "ERROR")
            
        finally:
            # Always stop animation and clean up
            try:
                # Stop mouth animation if VTS is connected
                vts_connected = self.vts_client.is_connected()
                if vts_connected:
                    await self.vts_client.stop_mouth_animation()
                    self._log_status("停止嘴型动画", "INFO")
                    
            except Exception as e:
                self.error_handler.handle_network_error("vts_animation_stop", e)
                self._log_status(f"停止嘴型动画失败: {str(e)}", "WARNING")
            
            # Clean up audio file
            if audio_file:
                try:
                    self.tts_player.cleanup_temp_file(audio_file)
                except Exception as e:
                    self.error_handler.handle_file_error(audio_file, e, "file_cleanup")
            
            # Reset system state
            self.system_state.set_audio_state(False)
    
    async def _process_basic_response(self, response_text: str) -> None:
        """
        Process basic response without emotional intelligence features (backward compatibility).
        
        This method provides the same functionality as the original system when
        emotional intelligence features are disabled.
        
        Args:
            response_text: The plain text response from the LLM
        """
        try:
            # Generate audio using TTS (with potential voice cloning fallback)
            self._log_status("正在生成语音...", "INFO")
            audio_file = await self.tts_player.generate_audio(response_text)
            
            if not audio_file:
                self._log_status("语音生成失败", "ERROR")
                return
            
            # Set audio state
            self.system_state.set_audio_state(True, audio_file)
            
            # Start dynamic mouth animation if VTS is connected (use ensure_connected for auto-reconnect)
            vts_available = await self.vts_client.ensure_connected()
            mouth_animation_task = None
            
            if vts_available:
                try:
                    # Start dynamic mouth animation in background
                    mouth_animation_task = asyncio.create_task(
                        self.vts_client.animate_mouth_speaking()
                    )
                    self._log_status("开始动态嘴型动画", "INFO")
                except Exception as e:
                    self.error_handler.handle_network_error("vts_animation_start", e)
                    self._log_status(f"嘴型动画启动失败: {str(e)}", "WARNING")
            else:
                self._log_status("VTS 未连接，跳过嘴型动画", "WARNING")
            
            # Play audio synchronously (original system behavior)
            playback_complete = threading.Event()
            
            def play_audio_sync():
                try:
                    self.tts_player.play_audio(audio_file)
                    self._log_status("语音播放完成", "SUCCESS")
                except Exception as e:
                    self.error_handler.handle_file_error(audio_file, e, "audio_playback")
                    self._log_status(f"语音播放失败: {str(e)}", "ERROR")
                finally:
                    playback_complete.set()
            
            # Start audio playback in background thread
            audio_thread = threading.Thread(target=play_audio_sync, daemon=True)
            audio_thread.start()
            
            # Wait for audio to complete while keeping event loop responsive
            while not playback_complete.is_set():
                await asyncio.sleep(0.1)
            
            # Stop mouth animation when audio completes
            if mouth_animation_task and not mouth_animation_task.done():
                mouth_animation_task.cancel()
                try:
                    await mouth_animation_task
                except asyncio.CancelledError:
                    pass
            
            # Ensure mouth is closed
            if vts_available:
                await self.vts_client.stop_mouth_animation()
            
        except Exception as e:
            self.error_handler.handle_file_error(
                audio_file or "unknown", e, "basic_tts_processing"
            )
            self._log_status(f"TTS 处理失败: {str(e)}", "ERROR")
            
        finally:
            # Always stop animation and clean up (original system behavior)
            try:
                # Stop mouth animation if VTS is connected
                vts_connected = self.vts_client.is_connected()
                if vts_connected:
                    await self.vts_client.stop_mouth_animation()
                    self._log_status("停止嘴型动画", "INFO")
                    
            except Exception as e:
                self.error_handler.handle_network_error("vts_animation_stop", e)
                self._log_status(f"停止嘴型动画失败: {str(e)}", "WARNING")
            
            # Clean up audio file
            if audio_file:
                try:
                    self.tts_player.cleanup_temp_file(audio_file)
                except Exception as e:
                    self.error_handler.handle_file_error(audio_file, e, "file_cleanup")
            
            # Reset system state
            self.system_state.set_audio_state(False)

    async def _generate_llm_response(self, user_input: str) -> Optional[str]:
        """
        Generate response from LLM with error handling (backward compatibility method).
        
        Args:
            user_input: User's input message
            
        Returns:
            Generated response text or None if failed
        """
        # Use the new structured response method but return only text for backward compatibility
        structured_response = await self._generate_structured_response(user_input)
        if structured_response:
            return structured_response.get('text')
        return None
    
    async def _process_tts_and_animation(self, text: str) -> None:
        """
        Process TTS generation and VTube Studio animation synchronization.
        
        This implements the coordinated audio-visual feedback according to
        requirements 6.3 and 6.4.
        
        Args:
            text: Text to convert to speech and animate
        """
        audio_file = None
        
        try:
            # Generate TTS audio
            self._log_status("生成 TTS 音频...", "INFO")
            audio_file = await self.tts_player.generate_audio(text)
            
            # Update system state
            self.system_state.set_audio_state(True, audio_file)
            
            # Check VTS connection status and start mouth animation (use ensure_connected for auto-reconnect)
            vts_available = await self.vts_client.ensure_connected()
            self._log_status(f"VTS 连接状态: {vts_available}", "DEBUG")
            
            if vts_available:
                try:
                    await self.vts_client.start_mouth_animation()
                    self._log_status("开始嘴型动画", "INFO")
                except Exception as e:
                    self.error_handler.handle_network_error("vts_animation_start", e)
                    self._log_status(f"嘴型动画启动失败: {str(e)}", "WARNING")
                    # Continue with audio playback even if animation fails
            else:
                self._log_status("VTS 未连接，跳过嘴型动画", "WARNING")
            
            # Play audio
            self._log_status("播放语音...", "INFO")
            
            # Run audio playback in thread to avoid blocking
            def play_audio_sync():
                try:
                    self.tts_player.play_audio(audio_file)
                except Exception as e:
                    self.error_handler.handle_file_error(audio_file, e, "audio_playback")
                    self._log_status(f"音频播放失败: {str(e)}", "ERROR")
            
            # Start audio playback in background thread
            audio_thread = threading.Thread(target=play_audio_sync, daemon=True)
            audio_thread.start()

            # Wait for audio to complete without blocking event loop
            while not playback_complete.is_set():
                await asyncio.sleep(0.1)
            
            self._log_status("语音播放完成", "SUCCESS")
            
        except Exception as e:
            self.error_handler.handle_file_error(
                audio_file or "unknown", e, "tts_generation"
            )
            self._log_status(f"TTS 处理失败: {str(e)}", "ERROR")
            
        finally:
            # Always stop animation and clean up
            try:
                # Stop mouth animation if VTS is connected
                vts_connected = self.vts_client.is_connected()
                if vts_connected:
                    await self.vts_client.stop_mouth_animation()
                    self._log_status("停止嘴型动画", "INFO")
                else:
                    self._log_status("VTS 未连接，跳过停止嘴型动画", "DEBUG")
                    
            except Exception as e:
                self.error_handler.handle_network_error("vts_animation_stop", e)
                self._log_status(f"停止嘴型动画失败: {str(e)}", "WARNING")
            
            # Clean up audio file
            if audio_file:
                try:
                    self.tts_player.cleanup_temp_file(audio_file)
                except Exception as e:
                    self.error_handler.handle_file_error(audio_file, e, "file_cleanup")
            
            # Reset system state
            self.system_state.set_audio_state(False)
    
    async def reconnect_services(self) -> Dict[str, bool]:
        """
        Attempt to reconnect to all external services.
        
        Returns:
            Dictionary with reconnection results
        """
        self._log_status("正在重新连接所有服务...", "INFO")
        
        # Reset connection states
        self.system_state.reset_connections()
        
        # Reinitialize connections
        return await self.initialize_connections()
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status information including error tracking.
        
        Returns:
            Dictionary with system status details including feature health
        """
        # Get feature status from error handler
        feature_status = self.error_handler.get_feature_status()
        
        return {
            "connections": self.system_state.get_connection_status(),
            "audio_state": {
                "is_speaking": self.system_state.is_speaking,
                "current_file": self.system_state.current_audio_file
            },
            "config": {
                "ollama_model": self.config.ollama_model,
                "tts_voice": self.config.tts_voice,
                "vts_port": self.config.vts_port,
                "emotional_intelligence_enabled": self.config.enable_emotional_intelligence,
                "voice_cloning_enabled": self.config.enable_voice_cloning,
                "expression_control_enabled": self.config.enable_expression_control
            },
            "error_tracking": {
                "retry_counts": dict(self.error_handler.retry_counts),
                "feature_health": feature_status,
                "system_health": feature_status.get("system_health", "unknown")
            }
        }
    
    async def shutdown(self) -> None:
        """
        Gracefully shutdown the system workflow.
        """
        self._log_status("正在关闭系统...", "INFO")
        
        try:
            # Stop any ongoing audio playback
            if self.system_state.is_speaking:
                self.tts_player.stop_playback()
                
                # Stop VTS animation if connected
                if self.system_state.vts_connected:
                    await self.vts_client.stop_mouth_animation()
            
            # Clean up current audio file
            if self.system_state.current_audio_file:
                self.tts_player.cleanup_temp_file(self.system_state.current_audio_file)
            
            # Disconnect from VTube Studio
            if self.system_state.vts_connected:
                await self.vts_client.disconnect()
            
            # Reset system state
            self.system_state.reset_connections()
            self.system_state.set_audio_state(False)
            
            self._log_status("系统关闭完成", "SUCCESS")
            
        except Exception as e:
            self.error_handler.handle_thread_error("system_shutdown", e)
            self._log_status(f"系统关闭时出错: {str(e)}", "ERROR")
