"""
Full-Duplex Conversational Engine

This module provides real-time, bidirectional voice conversation capabilities
for the AI VTuber system, enabling natural interruption and streaming speech recognition.
"""

from .streaming_ears import StreamingEars
from .duplex_manager import DuplexManager
from .text_processor import TextProcessor
from .audio_device_manager import AudioDeviceManager
from .configuration_manager import ConfigurationManager
from .logging_config import setup_audio_logging, get_component_logger

# Initialize logging when module is imported
setup_audio_logging()

__version__ = "1.0.0"
__all__ = [
    "StreamingEars",
    "DuplexManager", 
    "TextProcessor",
    "AudioDeviceManager",
    "ConfigurationManager",
    "setup_audio_logging",
    "get_component_logger"
]