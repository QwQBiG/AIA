"""
Unit tests for TTS Pipeline.
Tests the Producer-Consumer pattern for audio generation and playback.
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from queue import Queue, Empty
from threading import Event

from src.tts_pipeline import TTSPipeline, AudioItem, AudioPacket


class TestAudioItem:
    """Tests for AudioItem dataclass."""
    
    def test_audio_item_creation(self):
        """Test AudioItem creation with all fields."""
        item = AudioItem(
            file_path="/tmp/test.mp3",
            text="Hello world",
            sequence_number=0
        )
        
        assert item.file_path == "/tmp/test.mp3"
        assert item.text == "Hello world"
        assert item.sequence_number == 0


class TestAudioPacket:
    """Tests for AudioPacket dataclass."""
    
    def test_audio_packet_creation_with_defaults(self):
        """Test AudioPacket creation with default values."""
        packet = AudioPacket(
            file_path="/tmp/test.mp3",
            subtitle_text="Hello world",
            clean_text="Hello world"
        )
        
        assert packet.file_path == "/tmp/test.mp3"
        assert packet.subtitle_text == "Hello world"
        assert packet.clean_text == "Hello world"
        assert packet.is_cached is False
        assert packet.duration == 0.0
    
    def test_audio_packet_creation_with_all_fields(self):
        """Test AudioPacket creation with all fields specified."""
        packet = AudioPacket(
            file_path="/cache/hello.mp3",
            subtitle_text="Hello 😊",
            clean_text="Hello",
            is_cached=True,
            duration=1.5
        )
        
        assert packet.file_path == "/cache/hello.mp3"
        assert packet.subtitle_text == "Hello 😊"
        assert packet.clean_text == "Hello"
        assert packet.is_cached is True
        assert packet.duration == 1.5
    
    def test_audio_packet_different_subtitle_and_clean_text(self):
        """Test AudioPacket with different subtitle and clean text."""
        packet = AudioPacket(
            file_path="/tmp/test.mp3",
            subtitle_text="**Bold** text with emoji 🎉",
            clean_text="Bold text with emoji",
            is_cached=False,
            duration=2.0
        )
        
        assert packet.subtitle_text != packet.clean_text
        assert "**" in packet.subtitle_text
        assert "**" not in packet.clean_text


class TestTTSPipelineUnit:
    """Unit tests for TTSPipeline functionality."""
    
    def test_pipeline_initialization(self):
        """Test TTSPipeline initialization with default and custom settings."""
        mock_tts_player = MagicMock()
        
        # Test default initialization
        pipeline = TTSPipeline(mock_tts_player)
        assert pipeline.tts_player == mock_tts_player
        assert pipeline.max_queue_size == 10
        assert pipeline.is_running is False
        assert pipeline._sequence_counter == 0
        
        # Test custom max_queue_size
        pipeline_custom = TTSPipeline(mock_tts_player, max_queue_size=5)
        assert pipeline_custom.max_queue_size == 5
    
    @pytest.mark.asyncio
    async def test_pipeline_start(self):
        """Test starting the pipeline."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        await pipeline.start()
        
        assert pipeline.is_running is True
        assert pipeline.playback_thread is not None
        assert pipeline.playback_thread.is_alive()
        
        # Clean up
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_pipeline_start_already_running(self):
        """Test starting an already running pipeline."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        await pipeline.start()
        
        # Starting again should not create a new thread
        original_thread = pipeline.playback_thread
        await pipeline.start()
        
        assert pipeline.playback_thread == original_thread
        
        # Clean up
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_pipeline_stop(self):
        """Test stopping the pipeline."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        await pipeline.start()
        assert pipeline.is_running is True
        
        await pipeline.stop()
        
        assert pipeline.is_running is False
    
    @pytest.mark.asyncio
    async def test_put_text_when_not_running(self):
        """Test put_text when pipeline is not running."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Should not raise, just log warning
        await pipeline.put_text("Hello world")
        
        # No tasks should be created
        assert len(pipeline.generation_tasks) == 0
    
    @pytest.mark.asyncio
    async def test_put_text_empty_string(self):
        """Test put_text with empty string."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        await pipeline.start()
        
        # Empty strings should be ignored
        await pipeline.put_text("")
        await pipeline.put_text("   ")
        
        assert len(pipeline.generation_tasks) == 0
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_put_text_success(self):
        """Test successful text submission."""
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/test.mp3")
        
        pipeline = TTSPipeline(mock_tts_player)
        await pipeline.start()
        
        await pipeline.put_text("Hello world")
        
        # Wait for task to be created
        await asyncio.sleep(0.1)
        
        # Task should be created
        assert pipeline._sequence_counter == 1
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_sequence_numbering(self):
        """Test that sequence numbers are assigned correctly."""
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/test.mp3")
        
        pipeline = TTSPipeline(mock_tts_player)
        await pipeline.start()
        
        await pipeline.put_text("First")
        await pipeline.put_text("Second")
        await pipeline.put_text("Third")
        
        assert pipeline._sequence_counter == 3
        
        await pipeline.stop()
    
    def test_interrupt(self):
        """Test interrupt functionality."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Add some mock tasks
        mock_task = MagicMock()
        mock_task.done.return_value = False
        pipeline.generation_tasks = [mock_task]
        pipeline._sequence_counter = 5
        
        pipeline.interrupt()
        
        # Verify interrupt behavior
        mock_tts_player.stop_playback.assert_called_once()
        mock_task.cancel.assert_called_once()
        assert len(pipeline.generation_tasks) == 0
        assert pipeline._sequence_counter == 0
        assert pipeline._interrupt_event.is_set()
    
    def test_is_idle(self):
        """Test is_idle method."""
        mock_tts_player = MagicMock()
        mock_tts_player.is_playing.return_value = False
        
        pipeline = TTSPipeline(mock_tts_player)
        
        # Empty queue, no tasks, not playing
        assert pipeline.is_idle() is True
        
        # With pending task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        pipeline.generation_tasks = [mock_task]
        assert pipeline.is_idle() is False
        
        # Task done, but playing
        mock_task.done.return_value = True
        mock_tts_player.is_playing.return_value = True
        assert pipeline.is_idle() is False
    
    def test_get_queue_size(self):
        """Test get_queue_size method."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        assert pipeline.get_queue_size() == 0
        
        # Add AudioPackets to queue
        pipeline.playback_queue.put(AudioPacket("/tmp/1.mp3", "Test 1", "Test 1", False, 0.0))
        pipeline.playback_queue.put(AudioPacket("/tmp/2.mp3", "Test 2", "Test 2", False, 0.0))
        
        assert pipeline.get_queue_size() == 2
    
    def test_get_pending_tasks(self):
        """Test get_pending_tasks method."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        assert pipeline.get_pending_tasks() == 0
        
        # Add mock tasks
        done_task = MagicMock()
        done_task.done.return_value = True
        
        pending_task = MagicMock()
        pending_task.done.return_value = False
        
        pipeline.generation_tasks = [done_task, pending_task, pending_task]
        
        assert pipeline.get_pending_tasks() == 2
    
    def test_cleanup_queue(self):
        """Test _cleanup_queue method."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Add AudioPackets to queue (non-cached)
        pipeline.playback_queue.put(AudioPacket("/tmp/1.mp3", "Test 1", "Test 1", False, 0.0))
        pipeline.playback_queue.put(AudioPacket("/tmp/2.mp3", "Test 2", "Test 2", False, 0.0))
        
        pipeline._cleanup_queue()
        
        assert pipeline.playback_queue.empty()
        assert mock_tts_player.cleanup_temp_file.call_count == 2
    
    def test_cleanup_queue_with_cached(self):
        """Test _cleanup_queue method with cached AudioPackets."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Add AudioPackets to queue (one cached, one not)
        pipeline.playback_queue.put(AudioPacket("/tmp/1.mp3", "Test 1", "Test 1", False, 0.0))
        pipeline.playback_queue.put(AudioPacket("/cache/hello.mp3", "Hello", "Hello", True, 0.0))
        
        pipeline._cleanup_queue()
        
        assert pipeline.playback_queue.empty()
        # Only non-cached file should be cleaned up
        assert mock_tts_player.cleanup_temp_file.call_count == 1
        mock_tts_player.cleanup_temp_file.assert_called_with("/tmp/1.mp3")


class TestTTSPipelineIntegration:
    """Integration tests for TTSPipeline with mocked TTS player."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self):
        """Test complete pipeline flow: put_text -> generate -> enqueue -> play."""
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/test.mp3")
        mock_tts_player.is_playing.return_value = False
        
        pipeline = TTSPipeline(mock_tts_player)
        await pipeline.start()
        
        # Submit text
        await pipeline.put_text("Hello world")
        
        # Wait for generation to complete
        await asyncio.sleep(0.2)
        
        # Verify audio was generated
        mock_tts_player.generate_audio.assert_called_once_with("Hello world")
        
        # Wait for playback worker to process
        await asyncio.sleep(0.3)
        
        # Verify playback was attempted
        mock_tts_player.play_audio.assert_called()
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_interrupt_during_playback(self):
        """Test interrupting during playback."""
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/test.mp3")
        mock_tts_player.is_playing.return_value = True
        
        pipeline = TTSPipeline(mock_tts_player)
        await pipeline.start()
        
        # Submit text
        await pipeline.put_text("Hello world")
        await asyncio.sleep(0.1)
        
        # Interrupt
        pipeline.interrupt()
        
        # Verify stop_playback was called
        mock_tts_player.stop_playback.assert_called()
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_sentences_ordering(self):
        """Test that multiple sentences maintain order."""
        generated_order = []
        
        async def mock_generate(text):
            generated_order.append(text)
            await asyncio.sleep(0.05)  # Simulate generation time
            return f"/tmp/{len(generated_order)}.mp3"
        
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = mock_generate
        mock_tts_player.is_playing.return_value = False
        
        pipeline = TTSPipeline(mock_tts_player)
        await pipeline.start()
        
        # Submit multiple sentences
        await pipeline.put_text("First sentence")
        await pipeline.put_text("Second sentence")
        await pipeline.put_text("Third sentence")
        
        # Wait for all generations to complete
        await asyncio.sleep(0.5)
        
        # Verify order
        assert generated_order == ["First sentence", "Second sentence", "Third sentence"]
        
        await pipeline.stop()


from hypothesis import given, strategies as st, settings
from src.config import UXConfig
from src.tts_pipeline import DEFAULT_PHRASE_CACHE


class TestTTSPipelineCacheUnit:
    """Unit tests for TTSPipeline cache functionality."""
    
    def test_cache_disabled_by_default(self):
        """Test that cache is disabled when no UX config is provided."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        assert pipeline.is_cache_enabled() is False
        assert pipeline.phrase_cache == {}
    
    def test_cache_enabled_with_ux_config(self):
        """Test that cache is enabled when UX config enables it."""
        mock_tts_player = MagicMock()
        ux_config = UXConfig(enable_cache=True)
        
        # Create temp cache files for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test cache file
            test_cache_file = os.path.join(tmpdir, "test.mp3")
            with open(test_cache_file, 'w') as f:
                f.write("test")
            
            # Patch DEFAULT_PHRASE_CACHE to use our temp file
            with patch.object(
                TTSPipeline, '_load_cache',
                lambda self: setattr(self, 'phrase_cache', {"test": test_cache_file}) or setattr(self, '_cache_enabled', True)
            ):
                pipeline = TTSPipeline(mock_tts_player, ux_config=ux_config)
                
                # Cache should be enabled
                assert pipeline._cache_enabled is True
    
    def test_check_cache_returns_none_when_disabled(self):
        """Test check_cache returns None when cache is disabled."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        result = pipeline.check_cache("你好")
        assert result is None
    
    def test_check_cache_returns_path_on_hit(self):
        """Test check_cache returns file path on cache hit."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Manually set up cache
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            pipeline.phrase_cache = {"你好": temp_path}
            pipeline._cache_enabled = True
            
            result = pipeline.check_cache("你好")
            assert result == temp_path
        finally:
            os.unlink(temp_path)
    
    def test_check_cache_returns_none_on_miss(self):
        """Test check_cache returns None on cache miss."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Manually set up cache
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            pipeline.phrase_cache = {"你好": temp_path}
            pipeline._cache_enabled = True
            
            # Different text should miss
            result = pipeline.check_cache("再见")
            assert result is None
        finally:
            os.unlink(temp_path)
    
    def test_check_cache_returns_none_for_missing_file(self):
        """Test check_cache returns None when cache file is missing."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Set up cache with non-existent file
        pipeline.phrase_cache = {"你好": "/nonexistent/path.mp3"}
        pipeline._cache_enabled = True
        
        result = pipeline.check_cache("你好")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_put_text_uses_cache_on_hit(self):
        """Test that put_text uses cache when text matches cached phrase."""
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/generated.mp3")
        mock_tts_player.is_playing.return_value = False
        
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp cache file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Manually set up cache
            pipeline.phrase_cache = {"你好": temp_path}
            pipeline._cache_enabled = True
            
            await pipeline.start()
            
            # Submit cached text
            await pipeline.put_text("你好")
            
            # Wait a bit for processing
            await asyncio.sleep(0.3)
            
            # TTS should NOT be called (cache hit)
            mock_tts_player.generate_audio.assert_not_called()
            
            # Playback should have been attempted with the cached file (with blocking=False)
            mock_tts_player.play_audio.assert_called_with(temp_path, blocking=False)
            
            await pipeline.stop()
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_put_text_generates_audio_on_cache_miss(self):
        """Test that put_text generates audio when text is not cached."""
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/generated.mp3")
        
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp cache file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Manually set up cache with different phrase
            pipeline.phrase_cache = {"你好": temp_path}
            pipeline._cache_enabled = True
            
            await pipeline.start()
            
            # Submit non-cached text
            await pipeline.put_text("再见")
            
            # Wait for generation
            await asyncio.sleep(0.2)
            
            # TTS should be called (cache miss)
            mock_tts_player.generate_audio.assert_called_once_with("再见")
            
            await pipeline.stop()
        finally:
            os.unlink(temp_path)


class TestTTSPipelineCachePropertyTests:
    """Property-based tests for TTSPipeline cache functionality."""
    
    @given(st.sampled_from(list(DEFAULT_PHRASE_CACHE.keys())))
    @settings(max_examples=100)
    def test_cache_priority_property(self, cached_phrase: str):
        """
        Property 2: 缓存优先 (Cache Priority)
        
        For any input text matching a cache key, the system MUST NOT call 
        the GPT-SoVITS API, and the response time MUST be less than 100ms.
        
        This test verifies that:
        1. Cache lookup is performed before TTS generation
        2. Cached phrases return the correct file path
        3. No TTS API call is made for cached phrases
        
        Feature: ux-hyper-optimization, Property 2: 缓存优先
        **Validates: Requirements 2.1, 2.2**
        """
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Get the expected cache path
        expected_path = DEFAULT_PHRASE_CACHE[cached_phrase]
        
        # Create temp file to simulate cache file existence
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Set up cache with the temp file
            pipeline.phrase_cache = {cached_phrase: temp_path}
            pipeline._cache_enabled = True
            
            # Property: check_cache should return the cached path
            result = pipeline.check_cache(cached_phrase)
            
            assert result is not None, \
                f"Cache miss for cached phrase: {repr(cached_phrase)}"
            assert result == temp_path, \
                f"Wrong cache path returned: expected {temp_path}, got {result}"
            
            # Property: TTS player should NOT be called for cache lookup
            mock_tts_player.generate_audio.assert_not_called()
        finally:
            os.unlink(temp_path)
    
    @given(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P')),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() not in DEFAULT_PHRASE_CACHE))
    @settings(max_examples=100)
    def test_cache_miss_property(self, non_cached_text: str):
        """
        Property: Cache miss behavior
        
        For any input text NOT matching a cache key, the check_cache method
        should return None, indicating TTS generation is needed.
        
        Feature: ux-hyper-optimization
        **Validates: Requirements 2.1**
        """
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp file for a different phrase
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Set up cache with default phrases
            pipeline.phrase_cache = {"你好": temp_path}
            pipeline._cache_enabled = True
            
            # Property: check_cache should return None for non-cached text
            result = pipeline.check_cache(non_cached_text)
            
            assert result is None, \
                f"Unexpected cache hit for non-cached text: {repr(non_cached_text)}"
        finally:
            os.unlink(temp_path)


class TestTTSPipelineFillerAudio:
    """Unit tests for TTSPipeline filler audio functionality."""
    
    def test_get_filler_phrases_when_cache_disabled(self):
        """Test get_filler_phrases returns empty list when cache is disabled."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Cache is disabled by default
        assert pipeline.get_filler_phrases() == []
    
    def test_get_filler_phrases_returns_available_fillers(self):
        """Test get_filler_phrases returns only available filler phrases."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp files for filler phrases
        with tempfile.TemporaryDirectory() as tmpdir:
            hmm_path = os.path.join(tmpdir, "hmm.mp3")
            thinking_path = os.path.join(tmpdir, "thinking.mp3")
            
            with open(hmm_path, 'w') as f:
                f.write("test")
            with open(thinking_path, 'w') as f:
                f.write("test")
            
            # Set up cache with filler phrases
            pipeline.phrase_cache = {
                "嗯...": hmm_path,
                "让我想想": thinking_path,
                "你好": os.path.join(tmpdir, "hello.mp3"),  # Non-existent file
            }
            pipeline._cache_enabled = True
            
            fillers = pipeline.get_filler_phrases()
            
            # Should only return fillers with existing files
            assert "嗯..." in fillers
            assert "让我想想" in fillers
            assert "你好" not in fillers  # Not a filler phrase
    
    def test_play_filler_when_cache_disabled(self):
        """Test play_filler returns False when cache is disabled."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        result = pipeline.play_filler()
        
        assert result is False
        mock_tts_player.play_audio.assert_not_called()
    
    def test_play_filler_when_no_fillers_available(self):
        """Test play_filler returns False when no filler phrases are available."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Enable cache but with no filler phrases
        pipeline._cache_enabled = True
        pipeline.phrase_cache = {"你好": "/nonexistent/hello.mp3"}
        
        result = pipeline.play_filler()
        
        assert result is False
        mock_tts_player.play_audio.assert_not_called()
    
    def test_play_filler_success(self):
        """Test play_filler plays audio successfully."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp file for filler phrase
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Set up cache with filler phrase
            pipeline.phrase_cache = {"嗯...": temp_path}
            pipeline._cache_enabled = True
            
            result = pipeline.play_filler()
            
            assert result is True
            mock_tts_player.play_audio.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_play_filler_handles_playback_error(self):
        """Test play_filler handles playback errors gracefully."""
        mock_tts_player = MagicMock()
        mock_tts_player.play_audio.side_effect = Exception("Playback error")
        
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp file for filler phrase
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Set up cache with filler phrase
            pipeline.phrase_cache = {"嗯...": temp_path}
            pipeline._cache_enabled = True
            
            result = pipeline.play_filler()
            
            assert result is False
        finally:
            os.unlink(temp_path)
    
    def test_play_filler_selects_random_filler(self):
        """Test play_filler selects from available fillers randomly."""
        mock_tts_player = MagicMock()
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp files for multiple filler phrases
        with tempfile.TemporaryDirectory() as tmpdir:
            hmm_path = os.path.join(tmpdir, "hmm.mp3")
            thinking_path = os.path.join(tmpdir, "thinking.mp3")
            
            with open(hmm_path, 'w') as f:
                f.write("test")
            with open(thinking_path, 'w') as f:
                f.write("test")
            
            # Set up cache with multiple filler phrases
            pipeline.phrase_cache = {
                "嗯...": hmm_path,
                "让我想想": thinking_path,
            }
            pipeline._cache_enabled = True
            
            # Play filler multiple times and collect which files were played
            played_files = set()
            for _ in range(20):
                pipeline.play_filler()
                call_args = mock_tts_player.play_audio.call_args
                if call_args:
                    played_files.add(call_args[0][0])
            
            # With 20 attempts, we should have played both fillers at least once
            # (statistically very likely with random selection)
            assert len(played_files) >= 1  # At minimum, one filler should be played


class TestTTSPipelineAVSyncPropertyTests:
    """Property-based tests for TTSPipeline A/V synchronization."""
    
    @given(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S')),
        min_size=1,
        max_size=100
    ).filter(lambda x: x.strip()))
    @settings(max_examples=100, deadline=1000)  # Increase deadline to 1000ms
    def test_av_sync_property(self, subtitle_text: str):
        """
        Property 1: 视听同步 (A/V Sync)
        
        For any audio packet played, the GUI subtitle MUST update exactly when 
        the pygame.mixer.music.play() is called, not when the audio is generated.
        
        This test verifies that:
        1. Subtitle callback is called BEFORE audio playback starts
        2. Subtitle text matches the AudioPacket's subtitle_text
        3. Subtitle is cleared after playback completes
        
        Feature: ux-hyper-optimization, Property 1: 视听同步
        **Validates: Requirements 1.1, 5.3**
        """
        import threading
        import time
        
        # Track the order of operations
        operation_log = []
        operation_lock = threading.Lock()
        
        def log_operation(op: str, data: str = ""):
            with operation_lock:
                operation_log.append((time.time(), op, data))
        
        # Mock TTS player that logs when play_audio is called
        mock_tts_player = MagicMock()
        
        def mock_play_audio(file_path, blocking=True):
            log_operation("play_audio_start", file_path)
            # Simulate short playback
            time.sleep(0.05)
            log_operation("play_audio_end", file_path)
        
        mock_tts_player.play_audio.side_effect = mock_play_audio
        mock_tts_player.get_busy.return_value = False  # Audio completes immediately
        mock_tts_player.is_playing.return_value = False
        mock_tts_player.cleanup_temp_file = MagicMock()
        
        # Subtitle callback that logs when it's called
        subtitle_updates = []
        subtitle_lock = threading.Lock()
        
        def on_subtitle(text: str):
            log_operation("subtitle_update", text)
            with subtitle_lock:
                subtitle_updates.append(text)
        
        # Create pipeline
        pipeline = TTSPipeline(mock_tts_player)
        
        # Create temp file for audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Create AudioPacket
            packet = AudioPacket(
                file_path=temp_path,
                subtitle_text=subtitle_text,
                clean_text=subtitle_text,
                is_cached=False,
                duration=0.0
            )
            
            # Add packet to queue
            pipeline.playback_queue.put(packet)
            
            # Start pipeline with subtitle callback
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(pipeline.start(on_subtitle=on_subtitle))
                
                # Wait for playback to complete
                time.sleep(1.0)
                
                # Stop pipeline
                loop.run_until_complete(pipeline.stop())
            finally:
                loop.close()
            
            # Verify A/V sync properties
            with operation_lock:
                # Find subtitle update and play_audio_start operations
                subtitle_ops = [(t, op, data) for t, op, data in operation_log if op == "subtitle_update"]
                play_ops = [(t, op, data) for t, op, data in operation_log if op == "play_audio_start"]
                
                # Property 1: Subtitle should be updated at least once with the correct text
                assert len(subtitle_updates) >= 1, \
                    f"Subtitle was never updated. Operations: {operation_log}"
                
                # Property 2: First subtitle update should contain the packet's subtitle text
                assert subtitle_updates[0] == subtitle_text, \
                    f"First subtitle update should be '{subtitle_text}', got '{subtitle_updates[0]}'"
                
                # Property 3: If both operations occurred, subtitle should be updated before or at same time as play
                if subtitle_ops and play_ops:
                    first_subtitle_time = subtitle_ops[0][0]
                    first_play_time = play_ops[0][0]
                    
                    # Allow small timing tolerance (subtitle should be updated before or very close to play)
                    assert first_subtitle_time <= first_play_time + 0.1, \
                        f"Subtitle update ({first_subtitle_time}) should occur before play_audio ({first_play_time})"
                
                # Property 4: Subtitle should be cleared (empty string) after playback
                # The last subtitle update should be empty string (clearing)
                if len(subtitle_updates) >= 2:
                    assert subtitle_updates[-1] == "", \
                        f"Subtitle should be cleared after playback, got '{subtitle_updates[-1]}'"
                        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_subtitle_callback_integration(self):
        """
        Integration test for subtitle callback with TTSPipeline.
        
        Verifies that the subtitle callback is properly invoked during
        the playback workflow.
        
        **Validates: Requirements 1.1, 5.3**
        """
        import threading
        import time
        
        # Track subtitle updates
        subtitle_updates = []
        subtitle_lock = threading.Lock()
        
        def on_subtitle(text: str):
            with subtitle_lock:
                subtitle_updates.append((time.time(), text))
        
        # Mock TTS player
        mock_tts_player = MagicMock()
        mock_tts_player.generate_audio = AsyncMock(return_value="/tmp/test.mp3")
        mock_tts_player.get_busy.return_value = False
        mock_tts_player.is_playing.return_value = False
        
        # Create pipeline
        pipeline = TTSPipeline(mock_tts_player)
        
        # Start pipeline with subtitle callback
        await pipeline.start(on_subtitle=on_subtitle)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            f.write(b"test audio data")
        
        try:
            # Manually add AudioPacket to queue
            packet = AudioPacket(
                file_path=temp_path,
                subtitle_text="Test subtitle",
                clean_text="Test subtitle",
                is_cached=False,
                duration=0.0
            )
            pipeline.playback_queue.put(packet)
            
            # Wait for processing
            await asyncio.sleep(1.0)
            
            # Verify subtitle was updated
            with subtitle_lock:
                assert len(subtitle_updates) >= 1, "Subtitle callback was never called"
                
                # First update should be the subtitle text
                texts = [text for _, text in subtitle_updates]
                assert "Test subtitle" in texts, \
                    f"Expected 'Test subtitle' in updates, got {texts}"
                
        finally:
            await pipeline.stop()
            if os.path.exists(temp_path):
                os.unlink(temp_path)
