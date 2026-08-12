"""
Text-to-Speech Player using Edge-TTS and pygame
This module handles audio generation and playback for the AI VTuber system.
"""

import asyncio
import os
import tempfile
import logging
import time
import re
from pathlib import Path
from typing import Optional
import urllib.parse
import aiohttp
import edge_tts
import pygame


class TTSPlayer:
    """
    Text-to-Speech player that generates audio using GPT-SoVITS with Edge-TTS fallback.
    Handles temporary file management and cleanup.
    Includes circuit breaker pattern for reliability.
    """
    
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", config=None):
        """
        Initialize the TTS player.
        
        Args:
            voice: The voice to use for Edge-TTS generation
            config: SystemConfig instance for GPT-SoVITS settings
        """
        self.voice = voice
        self.config = config
        self.current_audio_file: Optional[str] = None
        self.is_playing_flag = False
        self.logger = logging.getLogger(__name__)
        
        # Circuit breaker for GPT-SoVITS reliability
        self.sovits_failure_count = 0
        self.sovits_circuit_open = False
        self.sovits_circuit_open_time = 0
        self.sovits_circuit_timeout = 60  # 60 seconds
        self.sovits_max_failures = 3
        
        # Semaphore to limit concurrent GPT-SoVITS requests (prevents request pile-up)
        self._sovits_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests
        
        # Initialize pygame mixer
        try:
            pygame.mixer.init()
            self.logger.info("Pygame mixer initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize pygame mixer: {e}")
            raise
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.sovits_circuit_open:
            return False
        
        # Check if circuit should be closed (timeout expired)
        if time.time() - self.sovits_circuit_open_time > self.sovits_circuit_timeout:
            self.logger.info("Circuit breaker timeout expired, attempting to close circuit")
            self.sovits_circuit_open = False
            self.sovits_failure_count = 0
            return False
        
        return True
    
    def _record_sovits_failure(self):
        """Record a GPT-SoVITS failure and potentially open circuit."""
        self.sovits_failure_count += 1
        self.logger.warning(f"GPT-SoVITS failure count: {self.sovits_failure_count}/{self.sovits_max_failures}")
        
        if self.sovits_failure_count >= self.sovits_max_failures:
            self.sovits_circuit_open = True
            self.sovits_circuit_open_time = time.time()
            self.logger.warning(f"Circuit breaker opened - GPT-SoVITS disabled for {self.sovits_circuit_timeout} seconds")
    
    def _record_sovits_success(self):
        """Record a GPT-SoVITS success and reset failure count."""
        if self.sovits_failure_count > 0:
            self.logger.info("GPT-SoVITS success - resetting failure count")
        self.sovits_failure_count = 0
        self.sovits_circuit_open = False
    
    def _clean_text_for_tts(self, text: str) -> str:
        """Clean text for TTS by removing problematic characters and tags."""
        if not text:
            return ""
        
        # Remove emotion tags like [happy], [sad], etc.
        text = re.sub(r'\[[\w\s]+\]', '', text)
        
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'`(.*?)`', r'\1', text)        # Code
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Ensure text is not empty after cleaning
        if not text:
            return "..."
        
        return text
    async def generate_audio(self, text: str) -> str:
        """
        Generate audio file from text using GPT-SoVITS with Edge-TTS fallback.
        Includes circuit breaker pattern for reliability.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            str: Absolute path to the generated audio file
            
        Raises:
            Exception: If both GPT-SoVITS and Edge-TTS fail
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Clean text for TTS
        clean_text = self._clean_text_for_tts(text)
        if not clean_text:
            raise ValueError("Text is empty after cleaning")
        
        # Try GPT-SoVITS first if enabled and circuit is closed
        if (self.config and 
            self.config.enable_voice_cloning and 
            self.config.fallback_to_edge_tts and
            not self._is_circuit_open()):
            
            try:
                self.logger.info("Attempting GPT-SoVITS audio generation...")
                start_time = time.time()
                
                # Try GPT-SoVITS with timeout
                audio_file = await self._generate_audio_sovits(clean_text)
                
                elapsed_time = time.time() - start_time
                self.logger.info(f"GPT-SoVITS generation successful in {elapsed_time:.2f}s")
                self._record_sovits_success()
                return audio_file
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                self.logger.warning(f"GPT-SoVITS failed after {elapsed_time:.2f}s: {e}")
                self._record_sovits_failure()
                self.logger.info("Falling back to Edge-TTS...")
        elif self._is_circuit_open():
            self.logger.info("GPT-SoVITS circuit breaker is open, using Edge-TTS directly")
        
        # Use Edge-TTS (either as fallback or primary method)
        try:
            self.logger.info("Using Edge-TTS for audio generation...")
            return await self._generate_audio_edge(clean_text)
            
        except Exception as e:
            self.logger.error(f"Edge-TTS fallback also failed: {e}")
            
            # Try with even more cleaned text as final attempt
            try:
                self.logger.info("Attempting Edge-TTS with simplified text...")
                simple_text = re.sub(r'[^\w\s\u4e00-\u9fff.,!?]', '', clean_text)
                if simple_text.strip():
                    return await self._generate_audio_edge(simple_text)
            except Exception as e2:
                self.logger.error(f"Edge-TTS with simplified text also failed: {e2}")
            
            raise Exception(f"Both GPT-SoVITS and Edge-TTS failed. Last error: {e}")
    
    async def _generate_audio_sovits(self, text: str) -> str:
        """
        Generate audio file from text using GPT-SoVITS API.
        Uses POST request with JSON payload for better stability.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            str: Absolute path to the generated audio file
            
        Raises:
            Exception: If GPT-SoVITS generation fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        if not self.config or not self.config.enable_voice_cloning:
            raise Exception("GPT-SoVITS is not enabled in configuration")
        
        # Check circuit breaker before acquiring semaphore
        if self._is_circuit_open():
            raise Exception("GPT-SoVITS circuit breaker is open")
        
        # Use semaphore to limit concurrent requests
        async with self._sovits_semaphore:
            # Check circuit breaker again after acquiring semaphore (may have opened while waiting)
            if self._is_circuit_open():
                raise Exception("GPT-SoVITS circuit breaker opened while waiting for semaphore")
            
            try:
                # Create temporary file with absolute path
                temp_dir = tempfile.gettempdir()
                temp_file = tempfile.NamedTemporaryFile(
                    suffix=".wav", 
                    delete=False, 
                    dir=temp_dir
                )
                output_file = os.path.abspath(temp_file.name)
                temp_file.close()
                
                # 构造绝对路径的参考音频路径
                ref_audio_path = self.config.sovits_ref_audio_path
                if ref_audio_path and not os.path.isabs(ref_audio_path):
                    # 转换为绝对路径
                    ref_audio_path = os.path.abspath(ref_audio_path)
                
                # 构造POST请求的JSON数据（完整参数）
                payload = {
                    "text": text,
                    "text_lang": self.config.sovits_language or "zh",
                    "ref_audio_path": ref_audio_path,
                    "prompt_text": self.config.sovits_prompt_text or "你好，我是AI助手！",
                    "prompt_lang": self.config.sovits_prompt_lang or "zh",
                    "text_split_method": "cut5",
                    "batch_size": 1,
                    "media_type": "wav",
                    "streaming_mode": False,
                    "parallel_infer": True,
                    "top_k": 5,
                    "top_p": 1.0,
                    "temperature": 1.0
                }
                
                # 使用根路径而不是/tts端点（兼容旧版GPT-SoVITS）
                tts_url = f"{self.config.sovits_url.rstrip('/')}"
                
                self.logger.info(f"Generating audio via GPT-SoVITS for text: {text[:50]}...")
                self.logger.info(f"GPT-SoVITS URL: {tts_url}")
                self.logger.info(f"Reference audio: {ref_audio_path}")
                self.logger.info(f"Output file: {output_file}")
                self.logger.debug(f"Payload: text_lang={payload['text_lang']}, prompt_text={payload['prompt_text'][:20]}...")
                
                # Make HTTP POST request to GPT-SoVITS
                timeout = aiohttp.ClientTimeout(total=self.config.sovits_timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(tts_url, json=payload) as response:
                        if response.status != 200:
                            # Try to get error details from response body
                            try:
                                error_body = await response.text()
                                self.logger.error(f"GPT-SoVITS error response: {error_body[:500]}")
                            except:
                                error_body = "Unable to read error body"
                            
                            if response.status == 400:
                                raise Exception(f"GPT-SoVITS API returned 400 Bad Request. "
                                              f"Check reference audio path and parameters. "
                                              f"Error: {error_body[:200]}")
                            elif response.status == 404:
                                raise Exception(f"GPT-SoVITS /tts endpoint not found. "
                                              f"Make sure you're using GPT-SoVITS v2 with API support.")
                            else:
                                raise Exception(f"GPT-SoVITS API returned status {response.status}: {error_body[:200]}")
                        
                        # Check content type
                        content_type = response.headers.get('content-type', '')
                        if not content_type.startswith('audio/'):
                            raise Exception(f"GPT-SoVITS returned non-audio content: {content_type}")
                        
                        # Write audio data to file with circuit breaker check during download
                        with open(output_file, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                # Check circuit breaker during download - abort if opened
                                if self._is_circuit_open():
                                    self.logger.warning("Circuit breaker opened during download, aborting")
                                    raise Exception("GPT-SoVITS circuit breaker opened during download")
                                f.write(chunk)
                
                # Verify file was created and has content
                if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                    raise Exception(f"GPT-SoVITS audio file generation failed: {output_file}")
                
                self.logger.info(f"GPT-SoVITS audio generated successfully: {output_file}")
                return output_file
                
            except asyncio.TimeoutError:
                self.logger.error(f"GPT-SoVITS request timed out after {self.config.sovits_timeout}s")
                # Clean up failed file if it exists
                if 'output_file' in locals() and os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except:
                        pass
                raise Exception("GPT-SoVITS request timed out")
            except Exception as e:
                self.logger.error(f"Failed to generate audio via GPT-SoVITS: {e}")
                # Clean up failed file if it exists
                if 'output_file' in locals() and os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except:
                        pass
                raise
    
                self.logger.error(f"Failed to generate audio via GPT-SoVITS: {e}")
                # Clean up failed file if it exists
                if 'output_file' in locals() and os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except:
                        pass
                raise
    
    async def _generate_audio_edge(self, text: str) -> str:
        """
        Generate audio file from text using Edge-TTS.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            str: Absolute path to the generated audio file
            
        Raises:
            Exception: If audio generation fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            # Create temporary file with absolute path
            temp_dir = tempfile.gettempdir()
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".mp3", 
                delete=False, 
                dir=temp_dir
            )
            output_file = os.path.abspath(temp_file.name)
            temp_file.close()
            
            self.logger.info(f"Generating audio via Edge-TTS for text: {text[:50]}...")
            self.logger.info(f"Output file: {output_file}")
            
            # Generate audio using Edge-TTS
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_file)
            
            # Verify file was created and has content
            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                raise Exception(f"Edge-TTS audio file generation failed: {output_file}")
            
            self.logger.info(f"Edge-TTS audio generated successfully: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to generate audio via Edge-TTS: {e}")
            # Clean up failed file if it exists
            if 'output_file' in locals() and os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            raise
    
    def play_audio(self, file_path: str, blocking: bool = True) -> None:
        """
        Play audio file using pygame.
        
        Args:
            file_path: Absolute path to the audio file to play
            blocking: If True, wait for playback to complete. If False, return immediately.
            
        Raises:
            Exception: If audio playback fails
        """
        if not os.path.isabs(file_path):
            raise ValueError(f"File path must be absolute: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        try:
            self.logger.info(f"Playing audio file: {file_path}")
            self.current_audio_file = file_path
            self.is_playing_flag = True
            
            # Load and play the audio file
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Wait for playback to complete if blocking mode
            if blocking:
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                
                self.is_playing_flag = False
                self.logger.info("Audio playback completed")
            
        except Exception as e:
            self.is_playing_flag = False
            self.logger.error(f"Failed to play audio: {e}")
            raise
    
    def get_busy(self) -> bool:
        """
        Check if pygame mixer is currently playing audio.
        
        This is a direct wrapper around pygame.mixer.music.get_busy() for
        external callers that need to poll playback status.
        
        Returns:
            bool: True if audio is currently playing, False otherwise
        """
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False
    
    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.
        
        Returns:
            bool: True if audio is playing, False otherwise
        """
        return self.is_playing_flag and pygame.mixer.music.get_busy()
    
    def stop_playback(self) -> None:
        """
        Stop current audio playback.
        """
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                self.logger.info("Audio playback stopped")
            self.is_playing_flag = False
        except Exception as e:
            self.logger.error(f"Failed to stop audio playback: {e}")
    
    def get_playback_position(self) -> float:
        """
        Get current playback position in seconds.
        
        Note: pygame.mixer.music does not provide position information,
        so this method returns an approximation based on playback start time.
        
        Returns:
            float: Approximate playback position in seconds, or 0.0 if not playing
        """
        try:
            if not self.is_playing():
                return 0.0
            
            # pygame.mixer.music doesn't provide position info
            # Return 0.0 as a placeholder - actual position tracking would require
            # more sophisticated audio library or manual timing
            return 0.0
            
        except Exception as e:
            self.logger.debug(f"Error getting playback position: {e}")
            return 0.0
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """
        Clean up temporary audio file.
        
        Args:
            file_path: Path to the temporary file to clean up
        """
        try:
            if file_path and os.path.exists(file_path):
                # Ensure pygame has released the file
                if pygame.mixer.get_init():
                    pygame.mixer.music.unload()
                
                # Small delay to ensure file handle is released
                import time
                time.sleep(0.1)
                
                os.remove(file_path)
                self.logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to clean up temporary file {file_path}: {e}")
            # Try again after a longer delay
            try:
                import time
                time.sleep(0.5)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.info(f"Cleaned up temporary file on retry: {file_path}")
            except Exception as retry_e:
                self.logger.warning(f"Could not clean up temporary file after retry {file_path}: {retry_e}")
    
    async def check_tts_health(self) -> dict:
        """
        Check the health of TTS services.
        
        Returns:
            dict: Health status of GPT-SoVITS and Edge-TTS
        """
        health_status = {
            "sovits": {"available": False, "circuit_open": self._is_circuit_open()},
            "edge_tts": {"available": False}
        }
        
        # Check GPT-SoVITS if enabled and circuit is closed
        if (self.config and 
            self.config.enable_voice_cloning and 
            not self._is_circuit_open()):
            
            try:
                # Quick health check with minimal text
                test_text = "测试"
                timeout = aiohttp.ClientTimeout(total=5.0)  # Short timeout for health check
                
                params = {
                    "text": test_text,
                    "text_lang": self.config.sovits_language
                }
                
                query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
                health_url = f"{self.config.sovits_url}?{query_string}"
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(health_url) as response:
                        if response.status == 200:
                            health_status["sovits"]["available"] = True
                            self.logger.debug("GPT-SoVITS health check passed")
                        else:
                            self.logger.debug(f"GPT-SoVITS health check failed: {response.status}")
                            
            except Exception as e:
                self.logger.debug(f"GPT-SoVITS health check failed: {e}")
        
        # Check Edge-TTS
        try:
            # Edge-TTS is usually available if the library is installed
            import edge_tts
            health_status["edge_tts"]["available"] = True
            self.logger.debug("Edge-TTS is available")
        except Exception as e:
            self.logger.debug(f"Edge-TTS not available: {e}")
        
        return health_status

    async def speak(self, text: str) -> None:
        """
        Complete TTS workflow: generate audio, play it, and clean up.
        
        Args:
            text: The text to convert to speech and play
        """
        audio_file = None
        try:
            # Generate audio
            audio_file = await self.generate_audio(text)
            
            # Play audio
            self.play_audio(audio_file)
            
        finally:
            # Always clean up temporary file
            if audio_file:
                self.cleanup_temp_file(audio_file)
                if audio_file == self.current_audio_file:
                    self.current_audio_file = None
    
    def __del__(self):
        """
        Cleanup when object is destroyed.
        """
        try:
            if self.current_audio_file and os.path.exists(self.current_audio_file):
                self.cleanup_temp_file(self.current_audio_file)
        except:
            pass