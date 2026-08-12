"""
TTS Pipeline - Producer-Consumer pattern for audio generation and playback.

This module implements a pipeline that generates audio asynchronously while
playing previously generated audio, enabling seamless sentence-by-sentence
playback with minimal latency.

Includes phrase caching for instant playback of common phrases.
"""

import asyncio
import logging
import os
from queue import Queue, Empty
from threading import Thread, Event
from typing import Optional, List, Dict, TYPE_CHECKING, Callable
from dataclasses import dataclass

if TYPE_CHECKING:
    from src.tts_player import TTSPlayer
    from src.config import UXConfig
    from src.vts_client import VTSClient


@dataclass
class AudioItem:
    """Represents an audio item in the playback queue."""
    file_path: str
    text: str  # Original text for debugging/logging
    sequence_number: int  # For maintaining order


@dataclass
class AudioPacket:
    """
    Rich media audio packet containing audio path and subtitle information.
    
    This dataclass enables synchronized subtitle display with audio playback
    by bundling the audio file path with its corresponding text content.
    
    Attributes:
        file_path: Path to the audio file (local cache or generated temp file)
        subtitle_text: Original text for subtitle display (before cleaning)
        clean_text: Cleaned text that was sent to TTS (after removing emoji/markdown)
        is_cached: Whether this audio came from the phrase cache (True) or was generated (False)
        duration: Audio duration in seconds (0.0 if unknown)
    
    Requirements: 5.1, 5.4
    """
    file_path: str
    subtitle_text: str
    clean_text: str
    is_cached: bool = False
    duration: float = 0.0


# Default phrase cache for common responses
# These phrases will be played instantly without calling TTS API
# Requirements: 2.3, 2.4
DEFAULT_PHRASE_CACHE: Dict[str, str] = {
    "嗯...": "assets/cache/hmm.mp3",
    "让我想想": "assets/cache/thinking.mp3",
    "你好": "assets/cache/hello.mp3",
    "好的": "assets/cache/ok.mp3",
    "是的": "assets/cache/yes.mp3",
    "嗯嗯": "assets/cache/hmm2.mp3",
    "哦": "assets/cache/oh.mp3",
    "啊": "assets/cache/ah.mp3",
}


class TTSPipeline:
    """
    TTS Pipeline implementing Producer-Consumer pattern.
    
    Producer: Receives text sentences, generates audio asynchronously,
              and enqueues completed audio files.
    Consumer: Monitors the queue and plays audio files in order.
    
    This enables overlapping audio generation with playback for
    seamless sentence-by-sentence TTS.
    
    Includes phrase caching for instant playback of common phrases.
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    
    def __init__(
        self, 
        tts_player: 'TTSPlayer',
        vts_client: 'VTSClient' = None,  # NEW: VTS client for lip-sync
        max_queue_size: int = 10,
        ux_config: 'UXConfig' = None
    ):
        """
        Initialize the TTS Pipeline.
        
        Args:
            tts_player: TTSPlayer instance for audio generation and playback
            vts_client: VTSClient instance for lip-sync support (optional)
            max_queue_size: Maximum number of audio files to queue (prevents memory issues)
            ux_config: UX configuration for cache settings (optional)
        """
        self.tts_player = tts_player
        self.vts_client = vts_client  # Store VTS client for lip-sync
        self.max_queue_size = max_queue_size
        self.ux_config = ux_config
        self.logger = logging.getLogger(__name__)
        
        # Playback queue - stores AudioPacket objects for rich media support
        # Requirements: 5.1, 5.2
        self.playback_queue: Queue[AudioPacket] = Queue(maxsize=max_queue_size)
        
        # Control flags
        self.is_running = False
        self._stop_event = Event()
        self._interrupt_event = Event()
        
        # Playback thread
        self.playback_thread: Optional[Thread] = None
        
        # Track generation tasks for cancellation
        self.generation_tasks: List[asyncio.Task] = []
        
        # Sequence counter for maintaining order
        self._sequence_counter = 0
        
        # Currently playing packet (for interrupt handling)
        self._current_packet: Optional[AudioPacket] = None
        
        # Phrase cache for instant playback
        # Requirements: 2.3, 2.4
        self.phrase_cache: Dict[str, str] = {}
        self._cache_enabled = False
        
        # Interruption callback for full-duplex engine integration
        self._interruption_callback: Optional[Callable] = None
        
        # State tracking for VTS synchronization
        self._playback_start_time: Optional[float] = None
        self._current_audio_duration: float = 0.0
        self._mouth_animation_active: bool = False
        
        # Load cache if UX config enables it
        if ux_config is not None and ux_config.enable_cache:
            self._load_cache()
    
    def set_vts_client(self, vts_client: 'VTSClient') -> None:
        """
        Set VTS client for lip-sync support.
        
        This method allows dependency injection of the VTSClient after
        TTSPipeline initialization, which is useful when the VTSClient
        needs to be initialized after the TTSPipeline.
        
        Args:
            vts_client: VTSClient instance for lip-sync support
        """
        self.vts_client = vts_client
        self.logger.info("VTSClient set for lip-sync support")
    
    def _load_cache(self) -> None:
        """
        Load phrase cache from default entries and configuration.
        
        Validates that cache files exist before adding them to the cache.
        Requirements: 2.3, 2.4
        """
        self.logger.info("Loading phrase cache...")
        
        # Start with default cache entries
        self.phrase_cache = {}
        
        for phrase, file_path in DEFAULT_PHRASE_CACHE.items():
            if os.path.exists(file_path):
                self.phrase_cache[phrase] = file_path
                self.logger.debug(f"Cached phrase: '{phrase}' -> {file_path}")
            else:
                self.logger.warning(f"Cache file not found for phrase '{phrase}': {file_path}")
        
        # Load additional cache entries from config if available
        if self.ux_config and hasattr(self.ux_config, 'custom_cache_entries'):
            custom_entries = getattr(self.ux_config, 'custom_cache_entries', {})
            for phrase, file_path in custom_entries.items():
                if os.path.exists(file_path):
                    self.phrase_cache[phrase] = file_path
                    self.logger.debug(f"Custom cached phrase: '{phrase}' -> {file_path}")
                else:
                    self.logger.warning(f"Custom cache file not found for phrase '{phrase}': {file_path}")
        
        self._cache_enabled = len(self.phrase_cache) > 0
        self.logger.info(f"Phrase cache loaded: {len(self.phrase_cache)} entries")
    
    def is_cache_enabled(self) -> bool:
        """Check if phrase cache is enabled and has entries."""
        return self._cache_enabled
    
    def get_cached_phrases(self) -> Dict[str, str]:
        """Get a copy of the current phrase cache."""
        return self.phrase_cache.copy()
    
    def check_cache(self, text: str) -> Optional[str]:
        """
        Check if text matches a cached phrase.
        
        Args:
            text: Text to check against cache
            
        Returns:
            File path if cache hit, None otherwise
            
        Requirements: 2.1, 2.2
        """
        if not self._cache_enabled:
            return None
        
        # Exact match check
        if text in self.phrase_cache:
            file_path = self.phrase_cache[text]
            if os.path.exists(file_path):
                self.logger.debug(f"Cache hit for phrase: '{text}'")
                return file_path
            else:
                self.logger.warning(f"Cache file missing: {file_path}")
                return None
        
        return None
    
    def get_filler_phrases(self) -> List[str]:
        """
        Get list of filler phrases suitable for latency masking.
        
        Filler phrases are short interjections like "嗯...", "让我想想" that
        can be played immediately while waiting for LLM response.
        
        Returns:
            List of filler phrase keys from the cache
            
        Requirements: 2.1 (extended)
        """
        # Define which cached phrases are suitable as fillers
        filler_keys = ["嗯...", "让我想想", "嗯嗯", "哦"]
        
        # Return only fillers that exist in cache and have valid files
        available_fillers = []
        for key in filler_keys:
            if key in self.phrase_cache:
                file_path = self.phrase_cache[key]
                if os.path.exists(file_path):
                    available_fillers.append(key)
        
        return available_fillers
    
    def play_filler(self) -> bool:
        """
        Play a random filler audio immediately to mask latency.
        
        This method selects a random filler phrase from the cache and plays
        it immediately (not through the queue) to fill the silence while
        waiting for LLM response and TTS generation.
        
        The filler audio is played directly without entering the playback queue,
        ensuring immediate playback for latency masking.
        
        Returns:
            True if filler was played successfully, False otherwise
            
        Requirements: 2.1 (extended) - Latency masking with filler audio
        """
        import random
        
        if not self._cache_enabled:
            self.logger.debug("Cache disabled, skipping filler audio")
            return False
        
        # Get available filler phrases
        available_fillers = self.get_filler_phrases()
        
        if not available_fillers:
            self.logger.debug("No filler phrases available in cache")
            return False
        
        # Select random filler
        filler_phrase = random.choice(available_fillers)
        filler_path = self.phrase_cache[filler_phrase]
        
        # Verify file exists
        if not os.path.exists(filler_path):
            self.logger.warning(f"Filler audio file not found: {filler_path}")
            return False
        
        try:
            self.logger.info(f"Playing filler audio: '{filler_phrase}' -> {filler_path}")

            # Play in background thread to avoid blocking asyncio event loop
            def play_filler_async():
                try:
                    self.tts_player.play_audio(filler_path)
                except Exception as e:
                    self.logger.error(f"Error in filler audio playback thread: {e}")

            import threading
            filler_thread = threading.Thread(target=play_filler_async, daemon=True)
            filler_thread.start()

            self.logger.debug(f"Filler audio playback started: '{filler_phrase}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to play filler audio: {e}")
            return False

    async def start(self, on_subtitle: Callable[[str], None] = None) -> None:
        """
        Start the TTS pipeline.
        
        Initializes the playback worker thread that monitors the queue
        and plays audio files as they become available.
        
        Args:
            on_subtitle: Optional callback function for subtitle updates.
                        Will be called with subtitle text before audio plays,
                        and with empty string after audio completes.
                        Must be thread-safe (e.g., use root.after() for Tkinter).
        
        Requirements: 1.1, 5.3 - A/V synchronization support
        """
        if self.is_running:
            self.logger.warning("TTSPipeline is already running")
            return
        
        self.logger.info("Starting TTS Pipeline...")
        self.is_running = True
        self._stop_event.clear()
        self._interrupt_event.clear()
        self._sequence_counter = 0
        
        # Store subtitle callback for use in playback worker
        self._on_subtitle_callback = on_subtitle
        
        # Start playback worker thread with subtitle callback
        self.playback_thread = Thread(
            target=self._playback_worker,
            args=(on_subtitle,),
            name="TTSPipeline-Playback",
            daemon=True
        )
        self.playback_thread.start()
        self.logger.info("TTS Pipeline started successfully")
    
    async def stop(self) -> None:
        """
        Stop the TTS pipeline gracefully.
        
        Waits for pending generation tasks to complete, then stops
        the playback thread and cleans up resources.
        """
        if not self.is_running:
            return
        
        self.logger.info("Stopping TTS Pipeline...")
        
        # Signal stop
        self._stop_event.set()
        self.is_running = False
        
        # Wait for generation tasks to complete
        if self.generation_tasks:
            self.logger.info(f"Waiting for {len(self.generation_tasks)} generation tasks...")
            await asyncio.gather(*self.generation_tasks, return_exceptions=True)
            self.generation_tasks.clear()
        
        # Wait for playback thread to finish
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2.0)
        
        # Clean up remaining items in queue
        self._cleanup_queue()
        
        self.logger.info("TTS Pipeline stopped")
    
    async def put_text(self, text: str, clean_text: str = None) -> None:
        """
        Producer: Submit text for audio generation.
        
        First checks the phrase cache for instant playback. If not cached,
        asynchronously generates audio for the given text and adds
        the result to the playback queue as an AudioPacket.
        
        Includes queue management to prevent overwhelming the system.
        
        Args:
            text: Original text (used for subtitle display)
            clean_text: Cleaned text for TTS (if None, uses original text)
            
        Requirements: 2.1, 2.2, 5.1, 5.2
        """
        if not self.is_running:
            self.logger.warning("TTSPipeline is not running, cannot accept text")
            return
        
        if not text or not text.strip():
            self.logger.debug("Ignoring empty text")
            return
        
        # Check queue size to prevent overwhelming
        if self.playback_queue.qsize() > 10:
            self.logger.warning("TTS queue is full (>10 items), pausing text acceptance")
            # Wait for queue to drain
            while self.playback_queue.qsize() > 5 and self.is_running:
                await asyncio.sleep(0.1)
            
            if not self.is_running:
                return
        
        # Use original text if no clean text provided
        if clean_text is None:
            clean_text = text
        
        # Assign sequence number for ordering
        sequence_number = self._sequence_counter
        self._sequence_counter += 1
        
        # Check cache first for instant playback
        # Requirements: 2.1, 2.2
        cached_path = self.check_cache(text.strip())
        if cached_path is not None:
            self.logger.info(f"Cache hit (seq={sequence_number}): '{text[:30]}...' -> {cached_path}")
            
            # Create AudioPacket with is_cached=True
            packet = AudioPacket(
                file_path=cached_path,
                subtitle_text=text,
                clean_text=clean_text,
                is_cached=True,
                duration=0.0
            )
            
            # Add directly to queue (no async generation needed)
            try:
                self.playback_queue.put(packet, timeout=5.0)
                self.logger.debug(f"Cached AudioPacket enqueued (seq={sequence_number})")
            except Exception as e:
                self.logger.error(f"Failed to enqueue cached AudioPacket: {e}")
            return
        
        self.logger.info(f"Queuing text for TTS (seq={sequence_number}): {text[:50]}...")
        
        # Create async task for generation
        task = asyncio.create_task(
            self._generate_and_enqueue(text, clean_text, sequence_number)
        )
        self.generation_tasks.append(task)
        
        # Clean up completed tasks
        self.generation_tasks = [t for t in self.generation_tasks if not t.done()]
    
    async def _generate_and_enqueue(self, text: str, clean_text: str, sequence_number: int) -> None:
        """
        Generate audio for text and add to playback queue as AudioPacket.
        Includes improved error handling and fallback mechanisms.
        
        Args:
            text: Original text (for subtitle display)
            clean_text: Cleaned text (sent to TTS)
            sequence_number: Order in which this text was submitted
            
        Requirements: 5.1, 5.2
        """
        # Check if interrupted before starting
        if self._interrupt_event.is_set():
            self.logger.debug(f"Skipping generation (seq={sequence_number}) - interrupted")
            return
        
        try:
            self.logger.debug(f"Generating audio (seq={sequence_number})...")
            audio_path = await self.tts_player.generate_audio(clean_text)
            
            # Check if interrupted after generation
            if self._interrupt_event.is_set():
                self.logger.debug(f"Discarding generated audio (seq={sequence_number}) - interrupted")
                self.tts_player.cleanup_temp_file(audio_path)
                return
            
            # Create AudioPacket with rich media information
            packet = AudioPacket(
                file_path=audio_path,
                subtitle_text=text,
                clean_text=clean_text,
                is_cached=False,
                duration=0.0  # Duration can be calculated later if needed
            )
            
            # Add to queue (blocks if queue is full)
            try:
                self.playback_queue.put(packet, timeout=5.0)
                self.logger.debug(f"AudioPacket enqueued (seq={sequence_number})")
            except Exception as e:
                self.logger.error(f"Failed to enqueue AudioPacket: {e}")
                self.tts_player.cleanup_temp_file(audio_path)
                
        except asyncio.CancelledError:
            self.logger.debug(f"Generation task cancelled (seq={sequence_number})")
            raise
        except Exception as e:
            self.logger.error(f"Failed to generate audio (seq={sequence_number}): {e}")
            
            # Insert silence placeholder to maintain timing
            try:
                silence_packet = AudioPacket(
                    file_path="",  # Empty path indicates silence
                    subtitle_text="[音频生成失败]",
                    clean_text="",
                    is_cached=False,
                    duration=0.5  # 0.5 second silence
                )
                self.playback_queue.put(silence_packet, timeout=1.0)
                self.logger.debug(f"Silence placeholder enqueued (seq={sequence_number})")
            except Exception as silence_error:
                self.logger.error(f"Failed to enqueue silence placeholder: {silence_error}")

    def _playback_worker(self, on_subtitle: Callable[[str], None] = None) -> None:
        """
        Consumer: Background thread that plays audio from the queue with A/V sync.
        
        Monitors the playback queue and plays AudioPackets in order.
        Updates subtitles BEFORE playing audio to ensure synchronization.
        Blocks until audio playback completes before clearing subtitles.
        Handles interruption requests and cleanup.
        
        Args:
            on_subtitle: Callback function for subtitle updates (thread-safe).
                        Called with subtitle text before audio plays,
                        and with empty string after audio completes.
        
        Requirements: 5.2, 5.3 - Ensures seamless audio transitions with subtitle support
        Requirements: 1.1, 1.2 - A/V synchronization
        """
        self.logger.info("Playback worker started")
        
        while not self._stop_event.is_set():
            try:
                # Check for interrupt
                if self._interrupt_event.is_set():
                    self._handle_interrupt_in_worker(on_subtitle)
                    continue
                
                # Try to get next AudioPacket (with timeout to check stop flag)
                try:
                    packet = self.playback_queue.get(timeout=0.1)
                except Empty:
                    continue
                
                # Check interrupt again before playing
                if self._interrupt_event.is_set():
                    if not packet.is_cached:
                        self.tts_player.cleanup_temp_file(packet.file_path)
                    continue
                
                # Set current packet for interrupt handling
                self._current_packet = packet
                cache_status = "(cached)" if packet.is_cached else "(generated)"
                self.logger.info(f"Playing AudioPacket {cache_status}: {packet.subtitle_text[:30]}...")
                
                try:
                    # Handle silence placeholder
                    if not packet.file_path:
                        self.logger.debug(f"Playing silence placeholder for {packet.duration}s")
                        # Update subtitle for error indication
                        if on_subtitle:
                            on_subtitle(packet.subtitle_text)
                        
                        # Wait for silence duration
                        import time
                        time.sleep(packet.duration)
                        
                        # Clear subtitle after silence
                        if on_subtitle:
                            on_subtitle("")
                        continue
                    
                    # Update subtitle BEFORE playing audio (A/V sync - Requirements 1.1, 5.3)
                    if on_subtitle:
                        on_subtitle(packet.subtitle_text)
                    
                    # Get audio duration for mouth animation
                    audio_duration = self._get_audio_duration(packet.file_path)
                    self._current_audio_duration = audio_duration
                    
                    # Start mouth animation BEFORE playing audio (Requirements 2.1, 2.2, 2.3)
                    mouth_animation_started = False
                    if self.vts_client:
                        try:
                            if audio_duration > 0:
                                # Use duration-based animation for natural mouth movement
                                success = self.vts_client.animate_mouth_for_duration(audio_duration)
                                if success:
                                    mouth_animation_started = True
                                    self._mouth_animation_active = True
                                    self.logger.debug(f"Started natural mouth animation for {audio_duration:.2f}s")
                                else:
                                    # Fallback to simple open/close
                                    success = self.vts_client.start_mouth_sync()
                                    mouth_animation_started = success
                                    self._mouth_animation_active = success
                                    self.logger.debug("Using fallback mouth animation (open/close)")
                            else:
                                # No duration info, use simple open/close
                                success = self.vts_client.start_mouth_sync()
                                mouth_animation_started = success
                                self._mouth_animation_active = success
                                self.logger.debug("Using simple mouth animation (no duration info)")
                                
                            if not mouth_animation_started:
                                self.logger.warning("Failed to start mouth animation - continuing with audio")
                        except Exception as e:
                            self.logger.warning(f"Error starting mouth animation: {e} - continuing with audio")
                    
                    # Record playback start time for position tracking
                    import time
                    self._playback_start_time = time.time()
                    
                    # Play audio in non-blocking mode so we can check for interrupts
                    self.tts_player.play_audio(packet.file_path, blocking=False)
                    
                    # BLOCK until audio finishes playing (Requirements 1.1, 1.2)
                    # This ensures subtitle stays visible for the duration of the audio
                    self._wait_for_playback_completion()
                    
                    # Stop mouth animation AFTER audio completes (Requirements 2.1, 2.2, 2.3)
                    # Only if we didn't use duration-based animation (which stops automatically)
                    if self.vts_client and mouth_animation_started and audio_duration <= 0:
                        try:
                            success = self.vts_client.stop_mouth_sync()
                            if success:
                                self._mouth_animation_active = False
                                self.logger.debug("Mouth animation stopped after audio completion")
                            else:
                                self.logger.warning("Failed to stop mouth animation")
                        except Exception as e:
                            self.logger.warning(f"Error stopping mouth animation: {e}")
                    elif audio_duration > 0:
                        # Duration-based animation should stop automatically, just update state
                        self._mouth_animation_active = False
                    
                    # Clear playback timing state
                    self._playback_start_time = None
                    self._current_audio_duration = 0.0
                    
                    # Clear subtitle after audio completes with configurable delay
                    if on_subtitle:
                        subtitle_delay = 0.5  # Default delay
                        if self.ux_config and hasattr(self.ux_config, 'subtitle_delay'):
                            subtitle_delay = self.ux_config.subtitle_delay
                        
                        import time
                        time.sleep(subtitle_delay)
                        on_subtitle("")
                    
                except Exception as e:
                    self.logger.error(f"Playback error: {e}")
                    # Clear subtitle on error
                    if on_subtitle:
                        on_subtitle("")
                finally:
                    # Clean up the temp file after playback (only for non-cached files)
                    if not packet.is_cached:
                        self.tts_player.cleanup_temp_file(packet.file_path)
                    self._current_packet = None
                    
            except Exception as e:
                self.logger.error(f"Playback worker error: {e}")
        
        self.logger.info("Playback worker stopped")
    
    def _get_audio_duration(self, audio_file: str) -> float:
        """
        Get the duration of an audio file in seconds.
        
        Args:
            audio_file: Path to the audio file
            
        Returns:
            float: Duration in seconds, or 0.0 if unable to determine
        """
        try:
            # Try using pygame to get duration
            import pygame
            
            # Initialize pygame mixer if not already done
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            # Load the sound to get its length
            sound = pygame.mixer.Sound(audio_file)
            duration = sound.get_length()
            
            self.logger.debug(f"Audio duration: {duration:.2f}s for {audio_file}")
            return duration
            
        except Exception as e:
            self.logger.debug(f"Could not determine audio duration for {audio_file}: {e}")
            return 0.0
    
    def _wait_for_playback_completion(self) -> None:
        """
        Block until audio playback completes.
        
        Uses pygame.mixer.music.get_busy() via tts_player.get_busy() to check 
        if audio is still playing. Polls at 50ms intervals to balance 
        responsiveness with CPU usage.
        Also checks for interrupt events to allow early termination.
        
        Requirements: 1.1, 1.2 - Synchronous playback for A/V sync
        """
        import time
        
        while self.tts_player.get_busy():
            # Check for interrupt during playback
            if self._interrupt_event.is_set():
                self.logger.debug("Playback interrupted while waiting for completion")
                break
            
            # Check for stop event
            if self._stop_event.is_set():
                self.logger.debug("Stop event received while waiting for playback")
                break
            
            # Small sleep to avoid busy-waiting
            time.sleep(0.05)
    
    def _handle_interrupt_in_worker(self, on_subtitle: Callable[[str], None] = None) -> None:
        """
        Handle interrupt signal in the playback worker thread.
        
        Args:
            on_subtitle: Callback function for subtitle updates.
                        Called with empty string to clear subtitle on interrupt.
        """
        self.logger.debug("Handling interrupt in playback worker")
        
        # Stop current playback
        self.tts_player.stop_playback()
        
        # Stop mouth animation on interrupt (Requirements 2.5)
        if self.vts_client:
            try:
                success = self.vts_client.stop_mouth_sync()
                if success:
                    self._mouth_animation_active = False
                    self.logger.debug("Mouth animation stopped due to interrupt")
                else:
                    self.logger.warning("Failed to stop mouth animation on interrupt")
            except Exception as e:
                self.logger.warning(f"Error stopping mouth animation on interrupt: {e}")
        
        # Clear playback timing state
        self._playback_start_time = None
        self._current_audio_duration = 0.0
        
        # Clear subtitle immediately on interrupt
        if on_subtitle:
            on_subtitle("")
        
        # Clean up current packet (only non-cached files)
        if self._current_packet:
            if not self._current_packet.is_cached:
                self.tts_player.cleanup_temp_file(self._current_packet.file_path)
            self._current_packet = None
        
        # Clear the queue
        self._cleanup_queue()
        
        # Clear interrupt flag
        self._interrupt_event.clear()
    
    def interrupt(self) -> None:
        """
        Interrupt current playback and clear pending items.
        
        Used when user sends a new message while previous response
        is still playing. Stops current audio, clears the queue,
        and cancels pending generation tasks.
        
        Requirements: 1.4 (extended) - Graceful interruption
        """
        self.logger.info("Interrupting TTS Pipeline...")
        
        # Set interrupt flag (worker thread will handle cleanup)
        self._interrupt_event.set()
        
        # Stop current playback immediately
        self.tts_player.stop_playback()
        
        # Cancel pending generation tasks
        for task in self.generation_tasks:
            if not task.done():
                task.cancel()
        self.generation_tasks.clear()
        
        # Reset sequence counter for new conversation
        self._sequence_counter = 0
        
        self.logger.info("TTS Pipeline interrupted")
    
    def emergency_stop(self) -> None:
        """
        Immediately stop audio playback and clear queues within 200ms.
        
        This method provides instant cessation of all audio output for
        full-duplex conversational engine barge-in functionality.
        Must complete within 200ms for natural interruption feel.
        
        Requirements: 5.1, 5.2 - Emergency stop capability
        """
        import time
        start_time = time.time()
        
        self.logger.info("Emergency stop initiated...")
        
        # 1. Immediately stop current audio playback
        self.tts_player.stop_playback()
        
        # 2. Set interrupt flag for worker thread
        self._interrupt_event.set()
        
        # 3. Stop mouth animation synchronously
        if self.vts_client:
            try:
                success = self.vts_client.stop_mouth_sync()
                if success:
                    self._mouth_animation_active = False
                    self.logger.debug("Mouth animation stopped synchronously during emergency stop")
                else:
                    self.logger.warning("Failed to stop mouth animation during emergency stop")
            except Exception as e:
                self.logger.warning(f"Error stopping mouth animation during emergency stop: {e}")
        
        # 4. Clear playback timing state
        self._playback_start_time = None
        self._current_audio_duration = 0.0
        
        # 5. Clear all queued audio packets immediately
        self._clear_queue_immediate()
        
        # 6. Cancel all pending generation tasks
        for task in self.generation_tasks:
            if not task.done():
                task.cancel()
        self.generation_tasks.clear()
        
        # 7. Reset sequence counter
        self._sequence_counter = 0
        
        # 8. Clear current packet reference
        if self._current_packet:
            if not self._current_packet.is_cached:
                self.tts_player.cleanup_temp_file(self._current_packet.file_path)
            self._current_packet = None
        
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        self.logger.info(f"Emergency stop completed in {elapsed_time:.1f}ms")
        
        # Call interruption callback if set
        if self._interruption_callback:
            try:
                self._interruption_callback()
            except Exception as e:
                self.logger.error(f"Error calling interruption callback: {e}")
        
        # Verify we met the 200ms requirement
        if elapsed_time > 200:
            self.logger.warning(f"Emergency stop took {elapsed_time:.1f}ms (>200ms requirement)")
    
    def _clear_queue_immediate(self) -> None:
        """
        Immediately clear all audio packets from the playback queue.
        
        This is a fast, non-blocking queue clearing operation for emergency stop.
        Cleans up temporary files for non-cached audio packets.
        """
        cleared_count = 0
        
        # Use get_nowait() to avoid blocking
        while True:
            try:
                packet = self.playback_queue.get_nowait()
                # Clean up non-cached files
                if not packet.is_cached and packet.file_path:
                    try:
                        self.tts_player.cleanup_temp_file(packet.file_path)
                    except Exception as e:
                        self.logger.debug(f"Error cleaning up temp file during emergency stop: {e}")
                cleared_count += 1
            except Empty:
                break
        
        if cleared_count > 0:
            self.logger.debug(f"Emergency stop cleared {cleared_count} queued audio packets")
    
    def _cleanup_queue(self) -> None:
        """Clean up all AudioPackets in the playback queue."""
        cleaned = 0
        while not self.playback_queue.empty():
            try:
                packet = self.playback_queue.get_nowait()
                # Only cleanup non-cached files
                if not packet.is_cached:
                    self.tts_player.cleanup_temp_file(packet.file_path)
                cleaned += 1
            except Empty:
                break
        
        if cleaned > 0:
            self.logger.debug(f"Cleaned up {cleaned} queued AudioPackets")
    
    def is_idle(self) -> bool:
        """
        Check if the pipeline is idle (no pending or playing audio).
        
        Returns:
            True if no audio is being generated, queued, or played
        """
        return (
            self.playback_queue.empty() and
            not self.tts_player.is_playing() and
            all(t.done() for t in self.generation_tasks)
        )
    
    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.
        
        Returns:
            True if audio is currently being played, False otherwise
        """
        return self.tts_player.is_playing()
    
    def get_playback_position(self) -> float:
        """
        Get current playback position in seconds.
        
        Returns:
            Current playback position in seconds, or 0.0 if not playing
        """
        try:
            return self.tts_player.get_playback_position()
        except Exception as e:
            self.logger.debug(f"Could not get playback position: {e}")
            return 0.0
    
    def set_interruption_callback(self, callback: Callable) -> None:
        """
        Set callback for when playback is interrupted.
        
        Args:
            callback: Function to call when interruption occurs
        """
        self._interruption_callback = callback
    
    def is_mouth_animation_active(self) -> bool:
        """
        Check if mouth animation is currently active.
        
        Returns:
            True if mouth animation is active, False otherwise
        """
        return self._mouth_animation_active
    
    def get_current_playback_info(self) -> Dict[str, any]:
        """
        Get current playback information for state coordination.
        
        Returns:
            Dictionary containing current playback state information
        """
        import time
        
        current_time = time.time()
        elapsed_time = 0.0
        remaining_time = 0.0
        
        if self._playback_start_time and self.is_playing():
            elapsed_time = current_time - self._playback_start_time
            if self._current_audio_duration > 0:
                remaining_time = max(0.0, self._current_audio_duration - elapsed_time)
        
        return {
            'is_playing': self.is_playing(),
            'is_mouth_animation_active': self._mouth_animation_active,
            'current_packet': self._current_packet,
            'queue_size': self.get_queue_size(),
            'pending_tasks': self.get_pending_tasks(),
            'elapsed_time': elapsed_time,
            'remaining_time': remaining_time,
            'total_duration': self._current_audio_duration
        }
    
    def force_stop_mouth_animation(self) -> bool:
        """
        Force stop mouth animation synchronously for emergency situations.
        
        This method provides direct control over mouth animation stopping
        for the DuplexManager during barge-in scenarios.
        
        Returns:
            True if mouth animation was stopped successfully, False otherwise
        """
        if not self.vts_client:
            return True  # No VTS client, consider it "stopped"
        
        try:
            success = self.vts_client.stop_mouth_sync()
            if success:
                self._mouth_animation_active = False
                self.logger.debug("Mouth animation force stopped")
            return success
        except Exception as e:
            self.logger.error(f"Error force stopping mouth animation: {e}")
            return False
    
    def get_queue_size(self) -> int:
        """
        Get the current number of items in the playback queue.
        
        Returns:
            Number of audio files waiting to be played
        """
        return self.playback_queue.qsize()
    
    def get_pending_tasks(self) -> int:
        """
        Get the number of pending generation tasks.
        
        Returns:
            Number of audio files currently being generated
        """
        return len([t for t in self.generation_tasks if not t.done()])
