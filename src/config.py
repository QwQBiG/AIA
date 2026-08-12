"""
AI VTuber 系统配置管理和数据模型

本模块定义了系统中使用的核心数据结构，
并提供配置加载和验证功能。

主要功能：
- 📋 系统配置数据类定义
- 🔧 配置文件加载和保存
- ✅ 配置验证和默认值处理
- 🔄 配置热更新支持
- 📊 配置统计和分析
"""

import json   
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class PerformanceConfig:
    """
    性能优化配置类
    
    用于配置流式响应和管道处理的性能参数，
    优化系统响应速度和用户体验。
    """
    # 流式响应配置
    enable_streaming: bool = True           # 启用流式响应显示
    
    # 分句处理配置
    enable_sentence_chunking: bool = True   # 启用智能分句 TTS
    stream_chunk_min_size: int = 5          # 最小分句长度（防止过短句子）
    
    # 队列管理配置
    max_queue_size: int = 10                # 最大队列长度（防止任务积压）
    
    # 系统预热配置
    warmup_enabled: bool = True             # 启用系统预热加载
    warmup_timeout: float = 10.0            # 预热超时时间（秒）
    
    # 用户交互配置
    enable_interruption: bool = True        # 启用用户打断功能


@dataclass
class UXConfig:
    """
    用户体验配置类
    
    配置字幕显示、缓存机制和文本处理等
    影响用户体验的功能参数。
    """
    # 字幕显示配置
    show_subtitles: bool = True             # 启用字幕显示
    subtitle_font_size: int = 24            # 字幕字体大小
    subtitle_delay: float = 0.5             # 音频结束后字幕保留时间（秒）
    subtitle_show_original: bool = True     # 显示原始文本还是清洗后文本
    
    # 缓存系统配置
    enable_cache: bool = True               # 启用音频缓存系统
    cache_directory: str = "assets/cache"   # 缓存文件存储目录
    
    # 智能分句配置
    aggressive_split: bool = True           # 启用激进分句
    aggressive_min_length: int = 10         # 激进分句最小缓冲长度
    
    # 文本清洗配置
    remove_emoji: bool = True               # 移除 Emoji
    remove_markdown: bool = True            # 移除 Markdown 格式
    remove_parenthetical: bool = True       # 移除括号内容


@dataclass
class AgentVisionConfig:
    """Agent vision system configuration."""
    vision_model: str = "llava"             # Vision language model name
    capture_region: Optional[list] = None   # Screen capture region [x, y, w, h] or None for full screen
    max_image_dimension: int = 1024         # Maximum image dimension for VLM optimization


@dataclass
class AgentActionsConfig:
    """Agent action system configuration."""
    use_directinput: bool = True            # Use DirectX-compatible input methods
    action_delay: float = 0.1               # Delay between actions (seconds)
    click_duration: float = 0.1             # Click hold duration (seconds)
    clamp_region: Optional[list] = None     # Coordinate clamping region [x, y, w, h] or None


@dataclass
class AgentSafetyConfig:
    """Agent safety system configuration."""
    enable_emergency_hotkey: bool = True    # Enable F9 emergency stop hotkey
    emergency_key: str = "<f9>"             # Emergency stop hotkey


@dataclass
class AgentConfig:
    """Agent mode configuration for vision-action system."""
    enabled: bool = False                   # Enable agent mode
    loop_interval: float = 2.0              # Time between agent loop cycles (seconds)
    cooldown_period: float = 1.0            # Cooldown after each action (seconds)
    
    # Sub-configurations
    vision: AgentVisionConfig = None        # Vision system settings
    actions: AgentActionsConfig = None      # Action system settings
    safety: AgentSafetyConfig = None        # Safety system settings
    
    def __post_init__(self):
        """Initialize sub-configurations if not provided."""
        if self.vision is None:
            self.vision = AgentVisionConfig()
        if self.actions is None:
            self.actions = AgentActionsConfig()
        if self.safety is None:
            self.safety = AgentSafetyConfig()


@dataclass
class SystemConfig:
    """System configuration data model."""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    vts_port: int = 8001
    log_level: str = "INFO"
    
    # Emotional Intelligence Settings
    enable_emotional_intelligence: bool = False
    enable_voice_cloning: bool = False
    enable_expression_control: bool = False
    
    # Performance Settings
    performance: PerformanceConfig = None
    
    # UX Settings
    ux: UXConfig = None
    
    # Agent Settings
    agent: AgentConfig = None
    
    # LLM Backend Settings
    llm_backend: str = "ollama"  # "ollama" or "koboldcpp"
    
    # KoboldCpp settings
    koboldcpp_url: str = "http://localhost:5001"
    koboldcpp_model: str = ""
    koboldcpp_max_context_length: int = 2048
    koboldcpp_max_length: int = 256
    koboldcpp_temperature: float = 0.7
    
    # GPT-SoVITS Configuration
    sovits_url: str = "http://127.0.0.1:9880"
    sovits_timeout: float = 10.0
    sovits_language: str = "zh"
    sovits_ref_audio_path: str = ""  # Reference audio path for voice cloning
    sovits_prompt_text: str = ""  # Prompt text for reference audio
    sovits_prompt_lang: str = "zh"  # Language of prompt text
    fallback_to_edge_tts: bool = True
    
    # Emotion to Hotkey Mapping
    emotion_hotkey_map: Dict[str, str] = None
    default_emotion: str = "neutral"
    expression_timeout: float = 0.5
    
    def __post_init__(self):
        """Initialize default emotion hotkey mapping and performance config if not provided."""
        if self.emotion_hotkey_map is None:
            self.emotion_hotkey_map = {
                "neutral": "",
                "happy": "",
                "angry": "",
                "sad": "",
                "surprised": ""
            }
        if self.performance is None:
            self.performance = PerformanceConfig()
        if self.ux is None:
            self.ux = UXConfig()
        if self.agent is None:
            self.agent = AgentConfig()
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'SystemConfig':
        """Load configuration from JSON file using absolute path.
        
        Supports both flat format (new) and nested format (legacy).
        """
        abs_path = os.path.abspath(config_path)
        
        if not os.path.exists(abs_path):
            # Return default configuration if file doesn't exist
            return cls()
        
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Create default instance first
            default_config = cls()
            
            # Check if this is a nested (legacy) format by looking for nested keys
            if 'ollama' in config_data and isinstance(config_data['ollama'], dict):
                # Convert nested format to flat format
                config_data = cls._convert_legacy_config(config_data)
            
            # Update with loaded data, preserving defaults for missing fields
            for key, value in config_data.items():
                if hasattr(default_config, key):
                    # Handle nested PerformanceConfig
                    if key == 'performance' and isinstance(value, dict):
                        perf_config = PerformanceConfig()
                        for perf_key, perf_value in value.items():
                            if hasattr(perf_config, perf_key):
                                setattr(perf_config, perf_key, perf_value)
                        setattr(default_config, key, perf_config)
                    # Handle nested UXConfig
                    elif key == 'ux' and isinstance(value, dict):
                        ux_config = UXConfig()
                        for ux_key, ux_value in value.items():
                            if hasattr(ux_config, ux_key):
                                setattr(ux_config, ux_key, ux_value)
                        setattr(default_config, key, ux_config)
                    # Handle nested AgentConfig
                    elif key == 'agent' and isinstance(value, dict):
                        agent_config = AgentConfig()
                        for agent_key, agent_value in value.items():
                            if hasattr(agent_config, agent_key):
                                # Handle nested sub-configurations
                                if agent_key == 'vision' and isinstance(agent_value, dict):
                                    vision_config = AgentVisionConfig()
                                    for vision_key, vision_value in agent_value.items():
                                        if hasattr(vision_config, vision_key):
                                            setattr(vision_config, vision_key, vision_value)
                                    setattr(agent_config, agent_key, vision_config)
                                elif agent_key == 'actions' and isinstance(agent_value, dict):
                                    actions_config = AgentActionsConfig()
                                    for actions_key, actions_value in agent_value.items():
                                        if hasattr(actions_config, actions_key):
                                            setattr(actions_config, actions_key, actions_value)
                                    setattr(agent_config, agent_key, actions_config)
                                elif agent_key == 'safety' and isinstance(agent_value, dict):
                                    safety_config = AgentSafetyConfig()
                                    for safety_key, safety_value in agent_value.items():
                                        if hasattr(safety_config, safety_key):
                                            setattr(safety_config, safety_key, safety_value)
                                    setattr(agent_config, agent_key, safety_config)
                                else:
                                    setattr(agent_config, agent_key, agent_value)
                        setattr(default_config, key, agent_config)
                    else:
                        setattr(default_config, key, value)
            
            # Ensure emotion_hotkey_map, performance, ux, and agent are properly initialized
            if default_config.emotion_hotkey_map is None:
                default_config.emotion_hotkey_map = {
                    "neutral": "",
                    "happy": "",
                    "angry": "",
                    "sad": "",
                    "surprised": ""
                }
            if default_config.performance is None:
                default_config.performance = PerformanceConfig()
            if default_config.ux is None:
                default_config.ux = UXConfig()
            if default_config.agent is None:
                default_config.agent = AgentConfig()
            
            return default_config
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid configuration file {abs_path}: {e}")
    
    @staticmethod
    def _convert_legacy_config(legacy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert nested (legacy) configuration format to flat format.
        
        Args:
            legacy_config: Configuration in nested format
            
        Returns:
            Configuration in flat format
        """
        config_data = {}
        
        # Map legacy structure to new flat structure
        if 'ollama' in legacy_config:
            config_data['ollama_url'] = legacy_config['ollama'].get('base_url', 'http://localhost:11434')
            config_data['ollama_model'] = legacy_config['ollama'].get('model', 'llama3')
        
        if 'vts' in legacy_config:
            config_data['vts_port'] = legacy_config['vts'].get('port', 8001)
        
        if 'tts' in legacy_config:
            config_data['tts_voice'] = legacy_config['tts'].get('voice', 'zh-CN-XiaoxiaoNeural')
        
        if 'logging' in legacy_config:
            config_data['log_level'] = legacy_config['logging'].get('level', 'INFO')
        
        # Copy emotional intelligence settings if present (flat format)
        emotional_keys = [
            'enable_emotional_intelligence', 'enable_voice_cloning', 'enable_expression_control',
            'sovits_url', 'sovits_timeout', 'sovits_language', 
            'sovits_ref_audio_path', 'sovits_prompt_text', 'sovits_prompt_lang',
            'fallback_to_edge_tts',
            'emotion_hotkey_map', 'default_emotion', 'expression_timeout'
        ]
        for key in emotional_keys:
            if key in legacy_config:
                config_data[key] = legacy_config[key]
        
        # Copy performance settings if present
        if 'performance' in legacy_config:
            config_data['performance'] = legacy_config['performance']
        
        # Copy UX settings if present
        if 'ux' in legacy_config:
            config_data['ux'] = legacy_config['ux']
        
        # Copy agent settings if present
        if 'agent' in legacy_config:
            config_data['agent'] = legacy_config['agent']
        
        return config_data
    
    def save_to_file(self, config_path: str) -> None:
        """Save configuration to JSON file using absolute path."""
        abs_path = os.path.abspath(config_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        try:
            with open(abs_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except (OSError, IOError) as e:
            raise IOError(f"Failed to save configuration to {abs_path}: {e}")
    
    def validate(self) -> None:
        """Validate configuration values."""
        if not self.ollama_url or not isinstance(self.ollama_url, str):
            raise ValueError("ollama_url must be a non-empty string")
        
        if not self.ollama_model or not isinstance(self.ollama_model, str):
            raise ValueError("ollama_model must be a non-empty string")
        
        if not self.tts_voice or not isinstance(self.tts_voice, str):
            raise ValueError("tts_voice must be a non-empty string")
        
        if not isinstance(self.vts_port, int) or self.vts_port <= 0:
            raise ValueError("vts_port must be a positive integer")
        
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            raise ValueError(f"log_level must be one of {valid_log_levels}")
        
        # Validate emotional intelligence settings
        if not isinstance(self.enable_emotional_intelligence, bool):
            raise ValueError("enable_emotional_intelligence must be a boolean")
        
        if not isinstance(self.enable_voice_cloning, bool):
            raise ValueError("enable_voice_cloning must be a boolean")
        
        if not isinstance(self.enable_expression_control, bool):
            raise ValueError("enable_expression_control must be a boolean")
        
        # Validate GPT-SoVITS configuration
        if not self.sovits_url or not isinstance(self.sovits_url, str):
            raise ValueError("sovits_url must be a non-empty string")
        
        if not isinstance(self.sovits_timeout, (int, float)) or self.sovits_timeout <= 0:
            raise ValueError("sovits_timeout must be a positive number")
        
        if not self.sovits_language or not isinstance(self.sovits_language, str):
            raise ValueError("sovits_language must be a non-empty string")
        
        if not isinstance(self.fallback_to_edge_tts, bool):
            raise ValueError("fallback_to_edge_tts must be a boolean")
        
        # Validate emotion configuration
        if not isinstance(self.emotion_hotkey_map, dict):
            raise ValueError("emotion_hotkey_map must be a dictionary")
        
        valid_emotions = {"neutral", "happy", "angry", "sad", "surprised"}
        for emotion in self.emotion_hotkey_map.keys():
            if emotion not in valid_emotions:
                raise ValueError(f"Invalid emotion '{emotion}'. Must be one of {valid_emotions}")
        
        if self.default_emotion not in valid_emotions:
            raise ValueError(f"default_emotion must be one of {valid_emotions}")
        
        if not isinstance(self.expression_timeout, (int, float)) or self.expression_timeout <= 0:
            raise ValueError("expression_timeout must be a positive number")
        
        # Validate performance configuration
        self._validate_performance_config()
        
        # Validate UX configuration
        self._validate_ux_config()
        
        # Validate agent configuration
        self._validate_agent_config()
    
    def _validate_performance_config(self) -> None:
        """Validate performance configuration values."""
        if self.performance is None:
            raise ValueError("performance configuration must not be None")
        
        perf = self.performance
        
        if not isinstance(perf.enable_streaming, bool):
            raise ValueError("performance.enable_streaming must be a boolean")
        
        if not isinstance(perf.enable_sentence_chunking, bool):
            raise ValueError("performance.enable_sentence_chunking must be a boolean")
        
        if not isinstance(perf.stream_chunk_min_size, int) or perf.stream_chunk_min_size < 0:
            raise ValueError("performance.stream_chunk_min_size must be a non-negative integer")
        
        if not isinstance(perf.max_queue_size, int) or perf.max_queue_size <= 0:
            raise ValueError("performance.max_queue_size must be a positive integer")
        
        if not isinstance(perf.warmup_enabled, bool):
            raise ValueError("performance.warmup_enabled must be a boolean")
        
        if not isinstance(perf.warmup_timeout, (int, float)) or perf.warmup_timeout <= 0:
            raise ValueError("performance.warmup_timeout must be a positive number")
        
        if not isinstance(perf.enable_interruption, bool):
            raise ValueError("performance.enable_interruption must be a boolean")
    
    def _validate_ux_config(self) -> None:
        """Validate UX configuration values."""
        if self.ux is None:
            raise ValueError("ux configuration must not be None")
        
        ux = self.ux
        
        if not isinstance(ux.show_subtitles, bool):
            raise ValueError("ux.show_subtitles must be a boolean")
        
        if not isinstance(ux.subtitle_font_size, int) or ux.subtitle_font_size <= 0:
            raise ValueError("ux.subtitle_font_size must be a positive integer")
        
        if not isinstance(ux.subtitle_delay, (int, float)) or ux.subtitle_delay < 0:
            raise ValueError("ux.subtitle_delay must be a non-negative number")
        
        if not isinstance(ux.subtitle_show_original, bool):
            raise ValueError("ux.subtitle_show_original must be a boolean")
        
        if not isinstance(ux.enable_cache, bool):
            raise ValueError("ux.enable_cache must be a boolean")
        
        if not isinstance(ux.cache_directory, str):
            raise ValueError("ux.cache_directory must be a string")
        
        if not isinstance(ux.aggressive_split, bool):
            raise ValueError("ux.aggressive_split must be a boolean")
        
        if not isinstance(ux.aggressive_min_length, int) or ux.aggressive_min_length <= 0:
            raise ValueError("ux.aggressive_min_length must be a positive integer")
        
        if not isinstance(ux.remove_emoji, bool):
            raise ValueError("ux.remove_emoji must be a boolean")
        
        if not isinstance(ux.remove_markdown, bool):
            raise ValueError("ux.remove_markdown must be a boolean")
        
        if not isinstance(ux.remove_parenthetical, bool):
            raise ValueError("ux.remove_parenthetical must be a boolean")
    
    def _validate_agent_config(self) -> None:
        """Validate agent configuration values."""
        if self.agent is None:
            raise ValueError("agent configuration must not be None")
        
        agent = self.agent
        
        if not isinstance(agent.enabled, bool):
            raise ValueError("agent.enabled must be a boolean")
        
        if not isinstance(agent.loop_interval, (int, float)) or agent.loop_interval <= 0:
            raise ValueError("agent.loop_interval must be a positive number")
        
        if not isinstance(agent.cooldown_period, (int, float)) or agent.cooldown_period < 0:
            raise ValueError("agent.cooldown_period must be a non-negative number")
        
        # Validate vision config
        if agent.vision is None:
            raise ValueError("agent.vision configuration must not be None")
        
        vision = agent.vision
        if not isinstance(vision.vision_model, str) or not vision.vision_model:
            raise ValueError("agent.vision.vision_model must be a non-empty string")
        
        if vision.capture_region is not None:
            if not isinstance(vision.capture_region, list) or len(vision.capture_region) != 4:
                raise ValueError("agent.vision.capture_region must be a list of 4 integers [x, y, w, h] or None")
            if not all(isinstance(x, int) and x >= 0 for x in vision.capture_region):
                raise ValueError("agent.vision.capture_region values must be non-negative integers")
        
        if not isinstance(vision.max_image_dimension, int) or vision.max_image_dimension <= 0:
            raise ValueError("agent.vision.max_image_dimension must be a positive integer")
        
        # Validate actions config
        if agent.actions is None:
            raise ValueError("agent.actions configuration must not be None")
        
        actions = agent.actions
        if not isinstance(actions.use_directinput, bool):
            raise ValueError("agent.actions.use_directinput must be a boolean")
        
        if not isinstance(actions.action_delay, (int, float)) or actions.action_delay < 0:
            raise ValueError("agent.actions.action_delay must be a non-negative number")
        
        if not isinstance(actions.click_duration, (int, float)) or actions.click_duration <= 0:
            raise ValueError("agent.actions.click_duration must be a positive number")
        
        if actions.clamp_region is not None:
            if not isinstance(actions.clamp_region, list) or len(actions.clamp_region) != 4:
                raise ValueError("agent.actions.clamp_region must be a list of 4 integers [x, y, w, h] or None")
            if not all(isinstance(x, int) and x >= 0 for x in actions.clamp_region):
                raise ValueError("agent.actions.clamp_region values must be non-negative integers")
        
        # Validate safety config
        if agent.safety is None:
            raise ValueError("agent.safety configuration must not be None")
        
        safety = agent.safety
        if not isinstance(safety.enable_emergency_hotkey, bool):
            raise ValueError("agent.safety.enable_emergency_hotkey must be a boolean")
        
        if not isinstance(safety.emergency_key, str) or not safety.emergency_key:
            raise ValueError("agent.safety.emergency_key must be a non-empty string")


@dataclass
class ChatMessage:
    """Chat message data model."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    
    def __post_init__(self):
        """Validate message data after initialization."""
        if self.role not in ["user", "assistant"]:
            raise ValueError("role must be either 'user' or 'assistant'")
        
        if not self.content or not isinstance(self.content, str):
            raise ValueError("content must be a non-empty string")
        
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime object")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """Create message from dictionary format."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class SystemState:
    """System state data model."""
    llm_connected: bool = False
    vts_connected: bool = False
    is_speaking: bool = False
    current_audio_file: Optional[str] = None
    def reset_connections(self) -> None:
        self.llm_connected = False
        self.vts_connected = False
    def set_audio_state(self, is_speaking: bool, audio_file: Optional[str] = None) -> None:
        self.is_speaking = is_speaking
        self.current_audio_file = audio_file if is_speaking else None
    def get_connection_status(self) -> Dict[str, bool]:
        return {"llm": self.llm_connected, "vts": self.vts_connected}


def load_config(config_path: str = "config.json") -> SystemConfig:
    """
    Load system configuration from file.
    
    Args:
        config_path: Path to configuration file (relative or absolute)
        
    Returns:
        SystemConfig instance
        
    Raises:
        ValueError: If configuration is invalid
        IOError: If file cannot be read
    """
    config = SystemConfig.load_from_file(config_path)
    config.validate()
    return config


def create_default_config(config_path: str = "config.json") -> SystemConfig:
    """
    Create and save default configuration file.
    
    Args:
        config_path: Path where to save the configuration file
        
    Returns:
        SystemConfig instance with default values
    """
    config = SystemConfig()
    config.save_to_file(config_path)
    return config
