"""
AudioDeviceManager Component

Manage audio hardware detection, configuration, and compatibility.
Handles device enumeration, headphones detection, and optimal parameter configuration.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging
import sounddevice as sd
import re

from .logging_config import get_component_logger

logger = get_component_logger("audio_device_manager")

@dataclass
class AudioConfiguration:
    """Audio hardware configuration details."""
    has_headphones: bool
    has_speakers: bool
    microphone_available: bool
    supports_full_duplex: bool
    recommended_sample_rate: int
    buffer_size: int

@dataclass
class AudioDeviceInfo:
    """Audio device information."""
    device_id: int
    name: str
    sample_rates: List[int]
    channels: int
    is_input: bool
    is_output: bool

@dataclass
class AudioSettings:
    """Optimal audio settings for a device."""
    sample_rate: int
    buffer_size: int
    channels: int
    latency: str  # 'low', 'medium', 'high'

class AudioDeviceManager:
    """Manage audio hardware detection and configuration."""
    
    def __init__(self):
        """Initialize audio device manager."""
        self.current_config: Optional[AudioConfiguration] = None
        self.available_devices: List[AudioDeviceInfo] = []
        self._device_change_callbacks: List[callable] = []
        self._monitoring_active = False
        self._last_device_state = None
        logger.info("AudioDeviceManager initialized")
        
        # Initialize sounddevice and enumerate devices
        try:
            self.enumerate_devices()
            self._last_device_state = self._get_device_state_snapshot()
            logger.info("Initial device enumeration completed")
        except Exception as e:
            logger.error(f"Failed to initialize audio devices: {e}")
    
    def detect_audio_configuration(self) -> AudioConfiguration:
        """Detect current audio hardware setup."""
        logger.info("Detecting audio hardware configuration...")
        
        try:
            # Get default devices
            default_input = sd.default.device[0] if sd.default.device[0] is not None else None
            default_output = sd.default.device[1] if sd.default.device[1] is not None else None
            
            # Check for microphone availability
            microphone_available = default_input is not None
            
            # Detect headphones vs speakers
            has_headphones, has_speakers = self._detect_output_type(default_output)
            
            # Determine full-duplex support
            supports_full_duplex = (microphone_available and 
                                   has_headphones and 
                                   self._check_duplex_capability())
            
            # Get recommended sample rate
            recommended_sample_rate = self._get_optimal_sample_rate(default_input)
            
            config = AudioConfiguration(
                has_headphones=has_headphones,
                has_speakers=has_speakers,
                microphone_available=microphone_available,
                supports_full_duplex=supports_full_duplex,
                recommended_sample_rate=recommended_sample_rate,
                buffer_size=int(recommended_sample_rate * 0.06)  # 60ms buffer
            )
            
            self.current_config = config
            logger.info(f"Audio configuration detected: {config}")
            return config
            
        except Exception as e:
            logger.error(f"Error detecting audio configuration: {e}")
            # Return safe defaults
            config = AudioConfiguration(
                has_headphones=False,
                has_speakers=True,
                microphone_available=False,
                supports_full_duplex=False,
                recommended_sample_rate=16000,
                buffer_size=960
            )
            self.current_config = config
            return config
    
    def _detect_output_type(self, output_device_id: Optional[int]) -> tuple[bool, bool]:
        """Detect if output device is headphones or speakers."""
        if output_device_id is None:
            return False, True  # Default to speakers if no device
        
        try:
            device_info = sd.query_devices(output_device_id)
            device_name = device_info['name'].lower()
            
            # Common headphone indicators in device names
            headphone_keywords = [
                'headphone', 'headset', 'earphone', 'earbud', 'airpods',
                'beats', 'sony wh', 'bose', 'sennheiser', 'audio-technica',
                'hyperx', 'steelseries', 'logitech g', 'corsair', 'razer'
            ]
            
            # Check for headphone indicators
            has_headphones = any(keyword in device_name for keyword in headphone_keywords)
            
            # If not clearly headphones, assume speakers
            has_speakers = not has_headphones
            
            logger.debug(f"Output device '{device_name}' detected as: "
                        f"headphones={has_headphones}, speakers={has_speakers}")
            
            return has_headphones, has_speakers
            
        except Exception as e:
            logger.warning(f"Could not detect output device type: {e}")
            return False, True  # Default to speakers
    
    def _check_duplex_capability(self) -> bool:
        """Check if the system supports full-duplex audio."""
        try:
            # Test if we can open both input and output streams simultaneously
            with sd.InputStream(channels=1, samplerate=16000, blocksize=960):
                with sd.OutputStream(channels=1, samplerate=16000, blocksize=960):
                    logger.debug("Full-duplex capability confirmed")
                    return True
        except Exception as e:
            logger.debug(f"Full-duplex test failed: {e}")
            return False
    
    def _get_optimal_sample_rate(self, input_device_id: Optional[int]) -> int:
        """Get optimal sample rate for the input device."""
        if input_device_id is None:
            return 16000  # Default for speech processing
        
        try:
            device_info = sd.query_devices(input_device_id)
            default_rate = int(device_info['default_samplerate'])
            
            # Prefer rates optimal for speech processing
            preferred_rates = [16000, 44100, 48000]
            
            # If device default is in our preferred list, use it
            if default_rate in preferred_rates:
                return default_rate
            
            # Otherwise, test which rates work
            for rate in preferred_rates:
                try:
                    sd.check_input_settings(device=input_device_id, 
                                          samplerate=rate, 
                                          channels=1)
                    return rate
                except:
                    continue
            
            # Fall back to device default
            return default_rate
            
        except Exception as e:
            logger.warning(f"Could not determine optimal sample rate: {e}")
            return 16000
    
    def enumerate_devices(self) -> List[AudioDeviceInfo]:
        """Enumerate available audio devices using sounddevice."""
        logger.info("Enumerating audio devices...")
        
        try:
            devices = []
            device_list = sd.query_devices()
            
            for i, device in enumerate(device_list):
                # Get supported sample rates
                supported_rates = self._get_supported_sample_rates(i, device)
                
                device_info = AudioDeviceInfo(
                    device_id=i,
                    name=device['name'],
                    sample_rates=supported_rates,
                    channels=device['max_input_channels'] if device['max_input_channels'] > 0 
                            else device['max_output_channels'],
                    is_input=device['max_input_channels'] > 0,
                    is_output=device['max_output_channels'] > 0
                )
                devices.append(device_info)
            
            self.available_devices = devices
            logger.info(f"Found {len(devices)} audio devices")
            
            # Log device details for debugging
            for device in devices:
                logger.debug(f"Device {device.device_id}: {device.name} "
                           f"(Input: {device.is_input}, Output: {device.is_output}, "
                           f"Channels: {device.channels})")
            
            return devices
            
        except Exception as e:
            logger.error(f"Failed to enumerate audio devices: {e}")
            return []
    
    def _get_supported_sample_rates(self, device_id: int, device_info: dict) -> List[int]:
        """Get supported sample rates for a specific device."""
        test_rates = [8000, 16000, 22050, 44100, 48000, 96000]
        supported_rates = []
        
        for rate in test_rates:
            try:
                if device_info['max_input_channels'] > 0:
                    sd.check_input_settings(device=device_id, 
                                          samplerate=rate, 
                                          channels=1)
                    supported_rates.append(rate)
                elif device_info['max_output_channels'] > 0:
                    sd.check_output_settings(device=device_id, 
                                           samplerate=rate, 
                                           channels=1)
                    supported_rates.append(rate)
            except:
                continue
        
        # If no rates found, use device default
        if not supported_rates:
            default_rate = int(device_info['default_samplerate'])
            supported_rates = [default_rate]
        
        return supported_rates
    
    def configure_for_device(self, device_info: AudioDeviceInfo) -> AudioSettings:
        """Configure optimal settings for detected audio device."""
        logger.info(f"Configuring settings for device: {device_info.name}")
        
        # Determine optimal sample rate from supported rates
        preferred_rates = [16000, 44100, 48000]
        sample_rate = 16000  # Default for speech
        
        for rate in preferred_rates:
            if rate in device_info.sample_rates:
                sample_rate = rate
                break
        
        # Configure buffer size based on sample rate (60ms for low latency)
        buffer_size = int(sample_rate * 0.06)
        
        # Determine latency setting based on device capabilities
        latency = 'low' if sample_rate >= 16000 else 'medium'
        
        settings = AudioSettings(
            sample_rate=sample_rate,
            buffer_size=buffer_size,
            channels=min(device_info.channels, 1),  # Mono for speech processing
            latency=latency
        )
        
        logger.info(f"Optimal settings for {device_info.name}: {settings}")
        return settings
    
    def is_full_duplex_compatible(self) -> bool:
        """Check if current setup supports full-duplex mode."""
        if not self.current_config:
            self.detect_audio_configuration()
        
        compatible = (self.current_config.has_headphones and 
                     self.current_config.microphone_available and
                     self.current_config.supports_full_duplex)
        
        logger.debug(f"Full-duplex compatibility: {compatible}")
        return compatible
    
    def get_supported_sample_rates(self) -> List[int]:
        """Get list of supported sample rates for current device."""
        if not self.current_config:
            self.detect_audio_configuration()
        
        # Get input device sample rates
        try:
            default_input = sd.default.device[0]
            if default_input is not None:
                input_device = next((d for d in self.available_devices 
                                   if d.device_id == default_input and d.is_input), None)
                if input_device:
                    return input_device.sample_rates
        except Exception as e:
            logger.warning(f"Could not get supported sample rates: {e}")
        
        return [16000, 44100, 48000]  # Safe defaults
    
    def handle_device_change(self, new_device: AudioDeviceInfo) -> None:
        """Handle audio device changes during operation."""
        logger.info(f"Handling device change to: {new_device.name}")
        
        try:
            # Validate new device compatibility
            validation = self.validate_device_compatibility(new_device)
            
            if not validation['compatible']:
                logger.warning(f"New device {new_device.name} is not compatible: {validation['errors']}")
                # Still proceed but with warnings
            
            # Reconfigure for new device
            new_settings = self.configure_for_device(new_device)
            
            # Update current configuration
            old_config = self.current_config
            self.detect_audio_configuration()
            
            # Check if configuration changed significantly
            config_changed = self._has_significant_config_change(old_config, self.current_config)
            
            # Notify registered callbacks
            for callback in self._device_change_callbacks:
                try:
                    callback(new_device, new_settings, config_changed)
                except Exception as e:
                    logger.error(f"Device change callback failed: {e}")
            
            logger.info("Device change handled successfully")
            
        except Exception as e:
            logger.error(f"Failed to handle device change: {e}")
    
    def _has_significant_config_change(self, old_config: Optional[AudioConfiguration], 
                                     new_config: AudioConfiguration) -> bool:
        """Check if configuration change is significant enough to require action."""
        if not old_config:
            return True
        
        # Check for significant changes
        significant_changes = [
            old_config.has_headphones != new_config.has_headphones,
            old_config.microphone_available != new_config.microphone_available,
            old_config.supports_full_duplex != new_config.supports_full_duplex,
            abs(old_config.recommended_sample_rate - new_config.recommended_sample_rate) > 1000
        ]
        
        return any(significant_changes)
    
    def start_device_monitoring(self) -> None:
        """Start monitoring for device changes."""
        if self._monitoring_active:
            logger.warning("Device monitoring already active")
            return
        
        self._monitoring_active = True
        logger.info("Started device change monitoring")
        
        # Note: In a real implementation, this would start a background thread
        # that periodically checks for device changes. For now, we provide
        # the infrastructure for manual device change detection.
    
    def stop_device_monitoring(self) -> None:
        """Stop monitoring for device changes."""
        self._monitoring_active = False
        logger.info("Stopped device change monitoring")
    
    def check_for_device_changes(self) -> bool:
        """Check if devices have changed since last check."""
        try:
            current_state = self._get_device_state_snapshot()
            
            if current_state != self._last_device_state:
                logger.info("Device configuration change detected")
                
                # Re-enumerate devices
                old_devices = self.available_devices.copy()
                self.enumerate_devices()
                
                # Detect what changed
                self._handle_device_state_change(old_devices, self.available_devices)
                
                self._last_device_state = current_state
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for device changes: {e}")
            return False
    
    def _get_device_state_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of current device state for change detection."""
        try:
            devices = sd.query_devices()
            default_devices = sd.default.device
            
            return {
                'device_count': len(devices),
                'default_input': default_devices[0],
                'default_output': default_devices[1],
                'device_names': [d['name'] for d in devices]
            }
        except Exception as e:
            logger.error(f"Failed to get device state snapshot: {e}")
            return {}
    
    def _handle_device_state_change(self, old_devices: List[AudioDeviceInfo], 
                                  new_devices: List[AudioDeviceInfo]) -> None:
        """Handle detected device state changes."""
        # Find added devices
        old_ids = {d.device_id for d in old_devices}
        new_ids = {d.device_id for d in new_devices}
        
        added_devices = [d for d in new_devices if d.device_id not in old_ids]
        removed_devices = [d for d in old_devices if d.device_id not in new_ids]
        
        for device in added_devices:
            logger.info(f"New device detected: {device.name}")
        
        for device in removed_devices:
            logger.info(f"Device removed: {device.name}")
        
        # If default devices changed, trigger reconfiguration
        if added_devices or removed_devices:
            self.detect_audio_configuration()
    
    def get_supported_sample_rates_for_device(self, device_id: int) -> List[int]:
        """Get supported sample rates for a specific device."""
        device = self.get_device_by_id(device_id)
        if device:
            return device.sample_rates
        
        logger.warning(f"Device {device_id} not found")
        return []
    
    def test_sample_rate_compatibility(self, device_id: int, sample_rate: int) -> bool:
        """Test if a device supports a specific sample rate."""
        try:
            device_info = sd.query_devices(device_id)
            
            if device_info['max_input_channels'] > 0:
                sd.check_input_settings(device=device_id, 
                                      samplerate=sample_rate, 
                                      channels=1)
                return True
            elif device_info['max_output_channels'] > 0:
                sd.check_output_settings(device=device_id, 
                                       samplerate=sample_rate, 
                                       channels=1)
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Sample rate {sample_rate} not supported on device {device_id}: {e}")
            return False
    
    def get_optimal_settings_for_sample_rate(self, device_id: int, 
                                           target_sample_rate: int) -> Optional[AudioSettings]:
        """Get optimal settings for a specific sample rate on a device."""
        device = self.get_device_by_id(device_id)
        if not device:
            return None
        
        # Check if target sample rate is supported
        if target_sample_rate not in device.sample_rates:
            logger.warning(f"Sample rate {target_sample_rate} not supported by device {device.name}")
            return None
        
        # Create optimized settings for the target sample rate
        buffer_size = int(target_sample_rate * 0.06)  # 60ms buffer
        
        # Adjust latency based on sample rate
        if target_sample_rate >= 44100:
            latency = 'low'
        elif target_sample_rate >= 16000:
            latency = 'medium'
        else:
            latency = 'high'
        
        settings = AudioSettings(
            sample_rate=target_sample_rate,
            buffer_size=buffer_size,
            channels=min(device.channels, 1),  # Mono for speech
            latency=latency
        )
        
        logger.debug(f"Optimal settings for {target_sample_rate}Hz on {device.name}: {settings}")
        return settings
    
    def graceful_device_transition(self, old_device_id: int, new_device_id: int) -> bool:
        """Perform graceful transition between audio devices."""
        logger.info(f"Performing graceful transition from device {old_device_id} to {new_device_id}")
        
        try:
            old_device = self.get_device_by_id(old_device_id)
            new_device = self.get_device_by_id(new_device_id)
            
            if not new_device:
                logger.error(f"Target device {new_device_id} not found")
                return False
            
            # Validate new device
            validation = self.validate_device_compatibility(new_device)
            if not validation['compatible']:
                logger.error(f"Target device is not compatible: {validation['errors']}")
                return False
            
            # Configure new device
            new_settings = self.configure_for_device(new_device)
            
            # Update configuration
            self.detect_audio_configuration()
            
            # Notify callbacks about the transition
            for callback in self._device_change_callbacks:
                try:
                    callback(new_device, new_settings, True)
                except Exception as e:
                    logger.error(f"Transition callback failed: {e}")
            
            logger.info("Graceful device transition completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Graceful device transition failed: {e}")
            return False
    
    def register_device_change_callback(self, callback: callable) -> None:
        """Register callback for device change events."""
        self._device_change_callbacks.append(callback)
        logger.debug("Device change callback registered")
    
    def get_device_by_id(self, device_id: int) -> Optional[AudioDeviceInfo]:
        """Get device information by device ID."""
        return next((d for d in self.available_devices if d.device_id == device_id), None)
    
    def get_default_input_device(self) -> Optional[AudioDeviceInfo]:
        """Get default input device information."""
        try:
            default_input = sd.default.device[0]
            if default_input is not None:
                return self.get_device_by_id(default_input)
        except Exception as e:
            logger.warning(f"Could not get default input device: {e}")
        return None
    
    def get_default_output_device(self) -> Optional[AudioDeviceInfo]:
        """Get default output device information."""
        try:
            default_output = sd.default.device[1]
            if default_output is not None:
                return self.get_device_by_id(default_output)
        except Exception as e:
            logger.warning(f"Could not get default output device: {e}")
        return None
    
    def enumerate_devices(self) -> List[AudioDeviceInfo]:
        """Enumerate available audio devices using sounddevice."""
        logger.info("Enumerating audio devices...")
        
        try:
            devices = []
            device_list = sd.query_devices()
            
            for i, device in enumerate(device_list):
                # Get supported sample rates
                supported_rates = self._get_supported_sample_rates(i, device)
                
                device_info = AudioDeviceInfo(
                    device_id=i,
                    name=device['name'],
                    sample_rates=supported_rates,
                    channels=device['max_input_channels'] if device['max_input_channels'] > 0 
                            else device['max_output_channels'],
                    is_input=device['max_input_channels'] > 0,
                    is_output=device['max_output_channels'] > 0
                )
                devices.append(device_info)
            
            self.available_devices = devices
            logger.info(f"Found {len(devices)} audio devices")
            
            # Log device details for debugging
            for device in devices:
                logger.debug(f"Device {device.device_id}: {device.name} "
                           f"(Input: {device.is_input}, Output: {device.is_output}, "
                           f"Channels: {device.channels})")
            
            return devices
            
        except Exception as e:
            logger.error(f"Failed to enumerate audio devices: {e}")
            return []
    
    def get_device_warnings(self) -> List[str]:
        """Get hardware compatibility warnings."""
        warnings = []
        
        if not self.current_config:
            self.detect_audio_configuration()
        
        if not self.current_config.has_headphones:
            warnings.append("⚠️ Please use headphones for Full-Duplex mode to prevent feedback")
        
        if not self.current_config.microphone_available:
            warnings.append("⚠️ No microphone detected - voice input unavailable")
        
        if not self.current_config.supports_full_duplex:
            warnings.append("⚠️ Current audio setup may not support full-duplex operation")
        
        return warnings
    
    def validate_device_compatibility(self, device_info: AudioDeviceInfo) -> Dict[str, Any]:
        """Validate device compatibility for full-duplex operation."""
        validation_result = {
            'compatible': True,
            'warnings': [],
            'errors': [],
            'recommended_settings': None
        }
        
        try:
            # Test if device supports required sample rates
            required_rates = [16000]  # Minimum for speech processing
            supported_required = [rate for rate in required_rates if rate in device_info.sample_rates]
            
            if not supported_required:
                validation_result['compatible'] = False
                validation_result['errors'].append(
                    f"Device does not support required sample rates: {required_rates}")
            
            # Check channel configuration
            if device_info.is_input and device_info.channels < 1:
                validation_result['compatible'] = False
                validation_result['errors'].append("Input device must support at least 1 channel")
            
            # Generate recommended settings if compatible
            if validation_result['compatible']:
                validation_result['recommended_settings'] = self.configure_for_device(device_info)
            
            logger.debug(f"Device validation for {device_info.name}: {validation_result}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Device validation failed: {e}")
            validation_result['compatible'] = False
            validation_result['errors'].append(f"Validation error: {str(e)}")
            return validation_result