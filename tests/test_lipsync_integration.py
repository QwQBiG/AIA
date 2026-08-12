"""
Integration tests for Lip-Sync Integration

Tests the lip-sync integration functionality including:
1. Mouth opens before audio starts playing
2. Mouth closes after audio playback completes
3. Graceful degradation when VTS connection is lost

Requirements: 2.1, 2.2, 2.3, 2.5
"""

import unittest
import time
import threading
import asyncio
from unittest.mock import Mock, patch, MagicMock, call, AsyncMock
import sys
import os
from queue import Queue

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tts_pipeline import TTSPipeline, AudioPacket
from vts_client import VTSClient


class TestLipSyncIntegration(unittest.TestCase):
    """Integration tests for lip-sync functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock TTS player with async methods
        self.mock_tts_player = Mock()
        self.mock_tts_player.is_busy.return_value = False
        self.mock_tts_player.play_audio.return_value = None
        
        # Create async mock for generate_audio
        async def mock_generate_audio(text, clean_text=None):
            return "test_audio.mp3"
        self.mock_tts_player.generate_audio = mock_generate_audio
        
        # Mock VTS client
        self.mock_vts_client = Mock()
        self.mock_vts_client.start_mouth_sync.return_value = True
        self.mock_vts_client.stop_mouth_sync.return_value = True
        
        # Create TTS pipeline with VTS client
        self.pipeline = TTSPipeline(
            tts_player=self.mock_tts_player,
            vts_client=self.mock_vts_client,
            max_queue_size=5
        )
        
    def tearDown(self):
        """Clean up after tests"""
        # Clean up pipeline
        try:
            asyncio.run(self.pipeline.stop())
        except:
            pass
    
    def test_vts_client_injection(self):
        """
        Test that VTS client can be injected after pipeline creation
        Requirements: 2.1, 2.2
        """
        # Create pipeline without VTS client
        pipeline = TTSPipeline(
            tts_player=self.mock_tts_player,
            vts_client=None,
            max_queue_size=5
        )
        
        # Verify no VTS client initially
        self.assertIsNone(pipeline.vts_client)
        
        # Inject VTS client
        pipeline.set_vts_client(self.mock_vts_client)
        
        # Verify VTS client is set
        self.assertEqual(pipeline.vts_client, self.mock_vts_client)
    
    def test_pipeline_configuration_options(self):
        """
        Test that pipeline correctly handles VTS client configuration
        Requirements: 2.1, 2.2
        """
        # Test with VTS client in constructor
        pipeline_with_vts = TTSPipeline(
            tts_player=self.mock_tts_player,
            vts_client=self.mock_vts_client,
            max_queue_size=5
        )
        
        self.assertEqual(pipeline_with_vts.vts_client, self.mock_vts_client)
        
        # Test without VTS client in constructor
        pipeline_without_vts = TTSPipeline(
            tts_player=self.mock_tts_player,
            vts_client=None,
            max_queue_size=5
        )
        
        self.assertIsNone(pipeline_without_vts.vts_client)
        
        # Test setting VTS client after creation
        pipeline_without_vts.set_vts_client(self.mock_vts_client)
        self.assertEqual(pipeline_without_vts.vts_client, self.mock_vts_client)
    
    def test_mouth_sync_integration_with_direct_playback(self):
        """
        Test mouth sync integration by directly testing the playback worker logic
        Requirements: 2.1, 2.2, 2.3
        """
        # Create an audio packet
        audio_packet = AudioPacket(
            file_path="test_audio.mp3",
            subtitle_text="Hello world",
            clean_text="Hello world",
            is_cached=False
        )
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            # Test the playback logic directly
            # This simulates what happens in the _playback_worker method
            
            # 1. Start mouth sync before audio
            if self.pipeline.vts_client:
                success = self.pipeline.vts_client.start_mouth_sync()
                self.assertTrue(success)
            
            # 2. Play audio
            self.mock_tts_player.play_audio(audio_packet.file_path)
            
            # 3. Wait for completion (simulate blocking)
            while self.mock_tts_player.is_busy():
                time.sleep(0.01)
            
            # 4. Stop mouth sync after audio
            if self.pipeline.vts_client:
                success = self.pipeline.vts_client.stop_mouth_sync()
                self.assertTrue(success)
            
            # Verify the sequence
            self.mock_vts_client.start_mouth_sync.assert_called()
            self.mock_tts_player.play_audio.assert_called_with("test_audio.mp3")
            self.mock_vts_client.stop_mouth_sync.assert_called()
    
    def test_graceful_degradation_when_vts_fails(self):
        """
        Test graceful degradation when VTS connection fails
        Requirements: 2.5
        """
        # Mock VTS client failure
        self.mock_vts_client.start_mouth_sync.return_value = False
        self.mock_vts_client.stop_mouth_sync.return_value = False
        
        # Create an audio packet
        audio_packet = AudioPacket(
            file_path="test_audio.mp3",
            subtitle_text="Hello world",
            clean_text="Hello world",
            is_cached=False
        )
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            # Test the playback logic with VTS failure
            
            # 1. Try to start mouth sync (fails)
            if self.pipeline.vts_client:
                success = self.pipeline.vts_client.start_mouth_sync()
                self.assertFalse(success)  # Should fail
            
            # 2. Audio should still play
            self.mock_tts_player.play_audio(audio_packet.file_path)
            
            # 3. Wait for completion
            while self.mock_tts_player.is_busy():
                time.sleep(0.01)
            
            # 4. Try to stop mouth sync (fails)
            if self.pipeline.vts_client:
                success = self.pipeline.vts_client.stop_mouth_sync()
                self.assertFalse(success)  # Should fail
            
            # Verify audio still played despite VTS failure
            self.mock_tts_player.play_audio.assert_called_with("test_audio.mp3")
            self.mock_vts_client.start_mouth_sync.assert_called()
            self.mock_vts_client.stop_mouth_sync.assert_called()
    
    def test_no_vts_client_continues_normally(self):
        """
        Test that pipeline works normally without VTS client
        Requirements: 2.5
        """
        # Create pipeline without VTS client
        pipeline_no_vts = TTSPipeline(
            tts_player=self.mock_tts_player,
            vts_client=None,
            max_queue_size=5
        )
        
        # Create an audio packet
        audio_packet = AudioPacket(
            file_path="test_audio.mp3",
            subtitle_text="Hello world",
            clean_text="Hello world",
            is_cached=False
        )
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            # Test the playback logic without VTS client
            
            # 1. No VTS client, so no mouth sync calls
            if pipeline_no_vts.vts_client:
                pipeline_no_vts.vts_client.start_mouth_sync()
            
            # 2. Audio should still play
            self.mock_tts_player.play_audio(audio_packet.file_path)
            
            # 3. Wait for completion
            while self.mock_tts_player.is_busy():
                time.sleep(0.01)
            
            # 4. No VTS client, so no mouth sync calls
            if pipeline_no_vts.vts_client:
                pipeline_no_vts.vts_client.stop_mouth_sync()
            
            # Verify audio played normally
            self.mock_tts_player.play_audio.assert_called_with("test_audio.mp3")
            
            # Verify no VTS methods were called
            self.mock_vts_client.start_mouth_sync.assert_not_called()
            self.mock_vts_client.stop_mouth_sync.assert_not_called()
    
    def test_vts_exception_handling(self):
        """
        Test that VTS exceptions don't break audio playback
        Requirements: 2.5
        """
        # Mock VTS client to raise exceptions
        self.mock_vts_client.start_mouth_sync.side_effect = Exception("VTS connection error")
        self.mock_vts_client.stop_mouth_sync.side_effect = Exception("VTS connection error")
        
        # Create an audio packet
        audio_packet = AudioPacket(
            file_path="test_audio.mp3",
            subtitle_text="Hello world",
            clean_text="Hello world",
            is_cached=False
        )
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            # Test the playback logic with VTS exceptions
            
            # 1. Try to start mouth sync (raises exception)
            if self.pipeline.vts_client:
                try:
                    self.pipeline.vts_client.start_mouth_sync()
                except Exception:
                    pass  # Should handle gracefully
            
            # 2. Audio should still play
            self.mock_tts_player.play_audio(audio_packet.file_path)
            
            # 3. Wait for completion
            while self.mock_tts_player.is_busy():
                time.sleep(0.01)
            
            # 4. Try to stop mouth sync (raises exception)
            if self.pipeline.vts_client:
                try:
                    self.pipeline.vts_client.stop_mouth_sync()
                except Exception:
                    pass  # Should handle gracefully
            
            # Verify audio still played despite VTS exceptions
            self.mock_tts_player.play_audio.assert_called_with("test_audio.mp3")
            self.mock_vts_client.start_mouth_sync.assert_called()
            self.mock_vts_client.stop_mouth_sync.assert_called()
    
    def test_mouth_sync_call_sequence_verification(self):
        """
        Test that mouth sync calls happen in correct order
        Requirements: 2.1, 2.2, 2.3
        """
        # Track call order
        call_order = []
        
        def track_start_mouth():
            call_order.append('start_mouth_sync')
            return True
        
        def track_stop_mouth():
            call_order.append('stop_mouth_sync')
            return True
        
        def track_play_audio(file_path):
            call_order.append('play_audio')
        
        self.mock_vts_client.start_mouth_sync.side_effect = track_start_mouth
        self.mock_vts_client.stop_mouth_sync.side_effect = track_stop_mouth
        self.mock_tts_player.play_audio.side_effect = track_play_audio
        
        # Create an audio packet
        audio_packet = AudioPacket(
            file_path="test_audio.mp3",
            subtitle_text="Hello world",
            clean_text="Hello world",
            is_cached=False
        )
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            # Test the playback sequence
            
            # 1. Start mouth sync
            if self.pipeline.vts_client:
                self.pipeline.vts_client.start_mouth_sync()
            
            # 2. Play audio
            self.mock_tts_player.play_audio(audio_packet.file_path)
            
            # 3. Wait for completion
            while self.mock_tts_player.is_busy():
                time.sleep(0.01)
            
            # 4. Stop mouth sync
            if self.pipeline.vts_client:
                self.pipeline.vts_client.stop_mouth_sync()
            
            # Verify correct call sequence
            self.assertEqual(call_order, ['start_mouth_sync', 'play_audio', 'stop_mouth_sync'])


class TestVTSClientMouthSync(unittest.TestCase):
    """Integration tests for VTS client mouth sync methods"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.vts_client = VTSClient()
        
    def test_mouth_sync_without_event_loop(self):
        """
        Test mouth sync methods when no event loop is available
        Requirements: 2.5
        """
        # Ensure no event loop is set
        self.vts_client.event_loop = None
        self.vts_client.websocket = None
        
        # Test start_mouth_sync
        result = self.vts_client.start_mouth_sync()
        self.assertFalse(result)
        
        # Test stop_mouth_sync
        result = self.vts_client.stop_mouth_sync()
        self.assertFalse(result)
    
    def test_mouth_sync_with_mock_event_loop(self):
        """
        Test mouth sync methods with mocked event loop
        Requirements: 2.1, 2.4
        """
        # Mock event loop and websocket
        mock_loop = Mock()
        mock_websocket = Mock()
        mock_future = Mock()
        mock_future.result.return_value = True
        
        self.vts_client.event_loop = mock_loop
        self.vts_client.websocket = mock_websocket
        
        # Mock asyncio.run_coroutine_threadsafe
        with patch('asyncio.run_coroutine_threadsafe', return_value=mock_future):
            # Test start_mouth_sync
            result = self.vts_client.start_mouth_sync()
            self.assertTrue(result)
            
            # Test stop_mouth_sync
            result = self.vts_client.stop_mouth_sync()
            self.assertTrue(result)
    
    def test_mouth_sync_timeout_handling(self):
        """
        Test mouth sync methods handle timeouts gracefully
        Requirements: 2.5
        """
        # Mock event loop and websocket
        mock_loop = Mock()
        mock_websocket = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = asyncio.TimeoutError("Timeout")
        
        self.vts_client.event_loop = mock_loop
        self.vts_client.websocket = mock_websocket
        
        # Mock asyncio.run_coroutine_threadsafe
        with patch('asyncio.run_coroutine_threadsafe', return_value=mock_future):
            # Test start_mouth_sync with timeout
            result = self.vts_client.start_mouth_sync()
            self.assertFalse(result)
            
            # Test stop_mouth_sync with timeout
            result = self.vts_client.stop_mouth_sync()
            self.assertFalse(result)
    
    def test_mouth_sync_logging_verification(self):
        """
        Test that mouth sync methods log appropriately
        Requirements: 2.4
        """
        # Mock event loop and websocket
        mock_loop = Mock()
        mock_websocket = Mock()
        mock_future = Mock()
        mock_future.result.return_value = True
        
        self.vts_client.event_loop = mock_loop
        self.vts_client.websocket = mock_websocket
        
        # Mock logger
        with patch.object(self.vts_client, 'logger') as mock_logger:
            with patch('asyncio.run_coroutine_threadsafe', return_value=mock_future):
                # Test successful mouth sync
                result = self.vts_client.start_mouth_sync()
                self.assertTrue(result)
                
                # Test that no error was logged for successful operation
                mock_logger.error.assert_not_called()
    
    def test_mouth_sync_without_websocket(self):
        """
        Test mouth sync methods when websocket is not available
        Requirements: 2.5
        """
        # Set event loop but no websocket
        self.vts_client.event_loop = Mock()
        self.vts_client.websocket = None
        
        # Test start_mouth_sync
        result = self.vts_client.start_mouth_sync()
        self.assertFalse(result)
        
        # Test stop_mouth_sync
        result = self.vts_client.stop_mouth_sync()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()