"""
ConfigurationManager Component

Manage user preferences and system configuration for audio processing.
Handles persistent storage, validation, and diagnostic information.
"""

import json
import os
import time
import platform
import psutil
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
import logging

from .logging_config import get_component_logger

logger = get_component_logger("configuration_manager")

@dataclass
class AudioPreferences:
    """User audio preferences."""
    vad_threshold: float = 0.8
    buffer_size: int = 960
    sample_rate: int = 16000
    enable_noise_suppression: bool = True
    auto_gain_control: bool = True
    preferred_model: str = "paraformer-streaming"

@dataclass
class VADConfig:
    """VAD configuration parameters."""
    threshold: float = 0.8
    chunk_size: int = 960
    sample_rate: int = 16000
    model_path: str = "silero_vad"

@dataclass
class ASRConfig:
    """ASR configuration parameters."""
    model_name: str = "paraformer-streaming"
    language: str = "zh"
    sample_rate: int = 16000
    chunk_size: int = 960
    confidence_threshold: float = 0.7

@dataclass
class DiagnosticInfo:
    """System diagnostic information."""
    timestamp: float
    system_info: Dict[str, Any]
    audio_info: Dict[str, Any]
    performance_info: Dict[str, Any]
    config_status: Dict[str, Any]

@dataclass
class OptimizationRecommendation:
    """Audio setup optimization recommendation."""
    category: str  # "performance", "quality", "compatibility"
    priority: str  # "high", "medium", "low"
    description: str
    current_value: Any
    recommended_value: Any
    reason: str

class ConfigurationManager:
    """Manage user preferences and system configuration."""
    
    def __init__(self, config_path: str = "assets/audio_config.json"):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.preferences: AudioPreferences = AudioPreferences()
        self.vad_config: VADConfig = VADConfig()
        self.asr_config: ASRConfig = ASRConfig()
        
        # Ensure config directory exists
        config_dir = os.path.dirname(config_path)
        if config_dir:  # Only create directory if path has a directory component
            os.makedirs(config_dir, exist_ok=True)
        
        # Load existing preferences if available
        self._load_config()
        
        logger.info(f"ConfigurationManager initialized with config_path={config_path}")
    
    def save_preferences(self, preferences: AudioPreferences) -> None:
        """Save user audio preferences to persistent storage."""
        logger.info("Saving audio preferences...")
        
        self.preferences = preferences
        
        config_data = {
            "preferences": asdict(preferences),
            "vad_config": asdict(self.vad_config),
            "asr_config": asdict(self.asr_config),
            "version": "1.0.0"
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Preferences saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            raise
    
    def load_preferences(self) -> AudioPreferences:
        """Load user audio preferences from storage."""
        logger.info("Loading audio preferences...")
        return self.preferences
    
    def get_vad_config(self) -> VADConfig:
        """Get VAD configuration parameters."""
        return self.vad_config
    
    def get_asr_config(self) -> ASRConfig:
        """Get ASR configuration parameters."""
        return self.asr_config
    
    def validate_configuration(self) -> List[str]:
        """Validate current configuration and return any issues."""
        issues = []
        
        # Validate VAD threshold
        if not 0.0 <= self.vad_config.threshold <= 1.0:
            issues.append("VAD threshold must be between 0.0 and 1.0")
        
        # Validate sample rates
        valid_rates = [16000, 44100, 48000]
        if self.preferences.sample_rate not in valid_rates:
            issues.append(f"Sample rate must be one of {valid_rates}")
        
        # Validate buffer size
        if self.preferences.buffer_size <= 0:
            issues.append("Buffer size must be positive")
        
        # Validate confidence threshold
        if not 0.0 <= self.asr_config.confidence_threshold <= 1.0:
            issues.append("ASR confidence threshold must be between 0.0 and 1.0")
        
        logger.debug(f"Configuration validation found {len(issues)} issues")
        return issues
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get diagnostic information for troubleshooting."""
        return {
            "config_path": self.config_path,
            "config_exists": os.path.exists(self.config_path),
            "preferences": asdict(self.preferences),
            "vad_config": asdict(self.vad_config),
            "asr_config": asdict(self.asr_config),
            "validation_issues": self.validate_configuration()
        }
    
    def get_comprehensive_diagnostic_info(self) -> DiagnosticInfo:
        """Get comprehensive diagnostic information for troubleshooting."""
        logger.info("Collecting comprehensive diagnostic information...")
        
        # System information
        system_info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2)
        }
        
        # Audio-specific information
        audio_info = {
            "sample_rate": self.preferences.sample_rate,
            "buffer_size": self.preferences.buffer_size,
            "vad_threshold": self.vad_config.threshold,
            "asr_confidence_threshold": self.asr_config.confidence_threshold,
            "noise_suppression_enabled": self.preferences.enable_noise_suppression,
            "auto_gain_control_enabled": self.preferences.auto_gain_control
        }
        
        # Performance information
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        performance_info = {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "disk_usage_percent": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
        }
        
        # Configuration status
        config_status = {
            "config_file_exists": os.path.exists(self.config_path),
            "config_file_size_bytes": os.path.getsize(self.config_path) if os.path.exists(self.config_path) else 0,
            "validation_issues": self.validate_configuration(),
            "last_modified": os.path.getmtime(self.config_path) if os.path.exists(self.config_path) else None
        }
        
        return DiagnosticInfo(
            timestamp=time.time(),
            system_info=system_info,
            audio_info=audio_info,
            performance_info=performance_info,
            config_status=config_status
        )
    
    def get_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on current configuration and system."""
        recommendations = []
        
        # Check CPU usage and recommend buffer size adjustments
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > 80:
                recommendations.append(OptimizationRecommendation(
                    category="performance",
                    priority="high",
                    description="High CPU usage detected, consider increasing buffer size",
                    current_value=self.preferences.buffer_size,
                    recommended_value=min(self.preferences.buffer_size * 2, 1920),
                    reason="Larger buffers reduce CPU overhead but increase latency"
                ))
        except Exception as e:
            logger.warning(f"Could not check CPU usage: {e}")
        
        # Check memory usage
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                recommendations.append(OptimizationRecommendation(
                    category="performance",
                    priority="medium",
                    description="High memory usage detected, consider disabling noise suppression",
                    current_value=self.preferences.enable_noise_suppression,
                    recommended_value=False,
                    reason="Noise suppression uses additional memory"
                ))
        except Exception as e:
            logger.warning(f"Could not check memory usage: {e}")
        
        # Check VAD threshold
        if self.vad_config.threshold < 0.5:
            recommendations.append(OptimizationRecommendation(
                category="quality",
                priority="medium",
                description="VAD threshold is very low, may cause false positives",
                current_value=self.vad_config.threshold,
                recommended_value=0.8,
                reason="Higher threshold reduces false speech detection"
            ))
        elif self.vad_config.threshold > 0.95:
            recommendations.append(OptimizationRecommendation(
                category="quality",
                priority="medium",
                description="VAD threshold is very high, may miss quiet speech",
                current_value=self.vad_config.threshold,
                recommended_value=0.8,
                reason="Lower threshold improves sensitivity to quiet speech"
            ))
        
        # Check sample rate compatibility
        if self.preferences.sample_rate not in [16000, 44100, 48000]:
            recommendations.append(OptimizationRecommendation(
                category="compatibility",
                priority="high",
                description="Unusual sample rate may cause compatibility issues",
                current_value=self.preferences.sample_rate,
                recommended_value=16000,
                reason="16kHz is optimal for speech recognition models"
            ))
        
        # Check ASR confidence threshold
        if self.asr_config.confidence_threshold < 0.5:
            recommendations.append(OptimizationRecommendation(
                category="quality",
                priority="low",
                description="ASR confidence threshold is low, may accept poor transcriptions",
                current_value=self.asr_config.confidence_threshold,
                recommended_value=0.7,
                reason="Higher threshold improves transcription quality"
            ))
        
        logger.info(f"Generated {len(recommendations)} optimization recommendations")
        return recommendations
    
    def tune_for_performance(self) -> None:
        """Automatically tune configuration for optimal performance."""
        logger.info("Auto-tuning configuration for performance...")
        
        # Get system information
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Adjust buffer size based on CPU cores
        if cpu_count >= 8:
            self.preferences.buffer_size = 480  # Smaller buffer for high-end systems
        elif cpu_count >= 4:
            self.preferences.buffer_size = 960  # Standard buffer
        else:
            self.preferences.buffer_size = 1920  # Larger buffer for low-end systems
        
        # Adjust settings based on available memory
        if memory_gb < 4:
            self.preferences.enable_noise_suppression = False
            self.preferences.auto_gain_control = False
        elif memory_gb < 8:
            self.preferences.enable_noise_suppression = True
            self.preferences.auto_gain_control = False
        else:
            self.preferences.enable_noise_suppression = True
            self.preferences.auto_gain_control = True
        
        # Set optimal sample rate for speech recognition
        self.preferences.sample_rate = 16000
        self.vad_config.sample_rate = 16000
        self.asr_config.sample_rate = 16000
        
        # Set conservative thresholds for reliability
        self.vad_config.threshold = 0.8
        self.asr_config.confidence_threshold = 0.7
        
        # Save the tuned configuration
        self.save_preferences(self.preferences)
        logger.info("Configuration auto-tuned for performance")
    
    def tune_for_quality(self) -> None:
        """Automatically tune configuration for optimal quality."""
        logger.info("Auto-tuning configuration for quality...")
        
        # Enable all quality features
        self.preferences.enable_noise_suppression = True
        self.preferences.auto_gain_control = True
        
        # Use smaller buffer for lower latency
        self.preferences.buffer_size = 480
        
        # Set optimal sample rate
        self.preferences.sample_rate = 16000
        self.vad_config.sample_rate = 16000
        self.asr_config.sample_rate = 16000
        
        # Set high-quality thresholds
        self.vad_config.threshold = 0.8
        self.asr_config.confidence_threshold = 0.8
        
        # Save the tuned configuration
        self.save_preferences(self.preferences)
        logger.info("Configuration auto-tuned for quality")
    
    def tune_for_compatibility(self) -> None:
        """Automatically tune configuration for maximum compatibility."""
        logger.info("Auto-tuning configuration for compatibility...")
        
        # Use conservative settings
        self.preferences.sample_rate = 16000
        self.preferences.buffer_size = 960
        self.preferences.enable_noise_suppression = False
        self.preferences.auto_gain_control = False
        
        # Set compatible thresholds
        self.vad_config.threshold = 0.8
        self.vad_config.sample_rate = 16000
        self.asr_config.sample_rate = 16000
        self.asr_config.confidence_threshold = 0.7
        
        # Save the tuned configuration
        self.save_preferences(self.preferences)
        logger.info("Configuration auto-tuned for compatibility")
    
    def export_diagnostic_report(self, output_path: str = "diagnostic_report.json") -> str:
        """Export comprehensive diagnostic report to file."""
        logger.info(f"Exporting diagnostic report to {output_path}")
        
        diagnostic_info = self.get_comprehensive_diagnostic_info()
        recommendations = self.get_optimization_recommendations()
        
        report = {
            "diagnostic_info": asdict(diagnostic_info),
            "optimization_recommendations": [asdict(rec) for rec in recommendations],
            "export_timestamp": time.time()
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Diagnostic report exported to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to export diagnostic report: {e}")
            raise
    
    def apply_recommendation(self, recommendation: OptimizationRecommendation) -> None:
        """Apply a specific optimization recommendation."""
        logger.info(f"Applying recommendation: {recommendation.description}")
        
        # Map recommendation to configuration changes
        if "buffer size" in recommendation.description.lower():
            self.preferences.buffer_size = recommendation.recommended_value
        elif "vad threshold" in recommendation.description.lower():
            self.vad_config.threshold = recommendation.recommended_value
            self.preferences.vad_threshold = recommendation.recommended_value
        elif "noise suppression" in recommendation.description.lower():
            self.preferences.enable_noise_suppression = recommendation.recommended_value
        elif "sample rate" in recommendation.description.lower():
            self.preferences.sample_rate = recommendation.recommended_value
            self.vad_config.sample_rate = recommendation.recommended_value
            self.asr_config.sample_rate = recommendation.recommended_value
        elif "confidence threshold" in recommendation.description.lower():
            self.asr_config.confidence_threshold = recommendation.recommended_value
        
        # Save the updated configuration
        self.save_preferences(self.preferences)
        logger.info(f"Applied recommendation and saved configuration")
    
    def _load_config(self) -> None:
        """Load configuration from file if it exists."""
        if not os.path.exists(self.config_path):
            logger.info("No existing config file found, using defaults")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Load preferences
            if "preferences" in config_data:
                prefs_data = config_data["preferences"]
                self.preferences = AudioPreferences(**prefs_data)
            
            # Load VAD config
            if "vad_config" in config_data:
                vad_data = config_data["vad_config"]
                self.vad_config = VADConfig(**vad_data)
            
            # Load ASR config
            if "asr_config" in config_data:
                asr_data = config_data["asr_config"]
                self.asr_config = ASRConfig(**asr_data)
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}, using defaults")
    
    def update_vad_threshold(self, threshold: float) -> None:
        """Update VAD threshold and save configuration."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("VAD threshold must be between 0.0 and 1.0")
        
        self.vad_config.threshold = threshold
        self.preferences.vad_threshold = threshold
        self.save_preferences(self.preferences)
        logger.info(f"VAD threshold updated to {threshold}")
    
    def reset_to_defaults(self) -> None:
        """Reset all configuration to default values."""
        logger.info("Resetting configuration to defaults")
        self.preferences = AudioPreferences()
        self.vad_config = VADConfig()
        self.asr_config = ASRConfig()
        self.save_preferences(self.preferences)