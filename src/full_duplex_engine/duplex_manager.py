"""
DuplexManager Component

Traffic control for managing conflicts between AI speech output and user speech input.
Handles barge-in protocol and conversation state management.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging
import time

from .logging_config import get_component_logger
from .performance_monitor import PerformanceMonitor
from .error_handler import get_error_handler, ErrorSeverity, ErrorCategory

logger = get_component_logger("duplex_manager")

class ConversationState(Enum):
    """Conversation state enumeration."""
    IDLE = "idle"
    AI_SPEAKING = "ai_speaking"
    USER_SPEAKING = "user_speaking"
    PROCESSING = "processing"
    INTERRUPTED = "interrupted"

@dataclass
class ConversationContext:
    """Current conversation state and context."""
    state: ConversationState
    ai_speaking_start: Optional[float]
    user_speaking_start: Optional[float]
    last_interruption: Optional[float]
    accumulated_text: str
    partial_text: str

class DuplexManager:
    """Traffic control for managing audio input/output conflicts."""
    
    def __init__(self, tts_pipeline=None, ui_controller=None):
        """Initialize duplex manager with required components."""
        self.tts_pipeline = tts_pipeline
        self.ui_controller = ui_controller
        self.current_state = ConversationState.IDLE
        self.context = ConversationContext(
            state=ConversationState.IDLE,
            ai_speaking_start=None,
            user_speaking_start=None,
            last_interruption=None,
            accumulated_text="",
            partial_text=""
        )
        
        # Performance monitoring for interruption response time
        self.performance_monitor = PerformanceMonitor(history_size=500)
        
        # Comprehensive error handling
        self.error_handler = get_error_handler()
        
        logger.info("DuplexManager initialized")
    
    def on_user_speech_detected(self, confidence: float) -> None:
        """Handle user speech detection event."""
        logger.debug(f"User speech detected with confidence: {confidence}")
        
        if self.current_state == ConversationState.AI_SPEAKING:
            logger.info("Executing barge-in protocol - interrupting AI")
            self._execute_barge_in()
        
        self._transition_to_state(ConversationState.USER_SPEAKING)
    
    def on_user_speech_ended(self) -> None:
        """Handle end of user speech event."""
        logger.debug("User speech ended")
        self._transition_to_state(ConversationState.PROCESSING)
    
    def set_ai_speaking_state(self, is_speaking: bool) -> None:
        """Update AI speaking state."""
        if is_speaking:
            logger.debug("AI started speaking")
            self._transition_to_state(ConversationState.AI_SPEAKING)
        else:
            logger.debug("AI stopped speaking")
            self._transition_to_state(ConversationState.IDLE)
    
    def get_current_state(self) -> ConversationState:
        """Get current conversation state."""
        return self.current_state
    
    def _execute_barge_in(self) -> None:
        """Execute barge-in protocol when user interrupts AI."""
        # Start measuring interruption response time
        measurement_id = self.performance_monitor.start_measurement(
            "interruption", "barge_in_response",
            {"ai_speaking_duration": time.time() - (self.context.ai_speaking_start or time.time())}
        )
        
        logger.info("Executing barge-in protocol")
        
        try:
            # Stop AI audio output immediately
            if self.tts_pipeline:
                self.tts_pipeline.emergency_stop()
            
            # Update UI to show interrupted state
            if self.ui_controller:
                self.ui_controller.update_status("Listening (Interrupted)")
            
            # Update context
            self.context.last_interruption = time.time()
            self._transition_to_state(ConversationState.INTERRUPTED)
            
            # End measurement - this should be <200ms per requirements
            duration = self.performance_monitor.end_measurement(measurement_id)
            if duration and duration > 0.2:  # 200ms threshold
                logger.warning(f"Interruption response time exceeded threshold: {duration*1000:.1f}ms")
            else:
                logger.debug(f"Interruption response time: {duration*1000:.1f}ms" if duration else "unknown")
                
        except Exception as e:
            # Use comprehensive error handler
            self.error_handler.handle_error(
                component="duplex_manager",
                error_type="barge_in_execution_error",
                exception=e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.PROCESSING,
                metadata={"component_instance": self}
            )
            self.performance_monitor.end_measurement(measurement_id)
    
    def _transition_to_state(self, new_state: ConversationState) -> None:
        """Transition to a new conversation state."""
        old_state = self.current_state
        self.current_state = new_state
        self.context.state = new_state
        
        logger.debug(f"State transition: {old_state.value} -> {new_state.value}")
        
        # Update timestamps based on state
        current_time = time.time()
        
        if new_state == ConversationState.AI_SPEAKING:
            self.context.ai_speaking_start = current_time
        elif new_state == ConversationState.USER_SPEAKING:
            self.context.user_speaking_start = current_time
    
    def get_performance_metrics(self):
        """Get performance metrics from the duplex manager."""
        return self.performance_monitor.get_current_metrics()
    
    def get_interruption_statistics(self):
        """Get detailed interruption performance statistics."""
        stats = self.performance_monitor.get_detailed_statistics()
        return stats.get('component_latencies', {}).get('interruption', {})