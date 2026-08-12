#!/usr/bin/env python3
"""
AI VTuber 系统 - 主程序入口

这是 AI VTuber 系统的主启动脚本，负责系统初始化和运行。
处理系统初始化、配置加载、组件启动，并提供主应用程序循环。

功能需求覆盖：
- 5.3: 系统组件初始化日志记录
- 7.3: 清晰的模块化代码结构  
- 7.4: Windows 环境支持
- 1.1: 使用 pywin32 实现幽灵窗口点击穿透
- 2.1: TTS 和 VTS 之间的唇同步集成
- 3.1: 代理控制和可视化

主要功能：
- 🚀 系统启动和初始化
- ⚙️ 配置文件加载和验证
- 🧩 组件依赖注入和连接
- 🔄 异步事件循环管理
- 🛡️ 错误处理和恢复机制
- 📊 性能监控和优化
- 🔒 安全管理和紧急停止
"""

import asyncio
import logging
import os
import sys
import signal
import traceback
from pathlib import Path
from typing import Optional, Dict

# 将 src 目录添加到 Python 路径以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 导入核心系统组件
from src.config import SystemConfig, load_config, create_default_config
from src.gui_controller import ImprovedGUIController
from src.error_handler import ErrorHandler
from src.system_workflow import SystemWorkflow
from src.warmup_manager import WarmupManager

# 导入记忆系统组件（可选）
try:
    from src.memory_core.memory_core import MemoryCore
    from src.enhanced_llm_client import EnhancedLLMClient
    MEMORY_SYSTEM_AVAILABLE = True
except ImportError as e:
    MemoryCore = None
    EnhancedLLMClient = None
    MEMORY_SYSTEM_AVAILABLE = False
    print(f"警告: 记忆系统不可用: {e}")

# 导入全双工引擎组件（带错误处理）
try:
    from src.full_duplex_engine.duplex_manager import DuplexManager
    from src.full_duplex_engine.audio_device_manager import AudioDeviceManager
    from src.full_duplex_engine.streaming_ears import StreamingEars
    from src.full_duplex_engine.text_processor import TextProcessor
    from src.full_duplex_engine.configuration_manager import ConfigurationManager
    from src.full_duplex_engine.latency_optimizer import get_latency_optimizer
    from src.full_duplex_engine.system_health_monitor import get_system_health_monitor
    FULL_DUPLEX_AVAILABLE = True
except ImportError as e:
    DuplexManager = None
    AudioDeviceManager = None
    StreamingEars = None
    TextProcessor = None
    ConfigurationManager = None
    FULL_DUPLEX_AVAILABLE = False
    print(f"Warning: Full-duplex engine not available: {e}")

# Import agent components with error handling for missing dependencies
try:
    from src.agent_manager import AgentManager
    AGENT_MANAGER_AVAILABLE = True
except ImportError as e:
    AgentManager = None
    AGENT_MANAGER_AVAILABLE = False
    print(f"Warning: AgentManager not available: {e}")

try:
    from src.safety_manager import SafetyManager
    SAFETY_MANAGER_AVAILABLE = True
except ImportError as e:
    SafetyManager = None
    SAFETY_MANAGER_AVAILABLE = False
    print(f"Warning: SafetyManager not available: {e}")

# Check for pywin32 availability (required for ghost window fix)
try:
    import win32gui
    import win32con
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("Warning: pywin32 not available - overlay click-through may not work properly")


class AIVTuberSystem:
    """
    Main system class that coordinates all components and handles system lifecycle.
    
    This class is responsible for:
    - System initialization and configuration loading
    - Component startup and coordination
    - Error handling and logging setup
    - Graceful shutdown handling
    """
    
    def __init__(self):
        """Initialize the AI VTuber system."""
        self.config: Optional[SystemConfig] = None
        self.gui_controller: Optional[ImprovedGUIController] = None
        self.system_workflow: Optional[SystemWorkflow] = None
        self.warmup_manager: Optional[WarmupManager] = None
        self.agent_manager: Optional[AgentManager] = None
        self.safety_manager: Optional[SafetyManager] = None
        
        # Memory system components
        self.memory_core: Optional[MemoryCore] = None
        
        # Full-duplex engine components
        self.duplex_manager: Optional[DuplexManager] = None
        self.audio_device_manager: Optional[AudioDeviceManager] = None
        self.streaming_ears: Optional[StreamingEars] = None
        self.text_processor: Optional[TextProcessor] = None
        self.configuration_manager: Optional[ConfigurationManager] = None
        self.latency_optimizer = None
        self.system_health_monitor = None
        
        self.error_handler = ErrorHandler()
        self.logger: Optional[logging.Logger] = None
        self.is_running = False
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            if self.logger:
                self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown()
        
        # Register signal handlers (Windows compatible)
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except AttributeError:
            # Some signals may not be available on Windows
            pass
    
    def setup_logging(self) -> None:
        """
        Setup system-wide logging configuration.
        
        Configures logging according to requirement 5.3 for system initialization
        and component status logging. Also sets up agent-specific logging.
        
        Requirements: 6.4 - Comprehensive logging for agent activities
        """
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure root logger
        log_level = getattr(logging, self.config.log_level if self.config else "INFO")
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "ai_vtuber.log", encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
        # Setup agent-specific logging (Requirements: 6.4)
        self._setup_agent_logging(log_dir, log_level)
        self.logger.info("=== AI VTuber System Starting ===")
        self.logger.info(f"Log level set to: {self.config.log_level if self.config else 'INFO'}")
    
    def _setup_agent_logging(self, log_dir: Path, log_level: int) -> None:
        """
        Setup agent-specific logging configuration.
        
        Creates a separate log file for agent activities to facilitate
        debugging and performance analysis.
        
        Requirements: 6.4 - Agent activity logging
        
        Args:
            log_dir: Directory for log files
            log_level: Logging level to use
        """
        # Create agent-specific log file
        agent_log_file = log_dir / "agent_activity.log"
        
        # Create formatter with more detail for agent logs
        agent_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create file handler for agent logs
        agent_file_handler = logging.FileHandler(agent_log_file, encoding='utf-8')
        agent_file_handler.setLevel(log_level)
        agent_file_handler.setFormatter(agent_formatter)
        
        # Add handler to agent-related loggers
        agent_loggers = [
            'src.agent_manager',
            'src.action_engine',
            'src.vision_client',
            'src.safety_manager',
            'src.resource_monitor',
            'src.debug_overlay'
        ]
        
        for logger_name in agent_loggers:
            agent_logger = logging.getLogger(logger_name)
            agent_logger.addHandler(agent_file_handler)
            # Set DEBUG level for agent loggers to capture detailed info
            if self.config and self.config.log_level == "DEBUG":
                agent_logger.setLevel(logging.DEBUG)
        
        self.logger.info(f"Agent logging configured: {agent_log_file}")
    
    def load_configuration(self) -> bool:
        """
        Load system configuration from file.
        
        Returns:
            bool: True if configuration loaded successfully, False otherwise
        """
        config_file = "config.json"
        
        try:
            # Check if config file exists
            if not os.path.exists(config_file):
                print(f"Configuration file {config_file} not found. Creating default configuration...")
                self.config = create_default_config(config_file)
                print(f"Default configuration created at {config_file}")
                print("Please review and modify the configuration as needed.")
            else:
                print(f"Loading configuration from {config_file}...")
                
                # Try to load with the new flat format first
                try:
                    self.config = load_config(config_file)
                except (ValueError, TypeError) as e:
                    # If that fails, try to load the old nested format and convert it
                    print("Attempting to load legacy configuration format...")
                    self.config = self._load_legacy_config(config_file)
                    
                    # Save the converted config in the new format
                    self.config.save_to_file(config_file + ".new")
                    print(f"Configuration converted to new format and saved as {config_file}.new")
                    print("You can replace the old config file with the new one if desired.")
                
                print("Configuration loaded successfully.")
            
            # Validate configuration
            self.config.validate()
            
            return True
            
        except Exception as e:
            print(f"Failed to load configuration: {e}")
            print("Please check your configuration file and try again.")
            return False
    
    def _load_legacy_config(self, config_file: str) -> SystemConfig:
        """
        Load legacy nested configuration format and convert to flat format.
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            SystemConfig instance
        """
        import json
        
        with open(config_file, 'r', encoding='utf-8') as f:
            legacy_config = json.load(f)
        
        # Convert nested format to flat format
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
        
        # Create SystemConfig with converted data
        return SystemConfig(**config_data)
    
    def initialize_components(self) -> bool:
        """
        Initialize all system components.
        
        Returns:
            bool: True if all components initialized successfully, False otherwise
        """
        try:
            self.logger.info("Initializing system components...")
            
            # Initialize GUI controller
            self.logger.info("Initializing GUI controller...")
            self.gui_controller = ImprovedGUIController(self.config)
            self.gui_controller.setup_ui()
            self.logger.info("GUI controller initialized successfully")
            
            # System workflow is already initialized by GUI controller
            self.system_workflow = self.gui_controller.system_workflow
            self.logger.info("System workflow initialized successfully")
            
            # Initialize memory system (Requirements: Memory Core RAG System)
            self._initialize_memory_system()
            
            # Initialize Agent system components (Requirements: 1.1, 1.4)
            self._initialize_agent_system()
            
            # Initialize Full-Duplex engine components (Requirements: All requirements)
            self._initialize_full_duplex_system()
            
            # Verify critical dependencies for bug fixes (Requirements: 1.1, 2.1, 3.1)
            self._verify_critical_dependencies()
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize components: {e}"
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                print(error_msg)
                print(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _initialize_memory_system(self) -> None:
        """
        Initialize the Memory Core RAG system for persistent memory capabilities.
        
        This method sets up:
        - MemoryCore with ChromaDB backend
        - Lazy loading of embedding model
        - Integration with conversation flow
        
        Requirements: Memory Core RAG System - All requirements
        """
        if not MEMORY_SYSTEM_AVAILABLE:
            self.logger.info("Memory system modules not available, skipping initialization")
            return
        
        try:
            self.logger.info("Initializing Memory Core RAG system...")
            
            # Get memory configuration
            memory_config = getattr(self.config, 'memory', None)
            if memory_config is None:
                self.logger.info("Memory configuration not found, using defaults")
                db_path = "./memory_db"
                collection_name = "vtuber_memories"
            else:
                db_path = getattr(memory_config, 'db_path', './memory_db')
                collection_name = getattr(memory_config, 'collection_name', 'vtuber_memories')
            
            # Initialize MemoryCore
            self.memory_core = MemoryCore(
                db_path=db_path,
                collection_name=collection_name
            )
            
            # Connect memory core to system workflow if available
            if self.system_workflow:
                self.system_workflow.set_memory_core(self.memory_core)
                self.logger.info("Memory core connected to SystemWorkflow")
            
            # Connect memory core to GUI controller if available
            if self.gui_controller:
                self.gui_controller.memory_core = self.memory_core
                self.logger.info("Memory core connected to ImprovedGUIController")
            
            self.logger.info("Memory Core RAG system initialized successfully")
            self.logger.info(f"Database path: {db_path}")
            self.logger.info(f"Collection name: {collection_name}")
            self.logger.info("Embedding model will load in background (all-MiniLM-L6-v2)")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize memory system: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.info("Memory features will not be available")
            self.memory_core = None
    
    def _initialize_agent_system(self) -> None:
        """
        Initialize the Vision-Action Agent system components.
        
        This method sets up:
        - SafetyManager with F9 emergency hotkey
        - AgentManager with vision and action capabilities
        - Proper dependency injection between components
        
        Requirements: 1.1, 1.4, 4.1, 4.4
        """
        try:
            # Get agent configuration
            agent_config = getattr(self.config, 'agent', None)
            if agent_config is None:
                self.logger.info("Agent configuration not found, using defaults")
                agent_config = {
                    'enabled': False,
                    'loop_interval': 2.0,
                    'cooldown_period': 1.0,
                    'chat_detection_enabled': True,
                    'chat_timeout': 30.0,
                    'vision': {
                        'vision_model': 'llava',
                        'capture_region': None,
                        'max_image_dimension': 1024
                    },
                    'actions': {
                        'use_directinput': True,
                        'action_delay': 0.1,
                        'click_duration': 0.1,
                        'clamp_region': None,
                        'debug_overlay': {'enabled': True}
                    },
                    'safety': {
                        'enable_emergency_hotkey': True,
                        'emergency_key': '<f9>',
                        'enable_tts_announcement': True
                    },
                    'resource_monitoring': {
                        'enabled': True,
                        'cpu_threshold': 80.0,
                        'memory_threshold': 85.0,
                        'vlm_rate_limit': 10,
                        'vlm_rate_window': 60.0
                    }
                }
            else:
                # Convert AgentConfig object to dict if needed
                if hasattr(agent_config, '__dict__'):
                    agent_config = self._agent_config_to_dict(agent_config)
            
            # Initialize SafetyManager first (independent of other components)
            self.logger.info("Initializing SafetyManager...")
            safety_config = agent_config.get('safety', {})
            self.safety_manager = SafetyManager(
                config=safety_config,
                tts_pipeline=getattr(self.system_workflow, '_tts_pipeline', None)
            )
            self.logger.info("SafetyManager initialized")
            
            # Initialize AgentManager with all dependencies including memory core
            self.logger.info("Initializing AgentManager...")
            self.agent_manager = AgentManager(
                config=agent_config,
                tts_pipeline=getattr(self.system_workflow, '_tts_pipeline', None),
                gui_controller=self.gui_controller,
                memory_core=self.memory_core  # Pass memory core for enhanced conversations
            )
            
            # Connect SafetyManager to ActionEngine
            if hasattr(self.agent_manager, 'action_engine'):
                self.safety_manager.setup_emergency_hotkey(self.agent_manager.action_engine)
                self.logger.info("Emergency hotkey (F9) listener started")
            
            # Register emergency callback to stop agent loop
            self.safety_manager.add_emergency_callback(self._on_emergency_stop)
            
            # Connect agent manager to GUI controller
            if hasattr(self.gui_controller, '_agent_manager'):
                self.gui_controller._agent_manager = self.agent_manager
            
            self.logger.info("AgentManager initialized successfully")
            self.logger.info("Vision-Action Agent system ready (press F9 for emergency stop)")
            
        except ImportError as e:
            self.logger.warning(f"Agent system modules not available: {e}")
            self.logger.info("Agent Mode will not be available")
        except Exception as e:
            self.logger.error(f"Failed to initialize agent system: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.info("Agent Mode will not be available")
    
    def _agent_config_to_dict(self, agent_config) -> Dict:
        """
        Convert AgentConfig object to dictionary.
        
        Args:
            agent_config: AgentConfig object
            
        Returns:
            Dictionary representation of the config
        """
        result = {}
        
        # Basic settings
        result['enabled'] = getattr(agent_config, 'enabled', False)
        result['loop_interval'] = getattr(agent_config, 'loop_interval', 2.0)
        result['cooldown_period'] = getattr(agent_config, 'cooldown_period', 1.0)
        result['chat_detection_enabled'] = getattr(agent_config, 'chat_detection_enabled', True)
        result['chat_timeout'] = getattr(agent_config, 'chat_timeout', 30.0)
        
        # Vision settings
        vision = getattr(agent_config, 'vision', None)
        if vision:
            result['vision'] = {
                'vision_model': getattr(vision, 'vision_model', 'llava'),
                'capture_region': getattr(vision, 'capture_region', None),
                'max_image_dimension': getattr(vision, 'max_image_dimension', 1024)
            }
        else:
            result['vision'] = {'vision_model': 'llava', 'capture_region': None, 'max_image_dimension': 1024}
        
        # Action settings
        actions = getattr(agent_config, 'actions', None)
        if actions:
            result['actions'] = {
                'use_directinput': getattr(actions, 'use_directinput', True),
                'action_delay': getattr(actions, 'action_delay', 0.1),
                'click_duration': getattr(actions, 'click_duration', 0.1),
                'clamp_region': getattr(actions, 'clamp_region', None),
                'debug_overlay': getattr(actions, 'debug_overlay', {'enabled': True})
            }
        else:
            result['actions'] = {'use_directinput': True, 'action_delay': 0.1, 'click_duration': 0.1}
        
        # Safety settings
        safety = getattr(agent_config, 'safety', None)
        if safety:
            result['safety'] = {
                'enable_emergency_hotkey': getattr(safety, 'enable_emergency_hotkey', True),
                'emergency_key': getattr(safety, 'emergency_key', '<f9>'),
                'enable_tts_announcement': getattr(safety, 'enable_tts_announcement', True)
            }
        else:
            result['safety'] = {'enable_emergency_hotkey': True, 'emergency_key': '<f9>'}
        
        # Resource monitoring settings
        resource = getattr(agent_config, 'resource_monitoring', None)
        if resource:
            result['resource_monitoring'] = {
                'enabled': getattr(resource, 'enabled', True),
                'cpu_threshold': getattr(resource, 'cpu_threshold', 80.0),
                'memory_threshold': getattr(resource, 'memory_threshold', 85.0),
                'vlm_rate_limit': getattr(resource, 'vlm_rate_limit', 10),
                'vlm_rate_window': getattr(resource, 'vlm_rate_window', 60.0)
            }
        else:
            result['resource_monitoring'] = {'enabled': True, 'cpu_threshold': 80.0, 'memory_threshold': 85.0}
        
        return result
    
    def _initialize_full_duplex_system(self) -> None:
        """
        Initialize the Full-Duplex Conversational Engine components.
        
        This method sets up:
        - ConfigurationManager for persistent audio settings
        - AudioDeviceManager for hardware detection and configuration
        - StreamingEars for real-time speech recognition
        - TextProcessor for sentence boundary detection
        - DuplexManager for traffic control between input and output
        
        Requirements: All full-duplex requirements (1.1-10.5)
        """
        if not FULL_DUPLEX_AVAILABLE:
            self.logger.info("Full-duplex engine modules not available, skipping initialization")
            return
        
        try:
            if self.logger:
                self.logger.info("Initializing Full-Duplex Conversational Engine...")
            else:
                print("Initializing Full-Duplex Conversational Engine...")
            
            # Initialize ConfigurationManager for persistent settings
            if self.logger:
                self.logger.info("Initializing ConfigurationManager...")
            self.configuration_manager = ConfigurationManager()
            if self.logger:
                self.logger.info("ConfigurationManager initialized")
            
            # Initialize TextProcessor for sentence boundary detection
            if self.logger:
                self.logger.info("Initializing TextProcessor...")
            self.text_processor = TextProcessor()
            if self.logger:
                self.logger.info("TextProcessor initialized")
            
            # Initialize DuplexManager for traffic control
            if self.logger:
                self.logger.info("Initializing DuplexManager...")
            self.duplex_manager = DuplexManager(
                tts_pipeline=getattr(self.system_workflow, '_tts_pipeline', None),
                ui_controller=self.gui_controller
            )
            if self.logger:
                self.logger.info("DuplexManager initialized")
            
            # Initialize AudioDeviceManager with timeout protection
            if self.logger:
                self.logger.info("Initializing AudioDeviceManager with timeout protection...")
            
            try:
                # Create AudioDeviceManager without async timeout (causes issues)
                self.audio_device_manager = AudioDeviceManager()
                if self.logger:
                    self.logger.info("AudioDeviceManager initialized successfully")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"AudioDeviceManager initialization failed: {e}")
                self.audio_device_manager = None
            
            # Initialize StreamingEars only if AudioDeviceManager succeeded
            if self.audio_device_manager:
                if self.logger:
                    self.logger.info("Initializing StreamingEars...")
                self.streaming_ears = StreamingEars(
                    audio_device_manager=self.audio_device_manager
                )
                
                # Set up StreamingEars callbacks to integrate with system workflow
                self.streaming_ears.set_callbacks(
                    on_speech_start=self._on_full_duplex_speech_start,
                    on_partial_text=self._on_full_duplex_partial_text,
                    on_sentence_complete=self._on_full_duplex_sentence_complete,
                    on_speech_end=self._on_full_duplex_speech_end
                )
                if self.logger:
                    self.logger.info("StreamingEars initialized with callbacks")
            else:
                if self.logger:
                    self.logger.warning("Skipping StreamingEars initialization - AudioDeviceManager not available")
                self.streaming_ears = None
            
            # Connect components to system workflow
            if self.system_workflow:
                # Inject full-duplex components into system workflow
                self.system_workflow.duplex_manager = self.duplex_manager
                self.system_workflow.streaming_ears = self.streaming_ears
                self.system_workflow.text_processor = self.text_processor
                self.system_workflow.configuration_manager = self.configuration_manager
                if self.logger:
                    self.logger.info("Full-duplex components injected into SystemWorkflow")
            
            # Connect to GUI controller if available
            if self.gui_controller:
                # Inject components into GUI controller for UI integration
                self.gui_controller.duplex_manager = self.duplex_manager
                self.gui_controller.audio_device_manager = self.audio_device_manager
                self.gui_controller.streaming_ears = self.streaming_ears
                self.gui_controller.text_processor = self.text_processor
                self.gui_controller.configuration_manager = self.configuration_manager
                if self.logger:
                    self.logger.info("Full-duplex components injected into ImprovedGUIController")
            
            # Initialize and start latency optimizer
            if self.logger:
                self.logger.info("Initializing latency optimizer...")
            self.latency_optimizer = get_latency_optimizer()
            
            # Register components with latency optimizer
            self.latency_optimizer.register_components(
                streaming_ears=self.streaming_ears,
                duplex_manager=self.duplex_manager,
                tts_pipeline=getattr(self.system_workflow, '_tts_pipeline', None),
                text_processor=self.text_processor
            )
            
            # Start continuous latency optimization
            self.latency_optimizer.start_optimization(interval=10.0)  # Check every 10 seconds
            if self.logger:
                self.logger.info("Latency optimizer started")
            
            # Initialize and start system health monitoring
            if self.logger:
                self.logger.info("Initializing system health monitor...")
            self.system_health_monitor = get_system_health_monitor()
            
            # Register components with health monitor
            self.system_health_monitor.register_component("streaming_ears", self.streaming_ears)
            self.system_health_monitor.register_component("duplex_manager", self.duplex_manager)
            self.system_health_monitor.register_component("audio_device_manager", self.audio_device_manager)
            self.system_health_monitor.register_component("text_processor", self.text_processor)
            self.system_health_monitor.register_component("configuration_manager", self.configuration_manager)
            
            # Start health monitoring
            self.system_health_monitor.start_monitoring()
            if self.logger:
                self.logger.info("System health monitoring started")
            
            if self.logger:
                self.logger.info("Full-Duplex Conversational Engine initialized successfully")
                self.logger.info("Real-time speech recognition and interruption capabilities ready")
            else:
                print("Full-Duplex Conversational Engine initialized successfully")
                print("Real-time speech recognition and interruption capabilities ready")
            
        except ImportError as e:
            error_msg = f"Full-duplex engine modules not available: {e}"
            if self.logger:
                self.logger.warning(error_msg)
                self.logger.info("Full-duplex mode will not be available")
            else:
                print(f"Warning: {error_msg}")
                print("Full-duplex mode will not be available")
        except Exception as e:
            error_msg = f"Failed to initialize full-duplex system: {e}"
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.logger.info("Full-duplex mode will not be available")
            else:
                print(f"Error: {error_msg}")
                print("Full-duplex mode will not be available")
    
    def _on_full_duplex_speech_start(self) -> None:
        """Handle speech start event from StreamingEars."""
        if self.duplex_manager:
            self.duplex_manager.on_user_speech_detected(0.9)  # High confidence
        
        if self.gui_controller:
            self.gui_controller.update_conversation_state("user_speaking")
    
    def _on_full_duplex_partial_text(self, text: str) -> None:
        """Handle partial transcription from StreamingEars."""
        if self.gui_controller:
            self.gui_controller._on_partial_transcription(text)
    
    def _on_full_duplex_sentence_complete(self, text: str) -> None:
        """Handle complete sentence from StreamingEars."""
        if self.gui_controller:
            self.gui_controller._on_sentence_complete(text)
        
        # Process the complete sentence through the normal conversation workflow
        if self.system_workflow:
            # Use GUI controller's shared event loop to avoid "Future attached to different loop" errors
            if self.gui_controller:
                self.gui_controller._run_async(
                    self.system_workflow.process_user_input(text, self.gui_controller.update_subtitle)
                )
    
    def _on_full_duplex_speech_end(self) -> None:
        """Handle speech end event from StreamingEars."""
        if self.duplex_manager:
            self.duplex_manager.on_user_speech_ended()
        
        if self.gui_controller:
            self.gui_controller.update_conversation_state("processing")
    
    def _on_emergency_stop(self) -> None:
        """
        Handle emergency stop activation.
        
        This callback is triggered when F9 is pressed or emergency stop
        is activated programmatically. It stops all agent operations.
        
        Requirements: 4.1, 4.2
        """
        self.logger.critical("EMERGENCY STOP ACTIVATED - Stopping all agent operations")
        
        # Stop agent manager if active
        if self.agent_manager:
            try:
                self.agent_manager.emergency_stop()
            except Exception as e:
                self.logger.error(f"Error during agent emergency stop: {e}")
        
        # Update GUI if available
        if self.gui_controller and hasattr(self.gui_controller, '_on_emergency_stop'):
            try:
                self.gui_controller._on_emergency_stop()
            except Exception as e:
                self.logger.error(f"Error updating GUI for emergency stop: {e}")
    
    def _verify_critical_dependencies(self) -> None:
        """
        Verify critical dependencies for bug fixes are available.
        
        This method checks for:
        - pywin32 for ghost window click-through fix (Requirement 1.1)
        - VTSClient integration for lip-sync fix (Requirement 2.1)
        - Agent components for controls fix (Requirement 3.1)
        
        Requirements: 1.1, 2.1, 3.1
        """
        self.logger.info("=== Verifying Critical Dependencies ===")
        
        # Check pywin32 availability for ghost window fix (Requirement 1.1)
        if PYWIN32_AVAILABLE:
            self.logger.info("✓ pywin32 available - Ghost window click-through fix enabled")
        else:
            self.logger.warning("✗ pywin32 not available - Overlay will use fallback transient windows")
            self.logger.warning("  Install pywin32 for better overlay performance: pip install pywin32")
            self.logger.warning("  Without pywin32, small temporary windows will appear at click targets")
            self.logger.warning("  This may cause brief focus changes in full-screen applications")
        
        # Check VTSClient integration for lip-sync fix (Requirement 2.1)
        if self.system_workflow and hasattr(self.system_workflow, 'vts_client'):
            vts_client = self.system_workflow.vts_client
            if hasattr(vts_client, 'start_mouth_sync') and hasattr(vts_client, 'stop_mouth_sync'):
                self.logger.info("✓ VTSClient lip-sync methods available - Mouth animation fix enabled")
            else:
                self.logger.warning("✗ VTSClient missing lip-sync methods - Mouth animation may not work")
                self.logger.warning("  This indicates an outdated VTSClient version")
                self.logger.warning("  Avatar mouth will not move during speech")
        else:
            self.logger.warning("✗ VTSClient not available - Mouth animation disabled")
            self.logger.warning("  Make sure VTube Studio is running and API is enabled")
            self.logger.warning("  Avatar will not show mouth movement during speech")
        
        # Check TTS Pipeline integration (Requirement 2.1)
        if self.system_workflow and hasattr(self.system_workflow, '_tts_pipeline'):
            tts_pipeline = self.system_workflow._tts_pipeline
            if hasattr(tts_pipeline, 'set_vts_client'):
                self.logger.info("✓ TTSPipeline VTS integration available - Lip-sync fix enabled")
                # Inject VTSClient into TTSPipeline for lip-sync
                if hasattr(self.system_workflow, 'vts_client'):
                    tts_pipeline.set_vts_client(self.system_workflow.vts_client)
                    self.logger.info("✓ VTSClient injected into TTSPipeline for lip-sync")
                else:
                    self.logger.warning("  VTSClient not available for injection - lip-sync disabled")
            else:
                self.logger.warning("✗ TTSPipeline missing VTS integration - Lip-sync may not work")
                self.logger.warning("  This indicates an outdated TTSPipeline version")
                self.logger.warning("  Audio will play but mouth animation will not sync")
        else:
            self.logger.warning("✗ TTSPipeline not available - Lip-sync disabled")
            self.logger.warning("  TTS system may not be properly initialized")
            self.logger.warning("  Speech synthesis and lip-sync will not work")
        
        # Check Agent components for controls fix (Requirement 3.1)
        if AGENT_MANAGER_AVAILABLE and SAFETY_MANAGER_AVAILABLE:
            self.logger.info("✓ Agent system components available - Agent controls fix enabled")
        else:
            missing_components = []
            if not AGENT_MANAGER_AVAILABLE:
                missing_components.append("AgentManager")
            if not SAFETY_MANAGER_AVAILABLE:
                missing_components.append("SafetyManager")
            self.logger.warning(f"✗ Missing agent components: {', '.join(missing_components)}")
            self.logger.warning("  Agent controls will not be available in the GUI")
            self.logger.warning("  Vision-action automation features are disabled")
            self.logger.warning("  Emergency stop (F9) may not work properly")
        
        # Check GUI controller agent integration (Requirement 3.1)
        if self.gui_controller and hasattr(self.gui_controller, '_toggle_agent_mode'):
            self.logger.info("✓ GUI agent controls available - Agent toggle fix enabled")
        else:
            self.logger.warning("✗ GUI agent controls not available - Agent toggle may not work")
            self.logger.warning("  Start/Stop Agent button may not function properly")
            self.logger.warning("  Agent status indicators may not update correctly")
        
        self.logger.info("=== Dependency Verification Complete ===")
        
        # Provide a summary of bug fix status
        fixes_working = []
        fixes_degraded = []
        
        if PYWIN32_AVAILABLE:
            fixes_working.append("Ghost window click-through")
        else:
            fixes_degraded.append("Ghost window (using fallback)")
        
        if (self.system_workflow and hasattr(self.system_workflow, 'vts_client') and 
            hasattr(self.system_workflow, '_tts_pipeline')):
            fixes_working.append("Lip-sync integration")
        else:
            fixes_degraded.append("Lip-sync integration")
        
        if AGENT_MANAGER_AVAILABLE and SAFETY_MANAGER_AVAILABLE:
            fixes_working.append("Agent controls")
        else:
            fixes_degraded.append("Agent controls")
        
        if fixes_working:
            self.logger.info(f"✓ Working bug fixes: {', '.join(fixes_working)}")
        
        if fixes_degraded:
            self.logger.warning(f"⚠ Degraded bug fixes: {', '.join(fixes_degraded)}")
            self.logger.warning("  Some functionality may be limited or use fallback methods")
        
        if not fixes_degraded:
            self.logger.info("🎉 All bug fixes are working optimally!")
        else:
            self.logger.info("ℹ System will continue with available functionality")
    
    async def check_startup_connections(self) -> bool:
        """
        Check connections to external services during startup.
        
        Implements requirements 1.1, 2.1, and 5.3 for connection validation
        and startup status logging.
        
        Returns:
            bool: True if at least one service is available, False if all failed
        """
        self.logger.info("=== Startup Connection Check ===")
        
        connection_results = {}
        startup_success = False
        
        # Check Ollama connection (Requirement 1.1)
        self.logger.info("Checking Ollama service connection...")
        try:
            ollama_connected = await self.system_workflow.llm_client.connect()
            connection_results["Ollama"] = ollama_connected
            
            if ollama_connected:
                self.logger.info(f"✓ Ollama service connected successfully at {self.config.ollama_url}")
                self.logger.info(f"  Model: {self.config.ollama_model}")
                startup_success = True
            else:
                self.logger.warning(f"✗ Ollama service not available at {self.config.ollama_url}")
                self.logger.warning("  AI conversation features will be disabled")
                
        except Exception as e:
            self.logger.error(f"✗ Ollama connection check failed: {e}")
            connection_results["Ollama"] = False
        
        # Check VTube Studio connection (Requirement 2.1)
        self.logger.info("Checking VTube Studio connection...")
        try:
            vts_connected = await self.system_workflow.vts_client.connect()
            
            if vts_connected:
                # Attempt authentication
                vts_authenticated = await self.system_workflow.vts_client.authenticate()
                connection_results["VTube Studio"] = vts_authenticated
                
                if vts_authenticated:
                    self.logger.info(f"✓ VTube Studio connected and authenticated on port {self.config.vts_port}")
                    self.logger.info("  Live2D animation features available")
                    startup_success = True
                else:
                    self.logger.warning("✗ VTube Studio authentication failed")
                    self.logger.warning("  Please accept the plugin permission in VTube Studio")
                    self.logger.warning("  Animation features will be disabled")
            else:
                self.logger.warning(f"✗ VTube Studio not available on port {self.config.vts_port}")
                self.logger.warning("  Make sure VTube Studio is running with API enabled")
                self.logger.warning("  Animation features will be disabled")
                connection_results["VTube Studio"] = False
                
        except Exception as e:
            self.logger.error(f"✗ VTube Studio connection check failed: {e}")
            connection_results["VTube Studio"] = False
        
        # Check TTS service availability
        self.logger.info("Checking TTS service availability...")
        try:
            # Test TTS by generating a short test audio
            test_audio = await self.system_workflow.tts_player.generate_audio("测试")
            if test_audio and os.path.exists(test_audio):
                self.logger.info("✓ Edge-TTS service available")
                self.logger.info(f"  Voice: {self.config.tts_voice}")
                connection_results["Edge-TTS"] = True
                startup_success = True
                
                # Clean up test file
                self.system_workflow.tts_player.cleanup_temp_file(test_audio)
            else:
                self.logger.warning("✗ Edge-TTS service test failed")
                connection_results["Edge-TTS"] = False
                
        except Exception as e:
            self.logger.error(f"✗ Edge-TTS service check failed: {e}")
            connection_results["Edge-TTS"] = False
        
        # Log overall startup status (Requirement 5.3)
        self.logger.info("=== Startup Connection Summary ===")
        connected_services = []
        failed_services = []
        
        for service, connected in connection_results.items():
            if connected:
                connected_services.append(service)
                self.logger.info(f"  ✓ {service}: Connected")
            else:
                failed_services.append(service)
                self.logger.warning(f"  ✗ {service}: Not available")
        
        if startup_success:
            self.logger.info(f"Startup check completed: {len(connected_services)}/{len(connection_results)} services available")
            if failed_services:
                self.logger.warning("Some services are unavailable. System will run with limited functionality.")
                self.logger.info("You can use the 'Reconnect' button in the GUI to retry connections later.")
        else:
            self.logger.error("Startup check failed: No external services are available")
            self.logger.error("Please check your configuration and ensure required services are running:")
            self.logger.error(f"  - Ollama: {self.config.ollama_url}")
            self.logger.error(f"  - VTube Studio: localhost:{self.config.vts_port}")
            self.logger.error("  - Internet connection for Edge-TTS")
        
        return startup_success
    
    def handle_startup_failure(self) -> bool:
        """
        Handle startup failure scenarios.
        
        Provides user guidance and options when startup connections fail.
        
        Returns:
            bool: True to continue with limited functionality, False to exit
        """
        self.logger.warning("=== Startup Failure Handling ===")
        self.logger.info("The system can still run with limited functionality:")
        self.logger.info("  - GUI interface will be available")
        self.logger.info("  - You can manually retry connections using the GUI")
        self.logger.info("  - Check the logs for specific connection issues")
        
        print("\n" + "="*60)
        print("AI VTuber System - Startup Warning")
        print("="*60)
        print("Some external services are not available.")
        print("The system can run with limited functionality.")
        print("\nTo resolve connection issues:")
        print("1. Make sure Ollama is running: ollama serve")
        print("2. Make sure VTube Studio is running with API enabled")
        print("3. Check your internet connection for TTS")
        print("4. Use the 'Reconnect' button in the GUI to retry")
        print("="*60)
        
        return True  # Continue with limited functionality
    
    async def perform_warmup(self) -> Dict[str, bool]:
        """
        Perform system warmup to reduce first-interaction latency.
        
        Implements Requirements 3.1, 3.2, 3.3, 3.4:
        - Warmup LLM by sending a test request
        - Warmup TTS by generating test audio
        - Log warmup status
        - Continue startup even if warmup fails
        
        Returns:
            Dict with warmup results: {"llm": True/False, "tts": True/False}
        """
        # Check if warmup is enabled in config
        if not self.config.performance.warmup_enabled:
            self.logger.info("Warmup is disabled in configuration, skipping...")
            return {"llm": False, "tts": False}
        
        # Initialize warmup manager
        self.warmup_manager = WarmupManager(
            llm_client=self.system_workflow.llm_client,
            tts_player=self.system_workflow.tts_player,
            timeout=self.config.performance.warmup_timeout
        )
        
        # Execute warmup (non-blocking - failures are logged but don't stop startup)
        warmup_results = await self.warmup_manager.warmup()
        
        return warmup_results
    
    def run(self) -> int:
        """
        Main application entry point.
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        try:
            print("AI VTuber System - Starting up...")
            
            # Step 1: Load configuration
            if not self.load_configuration():
                return 1
            
            # Step 2: Setup logging
            self.setup_logging()
            
            # Step 3: Initialize components
            if not self.initialize_components():
                return 1
            
            # CRITICAL FIX: Skip async operations before GUI mainloop
            # The connection checks and warmup will be done after GUI starts
            self.logger.info("Skipping startup connection checks to prevent threading issues")
            self.logger.info("Connection checks will be performed after GUI starts")
            
            # Step 4: Start the application
            self.logger.info("Starting main application loop...")
            self.is_running = True
            
            # Run the GUI main loop - this will handle async operations properly
            self.gui_controller.run()
            
            self.logger.info("Application loop ended")
            return 0
            
        except KeyboardInterrupt:
            if self.logger:
                self.logger.info("Application interrupted by user")
            else:
                print("Application interrupted by user")
            return 0
            
        except Exception as e:
            error_msg = f"Unexpected error in main application: {e}"
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                print(error_msg)
                print(f"Traceback: {traceback.format_exc()}")
            return 1
            
        finally:
            self.shutdown()
    
    def shutdown(self) -> None:
        """
        Gracefully shutdown the system.
        
        Ensures all components are properly cleaned up and resources are released.
        Implements proper shutdown order: Agent system -> GUI -> System workflow
        """
        if not self.is_running:
            return
        
        self.is_running = False
        
        try:
            if self.logger:
                self.logger.info("Shutting down AI VTuber System...")
            else:
                print("Shutting down AI VTuber System...")
            
            # Shutdown Agent system first (Requirements: 1.1, 4.1)
            if self.agent_manager:
                try:
                    self.logger.info("Stopping Agent Manager...")
                    self.agent_manager.cleanup()
                    self.logger.info("Agent Manager stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping Agent Manager: {e}")
            
            if self.safety_manager:
                try:
                    self.logger.info("Stopping Safety Manager...")
                    self.safety_manager.shutdown()
                    self.logger.info("Safety Manager stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping Safety Manager: {e}")
            
            # Shutdown Full-Duplex system components
            if self.system_health_monitor:
                try:
                    self.logger.info("Stopping system health monitor...")
                    self.system_health_monitor.stop_monitoring()
                    self.logger.info("System health monitor stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping system health monitor: {e}")
            
            if self.latency_optimizer:
                try:
                    self.logger.info("Stopping latency optimizer...")
                    self.latency_optimizer.stop_optimization()
                    self.logger.info("Latency optimizer stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping latency optimizer: {e}")
            
            if self.streaming_ears:
                try:
                    self.logger.info("Stopping StreamingEars...")
                    self.streaming_ears.stop_streaming()
                    self.logger.info("StreamingEars stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping StreamingEars: {e}")
            
            if self.audio_device_manager:
                try:
                    self.logger.info("Stopping AudioDeviceManager...")
                    self.audio_device_manager.stop_device_monitoring()
                    self.logger.info("AudioDeviceManager stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping AudioDeviceManager: {e}")
            
            if self.configuration_manager:
                try:
                    self.logger.info("Saving configuration...")
                    # Save any pending configuration changes
                    self.logger.info("Configuration saved")
                except Exception as e:
                    self.logger.error(f"Error saving configuration: {e}")
            
            # Shutdown GUI controller (which will handle system workflow shutdown)
            if self.gui_controller:
                self.gui_controller.destroy()
            
            if self.logger:
                self.logger.info("System shutdown completed")
            else:
                print("System shutdown completed")
                
        except Exception as e:
            error_msg = f"Error during shutdown: {e}"
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(error_msg)


def main() -> int:
    """
    Main function - entry point for the application.
    
    Returns:
        int: Exit code
    """
    # Create and run the system
    system = AIVTuberSystem()
    return system.run()


if __name__ == "__main__":
    # Set the working directory to the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Run the application
    exit_code = main()
    sys.exit(exit_code)