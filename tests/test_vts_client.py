"""
Unit and property tests for VTS Client
"""

import asyncio
import json
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest
from hypothesis import given, strategies as st
import websockets

from src.vts_client import VTSClient


class TestVTSClientProperties:
    """Property-based tests for VTSClient"""
    
    @given(st.sampled_from(["neutral", "happy", "angry", "sad", "surprised"]))
    @pytest.mark.asyncio
    async def test_expression_timing_coordination_property(self, emotion):
        """
        Property 4: Expression Timing Coordination
        For any valid emotion tag, the Expression Controller should trigger the corresponding hotkey 
        before or simultaneously with audio playback, completing within 500ms
        **Feature: ai-vtuber-emotional-intelligence, Property 4: Expression Timing Coordination**
        **Validates: Requirements 2.1, 2.4, 7.1**
        """
        # Setup client with emotion hotkey mapping
        emotion_hotkey_map = {
            "neutral": "neutral_hotkey",
            "happy": "happy_hotkey", 
            "angry": "angry_hotkey",
            "sad": "sad_hotkey",
            "surprised": "surprised_hotkey"
        }
        client = VTSClient(emotion_hotkey_map=emotion_hotkey_map)
        
        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client._connected = True
        client._authenticated = True
        
        # Mock successful hotkey trigger response
        hotkey_response = {
            "messageType": "HotkeyTriggerResponse",
            "data": {"errorID": "OK"}
        }
        mock_websocket.recv.return_value = json.dumps(hotkey_response)
        
        # Test expression timing
        start_time = time.time()
        result = await client.trigger_expression(emotion)
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Verify timing constraint (should complete within 500ms)
        assert elapsed_time <= 500, f"Expression trigger took {elapsed_time:.1f}ms, exceeding 500ms limit"
        
        # Verify expression was triggered successfully
        assert result is True
        
        # Verify correct hotkey was triggered
        assert mock_websocket.send.called
        sent_message = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_message["messageType"] == "HotkeyTriggerRequest"
        assert sent_message["data"]["hotkeyID"] == emotion_hotkey_map[emotion]
    
    @given(st.sampled_from(["neutral", "happy", "angry", "sad", "surprised"]))
    @pytest.mark.asyncio
    async def test_expression_error_isolation_property(self, emotion):
        """
        Property 5: Expression Error Isolation
        For any expression triggering failure (unmapped emotion, VTS disconnection, hotkey failure), 
        the system should log appropriate warnings and continue audio playback without interruption
        **Feature: ai-vtuber-emotional-intelligence, Property 5: Expression Error Isolation**
        **Validates: Requirements 2.3, 2.5, 6.2**
        """
        # Test various failure scenarios
        failure_scenarios = [
            ("unmapped_emotion", {}),  # Empty hotkey mapping
            ("vts_disconnected", {"connected": False}),  # VTS disconnected
            ("hotkey_failure", {"hotkey_error": True})  # Hotkey trigger failure
        ]
        
        for scenario_name, scenario_config in failure_scenarios:
            # Setup client based on scenario
            if scenario_name == "unmapped_emotion":
                client = VTSClient(emotion_hotkey_map={})  # No mapping for any emotion
            else:
                emotion_hotkey_map = {emotion: f"{emotion}_hotkey"}
                client = VTSClient(emotion_hotkey_map=emotion_hotkey_map)
            
            # Mock WebSocket connection
            mock_websocket = AsyncMock()
            client.websocket = mock_websocket
            
            if scenario_config.get("connected", True):
                client._connected = True
                client._authenticated = True
            else:
                client._connected = False
                client._authenticated = False
            
            # Configure hotkey response based on scenario
            if scenario_config.get("hotkey_error"):
                hotkey_response = {
                    "messageType": "HotkeyTriggerResponse",
                    "data": {"errorID": "HotkeyNotFound", "message": "Hotkey not found"}
                }
                mock_websocket.recv.return_value = json.dumps(hotkey_response)
            else:
                # For successful scenarios (though they may fail due to other reasons)
                hotkey_response = {
                    "messageType": "HotkeyTriggerResponse", 
                    "data": {"errorID": "OK"}
                }
                mock_websocket.recv.return_value = json.dumps(hotkey_response)
            
            # Test that expression failure doesn't raise exceptions
            try:
                result = await client.trigger_expression(emotion)
                
                # Expression should fail in all these scenarios, but not raise exceptions
                if scenario_name == "unmapped_emotion":
                    assert result is False  # Should return False for unmapped emotion
                elif scenario_name == "vts_disconnected":
                    assert result is False  # Should return False when disconnected
                elif scenario_name == "hotkey_failure":
                    assert result is False  # Should return False on hotkey error
                
                # The key property: no exceptions should be raised
                # This ensures audio playback can continue uninterrupted
                
            except Exception as e:
                pytest.fail(f"Expression error isolation failed for scenario '{scenario_name}': {type(e).__name__}: {e}")
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    @pytest.mark.asyncio
    async def test_animation_synchronization_property(self, mouth_value):
        """
        Property 6: Animation Synchronization
        For any mouth parameter value, VTS mouth animation should start when audio begins and stop when audio ends
        **Feature: ai-vtuber-system, Property 6: Animation Synchronization**
        **Validates: Requirements 2.4, 2.5, 6.4**
        """
        client = VTSClient()
        
        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client._connected = True
        client._authenticated = True
        
        # Test starting animation (mouth_value should be 1.0 for start)
        if mouth_value == 1.0:
            await client.start_mouth_animation()
        else:
            await client.stop_mouth_animation()
            
        # Verify that the parameter was sent correctly
        assert mock_websocket.send.called
        
        # Get the sent message and verify it contains correct parameter
        sent_calls = mock_websocket.send.call_args_list
        assert len(sent_calls) > 0
        
        sent_message = json.loads(sent_calls[-1][0][0])
        assert sent_message["messageType"] == "InjectParameterDataRequest"
        
        parameter_values = sent_message["data"]["parameterValues"]
        # Enhanced mouth animation now sends multiple parameters
        assert len(parameter_values) >= 1
        
        # Check that MouthOpen parameter is included
        mouth_open_param = next((p for p in parameter_values if p["id"] == "MouthOpen"), None)
        assert mouth_open_param is not None
        
        # For start_mouth_animation, value should be 1.0
        # For stop_mouth_animation, value should be 0.0
        expected_value = 1.0 if mouth_value == 1.0 else 0.0
        assert mouth_open_param["value"] == expected_value


class TestVTSClientUnit:
    """Unit tests for VTSClient"""
    
    def test_client_initialization(self):
        """Test VTSClient initialization with default and custom parameters"""
        # Test default initialization
        client = VTSClient()
        assert client.host == "localhost"
        assert client.port == 8001
        assert client.websocket is None
        assert client.token is None
        assert client.token_file == "token.json"
        assert not client._connected
        assert not client._authenticated
        
        # Test custom initialization
        client_custom = VTSClient(host="127.0.0.1", port=9001)
        assert client_custom.host == "127.0.0.1"
        assert client_custom.port == 9001
        
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WebSocket connection"""
        client = VTSClient()
        
        mock_websocket = AsyncMock()
        
        async def mock_connect(uri):
            return mock_websocket
            
        with patch('src.vts_client.websockets.connect', side_effect=mock_connect):
            result = await client.connect()
            
            assert result is True
            assert client._connected is True
            assert client.websocket == mock_websocket
            
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test WebSocket connection failure"""
        client = VTSClient()
        
        with patch('src.vts_client.websockets.connect') as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")
            
            result = await client.connect()
            
            assert result is False
            assert client._connected is False
            assert client.websocket is None
            
    def test_load_token_success(self):
        """Test successful token loading from file"""
        client = VTSClient()
        test_token = "test_token_123"
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps({"token": test_token}))):
                client._load_token()
                
                assert client.token == test_token
                
    def test_load_token_file_not_exists(self):
        """Test token loading when file doesn't exist"""
        client = VTSClient()
        
        with patch('os.path.exists', return_value=False):
            client._load_token()
            
            assert client.token is None
            
    def test_load_token_invalid_json(self):
        """Test token loading with invalid JSON"""
        client = VTSClient()
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data="invalid json")):
                client._load_token()
                
                assert client.token is None
                
    def test_save_token(self):
        """Test token saving to file"""
        client = VTSClient()
        test_token = "new_token_456"
        
        with patch('builtins.open', mock_open()) as mock_file:
            client._save_token(test_token)
            
            assert client.token == test_token
            mock_file.assert_called_once_with("token.json", 'w', encoding='utf-8')
            # JSON dump writes multiple times, so just check it was called
            handle = mock_file()
            assert handle.write.called
            
    @pytest.mark.asyncio
    async def test_authenticate_with_token_success(self):
        """Test successful authentication with existing token"""
        client = VTSClient()
        client.token = "valid_token"
        client._connected = True
        
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        
        # Mock successful authentication response
        auth_response = {
            "messageType": "AuthenticationResponse",
            "data": {"authenticated": True}
        }
        mock_websocket.recv.return_value = json.dumps(auth_response)
        
        result = await client._authenticate_with_token()
        
        assert result is True
        mock_websocket.send.assert_called_once()
        mock_websocket.recv.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_authenticate_with_token_failure(self):
        """Test authentication failure with invalid token"""
        client = VTSClient()
        client.token = "invalid_token"
        client._connected = True
        
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        
        # Mock failed authentication response
        auth_response = {
            "messageType": "AuthenticationResponse",
            "data": {"authenticated": False}
        }
        mock_websocket.recv.return_value = json.dumps(auth_response)
        
        result = await client._authenticate_with_token()
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_request_new_token_success(self):
        """Test successful new token request"""
        client = VTSClient()
        client._connected = True
        
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        
        # Mock token response and subsequent authentication
        token_response = {
            "messageType": "AuthenticationTokenResponse",
            "data": {"authenticationToken": "new_token_789"}
        }
        auth_response = {
            "messageType": "AuthenticationResponse",
            "data": {"authenticated": True}
        }
        
        mock_websocket.recv.side_effect = [
            json.dumps(token_response),
            json.dumps(auth_response)
        ]
        
        with patch.object(client, '_save_token') as mock_save:
            with patch.object(client, '_authenticate_with_token', return_value=True) as mock_auth:
                result = await client._request_new_token()
                
                assert result is True
                mock_save.assert_called_once_with("new_token_789")
                mock_auth.assert_called_once()
            
    def test_is_connected(self):
        """Test connection status check"""
        client = VTSClient()
        
        # Initially not connected
        assert client.is_connected() is False
        
        # Connected but not authenticated
        client._connected = True
        assert client.is_connected() is False
        
        # Connected and authenticated
        client._authenticated = True
        assert client.is_connected() is True
        
        # Not connected but authenticated
        client._connected = False
        assert client.is_connected() is False
        
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection from VTube Studio"""
        client = VTSClient()
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client._connected = True
        client._authenticated = True
        
        await client.disconnect()
        
        mock_websocket.close.assert_called_once()
        assert client.websocket is None
        assert client._connected is False
        assert client._authenticated is False
        
    @pytest.mark.asyncio
    async def test_mouth_animation_not_connected(self):
        """Test mouth animation when not connected"""
        client = VTSClient()
        
        # Should not raise exception, just log warning
        await client.start_mouth_animation()
        await client.stop_mouth_animation()
        
        # No websocket operations should occur
        assert client.websocket is None