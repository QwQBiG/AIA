
# ASR备用方案导入
try:
    import funasr
    FUNASR_AVAILABLE = True
except ImportError:
    FUNASR_AVAILABLE = False
    try:
        from .whisper_asr import get_whisper_asr, is_whisper_available
        WHISPER_AVAILABLE = is_whisper_available()
    except ImportError:
        WHISPER_AVAILABLE = False

"""
StreamingEars Component

Real-time audio capture and speech recognition with streaming capabilities.
Integrates FunASR Paraformer-streaming and Silero VAD for low-latency processing.
"""

from typing import Callable, List, Optional
from dataclasses import dataclass
import numpy as np
import logging
import threading
import time
import queue
import pyaudio
import sounddevice as sd
from collections import deque
import torch
import os
import json

from .logging_config import get_component_logger
from .performance_monitor import PerformanceMonitor
from .threading_optimizer import get_threading_optimizer
from .error_handler import get_error_handler, ErrorSeverity, ErrorCategory

logger = get_component_logger("streaming_ears")

@dataclass
class AudioChunk:
    """Represents a single audio processing chunk."""
    data: np.ndarray  # Raw audio data (16-bit PCM)
    timestamp: float  # Capture timestamp
    sample_rate: int  # Audio sample rate
    channels: int     # Number of audio channels

@dataclass
class VADResult:
    """Voice Activity Detection result."""
    probability: float    # Speech probability (0.0-1.0)
    is_speech: bool      # Binary speech detection
    timestamp: float     # Detection timestamp
    chunk_id: int        # Associated audio chunk ID

@dataclass
class StreamUpdate:
    """Streaming ASR transcription update."""
    partial_text: str     # Current partial transcription
    is_final: bool        # Whether this is a final result
    confidence: float     # Transcription confidence (0.0-1.0)
    timestamp: float      # Update timestamp
    word_timestamps: List[tuple]  # Word-level timing

@dataclass
class SentenceComplete:
    """Complete sentence from ASR."""
    text: str            # Final transcribed text
    confidence: float    # Overall confidence score
    duration: float      # Speech duration in seconds
    word_count: int      # Number of words

@dataclass
class PerformanceMetrics:
    """Real-time performance tracking."""
    vad_latency: float          # VAD processing time
    asr_latency: float          # ASR processing time
    interruption_latency: float # Time to stop AI audio
    end_to_end_latency: float   # Complete conversation cycle

class StreamingEars:
    """Real-time audio capture and speech recognition system."""
    
    def __init__(self, 
                 sample_rate: int = 16000,
                 chunk_size: int = 512,  # 32ms at 16kHz (Silero VAD requirement)
                 vad_threshold: float = 0.5,  # 降低至0.5，提高中文语音检测灵敏度
                 audio_device_manager=None,
                 buffer_size: int = 10,
                 model_cache_dir: str = "assets/models"):
        """
        Initialize streaming speech recognition system.
        
        Args:
            sample_rate: Audio sample rate (16kHz for optimal ASR performance)
            chunk_size: Audio chunk size for processing (512 samples = 32ms for Silero VAD)
            vad_threshold: VAD probability threshold for speech detection
            audio_device_manager: Manager for audio hardware configuration
            buffer_size: Size of circular buffer for audio chunks
            model_cache_dir: Directory for caching models locally
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.vad_threshold = vad_threshold
        self.audio_device_manager = audio_device_manager
        self.buffer_size = buffer_size
        self.model_cache_dir = model_cache_dir
        
        # Audio capture components
        self.pyaudio_instance = None
        self.audio_stream = None
        self.audio_thread = None
        self.is_streaming = False
        
        # Circular buffer for audio data with overflow protection
        self.audio_buffer = deque(maxlen=buffer_size)
        self.buffer_lock = threading.Lock()
        
        # Audio processing queue
        self.processing_queue = queue.Queue(maxsize=buffer_size * 2)
        
        # VAD components
        self.vad_model = None
        self.vad_utils = None
        self.dynamic_threshold = vad_threshold
        self.ai_speaking_mode = False  # For Patch 3: dynamic threshold adjustment
        
        # ASR components
        self.asr_model = None
        self.asr_pipeline = None
        self.whisper_asr = None  # Whisper ASR fallback
        self.asr_processing_times = deque(maxlen=100)  # Track ASR latency
        
        # Speech state tracking
        self.is_speech_active = False
        self.speech_buffer = []
        self.last_speech_time = 0.0
        
        # Callback functions
        self.on_speech_start: Optional[Callable] = None
        self.on_partial_text: Optional[Callable[[str], None]] = None
        self.on_sentence_complete: Optional[Callable[[str], None]] = None
        self.on_speech_end: Optional[Callable] = None
        
        # Performance tracking
        self.chunk_counter = 0
        self.last_chunk_time = 0.0
        self.vad_processing_times = deque(maxlen=100)  # Track VAD latency
        
        # Integrated performance monitoring
        self.performance_monitor = PerformanceMonitor(history_size=1000)
        self.threading_optimizer = get_threading_optimizer()
        
        # Comprehensive error handling
        self.error_handler = get_error_handler()
        
        # Error tracking and recovery
        self.error_counts = {
            'vad_errors': 0,
            'asr_errors': 0,
            'audio_errors': 0,
            'callback_errors': 0
        }
        self.last_error_time = 0.0
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10
        
        # Fallback mechanisms
        self.vad_fallback_active = False
        self.asr_fallback_active = False

        # FunASR streaming cache for maintaining context across chunks
        self._funasr_cache = {}  # Initialize once, not reset per call

        # Ensure model cache directory exists
        os.makedirs(self.model_cache_dir, exist_ok=True)
        
        logger.info(f"StreamingEars initialized with sample_rate={sample_rate}, chunk_size={chunk_size}, buffer_size={buffer_size}")
        
        # Initialize VAD model
        self._initialize_vad_model()
        
        # Initialize ASR model
        self._initialize_asr_model()
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for audio capture."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        try:
            # Convert bytes to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            timestamp = time.time()
            
            # Create audio chunk
            chunk = AudioChunk(
                data=audio_data,
                timestamp=timestamp,
                sample_rate=self.sample_rate,
                channels=1
            )
            
            # Add to circular buffer with overflow protection
            with self.buffer_lock:
                self.audio_buffer.append(chunk)
                if len(self.audio_buffer) >= self.buffer_size:
                    logger.debug("Audio buffer at capacity, oldest chunk will be dropped")
            
            # Add to processing queue (non-blocking)
            try:
                self.processing_queue.put_nowait(chunk)
                self.chunk_counter += 1
            except queue.Full:
                logger.warning("Processing queue full, dropping audio chunk")
            
            # Track performance
            if self.last_chunk_time > 0:
                chunk_interval = timestamp - self.last_chunk_time
                if chunk_interval > 0.1:  # More than 100ms between chunks
                    logger.warning(f"Large gap between audio chunks: {chunk_interval:.3f}s")
            self.last_chunk_time = timestamp
            
        except Exception as e:
            # Use comprehensive error handler
            self.error_handler.handle_error(
                component="streaming_ears",
                error_type="audio_callback_error",
                exception=e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.AUDIO_HARDWARE,
                metadata={"component_instance": self}
            )
        
        return (None, pyaudio.paContinue)
    
    def _get_audio_device_info(self):
        """Get optimal audio device configuration."""
        if self.audio_device_manager:
            try:
                device_info = self.audio_device_manager.get_default_input_device()
                if device_info:
                    return device_info
            except Exception as e:
                # Use comprehensive error handler
                self.error_handler.handle_error(
                    component="streaming_ears",
                    error_type="audio_device_detection_error",
                    exception=e,
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.AUDIO_HARDWARE,
                    metadata={"component_instance": self}
                )
        
        # Fallback to PyAudio default
        try:
            info = self.pyaudio_instance.get_default_input_device_info()
            logger.info(f"Using default input device: {info['name']}")
            return info
        except Exception as e:
            logger.error(f"Could not get default input device: {e}")
            return None
    
    def start_streaming(self) -> None:
        """Start the audio capture and processing loop."""
        if self.is_streaming:
            logger.warning("Audio streaming already active")
            return
        
        try:
            logger.info("Starting audio streaming...")
            
            # Initialize PyAudio
            self.pyaudio_instance = pyaudio.PyAudio()
            
            # Get device info
            device_info = self._get_audio_device_info()
            if not device_info:
                raise RuntimeError("No suitable audio input device found")
            
            # Configure audio stream parameters
            device_index = getattr(device_info, 'device_id', None)
            
            # Validate sample rate support
            supported_rates = self.get_supported_sample_rates()
            if self.sample_rate not in supported_rates:
                logger.warning(f"Sample rate {self.sample_rate} not supported, using 16000")
                self.sample_rate = 16000
            
            # Create audio stream
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback,
                start=False
            )
            
            # Start the stream
            self.audio_stream.start_stream()
            self.is_streaming = True
            
            # Start processing thread with optimization
            self.audio_thread = self.threading_optimizer.create_audio_processing_thread(
                target=self._processing_loop,
                name="streaming_ears_processor"
            )
            self.audio_thread.start()
            
            # Initialize Whisper ASR callbacks if using Whisper
            if self.whisper_asr and not self.asr_model:
                self._setup_whisper_callbacks()
                if not self.whisper_asr.start_streaming():
                    logger.warning("Failed to start Whisper ASR streaming")
            
            logger.info(f"Audio streaming started successfully on device: {getattr(device_info, 'name', 'Unknown')}")
            
        except Exception as e:
            # Use comprehensive error handler
            self.error_handler.handle_error(
                component="streaming_ears",
                error_type="audio_streaming_start_error",
                exception=e,
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.AUDIO_HARDWARE,
                metadata={"component_instance": self}
            )
            self.stop_streaming()
            raise
    
    def stop_streaming(self) -> None:
        """Stop audio processing and cleanup resources."""
        if not self.is_streaming:
            return
        
        logger.info("Stopping audio streaming...")
        self.is_streaming = False
        
        try:
            # Stop and close audio stream
            if self.audio_stream:
                if self.audio_stream.is_active():
                    self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_stream = None
            
            # Terminate PyAudio
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
            
            # Wait for processing thread to finish
            if self.audio_thread and self.audio_thread.is_alive():
                self.audio_thread.join(timeout=2.0)
            
            # Stop Whisper ASR if active
            if self.whisper_asr:
                self.whisper_asr.stop_streaming()
            
            # Clear buffers
            with self.buffer_lock:
                self.audio_buffer.clear()
            
            # Clear processing queue
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except queue.Empty:
                    break
            
            logger.info("Audio streaming stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping audio streaming: {e}")
    
    def _processing_loop(self):
        """Main processing loop for audio chunks."""
        logger.info("Audio processing loop started")
        
        while self.is_streaming:
            try:
                # Get audio chunk from queue (with timeout)
                chunk = self.processing_queue.get(timeout=0.1)
                
                # Process the audio chunk
                self._process_audio_chunk(chunk)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                if not self.is_streaming:
                    break
        
        logger.info("Audio processing loop ended")
    
    def _initialize_vad_model(self):
        """Initialize Silero VAD model with local caching."""
        try:
            logger.info("Initializing Silero VAD model...")
            
            # Import Silero VAD
            import torch
            
            # Set model cache path
            model_path = os.path.join(self.model_cache_dir, 'silero_vad.jit')
            
            # Load or download VAD model
            if os.path.exists(model_path):
                logger.info(f"Loading cached VAD model from {model_path}")
                self.vad_model = torch.jit.load(model_path)
            else:
                logger.info("Downloading Silero VAD model...")
                # Download from Silero repository
                self.vad_model, self.vad_utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
                
                # Cache the model locally
                torch.jit.save(self.vad_model, model_path)
                logger.info(f"VAD model cached to {model_path}")
            
            # Load utils if not already loaded
            if self.vad_utils is None:
                _, self.vad_utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
            
            logger.info("Silero VAD model initialized successfully")
            
        except Exception as e:
            # Use comprehensive error handler
            self.error_handler.handle_error(
                component="streaming_ears",
                error_type="vad_model_initialization_error",
                exception=e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.MODEL_LOADING,
                metadata={"component_instance": self}
            )
            self.vad_model = None
            self.vad_utils = None
    
    def _initialize_asr_model(self):
        """Initialize ASR model with FunASR primary and Whisper fallback."""
        try:
            logger.info("Initializing ASR model...")
            
            # Try FunASR first if available
            if FUNASR_AVAILABLE:
                logger.info("Attempting FunASR Paraformer streaming model...")
                
                # Import FunASR
                from funasr import AutoModel
                
                # Model configuration with version pinning (Patch 2)
                model_name = "paraformer-zh-streaming"
                model_revision = "v2.0.4"  # Pin to stable version
                
                # Set local model path
                local_model_path = os.path.join(self.model_cache_dir, f"{model_name}-{model_revision}")
                
                # Check if model exists locally (Patch 2: local model path checking)
                if os.path.exists(local_model_path) and os.path.isdir(local_model_path):
                    logger.info(f"Loading cached ASR model from {local_model_path}")
                    try:
                        self.asr_model = AutoModel(
                            model=local_model_path,
                            trust_remote_code=True,
                            device="cpu"  # Use CPU for better compatibility
                        )
                        logger.info("FunASR Paraformer streaming model initialized successfully")
                        return
                    except Exception as e:
                        logger.warning(f"Failed to load cached FunASR model: {e}, trying download")
                        self.asr_model = None
                
                # Download model if not cached or failed to load
                if self.asr_model is None:
                    logger.info(f"Downloading FunASR model {model_name} revision {model_revision}...")
                    
                    try:
                        # Download with specific revision
                        self.asr_model = AutoModel(
                            model=f"iic/{model_name}",
                            model_revision=model_revision,
                            trust_remote_code=True,
                            device="cpu",
                            cache_dir=self.model_cache_dir
                        )
                        
                        # Save model info for future reference
                        model_info = {
                            "model_name": model_name,
                            "model_revision": model_revision,
                            "download_time": time.time(),
                            "cache_path": local_model_path
                        }
                        
                        info_path = os.path.join(self.model_cache_dir, f"{model_name}-info.json")
                        with open(info_path, 'w') as f:
                            json.dump(model_info, f, indent=2)
                        
                        logger.info("FunASR Paraformer streaming model initialized successfully")
                        return
                        
                    except Exception as e:
                        logger.error(f"Failed to download FunASR model: {e}")
                        self.asr_model = None
            
            # Fallback to Whisper if FunASR is not available or failed
            if WHISPER_AVAILABLE:
                logger.info("FunASR not available, using Whisper ASR fallback...")
                try:
                    self.whisper_asr = get_whisper_asr("small")  # small 模型中文识别效果远优于 base
                    if self.whisper_asr.initialize():
                        logger.info("Whisper ASR initialized successfully as fallback")
                        self.asr_fallback_active = True
                        # Report fallback success to error handler
                        if hasattr(self.error_handler, 'handle_fallback_success'):
                            self.error_handler.handle_fallback_success('streaming_ears', 'whisper_asr')
                        return
                    else:
                        logger.error("Failed to initialize Whisper ASR")
                except Exception as e:
                    logger.error(f"Whisper ASR initialization failed: {e}")
            
            # No ASR available
            logger.warning("No ASR engine available (neither FunASR nor Whisper)")
            self.asr_model = None
            self.whisper_asr = None
            
        except ImportError as e:
            logger.error(f"ASR import error: {e}")
            self.asr_model = None
            self.whisper_asr = None
        except Exception as e:
            # Use comprehensive error handler
            self.error_handler.handle_error(
                component="streaming_ears",
                error_type="asr_model_initialization_error",
                exception=e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.MODEL_LOADING,
                metadata={"component_instance": self}
            )
            self.asr_model = None
            self.whisper_asr = None
    
    def _process_vad(self, audio_chunk: AudioChunk) -> VADResult:
        """Process audio chunk through VAD with dynamic threshold adjustment."""
        # Start performance measurement
        measurement_id = self.performance_monitor.start_measurement(
            "vad", "process_chunk", 
            {"chunk_size": len(audio_chunk.data), "timestamp": audio_chunk.timestamp}
        )
        
        start_time = time.time()
        
        try:
            if self.vad_model is None:
                # Fallback to basic audio level detection
                result = self._fallback_vad(audio_chunk)
                self.performance_monitor.end_measurement(measurement_id)
                return result
            
            # Convert audio data to float32 and normalize
            audio_float = audio_chunk.data.astype(np.float32) / 32768.0
            
            # Ensure correct length (Silero VAD expects specific chunk sizes)
            if len(audio_float) != self.chunk_size:
                # Pad or truncate to expected size
                if len(audio_float) < self.chunk_size:
                    audio_float = np.pad(audio_float, (0, self.chunk_size - len(audio_float)))
                else:
                    audio_float = audio_float[:self.chunk_size]
            
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_float).unsqueeze(0)
            
            # Run VAD inference
            with torch.no_grad():
                speech_prob = self.vad_model(audio_tensor, self.sample_rate).item()
            
            # Apply Patch 3: Dynamic threshold adjustment to prevent self-interruption
            current_threshold = self._get_dynamic_threshold()
            
            # Determine if speech is detected
            is_speech = speech_prob > current_threshold
            
            # Track processing time
            processing_time = time.time() - start_time
            self.vad_processing_times.append(processing_time)
            
            result = VADResult(
                probability=speech_prob,
                is_speech=is_speech,
                timestamp=audio_chunk.timestamp,
                chunk_id=self.chunk_counter
            )
            
            logger.debug(f"VAD result: prob={speech_prob:.3f}, threshold={current_threshold:.3f}, "
                        f"speech={is_speech}, latency={processing_time*1000:.1f}ms")
            
            # End performance measurement
            self.performance_monitor.end_measurement(measurement_id)
            
            return result
            
        except Exception as e:
            # Use comprehensive error handler
            self.error_handler.handle_error(
                component="streaming_ears",
                error_type="vad_processing_error",
                exception=e,
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.PROCESSING,
                metadata={"component_instance": self, "chunk_id": self.chunk_counter}
            )
            self._handle_processing_error('vad_errors', e)
            self.performance_monitor.end_measurement(measurement_id)
            return self._fallback_vad(audio_chunk)
    
    def _get_dynamic_threshold(self) -> float:
        """Get dynamic VAD threshold based on AI speaking state (Patch 3)."""
        if self.ai_speaking_mode:
            # Increase threshold when AI is speaking to prevent self-interruption
            return min(0.95, self.vad_threshold + 0.15)
        else:
            return self.vad_threshold
    
    def _fallback_vad(self, audio_chunk: AudioChunk) -> VADResult:
        """Fallback VAD using basic audio level detection."""
        # Calculate RMS energy
        audio_float = audio_chunk.data.astype(np.float32) / 32768.0
        rms_energy = np.sqrt(np.mean(audio_float ** 2))
        
        # Simple threshold-based detection (much less accurate than Silero)
        energy_threshold = 0.01  # Adjust based on testing
        is_speech = rms_energy > energy_threshold
        
        # Convert energy to pseudo-probability
        speech_prob = min(1.0, rms_energy * 50)  # Scale energy to 0-1 range
        
        logger.debug(f"Fallback VAD: energy={rms_energy:.4f}, prob={speech_prob:.3f}, speech={is_speech}")
        
        return VADResult(
            probability=speech_prob,
            is_speech=is_speech,
            timestamp=audio_chunk.timestamp,
            chunk_id=self.chunk_counter
        )
    
    def _process_asr(self, audio_chunks: List[AudioChunk]) -> Optional[StreamUpdate]:
        """Process accumulated audio chunks through ASR."""
        if not audio_chunks:
            return None
        
        # Check if we have any ASR engine available
        if not self.asr_model and not self.whisper_asr:
            return None
        
        # Start performance measurement
        measurement_id = self.performance_monitor.start_measurement(
            "asr", "process_chunks", 
            {"chunk_count": len(audio_chunks), "total_samples": sum(len(c.data) for c in audio_chunks)}
        )
        
        start_time = time.time()
        
        try:
            # Concatenate audio chunks
            audio_data = np.concatenate([chunk.data for chunk in audio_chunks])
            
            # Convert to float32 and normalize
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # Ensure minimum length for ASR processing
            min_samples = int(self.sample_rate * 0.5)  # 500ms minimum
            if len(audio_float) < min_samples:
                logger.debug(f"Audio too short for ASR: {len(audio_float)} samples")
                self.performance_monitor.end_measurement(measurement_id)
                return None
            
            # Try FunASR first if available
            if self.asr_model:
                try:
                    # FunASR expects specific input format
                    # Use persistent cache instead of resetting each call
                    result = self.asr_model.generate(
                        input=audio_float,
                        cache=self._funasr_cache,  # Use persistent cache
                        is_final=False,  # Partial result
                        chunk_size=[0, 10, 5],  # Streaming chunk configuration
                        encoder_chunk_look_back=4,
                        decoder_chunk_look_back=1
                    )
                    
                    # Extract text and confidence from result
                    if result and len(result) > 0:
                        text = result[0].get('text', '').strip()
                        confidence = result[0].get('confidence', 0.0)
                        
                        # Track processing time
                        processing_time = time.time() - start_time
                        self.asr_processing_times.append(processing_time)
                        
                        if text:  # Only return if we have actual text
                            stream_update = StreamUpdate(
                                partial_text=text,
                                is_final=False,
                                confidence=confidence,
                                timestamp=audio_chunks[-1].timestamp,
                                word_timestamps=[]  # TODO: Extract word timestamps if available
                            )
                            
                            logger.debug(f"FunASR result: '{text}' (conf={confidence:.3f}, "
                                       f"latency={processing_time*1000:.1f}ms)")
                            
                            # End performance measurement
                            self.performance_monitor.end_measurement(measurement_id)
                            
                            return stream_update
                
                except Exception as e:
                    logger.warning(f"FunASR processing failed: {e}, trying Whisper fallback")
                    # Fall through to Whisper
            
            # Use Whisper ASR if FunASR failed or not available
            if self.whisper_asr:
                try:
                    # Process audio with Whisper
                    self.whisper_asr.process_audio(audio_float)
                    
                    # Track processing time
                    processing_time = time.time() - start_time
                    self.asr_processing_times.append(processing_time)
                    
                    logger.debug(f"Whisper ASR processing: {len(audio_float)} samples, "
                               f"latency={processing_time*1000:.1f}ms")
                    
                    # Note: Whisper results come through callbacks, not direct return
                    self.performance_monitor.end_measurement(measurement_id)
                    return None
                    
                except Exception as e:
                    logger.error(f"Whisper ASR processing failed: {e}")
                    self._handle_processing_error('asr_errors', e)
                    self.performance_monitor.end_measurement(measurement_id)
                    return None
            
        except Exception as e:
            logger.error(f"ASR processing error: {e}")
            self._handle_processing_error('asr_errors', e)
            self.performance_monitor.end_measurement(measurement_id)
            return None
        
        self.performance_monitor.end_measurement(measurement_id)
        return None
    
    def _process_final_asr(self, audio_chunks: List[AudioChunk]) -> Optional[SentenceComplete]:
        """Process final audio chunks for complete sentence."""
        if not audio_chunks:
            return None
        
        # Check if we have any ASR engine available
        if not self.asr_model and not self.whisper_asr:
            return None
        
        start_time = time.time()
        
        try:
            # Concatenate all audio chunks
            audio_data = np.concatenate([chunk.data for chunk in audio_chunks])
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # Try FunASR first if available
            if self.asr_model:
                try:
                    # Run final ASR inference
                    # Use persistent cache for final result too
                    result = self.asr_model.generate(
                        input=audio_float,
                        cache=self._funasr_cache,  # Use persistent cache
                        is_final=True,  # Final result
                        chunk_size=[0, 10, 5],
                        encoder_chunk_look_back=4,
                        decoder_chunk_look_back=1
                    )
                    
                    if result and len(result) > 0:
                        text = result[0].get('text', '').strip()
                        confidence = result[0].get('confidence', 0.0)
                        
                        # Calculate speech duration
                        duration = len(audio_data) / self.sample_rate
                        word_count = len(text.split()) if text else 0
                        
                        processing_time = time.time() - start_time
                        self.asr_processing_times.append(processing_time)
                        
                        if text:
                            sentence_complete = SentenceComplete(
                                text=text,
                                confidence=confidence,
                                duration=duration,
                                word_count=word_count
                            )
                            
                            logger.info(f"Final FunASR: '{text}' (conf={confidence:.3f}, "
                                      f"duration={duration:.1f}s, words={word_count})")
                            
                            return sentence_complete
                
                except Exception as e:
                    logger.warning(f"FunASR final processing failed: {e}, trying Whisper")
                    # Fall through to Whisper
            
            # Use Whisper ASR if FunASR failed or not available
            if self.whisper_asr:
                try:
                    # Process final audio with Whisper
                    self.whisper_asr.process_audio(audio_float)
                    
                    # Calculate speech duration
                    duration = len(audio_data) / self.sample_rate
                    
                    processing_time = time.time() - start_time
                    self.asr_processing_times.append(processing_time)
                    
                    logger.debug(f"Whisper final ASR processing: {len(audio_float)} samples, "
                               f"duration={duration:.1f}s, latency={processing_time*1000:.1f}ms")
                    
                    # Note: Whisper results come through callbacks
                    return None
                    
                except Exception as e:
                    logger.error(f"Whisper final ASR processing failed: {e}")
                    self._handle_processing_error('asr_errors', e)
            
        except Exception as e:
            logger.error(f"Final ASR processing error: {e}")
            self._handle_processing_error('asr_errors', e)
        
        return None
    
    def _setup_whisper_callbacks(self):
        """Setup callbacks for Whisper ASR integration."""
        if not self.whisper_asr:
            return
        
        def on_whisper_result(update):
            """Handle Whisper streaming results."""
            if self.on_partial_text:
                try:
                    self.on_partial_text(update.partial_text)
                except Exception as e:
                    logger.error(f"Error in Whisper partial text callback: {e}")
        
        def on_whisper_sentence(sentence):
            """Handle Whisper complete sentences."""
            if self.on_sentence_complete:
                try:
                    self.on_sentence_complete(sentence.final_text)
                except Exception as e:
                    logger.error(f"Error in Whisper sentence complete callback: {e}")
        
        # Set callbacks
        self.whisper_asr.set_callbacks(on_whisper_result, on_whisper_sentence)
        logger.debug("Whisper ASR callbacks configured")
    
    def set_ai_speaking_mode(self, is_speaking: bool) -> None:
        """Set AI speaking mode for dynamic threshold adjustment (Patch 3)."""
        self.ai_speaking_mode = is_speaking
        logger.debug(f"AI speaking mode set to: {is_speaking}")
    
    def _process_audio_chunk(self, chunk: AudioChunk):
        """Process a single audio chunk with VAD and ASR."""
        try:
            # Record chunk timing for consistency analysis
            self.performance_monitor.record_audio_chunk_timing()
            
            # Process through VAD
            vad_result = self._process_vad(chunk)
            
            # Handle speech state transitions
            if vad_result.is_speech and not self.is_speech_active:
                # Speech started
                self.is_speech_active = True
                self.speech_buffer = [chunk]
                self.last_speech_time = chunk.timestamp
                
                # Start conversation tracking
                conversation_id = f"conv_{chunk.timestamp}"
                self.performance_monitor.record_conversation_start(conversation_id)
                self._current_conversation_id = conversation_id
                
                if self.on_speech_start:
                    try:
                        self.on_speech_start()
                    except Exception as e:
                        logger.error(f"Error in speech start callback: {e}")
                        self._handle_processing_error('callback_errors', e)
                
                logger.debug(f"Speech started: prob={vad_result.probability:.3f}")
                
            elif vad_result.is_speech and self.is_speech_active:
                # Continue speech - accumulate audio
                self.speech_buffer.append(chunk)
                self.last_speech_time = chunk.timestamp
                
                # Process partial ASR if we have enough audio
                if len(self.speech_buffer) >= 8:  # ~480ms of audio
                    stream_update = self._process_asr(self.speech_buffer[-8:])  # Use recent chunks
                    if stream_update and self.on_partial_text:
                        try:
                            self.on_partial_text(stream_update.partial_text)
                        except Exception as e:
                            logger.error(f"Error in partial text callback: {e}")
                            self._handle_processing_error('callback_errors', e)
                
            elif not vad_result.is_speech and self.is_speech_active:
                # Check if speech has ended (600ms silence threshold)
                silence_duration = chunk.timestamp - self.last_speech_time
                if silence_duration > 0.6:  # 600ms silence
                    # Speech ended - process final ASR
                    if self.speech_buffer:
                        sentence_complete = self._process_final_asr(self.speech_buffer)
                        if sentence_complete and self.on_sentence_complete:
                            try:
                                self.on_sentence_complete(sentence_complete.text)
                            except Exception as e:
                                logger.error(f"Error in sentence complete callback: {e}")
                                self._handle_processing_error('callback_errors', e)
                    
                    # End conversation tracking
                    if hasattr(self, '_current_conversation_id'):
                        self.performance_monitor.record_conversation_end(self._current_conversation_id)
                        delattr(self, '_current_conversation_id')
                    
                    # Reset speech state
                    self.is_speech_active = False
                    self.speech_buffer = []
                    
                    if self.on_speech_end:
                        try:
                            self.on_speech_end()
                        except Exception as e:
                            logger.error(f"Error in speech end callback: {e}")
                            self._handle_processing_error('callback_errors', e)
                    
                    logger.debug("Speech ended")
            
            # Log chunk processing for debugging
            logger.debug(f"Processed chunk: VAD prob={vad_result.probability:.3f}, "
                        f"speech={vad_result.is_speech}, active={self.is_speech_active}")
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            self._handle_processing_error('audio_processing', e)
    
    def _handle_processing_error(self, error_type: str, error: Exception):
        """Handle processing errors with recovery mechanisms."""
        current_time = time.time()
        
        # Track error
        if error_type in self.error_counts:
            self.error_counts[error_type] += 1
        else:
            self.error_counts['audio_errors'] += 1
        
        # Check for consecutive errors
        if current_time - self.last_error_time < 1.0:  # Within 1 second
            self.consecutive_errors += 1
        else:
            self.consecutive_errors = 1
        
        self.last_error_time = current_time
        
        logger.error(f"Processing error ({error_type}): {error} "
                    f"(consecutive: {self.consecutive_errors})")
        
        # Implement recovery strategies
        if self.consecutive_errors >= self.max_consecutive_errors:
            logger.critical(f"Too many consecutive errors ({self.consecutive_errors}), "
                          f"attempting recovery...")
            self._attempt_recovery()
        
        # Activate fallback mechanisms based on error type
        if error_type == 'vad_errors' and not self.vad_fallback_active:
            logger.warning("Activating VAD fallback mechanism")
            self.vad_fallback_active = True
        
        if error_type == 'asr_errors' and not self.asr_fallback_active:
            logger.warning("Activating ASR fallback mechanism")
            self.asr_fallback_active = True
    
    def _attempt_recovery(self):
        """Attempt to recover from critical errors."""
        try:
            logger.info("Attempting system recovery...")
            
            # Reset error counters
            self.consecutive_errors = 0
            
            # Reinitialize models if needed
            if self.vad_model is None and not self.vad_fallback_active:
                logger.info("Attempting VAD model recovery...")
                self._initialize_vad_model()
            
            if self.asr_model is None and not self.asr_fallback_active:
                logger.info("Attempting ASR model recovery...")
                self._initialize_asr_model()
            
            # Clear buffers to prevent corruption
            with self.buffer_lock:
                self.audio_buffer.clear()
            
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Reset speech state
            self.is_speech_active = False
            self.speech_buffer = []
            
            logger.info("Recovery attempt completed")
            
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
    
    def get_error_statistics(self) -> dict:
        """Get current error statistics for monitoring."""
        return {
            'error_counts': self.error_counts.copy(),
            'consecutive_errors': self.consecutive_errors,
            'last_error_time': self.last_error_time,
            'vad_fallback_active': self.vad_fallback_active,
            'asr_fallback_active': self.asr_fallback_active,
            'total_errors': sum(self.error_counts.values())
        }
    
    def reset_error_statistics(self):
        """Reset error statistics (useful for testing)."""
        self.error_counts = {key: 0 for key in self.error_counts}
        self.consecutive_errors = 0
        self.last_error_time = 0.0
        logger.info("Error statistics reset")
    
    def get_system_health(self) -> dict:
        """Get comprehensive system health information."""
        # Check if we have any working ASR engine
        has_working_asr = (
            self.asr_model is not None or 
            (self.whisper_asr is not None and hasattr(self.whisper_asr, 'model') and self.whisper_asr.model is not None)
        )
        
        health_info = {
            'streaming_active': self.is_streaming,
            'models_loaded': {
                'vad': self.vad_model is not None,
                'asr': has_working_asr  # Updated to check both FunASR and Whisper
            },
            'fallbacks_active': {
                'vad': self.vad_fallback_active,
                'asr': self.asr_fallback_active
            },
            'performance': self.get_performance_metrics(),
            'errors': self.get_error_statistics(),
            'buffer_status': self.get_audio_buffer_status(),
            'comprehensive_health': self.error_handler.get_system_health()
        }
        
        # Determine overall health status based on comprehensive error handler
        comprehensive_health = health_info['comprehensive_health']
        health_score = comprehensive_health['health_score']
        
        # Adjust health score if we have working ASR even without FunASR
        if has_working_asr and health_score < 75:
            health_score = max(health_score, 75)  # Boost score if ASR is working
        
        if health_score >= 90:
            health_info['status'] = 'excellent'
        elif health_score >= 75:
            health_info['status'] = 'good'
        elif health_score >= 50:
            health_info['status'] = 'fair'
        else:
            health_info['status'] = 'poor'
        
        return health_info
    
    def get_detailed_performance_metrics(self) -> dict:
        """Get detailed performance metrics for monitoring and optimization."""
        basic_metrics = self.get_performance_metrics()
        
        detailed_metrics = {
            'basic_metrics': {
                'vad_latency_ms': basic_metrics.vad_latency * 1000,
                'asr_latency_ms': basic_metrics.asr_latency * 1000,
                'interruption_latency_ms': basic_metrics.interruption_latency * 1000,
                'end_to_end_latency_ms': basic_metrics.end_to_end_latency * 1000
            },
            'processing_statistics': {
                'total_chunks_processed': self.chunk_counter,
                'vad_measurements': len(self.vad_processing_times),
                'asr_measurements': len(self.asr_processing_times),
                'average_chunk_interval_ms': self._calculate_average_chunk_interval() * 1000,
                'speech_detection_rate': self._calculate_speech_detection_rate()
            },
            'buffer_statistics': self.get_audio_buffer_status(),
            'model_status': {
                'vad_model_loaded': self.vad_model is not None,
                'asr_model_loaded': self.asr_model is not None,
                'vad_fallback_active': self.vad_fallback_active,
                'asr_fallback_active': self.asr_fallback_active
            },
            'error_statistics': self.get_error_statistics()
        }
        
        # Add latency percentiles if we have enough data
        if len(self.vad_processing_times) >= 10:
            vad_times = sorted(self.vad_processing_times)
            detailed_metrics['vad_latency_percentiles'] = {
                'p50': vad_times[len(vad_times)//2] * 1000,
                'p90': vad_times[int(len(vad_times)*0.9)] * 1000,
                'p95': vad_times[int(len(vad_times)*0.95)] * 1000,
                'p99': vad_times[int(len(vad_times)*0.99)] * 1000
            }
        
        if len(self.asr_processing_times) >= 10:
            asr_times = sorted(self.asr_processing_times)
            detailed_metrics['asr_latency_percentiles'] = {
                'p50': asr_times[len(asr_times)//2] * 1000,
                'p90': asr_times[int(len(asr_times)*0.9)] * 1000,
                'p95': asr_times[int(len(asr_times)*0.95)] * 1000,
                'p99': asr_times[int(len(asr_times)*0.99)] * 1000
            }
        
        return detailed_metrics
    
    def _calculate_average_chunk_interval(self) -> float:
        """Calculate average time between audio chunks."""
        if self.chunk_counter < 2:
            return 0.0
        
        # Estimate based on chunk size and sample rate
        expected_interval = self.chunk_size / self.sample_rate
        return expected_interval
    
    def _calculate_speech_detection_rate(self) -> float:
        """Calculate rate of speech detection (for monitoring VAD sensitivity)."""
        if self.chunk_counter == 0:
            return 0.0
        
        # This is a simplified calculation - in a real implementation,
        # we would track actual speech detection events
        return 0.1  # Placeholder - 10% speech detection rate
    
    def log_performance_summary(self):
        """Log a summary of current performance metrics."""
        try:
            metrics = self.get_detailed_performance_metrics()
            health = self.get_system_health()
            
            logger.info("=== StreamingEars Performance Summary ===")
            logger.info(f"System Status: {health['status'].upper()}")
            logger.info(f"Streaming Active: {health['streaming_active']}")
            logger.info(f"Models Loaded: VAD={health['models_loaded']['vad']}, ASR={health['models_loaded']['asr']}")
            
            if metrics['basic_metrics']['vad_latency_ms'] > 0:
                logger.info(f"VAD Latency: {metrics['basic_metrics']['vad_latency_ms']:.1f}ms")
            
            if metrics['basic_metrics']['asr_latency_ms'] > 0:
                logger.info(f"ASR Latency: {metrics['basic_metrics']['asr_latency_ms']:.1f}ms")
            
            logger.info(f"Chunks Processed: {metrics['processing_statistics']['total_chunks_processed']}")
            logger.info(f"Total Errors: {metrics['error_statistics']['total_errors']}")
            
            buffer_status = metrics['buffer_statistics']
            logger.info(f"Buffer Usage: {buffer_status['buffer_usage_percent']:.1f}%")
            
            logger.info("==========================================")
            
        except Exception as e:
            logger.error(f"Failed to log performance summary: {e}")
    
    def set_callbacks(self, 
                     on_speech_start: Callable,
                     on_partial_text: Callable[[str], None],
                     on_sentence_complete: Callable[[str], None],
                     on_speech_end: Callable) -> None:
        """Register callback functions for speech events."""
        self.on_speech_start = on_speech_start
        self.on_partial_text = on_partial_text
        self.on_sentence_complete = on_sentence_complete
        self.on_speech_end = on_speech_end
        logger.debug("Speech event callbacks registered")
    
    def configure_audio_device(self, device_info) -> None:
        """Configure audio processing for specific device."""
        logger.info(f"Configuring audio device: {device_info}")
        if self.is_streaming:
            logger.warning("Cannot configure device while streaming is active")
            return
        
        # Store device configuration for next stream start
        if hasattr(device_info, 'sample_rate'):
            self.sample_rate = device_info.sample_rate
        if hasattr(device_info, 'buffer_size'):
            self.chunk_size = device_info.buffer_size
        
        logger.info(f"Audio device configured: sample_rate={self.sample_rate}, chunk_size={self.chunk_size}")
    
    def get_supported_sample_rates(self) -> List[int]:
        """Get supported sample rates for current audio device."""
        # Standard rates that work well with most devices and ASR models
        standard_rates = [16000, 44100, 48000]
        
        if not self.pyaudio_instance:
            return standard_rates
        
        try:
            device_info = self._get_audio_device_info()
            if not device_info:
                return standard_rates
            
            supported_rates = []
            for rate in standard_rates:
                try:
                    # Test if rate is supported
                    if self.pyaudio_instance.is_format_supported(
                        rate=rate,
                        input_device=getattr(device_info, 'index', None),
                        input_channels=1,
                        input_format=pyaudio.paInt16
                    ):
                        supported_rates.append(rate)
                except Exception:
                    continue
            
            return supported_rates if supported_rates else standard_rates
            
        except Exception as e:
            logger.warning(f"Could not determine supported sample rates: {e}")
            return standard_rates
    
    def set_vad_threshold(self, threshold: float) -> None:
        """Dynamically adjust VAD sensitivity threshold."""
        if not 0.0 <= threshold <= 1.0:
            logger.warning(f"Invalid VAD threshold {threshold}, must be between 0.0 and 1.0")
            return
        
        self.vad_threshold = threshold
        logger.debug(f"VAD threshold updated to {threshold}")
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics for monitoring."""
        # Get enhanced metrics from performance monitor
        enhanced_metrics = self.performance_monitor.get_current_metrics()
        
        # Calculate VAD latency from recent measurements
        vad_latency = 0.0
        if self.vad_processing_times:
            vad_latency = sum(self.vad_processing_times) / len(self.vad_processing_times)
        
        # Calculate ASR latency from recent measurements
        asr_latency = 0.0
        if self.asr_processing_times:
            asr_latency = sum(self.asr_processing_times) / len(self.asr_processing_times)
        
        # Use enhanced metrics where available, fall back to basic measurements
        return PerformanceMetrics(
            vad_latency=enhanced_metrics.vad_latency_ms / 1000.0 if enhanced_metrics.vad_latency_ms > 0 else vad_latency,
            asr_latency=enhanced_metrics.asr_latency_ms / 1000.0 if enhanced_metrics.asr_latency_ms > 0 else asr_latency,
            interruption_latency=enhanced_metrics.interruption_response_time_ms / 1000.0,
            end_to_end_latency=enhanced_metrics.total_conversation_latency_ms / 1000.0
        )
    
    def get_enhanced_performance_metrics(self):
        """Get enhanced performance metrics from integrated performance monitor."""
        return self.performance_monitor.get_current_metrics()
    
    def get_performance_statistics(self):
        """Get detailed performance statistics for optimization."""
        return self.performance_monitor.get_detailed_statistics()
    
    def optimize_for_latency(self):
        """Apply latency optimizations to the streaming ears component."""
        # Apply threading optimizations
        optimizations = self.threading_optimizer.optimize_for_latency()
        
        # Log optimization results
        logger.info("Applied latency optimizations to StreamingEars:")
        for opt_name, applied in optimizations.items():
            if isinstance(applied, bool):
                status = "✓" if applied else "✗"
                logger.info(f"  {status} {opt_name}")
            elif isinstance(applied, list) and applied:
                logger.info(f"  Recommendations:")
                for rec in applied:
                    logger.info(f"    - {rec}")
        
        return optimizations
    
    def get_audio_buffer_status(self) -> dict:
        """Get current audio buffer status for diagnostics."""
        with self.buffer_lock:
            return {
                'buffer_size': len(self.audio_buffer),
                'buffer_capacity': self.buffer_size,
                'buffer_usage_percent': (len(self.audio_buffer) / self.buffer_size * 100) if self.buffer_size > 0 else 0,
                'queue_size': self.processing_queue.qsize(),
                'chunks_processed': self.chunk_counter,
                'is_streaming': self.is_streaming
            }