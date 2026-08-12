"""
Logging Configuration for Full-Duplex Conversational Engine

Provides specialized logging configuration for audio processing components
with performance-optimized settings and structured output.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional

def setup_audio_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_performance_logging: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for audio processing components.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path (defaults to logs/full_duplex_engine.log)
        enable_performance_logging: Enable detailed performance metrics logging
    
    Returns:
        Configured logger instance
    """
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Default log file path
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(log_dir, f"full_duplex_engine_{timestamp}.log")
    
    # Create logger
    logger = logging.getLogger("full_duplex_engine")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Performance logging handler (if enabled)
    if enable_performance_logging:
        perf_log_file = os.path.join(log_dir, f"performance_{timestamp}.log")
        perf_handler = logging.handlers.RotatingFileHandler(
            filename=perf_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.DEBUG)
        perf_handler.setFormatter(detailed_formatter)
        
        # Create performance logger
        perf_logger = logging.getLogger("full_duplex_engine.performance")
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.DEBUG)
    
    logger.info(f"Audio processing logging configured - Level: {log_level}, File: {log_file}")
    return logger

def get_component_logger(component_name: str) -> logging.Logger:
    """
    Get a logger for a specific component.
    
    Args:
        component_name: Name of the component (e.g., 'streaming_ears', 'duplex_manager')
    
    Returns:
        Component-specific logger
    """
    return logging.getLogger(f"full_duplex_engine.{component_name}")

def log_performance_metric(
    component: str,
    metric_name: str,
    value: float,
    unit: str = "ms",
    context: Optional[dict] = None
) -> None:
    """
    Log a performance metric with structured format.
    
    Args:
        component: Component name
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        context: Additional context information
    """
    perf_logger = logging.getLogger("full_duplex_engine.performance")
    
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items()]
        context_str = f" | {' | '.join(context_items)}"
    
    perf_logger.debug(f"PERF | {component} | {metric_name}={value}{unit}{context_str}")

class AudioProcessingFilter(logging.Filter):
    """Custom filter for audio processing logs to reduce noise."""
    
    def __init__(self, min_interval: float = 1.0):
        """
        Initialize filter.
        
        Args:
            min_interval: Minimum interval between similar log messages (seconds)
        """
        super().__init__()
        self.min_interval = min_interval
        self.last_log_times = {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records to reduce repetitive messages."""
        import time
        
        # Allow all non-DEBUG messages
        if record.levelno > logging.DEBUG:
            return True
        
        # For DEBUG messages, implement rate limiting
        message_key = f"{record.name}:{record.funcName}:{record.msg}"
        current_time = time.time()
        
        if message_key in self.last_log_times:
            if current_time - self.last_log_times[message_key] < self.min_interval:
                return False
        
        self.last_log_times[message_key] = current_time
        return True

# Initialize default logging when module is imported
_default_logger = None

def get_default_logger() -> logging.Logger:
    """Get the default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = setup_audio_logging()
    return _default_logger