"""
VTube Studio Client for WebSocket communication
This module handles VTube Studio API integration and model control
"""

import asyncio
import json
import logging
import os
import threading
import time
from typing import Optional, Dict, List
import websockets
from websockets import State
from websockets.exceptions import ConnectionClosed, InvalidURI


class VTSClient:
    """Client for communicating with VTube Studio via WebSocket API"""
    
    def __init__(self, host: str = "localhost", port: int = 8001, emotion_hotkey_map: Optional[Dict[str, str]] = None):
        """
        Initialize VTS client
        
        Args:
            host: VTube Studio WebSocket host
            port: VTube Studio WebSocket port
            emotion_hotkey_map: Mapping of emotion tags to hotkey IDs
        """
        self.host = host
        self.port = port
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.token: Optional[str] = None
        self.token_file = "token.json"
        self.logger = logging.getLogger(__name__)
        self._connected = False
        self._authenticated = False
        self.emotion_hotkey_map = emotion_hotkey_map or {}
        self._expression_timeout = 0.5  # 500ms timeout for expression triggering
        
        # Use only asyncio.Lock for comprehensive thread safety
        # asyncio.Lock is sufficient for both async and sync operations when properly managed
        self._connection_lock = None  # Removed - asyncio.Lock handles all cases
        self._async_lock: Optional[asyncio.Lock] = None
        
        # Store reference to main event loop for thread-safe mouth sync
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        
    async def connect(self) -> bool:
        """
        Connect to VTube Studio WebSocket server
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        # Initialize asyncio.Lock if not already done
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        
        # Use only asyncio.Lock for thread-safe async operations
        async with self._async_lock:
                # Close existing connection if any
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except:
                        pass
                    self.websocket = None
                
                try:
                    uri = f"ws://{self.host}:{self.port}"
                    self.websocket = await websockets.connect(uri, ping_interval=20, ping_timeout=20)
                    self._connected = True
                    # Store reference to main event loop for thread-safe operations
                    self.event_loop = asyncio.get_running_loop()
                    self.logger.info(f"Connected to VTube Studio at {uri}")
                    return True
                    
                except (ConnectionRefusedError, InvalidURI, OSError) as e:
                    self.logger.error(f"Failed to connect to VTube Studio: {e}")
                    self._connected = False
                    return False
    
    async def ensure_connected(self) -> bool:
        """
        Ensure WebSocket connection is active, reconnect if needed.
        
        Returns:
            bool: True if connected and authenticated, False otherwise
        """
        # Check if websocket is still open (websockets 16.0+ uses state instead of open)
        if self.websocket and self.websocket.state == State.OPEN:
            return self._connected and self._authenticated
        
        # Connection lost, try to reconnect
        self.logger.warning("VTS WebSocket connection lost, attempting to reconnect...")
        self._connected = False
        self._authenticated = False
        
        if await self.connect():
            if await self.authenticate():
                self.logger.info("VTS reconnection successful")
                return True
        
        self.logger.error("VTS reconnection failed")
        return False
            
    async def authenticate(self) -> bool:
        """
        Authenticate with VTube Studio using token
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        if not self._connected or not self.websocket:
            self.logger.error("Not connected to VTube Studio")
            return False
            
        # Try to load existing token
        self._load_token()
        
        if self.token:
            # Try to authenticate with existing token
            if await self._authenticate_with_token():
                self._authenticated = True
                return True
                
        # Request new token if no token or authentication failed
        if await self._request_new_token():
            self._authenticated = True
            return True
            
        return False
        
    def _load_token(self) -> None:
        """Load authentication token from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.token = data.get('token')
                    self.logger.info("Loaded existing authentication token")
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to load token file: {e}")
            self.token = None
            
    def _save_token(self, token: str) -> None:
        """Save authentication token to file"""
        try:
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump({'token': token}, f)
            self.token = token
            self.logger.info("Saved authentication token")
        except IOError as e:
            self.logger.error(f"Failed to save token: {e}")
            
    async def _authenticate_with_token(self) -> bool:
        """Authenticate using existing token"""
        if not self.token:
            return False
        
        # Ensure async lock is available
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
            
        auth_request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "auth_request",
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": "AI VTuber System",
                "pluginDeveloper": "AI VTuber Dev",
                "authenticationToken": self.token
            }
        }
        
        try:
            async with self._async_lock:
                await self.websocket.send(json.dumps(auth_request))
                response = await self.websocket.recv()
                data = json.loads(response)
            
            if data.get("messageType") == "AuthenticationResponse":
                if data.get("data", {}).get("authenticated", False):
                    self.logger.info("Authentication successful with existing token")
                    return True
                else:
                    self.logger.warning("Authentication failed with existing token")
                    
        except (ConnectionClosed, json.JSONDecodeError) as e:
            self.logger.error(f"Authentication error: {e}")
            
        return False
        
    async def _request_new_token(self) -> bool:
        """Request new authentication token from VTube Studio"""
        token_request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "token_request",
            "messageType": "AuthenticationTokenRequest",
            "data": {
                "pluginName": "AI VTuber System",
                "pluginDeveloper": "AI VTuber Dev",
                "pluginIcon": None
            }
        }
        
        try:
            async with self._async_lock:
                await self.websocket.send(json.dumps(token_request))
                self.logger.info("Requesting new authentication token - please accept in VTube Studio")
                
                response = await self.websocket.recv()
                data = json.loads(response)
            
            if data.get("messageType") == "AuthenticationTokenResponse":
                token = data.get("data", {}).get("authenticationToken")
                if token:
                    self._save_token(token)
                    # Now authenticate with the new token
                    return await self._authenticate_with_token()
                    
        except (ConnectionClosed, json.JSONDecodeError) as e:
            self.logger.error(f"Token request error: {e}")
            
        return False
        
    async def start_mouth_animation(self) -> bool:
        """
        Start mouth animation by setting multiple mouth parameters for more noticeable effect
        
        Returns:
            bool: True if mouth animation started successfully, False otherwise
        """
        success = await self._set_mouth_parameters({
            "MouthOpen": 1.0,
            "VoiceVolumePlusMouthOpen": 0.8  # Additional volume-based animation
        })
        if success:
            self.logger.info("Sending Mouth Parameter: MouthOpen=1.0")
        return success
        
    async def stop_mouth_animation(self) -> bool:
        """
        Stop mouth animation by resetting all mouth parameters
        
        Returns:
            bool: True if mouth animation stopped successfully, False otherwise
        """
        success = await self._set_mouth_parameters({
            "MouthOpen": 0.0,
            "VoiceVolumePlusMouthOpen": 0.0
        })
        if success:
            self.logger.info("Sending Mouth Parameter: MouthOpen=0.0")
        return success
    
    async def animate_mouth_during_playback(self, duration_seconds: float) -> None:
        """
        Animate mouth with natural speaking pattern during audio playback.
        
        This creates a more realistic speaking animation by varying the mouth
        opening value over time instead of just static open/close.
        
        Args:
            duration_seconds: Duration of the audio playback
        """
        import math
        import random
        
        if duration_seconds <= 0:
            # Fallback to simple open/close if no duration provided
            await self.start_mouth_animation()
            return
        
        start_time = time.time()
        frame_interval = 0.1  # 10 fps for smooth animation
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Stop if duration exceeded
                if elapsed >= duration_seconds:
                    break
                
                # Generate natural-looking mouth movement
                # Combine sine wave with random variation for organic feel
                base_value = 0.6 + 0.3 * math.sin(elapsed * 6)  # Base oscillation
                variation = random.uniform(-0.1, 0.1)  # Random variation
                mouth_value = max(0.3, min(1.0, base_value + variation))
                
                await self._set_mouth_parameters({
                    "MouthOpen": mouth_value,
                    "VoiceVolumePlusMouthOpen": mouth_value * 0.7
                })
                
                await asyncio.sleep(frame_interval)
                
        except asyncio.CancelledError:
            # Animation was cancelled, close mouth
            await self.stop_mouth_animation()
            raise
        except Exception as e:
            self.logger.warning(f"Mouth animation error: {e}")
            await self.stop_mouth_animation()
    
    def start_mouth_sync(self) -> bool:
        """
        Thread-safe wrapper to trigger mouth movement from TTS thread.
        
        Uses asyncio.run_coroutine_threadsafe() to schedule the coroutine
        on the main event loop from any thread.
        
        Returns:
            bool: True if mouth sync started successfully, False otherwise
        """
        if not self.event_loop or not self.websocket:
            self.logger.warning("Cannot start mouth sync - no event loop or websocket connection")
            return False
        
        try:
            # Schedule the coroutine to run on the main asyncio loop
            future = asyncio.run_coroutine_threadsafe(self.start_mouth_animation(), self.event_loop)
            # Wait for completion with timeout to avoid blocking indefinitely
            return future.result(timeout=1.0)
        except Exception as e:
            self.logger.error(f"Failed to start mouth sync: {e}")
            return False
    
    def stop_mouth_sync(self) -> bool:
        """
        Thread-safe wrapper to stop mouth movement from TTS thread.
        
        Uses asyncio.run_coroutine_threadsafe() to schedule the coroutine
        on the main event loop from any thread.
        
        Returns:
            bool: True if mouth sync stopped successfully, False otherwise
        """
        if not self.event_loop or not self.websocket:
            self.logger.warning("Cannot stop mouth sync - no event loop or websocket connection")
            return False
        
        try:
            # Schedule the coroutine to run on the main asyncio loop
            future = asyncio.run_coroutine_threadsafe(self.stop_mouth_animation(), self.event_loop)
            # Wait for completion with timeout to avoid blocking indefinitely
            return future.result(timeout=1.0)
        except Exception as e:
            self.logger.error(f"Failed to stop mouth sync: {e}")
            return False
    
    def animate_mouth_for_duration(self, duration_seconds: float) -> bool:
        """
        Thread-safe wrapper to animate mouth for a specific duration.
        
        This provides natural speaking animation throughout the audio playback
        instead of just static open/close.
        
        Args:
            duration_seconds: Duration of the audio playback
            
        Returns:
            bool: True if animation started successfully, False otherwise
        """
        if not self.event_loop or not self.websocket:
            self.logger.warning("Cannot animate mouth - no event loop or websocket connection")
            return False
        
        try:
            # Schedule the animation coroutine to run on the main asyncio loop
            future = asyncio.run_coroutine_threadsafe(
                self.animate_mouth_during_playback(duration_seconds), 
                self.event_loop
            )
            # Don't wait for completion since this is a long-running animation
            # The animation will run in the background and stop automatically
            return True
        except Exception as e:
            self.logger.error(f"Failed to start mouth animation: {e}")
            return False
    
    async def animate_mouth_speaking(self, duration_seconds: float = 0.0) -> None:
        """
        Animate mouth with speaking pattern during audio playback.
        
        This creates a more natural speaking animation by varying the mouth
        opening value over time instead of just static open/close.
        
        Args:
            duration_seconds: Expected duration of speech (0 = indefinite until stop)
        """
        import math
        import random
        
        start_time = time.time()
        frame_interval = 0.08  # ~12.5 fps for smooth animation
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Stop if duration exceeded (if specified)
                if duration_seconds > 0 and elapsed >= duration_seconds:
                    break
                
                # Generate natural-looking mouth movement
                # Combine sine wave with random variation for organic feel
                base_value = 0.5 + 0.3 * math.sin(elapsed * 8)  # Base oscillation
                variation = random.uniform(-0.15, 0.15)  # Random variation
                mouth_value = max(0.2, min(1.0, base_value + variation))
                
                await self._set_mouth_parameters({
                    "MouthOpen": mouth_value,
                    "VoiceVolumePlusMouthOpen": mouth_value * 0.8
                })
                
                await asyncio.sleep(frame_interval)
                
        except asyncio.CancelledError:
            # Animation was cancelled, close mouth
            await self.stop_mouth_animation()
            raise
        except Exception as e:
            self.logger.warning(f"Mouth animation error: {e}")
            await self.stop_mouth_animation()
        
    async def _set_mouth_parameter(self, value: float) -> None:
        """
        Set MouthOpen parameter value (legacy method for backward compatibility)
        
        Args:
            value: Parameter value (0.0 to 1.0)
        """
        await self._set_mouth_parameters({"MouthOpen": value})
        
    async def _set_mouth_parameters(self, parameters: dict) -> bool:
        """
        Set multiple mouth parameters simultaneously
        
        Args:
            parameters: Dictionary of parameter_name: value pairs
            
        Returns:
            bool: True if parameters were set successfully, False otherwise
        """
        # Ensure connection is active
        if not await self.ensure_connected():
            self.logger.warning("Cannot set mouth parameters - not connected or authenticated")
            return False
            
        parameter_values = [
            {"id": param_name, "value": value}
            for param_name, value in parameters.items()
        ]
        
        parameter_request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "mouth_params_request",
            "messageType": "InjectParameterDataRequest",
            "data": {
                "parameterValues": parameter_values
            }
        }
        
        try:
            async with self._async_lock:
                await self.websocket.send(json.dumps(parameter_request))
                # Fire-and-forget for high-frequency updates (mouth animation)
                # Only wait for response on initial connections, not every update
                self.logger.debug(f"Set mouth parameters: {parameters}")
            return True
            
        except asyncio.TimeoutError:
            self.logger.warning("Timeout waiting for mouth parameter response")
            return False
        except ConnectionClosed as e:
            self.logger.error(f"Failed to set mouth parameters: {e}")
            self._connected = False
            self._authenticated = False
            return False
        except Exception as e:
            self.logger.error(f"Error setting mouth parameters: {e}")
            return False
            
    def is_connected(self) -> bool:
        """
        Check if client is connected and authenticated
        
        Returns:
            bool: True if connected and authenticated, False otherwise
        """
        # Check actual WebSocket state (websockets 16.0+ uses state instead of open)
        if self.websocket and self.websocket.state == State.OPEN:
            return self._connected and self._authenticated
        return False
    
    async def trigger_expression(self, emotion: str) -> bool:
        """
        Trigger Live2D expression based on emotion tag
        
        Args:
            emotion: Emotion tag ("neutral", "happy", "angry", "sad", "surprised")
            
        Returns:
            bool: True if expression triggered successfully, False otherwise
            
        Note:
            This method implements error isolation - expression failures do not affect audio playback.
            All errors are logged but do not raise exceptions to prevent disrupting the conversation flow.
        """
        if not self._connected or not self._authenticated:
            self.logger.warning(f"Cannot trigger expression for emotion '{emotion}' - not connected or authenticated")
            return False
        
        # Get hotkey ID for the emotion
        hotkey_id = self.emotion_hotkey_map.get(emotion)
        if not hotkey_id:
            self.handle_unmapped_emotion(emotion)
            return False
        
        # Trigger the hotkey with timeout and comprehensive error handling
        start_time = time.time()
        try:
            success = await asyncio.wait_for(
                self._trigger_hotkey(hotkey_id),
                timeout=self._expression_timeout
            )
            
            elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            if success:
                self.logger.debug(f"Expression triggered for emotion '{emotion}' in {elapsed_time:.1f}ms")
            else:
                self.logger.warning(f"Failed to trigger expression for emotion '{emotion}' after {elapsed_time:.1f}ms - continuing with audio")
            
            return success
            
        except asyncio.TimeoutError:
            elapsed_time = (time.time() - start_time) * 1000
            self.logger.warning(f"Expression trigger timeout for emotion '{emotion}' after {elapsed_time:.1f}ms - continuing with audio")
            return False
        except ConnectionClosed:
            elapsed_time = (time.time() - start_time) * 1000
            self.logger.error(f"VTube Studio connection lost during expression trigger for '{emotion}' after {elapsed_time:.1f}ms - continuing with audio")
            self._handle_connection_lost()
            return False
        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            self.logger.error(f"Unexpected error triggering expression for emotion '{emotion}' after {elapsed_time:.1f}ms: {e} - continuing with audio")
            return False
    
    async def _trigger_hotkey(self, hotkey_id: str) -> bool:
        """
        Send hotkey trigger request to VTube Studio
        
        Args:
            hotkey_id: VTube Studio hotkey identifier
            
        Returns:
            bool: True if hotkey triggered successfully, False otherwise
            
        Note:
            This method implements comprehensive error handling and logging
            for debugging expression control issues.
        """
        if not self.websocket:
            self.logger.error("Cannot trigger hotkey - no WebSocket connection")
            return False
        
        hotkey_request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": f"hotkey_trigger_{hotkey_id}",
            "messageType": "HotkeyTriggerRequest",
            "data": {
                "hotkeyID": hotkey_id
            }
        }
        
        try:
            self.logger.debug(f"Sending hotkey trigger request for '{hotkey_id}'")
            async with self._async_lock:
                await self.websocket.send(json.dumps(hotkey_request))
                response = await self.websocket.recv()
                data = json.loads(response)
            
            if data.get("messageType") == "HotkeyTriggerResponse":
                # VTS API returns errorID as integer: 0 = success, non-zero = error
                # Some versions may not include errorID on success
                response_data = data.get("data", {})
                error_id = response_data.get("errorID")
                
                # Log full response for debugging
                self.logger.debug(f"VTS HotkeyTriggerResponse: {response_data}")
                
                # Success conditions: errorID is 0, None (not present), or "OK"
                if error_id is None or error_id == 0 or error_id == "OK":
                    self.logger.info(f"Hotkey '{hotkey_id}' triggered successfully")
                    return True
                else:
                    error_msg = response_data.get("message", "Unknown error")
                    self.logger.warning(f"Hotkey trigger failed for '{hotkey_id}' (errorID: {error_id}): {error_msg}")
                    self.logger.debug(f"Full VTS response: {data}")
                    return False
            else:
                self.logger.warning(f"Unexpected response type for hotkey trigger: {data.get('messageType')} (expected HotkeyTriggerResponse)")
                return False
                
        except ConnectionClosed as e:
            self.logger.error(f"Connection lost while triggering hotkey '{hotkey_id}': {e}")
            self._handle_connection_lost()
            return False
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response for hotkey trigger '{hotkey_id}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error triggering hotkey '{hotkey_id}': {type(e).__name__}: {e}")
            return False
    
    def update_emotion_hotkey_map(self, emotion_hotkey_map: Dict[str, str]) -> None:
        """
        Update the emotion to hotkey mapping
        
        Args:
            emotion_hotkey_map: New mapping of emotion tags to hotkey IDs
        """
        self.emotion_hotkey_map = emotion_hotkey_map.copy()
        self.logger.info(f"Updated emotion hotkey mapping: {self.emotion_hotkey_map}")
    
    async def get_available_hotkeys(self) -> List[Dict]:
        """
        Retrieve available hotkeys from current VTube Studio model
        
        Returns:
            List[Dict]: List of available hotkeys with their IDs and names
                       Each dict contains: {"hotkeyID": str, "name": str, "type": str}
                       Returns empty list if retrieval fails (with appropriate logging)
        """
        if not self._connected or not self._authenticated:
            self.logger.warning("Cannot get hotkeys - not connected or authenticated")
            return []
        
        if not self.websocket:
            self.logger.error("Cannot get hotkeys - no WebSocket connection")
            return []
        
        hotkeys_request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "get_hotkeys_request",
            "messageType": "HotkeysInCurrentModelRequest",
            "data": {}
        }
        
        try:
            self.logger.debug("Requesting available hotkeys from VTube Studio")
            async with self._async_lock:
                await self.websocket.send(json.dumps(hotkeys_request))
                response = await self.websocket.recv()
                data = json.loads(response)
            
            if data.get("messageType") == "HotkeysInCurrentModelResponse":
                hotkeys = data.get("data", {}).get("availableHotkeys", [])
                self.logger.info(f"Retrieved {len(hotkeys)} available hotkeys from VTube Studio")
                
                # Log hotkey details for debugging
                if hotkeys:
                    self.logger.debug("Available hotkeys:")
                    for hotkey in hotkeys:
                        self.logger.debug(f"  - {hotkey.get('name', 'Unknown')} (ID: {hotkey.get('hotkeyID', 'Unknown')})")
                
                return hotkeys
            else:
                self.logger.warning(f"Unexpected response type for hotkeys request: {data.get('messageType')} (expected HotkeysInCurrentModelResponse)")
                return []
                
        except ConnectionClosed as e:
            self.logger.error(f"Connection lost while getting hotkeys: {e}")
            self._handle_connection_lost()
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response for hotkeys request: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error getting hotkeys: {type(e).__name__}: {e}")
            return []
    
    async def validate_hotkey_mappings(self, emotion_hotkey_map: Dict[str, str]) -> Dict[str, bool]:
        """
        Validate emotion-to-hotkey mappings against available hotkeys
        
        Args:
            emotion_hotkey_map: Mapping of emotion tags to hotkey IDs to validate
            
        Returns:
            Dict[str, bool]: Validation results for each emotion mapping
                           True if hotkey exists, False if not found
        """
        available_hotkeys = await self.get_available_hotkeys()
        if not available_hotkeys:
            self.logger.warning("No available hotkeys found - cannot validate mappings")
            return {emotion: False for emotion in emotion_hotkey_map.keys()}
        
        # Create set of available hotkey IDs for fast lookup
        available_hotkey_ids = {hotkey.get("hotkeyID") for hotkey in available_hotkeys}
        
        validation_results = {}
        for emotion, hotkey_id in emotion_hotkey_map.items():
            if not hotkey_id:  # Empty hotkey ID is valid (means no mapping)
                validation_results[emotion] = True
            else:
                is_valid = hotkey_id in available_hotkey_ids
                validation_results[emotion] = is_valid
                
                if not is_valid:
                    self.logger.warning(f"Invalid hotkey mapping: emotion '{emotion}' -> hotkey '{hotkey_id}' not found")
                else:
                    self.logger.debug(f"Valid hotkey mapping: emotion '{emotion}' -> hotkey '{hotkey_id}'")
        
        return validation_results
    
    def handle_unmapped_emotion(self, emotion: str) -> None:
        """
        Handle unmapped emotions gracefully
        
        Args:
            emotion: The emotion tag that has no hotkey mapping
        """
        self.logger.info(f"Emotion '{emotion}' has no hotkey mapping - continuing without expression trigger")
        # This method provides a centralized place for handling unmapped emotions
        # Currently just logs, but could be extended for other behaviors like
        # using a default expression or notifying the user
    
    def _handle_connection_lost(self) -> None:
        """
        Handle VTube Studio connection loss gracefully
        
        This method implements error isolation by updating connection state
        without raising exceptions that could disrupt audio playback.
        """
        self._connected = False
        self._authenticated = False
        self.logger.error("VTube Studio connection lost - expressions disabled until reconnection")
        # Note: This does not attempt automatic reconnection to avoid blocking
        # The system workflow should handle reconnection attempts if needed
    
    def is_expression_available(self) -> bool:
        """
        Check if expression control is currently available
        
        Returns:
            bool: True if expressions can be triggered, False otherwise
        """
        return self._connected and self._authenticated and bool(self.emotion_hotkey_map)
    
    def get_expression_status(self) -> Dict[str, any]:
        """
        Get detailed status information for expression control debugging
        
        Returns:
            Dict containing connection status, mapping info, and error state
        """
        return {
            "connected": self._connected,
            "authenticated": self._authenticated,
            "has_hotkey_mappings": bool(self.emotion_hotkey_map),
            "mapped_emotions": list(self.emotion_hotkey_map.keys()),
            "expression_timeout": self._expression_timeout,
            "websocket_available": self.websocket is not None
        }
        
    async def disconnect(self) -> None:
        """Disconnect from VTube Studio"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        self._connected = False
        self._authenticated = False
        self.logger.info("Disconnected from VTube Studio")