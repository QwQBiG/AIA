"""
Agent Manager for AI VTuber Vision-Action Agent

This module orchestrates the agent loop and coordinates with existing systems,
managing dual-mode operation between Chat Mode and Agent Mode.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime

from .vision_client import VisionClient, AgentCommand
from .action_engine import ActionEngine, ActionResult
from .resource_monitor import ResourceMonitor
from .enhanced_llm_client import EnhancedLLMClient
from .memory_core.memory_core import MemoryCore


@dataclass
class AgentState:
    """Current state of the agent system"""
    mode: str  # "idle", "active", "paused", "emergency"
    current_objective: str
    loop_count: int
    last_action: Optional[AgentCommand]
    performance_metrics: Dict[str, Any]
    last_update: datetime
    
    # State preservation fields
    chat_mode_active: bool = False
    pending_actions: list = None
    saved_context: Dict[str, Any] = None
    transition_timestamp: Optional[datetime] = None
    previous_mode: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields"""
        if self.pending_actions is None:
            self.pending_actions = []
        if self.saved_context is None:
            self.saved_context = {}


class AgentManager:
    """Orchestrates the agent loop and coordinates with existing systems"""
    
    def __init__(self, config, tts_pipeline=None, gui_controller=None, memory_core: Optional[MemoryCore] = None):
        """
        Initialize AgentManager with configuration and system components
        
        Args:
            config: Configuration object (AgentConfig dataclass or dict) containing agent settings
            tts_pipeline: Existing TTS pipeline for commentary
            gui_controller: GUI controller for status updates
            memory_core: Memory core for enhanced conversations (optional)
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # System components
        self.tts_pipeline = tts_pipeline
        self.gui_controller = gui_controller
        self.memory_core = memory_core
        
        # Set up GUI state update callback
        if self.gui_controller and hasattr(self.gui_controller, 'update_agent_state_label'):
            self._gui_update_callback = self.gui_controller.update_agent_state_label
        else:
            self._gui_update_callback = None
        
        # Agent components - handle both dict and dataclass config
        if hasattr(config, '__dict__'):  # Dataclass
            vision_config = getattr(config, 'vision', {})
            action_config = getattr(config, 'actions', {})
            resource_config = getattr(config, 'resource_monitoring', {})
            llm_config = getattr(config, 'llm', {})
        else:  # Dict
            vision_config = config.get('vision', {})
            action_config = config.get('actions', {})
            resource_config = config.get('resource_monitoring', {})
            llm_config = config.get('llm', {})
        
        self.vision_client = VisionClient(vision_config)
        self.action_engine = ActionEngine(action_config)
        self.resource_monitor = ResourceMonitor(resource_config)
        
        # Initialize Enhanced LLM Client for memory-enhanced conversations
        if hasattr(llm_config, '__dict__'):  # Dataclass
            ollama_url = getattr(llm_config, 'base_url', 'http://localhost:11434')
            model_name = getattr(llm_config, 'model', 'llama3')
            enable_memory = getattr(llm_config, 'enable_memory', True)
        else:  # Dict
            ollama_url = llm_config.get('base_url', 'http://localhost:11434')
            model_name = llm_config.get('model', 'llama3')
            enable_memory = llm_config.get('enable_memory', True)
        
        self.llm_client = EnhancedLLMClient(
            base_url=ollama_url,
            model=model_name,
            memory_core=self.memory_core,
            enable_memory=enable_memory
        )
        
        self.logger.info(f"Enhanced LLM Client initialized: {model_name} at {ollama_url}, memory={'enabled' if enable_memory else 'disabled'}")
        
        # Reflex Engine (optional, initialized when needed)
        self.reflex_engine: Optional[Any] = None
        self._reflex_feedback_queue = []
        
        # Loop control
        self.loop_active = False
        self.loop_thread: Optional[threading.Thread] = None
        self.loop_interval = config.get('loop_interval', 2.0)  # seconds
        self.cooldown_period = config.get('cooldown_period', 1.0)  # seconds
        
        # Priority system for chat interruption
        self.chat_priority_event = threading.Event()
        self.chat_priority_event.set()  # Start allowing agent operations
        
        # Action cycle tracking for graceful shutdown
        self._current_action_active = False
        
        # Chat priority detection
        self._chat_detection_enabled = config.get('chat_detection_enabled', True)
        self._last_chat_time = None
        self._chat_timeout = config.get('chat_timeout', 30.0)  # Resume agent after timeout
        
        # State tracking
        self.agent_state = AgentState(
            mode="idle",
            current_objective="Waiting for activation",
            loop_count=0,
            last_action=None,
            performance_metrics={},
            last_update=datetime.now(),
            chat_mode_active=False,
            pending_actions=[],
            saved_context={},
            transition_timestamp=None,
            previous_mode=None
        )
        
        # Performance tracking
        self.performance_metrics = {
            'total_cycles': 0,
            'successful_actions': 0,
            'failed_actions': 0,
            'vision_failures': 0,
            'action_failures': 0,
            'tts_failures': 0,
            'average_cycle_time': 0.0,
            'last_cycle_time': 0.0,
            'uptime_start': None,
            'error_count': 0,
            'last_error_time': None,
            'consecutive_failures': 0,
            'max_consecutive_failures': 5,  # Threshold for degraded mode
            'resource_scaling_events': 0,
            'vlm_requests_made': 0,
            'vlm_requests_rate_limited': 0,
            'memory_cleanup_events': 0
        }
        
        # Resource monitoring integration
        self.original_loop_interval = self.loop_interval
        self.original_cooldown_period = self.cooldown_period
        self.resource_monitor.register_scale_callback(self._on_performance_scale)
        
        # Safety manager for emergency stop integration
        self.safety_manager = SafetyManager()
        
        # Agent debugger integration (optional)
        self._agent_debugger: Optional[Any] = None
        
        self.logger.info("AgentManager initialized")
    
    async def start_agent_loop(self):
        """Start the main agent processing loop"""
        if self.loop_active:
            self.logger.warning("Agent loop already active")
            return
        
        self.loop_active = True
        self.performance_metrics['uptime_start'] = datetime.now()
        self.agent_state.mode = "active"
        self.agent_state.current_objective = "Autonomous operation active"
        
        # Update GUI state
        if self._gui_update_callback:
            try:
                self._gui_update_callback("active")
            except Exception as e:
                self.logger.error(f"Failed to update GUI state: {e}")
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        # Start loop in separate thread to avoid blocking
        self.loop_thread = threading.Thread(target=self._run_agent_loop, daemon=True)
        self.loop_thread.start()
        
        self.logger.info("Agent loop started")
        
        # Announce activation via TTS if available
        if self.tts_pipeline:
            await self._send_commentary_safe("Agent mode activated! I'm now watching the screen.")
    
    def _run_agent_loop(self):
        """Main agent loop (runs in separate thread)"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        
        try:
            loop.run_until_complete(self._agent_loop_async())
        except Exception as e:
            self.logger.error(f"Agent loop crashed: {e}")
            self.agent_state.mode = "error"
        finally:
            loop.close()
    
    async def _agent_loop_async(self):
        """Async agent loop implementation"""
        while self.loop_active:
            cycle_start = time.time()
            
            try:
                # Check for automatic resume after chat timeout
                self._check_auto_resume()
                
                # Check if step mode is active - pause automatic execution
                if self.is_step_mode_active():
                    self.agent_state.mode = "step_debug"
                    # Update GUI state
                    if self._gui_update_callback:
                        try:
                            self._gui_update_callback("step_debug")
                        except Exception:
                            pass
                    await asyncio.sleep(0.5)  # Check again soon
                    continue
                
                # Check if chat has priority (pause for conversation)
                if not self.chat_priority_event.is_set():
                    self.agent_state.mode = "paused"
                    # Update GUI state
                    if self._gui_update_callback:
                        try:
                            self._gui_update_callback("paused")
                        except Exception:
                            pass
                    await asyncio.sleep(0.5)  # Check again soon
                    continue
                
                self.agent_state.mode = "active"
                # Update GUI state
                if self._gui_update_callback:
                    try:
                        self._gui_update_callback("active")
                    except Exception:
                        pass
                
                # Check safety lock
                if self.action_engine.is_safety_active():
                    self.agent_state.mode = "emergency"
                    # Update GUI state
                    if self._gui_update_callback:
                        try:
                            self._gui_update_callback("emergency")
                        except Exception:
                            pass
                    await asyncio.sleep(1.0)  # Wait longer when safety is active
                    continue
                
                # Execute one agent cycle
                await self._execute_agent_cycle()
                
                # Update performance metrics
                cycle_time = time.time() - cycle_start
                self._update_performance_metrics(cycle_time)
                
                # Wait for next cycle
                await asyncio.sleep(self.loop_interval)
                
            except Exception as e:
                self.logger.error(f"Agent cycle error: {e}")
                self.performance_metrics['failed_actions'] += 1
                await asyncio.sleep(self.loop_interval * 2)  # Wait longer on error
    
    async def _execute_agent_cycle(self):
        """Execute one complete agent cycle: capture -> analyze -> act -> comment"""
        cycle_success = True
        error_details = None
        
        # Mark that we're in an active action cycle
        self._current_action_active = True
        
        try:
            # 1. Capture screenshot with error handling
            try:
                image_b64 = await self.vision_client.capture_screen()
                
                # Update debugger with screenshot if available
                if self._agent_debugger:
                    try:
                        self._agent_debugger.update_screenshot(image_b64)
                    except Exception as e:
                        self.logger.debug(f"Failed to update debugger screenshot: {e}")
                        
            except Exception as e:
                self.logger.error(f"Screenshot capture failed: {e}")
                self.performance_metrics['vision_failures'] += 1
                # Try to continue with cached/fallback behavior
                await self._handle_vision_failure(e)
                return
            
            # 2. Analyze scene with action history for hallucination prevention
            try:
                # Update GUI to show thinking state
                if self._gui_update_callback:
                    try:
                        self._gui_update_callback("thinking")
                    except Exception:
                        pass
                
                # Check VLM rate limiting before making request
                if not self.resource_monitor.can_make_vlm_request():
                    self.logger.warning("VLM request rate limited, using fallback")
                    self.performance_metrics['vlm_requests_rate_limited'] += 1
                    command = await self._get_fallback_command("Rate limited")
                    if not command:
                        return
                else:
                    # Record VLM request for rate limiting
                    self.resource_monitor.record_vlm_request()
                    self.performance_metrics['vlm_requests_made'] += 1
                    
                    action_history = self.action_engine.get_action_history()
                    command = await self.vision_client.analyze_scene(
                        image_b64, 
                        context="testing - click on any buttons or interactive elements you see",
                        action_history=action_history
                    )
                    
                    # Pass raw data to debugger if available
                    if self._agent_debugger and hasattr(self._agent_debugger, 'update_raw_data'):
                        try:
                            # Get raw prompt and response from vision client
                            raw_prompt = getattr(self.vision_client, 'last_prompt', 'Prompt not available')
                            raw_response = getattr(self.vision_client, 'last_raw_response', 'Response not available')
                            self._agent_debugger.update_raw_data(raw_prompt, raw_response)
                        except Exception as e:
                            self.logger.debug(f"Failed to update debugger raw data: {e}")
                    
                    # Update debugger with VLM response and command if available
                    if self._agent_debugger:
                        try:
                            # Create timing metrics for debugger
                            timing_metrics = {
                                'screenshot_time': 0.1,  # Approximate screenshot time
                                'vlm_inference_time': time.time() - cycle_start,  # Approximate VLM time
                                'action_execution_time': 0.0,  # Will be updated later
                                'total_cycle_time': 0.0  # Will be updated at end
                            }
                            
                            # Create VLM response dict (simplified for debugger)
                            vlm_response = {
                                'thought': command.thought if command else 'Analysis failed',
                                'commentary': command.commentary if command else '',
                                'action_type': command.action_type if command else 'none',
                                'target': command.target if command else None,
                                'confidence': command.confidence if command else 0.0
                            }
                            
                            self._agent_debugger.update_thought_log(vlm_response, timing_metrics)
                            self._agent_debugger.update_screenshot(image_b64, command)
                        except Exception as e:
                            self.logger.debug(f"Failed to update debugger with VLM response: {e}")
            except Exception as e:
                self.logger.error(f"Vision analysis failed: {e}")
                self.performance_metrics['vision_failures'] += 1
                # Try to continue with safe default action
                command = await self._get_fallback_command(e)
                if not command:
                    return
            
            # 3. Execute action and commentary in parallel with error handling
            try:
                action_task = asyncio.create_task(self._execute_action_safe(command))
                commentary_task = asyncio.create_task(self._send_commentary_safe(command.commentary))
                
                # Wait for both to complete
                action_result, commentary_result = await asyncio.gather(
                    action_task, commentary_task, return_exceptions=True
                )
                
                # Check for exceptions in results
                if isinstance(action_result, Exception):
                    self.logger.error(f"Action execution failed: {action_result}")
                    self.performance_metrics['action_failures'] += 1
                    cycle_success = False
                    error_details = str(action_result)
                else:
                    # Update debugger with action result if available
                    if self._agent_debugger and hasattr(action_result, 'success'):
                        try:
                            # Create a simple action result summary for the debugger
                            action_summary = {
                                'success': action_result.success,
                                'action_type': action_result.action_type if hasattr(action_result, 'action_type') else 'unknown',
                                'execution_time': action_result.execution_time if hasattr(action_result, 'execution_time') else 0.0,
                                'error_message': action_result.error_message if hasattr(action_result, 'error_message') else None
                            }
                            
                            # Update timing metrics with actual action execution time
                            timing_metrics = {
                                'screenshot_time': 0.1,
                                'vlm_inference_time': 0.5,  # Approximate
                                'action_execution_time': action_result.execution_time if hasattr(action_result, 'execution_time') else 0.0,
                                'total_cycle_time': time.time() - cycle_start
                            }
                            
                            # Log action result in debugger
                            self._agent_debugger.update_thought_log(action_summary, timing_metrics)
                        except Exception as e:
                            self.logger.debug(f"Failed to update debugger with action result: {e}")
                
                if isinstance(commentary_result, Exception):
                    self.logger.error(f"Commentary failed: {commentary_result}")
                    self.performance_metrics['tts_failures'] += 1
                    # Commentary failure doesn't fail the whole cycle
                
            except Exception as e:
                self.logger.error(f"Parallel execution failed: {e}")
                cycle_success = False
                error_details = str(e)
            
            # 4. Update state
            self.agent_state.last_action = command
            self.agent_state.loop_count += 1
            self.agent_state.last_update = datetime.now()
            
            # 5. Cooldown period
            if self.cooldown_period > 0:
                await asyncio.sleep(self.cooldown_period)
            
            # 6. Memory cleanup for temporary image data
            await self._cleanup_temporary_memory()
            
            # 7. Update error tracking
            if cycle_success:
                self.performance_metrics['consecutive_failures'] = 0
                self.logger.debug(f"Agent cycle complete: {command.action_type} with confidence {command.confidence}")
            else:
                self.performance_metrics['consecutive_failures'] += 1
                self.performance_metrics['error_count'] += 1
                self.performance_metrics['last_error_time'] = datetime.now()
                
                # Check if we need to enter degraded mode
                if (self.performance_metrics['consecutive_failures'] >= 
                    self.performance_metrics['max_consecutive_failures']):
                    await self._enter_degraded_mode(error_details)
            
        except Exception as e:
            self.logger.error(f"Agent cycle execution failed: {e}")
            self.performance_metrics['error_count'] += 1
            self.performance_metrics['consecutive_failures'] += 1
            self.performance_metrics['last_error_time'] = datetime.now()
            raise
        finally:
            # Mark that we're no longer in an active action cycle
            self._current_action_active = False
    
    async def _execute_action_safe(self, command: AgentCommand) -> ActionResult:
        """Execute action command with error handling and retries"""
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Run action execution in thread pool to avoid blocking
                result = await asyncio.to_thread(self.action_engine.execute_command, command)
                
                # Update performance metrics
                if result.success:
                    self.performance_metrics['successful_actions'] += 1
                    return result
                else:
                    self.performance_metrics['failed_actions'] += 1
                    self.logger.warning(f"Action failed (attempt {attempt + 1}): {result.error_message}")
                    last_error = result.error_message
                    
                    # Wait before retry
                    if attempt < max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                        
            except Exception as e:
                self.logger.error(f"Action execution exception (attempt {attempt + 1}): {e}")
                last_error = str(e)
                
                # Wait before retry
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        # All retries failed
        self.performance_metrics['failed_actions'] += 1
        return ActionResult(
            success=False,
            action_type=command.action_type,
            target=command.target,
            error_message=f"Failed after {max_retries + 1} attempts: {last_error}",
            execution_time=0.0,
            timestamp=datetime.now()
        )
    
    async def _send_commentary_safe(self, commentary_text: str):
        """Send commentary to TTS pipeline with error handling"""
        if not commentary_text or not self.tts_pipeline:
            return
        
        max_retries = 1  # Fewer retries for commentary to avoid delays
        
        for attempt in range(max_retries + 1):
            try:
                # Send to TTS pipeline using put_text method
                if hasattr(self.tts_pipeline, 'put_text'):
                    await self.tts_pipeline.put_text(commentary_text)
                    return  # Success
                else:
                    self.logger.warning("TTS pipeline interface not available")
                    return
                    
            except Exception as e:
                self.logger.error(f"Failed to send commentary (attempt {attempt + 1}): {e}")
                
                # Wait before retry
                if attempt < max_retries:
                    await asyncio.sleep(0.2)
        
        # All retries failed - log but don't raise (commentary is not critical)
        self.logger.error(f"Commentary failed after {max_retries + 1} attempts")
    
    async def _handle_vision_failure(self, error: Exception):
        """Handle vision system failures with graceful degradation"""
        self.logger.warning(f"Vision system failure, attempting recovery: {error}")
        
        # Try to reinitialize vision client
        try:
            vision_config = self.config.get('vision', {})
            self.vision_client = VisionClient(vision_config)
            self.logger.info("Vision client reinitialized")
        except Exception as e:
            self.logger.error(f"Failed to reinitialize vision client: {e}")
            
        # Send status update via TTS if available
        if self.tts_pipeline:
            try:
                await self._send_commentary_safe("Vision system error, attempting recovery")
            except Exception:
                pass  # Don't let TTS errors compound the problem
    
    async def _get_fallback_command(self, error: Exception) -> Optional[AgentCommand]:
        """Generate a safe fallback command when vision analysis fails"""
        self.logger.info("Generating fallback command due to vision failure")
        
        # Return a safe "wait" command
        return AgentCommand(
            thought=f"Vision analysis failed: {str(error)[:100]}. Waiting for recovery.",
            commentary="I'm having trouble seeing the screen. Let me wait a moment.",
            action_type="wait",
            target=None,
            key=None,
            confidence=0.1,  # Low confidence for fallback
            timestamp=datetime.now()
        )
    
    async def _enter_degraded_mode(self, error_details: str):
        """Enter degraded mode after consecutive failures"""
        self.logger.warning(f"Entering degraded mode after {self.performance_metrics['consecutive_failures']} consecutive failures")
        
        # Increase loop interval to reduce system stress
        original_interval = self.loop_interval
        self.loop_interval = min(self.loop_interval * 2, 10.0)  # Cap at 10 seconds
        
        # Announce degraded mode
        if self.tts_pipeline:
            try:
                await self._send_commentary_safe(
                    "I'm experiencing some difficulties. Switching to slower operation mode."
                )
            except Exception:
                pass
        
        # Wait longer before next attempt
        await asyncio.sleep(5.0)
        
        # Reset consecutive failures counter to give system a chance
        self.performance_metrics['consecutive_failures'] = 0
        
        self.logger.info(f"Degraded mode: interval increased from {original_interval}s to {self.loop_interval}s")
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health metrics"""
        uptime = 0.0
        if self.performance_metrics['uptime_start']:
            uptime = (datetime.now() - self.performance_metrics['uptime_start']).total_seconds()
        
        total_actions = (self.performance_metrics['successful_actions'] + 
                        self.performance_metrics['failed_actions'])
        
        success_rate = 0.0
        if total_actions > 0:
            success_rate = self.performance_metrics['successful_actions'] / total_actions
        
        return {
            'uptime_seconds': uptime,
            'total_cycles': self.performance_metrics['total_cycles'],
            'success_rate': success_rate,
            'error_count': self.performance_metrics['error_count'],
            'consecutive_failures': self.performance_metrics['consecutive_failures'],
            'last_error_time': self.performance_metrics['last_error_time'],
            'average_cycle_time': self.performance_metrics['average_cycle_time'],
            'vision_failures': self.performance_metrics['vision_failures'],
            'action_failures': self.performance_metrics['action_failures'],
            'tts_failures': self.performance_metrics['tts_failures'],
            'current_mode': self.agent_state.mode,
            'loop_interval': self.loop_interval,
            'is_degraded': self.performance_metrics['consecutive_failures'] > 0
        }
    
    def pause_for_chat(self):
        """Pause agent loop to prioritize chat interaction"""
        # Save current state before pausing
        self._save_agent_state()
        
        self.chat_priority_event.clear()
        self.agent_state.chat_mode_active = True
        self.agent_state.previous_mode = self.agent_state.mode
        self.agent_state.mode = "paused"
        self.agent_state.transition_timestamp = datetime.now()
        
        # Update last chat time for automatic resumption
        self._last_chat_time = datetime.now()
        
        self.logger.info("Agent loop paused for chat priority")
    
    def resume_agent_loop(self):
        """Resume agent loop after chat interaction"""
        # Restore previous state
        self._restore_agent_state()
        
        self.chat_priority_event.set()
        self.agent_state.chat_mode_active = False
        
        # Restore previous mode if available
        if self.agent_state.previous_mode:
            self.agent_state.mode = self.agent_state.previous_mode
            self.agent_state.previous_mode = None
        else:
            self.agent_state.mode = "active" if self.loop_active else "idle"
        
        self.agent_state.transition_timestamp = datetime.now()
        
        # Clear chat time tracking
        self._last_chat_time = None
        
        self.logger.info("Agent loop resumed after chat")
    
    def notify_chat_activity(self):
        """Notify agent manager of chat activity for priority detection"""
        if not self._chat_detection_enabled:
            return
        
        current_time = datetime.now()
        
        # If agent is active and not already paused for chat, pause it
        if (self.loop_active and 
            self.chat_priority_event.is_set() and 
            self.agent_state.mode == "active"):
            
            self.pause_for_chat()
            self.logger.info("Auto-paused agent for detected chat activity")
        
        # Update last chat time
        self._last_chat_time = current_time
    
    def _check_auto_resume(self):
        """Check if agent should automatically resume after chat timeout"""
        if (self._last_chat_time and 
            not self.chat_priority_event.is_set() and 
            self.agent_state.chat_mode_active):
            
            time_since_chat = (datetime.now() - self._last_chat_time).total_seconds()
            
            if time_since_chat >= self._chat_timeout:
                self.resume_agent_loop()
                self.logger.info(f"Auto-resumed agent after {time_since_chat:.1f}s of no chat activity")
    
    def set_chat_detection_enabled(self, enabled: bool):
        """Enable or disable automatic chat priority detection"""
        self._chat_detection_enabled = enabled
        self.logger.info(f"Chat priority detection {'enabled' if enabled else 'disabled'}")
    
    def set_chat_timeout(self, timeout_seconds: float):
        """Set timeout for automatic agent resumption after chat"""
        self._chat_timeout = max(5.0, timeout_seconds)  # Minimum 5 seconds
        self.logger.info(f"Chat timeout set to {self._chat_timeout}s")
    
    def _save_agent_state(self):
        """Save current agent state for preservation during mode transitions"""
        try:
            # Save current context and pending operations
            self.agent_state.saved_context = {
                'current_objective': self.agent_state.current_objective,
                'loop_count': self.agent_state.loop_count,
                'performance_metrics': self.performance_metrics.copy(),
                'loop_interval': self.loop_interval,
                'cooldown_period': self.cooldown_period,
                'last_action': self.agent_state.last_action,
                'vision_client_state': self._get_vision_client_state(),
                'action_engine_state': self._get_action_engine_state()
            }
            
            # Save any pending actions (if action engine has a queue)
            if hasattr(self.action_engine, 'get_pending_actions'):
                self.agent_state.pending_actions = self.action_engine.get_pending_actions()
            
            self.logger.debug("Agent state saved for preservation")
            
        except Exception as e:
            self.logger.error(f"Failed to save agent state: {e}")
    
    def _restore_agent_state(self):
        """Restore agent state after mode transition"""
        try:
            if not self.agent_state.saved_context:
                self.logger.debug("No saved state to restore")
                return
            
            # Restore context
            saved = self.agent_state.saved_context
            self.agent_state.current_objective = saved.get('current_objective', self.agent_state.current_objective)
            self.agent_state.loop_count = saved.get('loop_count', self.agent_state.loop_count)
            
            # Restore performance metrics (merge with current)
            saved_metrics = saved.get('performance_metrics', {})
            for key, value in saved_metrics.items():
                if key not in ['uptime_start', 'last_error_time']:  # Don't restore time-sensitive metrics
                    self.performance_metrics[key] = value
            
            # Restore timing settings
            self.loop_interval = saved.get('loop_interval', self.loop_interval)
            self.cooldown_period = saved.get('cooldown_period', self.cooldown_period)
            
            # Restore component states
            vision_state = saved.get('vision_client_state')
            if vision_state:
                self._restore_vision_client_state(vision_state)
            
            action_state = saved.get('action_engine_state')
            if action_state:
                self._restore_action_engine_state(action_state)
            
            # Restore pending actions
            if self.agent_state.pending_actions and hasattr(self.action_engine, 'restore_pending_actions'):
                self.action_engine.restore_pending_actions(self.agent_state.pending_actions)
            
            # Clear saved state
            self.agent_state.saved_context = {}
            self.agent_state.pending_actions = []
            
            self.logger.debug("Agent state restored after mode transition")
            
        except Exception as e:
            self.logger.error(f"Failed to restore agent state: {e}")
    
    def _get_vision_client_state(self) -> Dict[str, Any]:
        """Get current vision client state for preservation"""
        try:
            return {
                'capture_region': getattr(self.vision_client, 'capture_region', None),
                'model_name': getattr(self.vision_client, 'model_name', 'llava'),
                'last_capture_time': getattr(self.vision_client, 'last_capture_time', None)
            }
        except Exception as e:
            self.logger.error(f"Failed to get vision client state: {e}")
            return {}
    
    def _restore_vision_client_state(self, state: Dict[str, Any]):
        """Restore vision client state"""
        try:
            if hasattr(self.vision_client, 'capture_region'):
                self.vision_client.capture_region = state.get('capture_region')
            if hasattr(self.vision_client, 'model_name'):
                self.vision_client.model_name = state.get('model_name', 'llava')
        except Exception as e:
            self.logger.error(f"Failed to restore vision client state: {e}")
    
    def _get_action_engine_state(self) -> Dict[str, Any]:
        """Get current action engine state for preservation"""
        try:
            return {
                'safety_active': self.action_engine.is_safety_active(),
                'action_delay': getattr(self.action_engine, 'action_delay', 0.1),
                'last_action_time': getattr(self.action_engine, 'last_action_time', None)
            }
        except Exception as e:
            self.logger.error(f"Failed to get action engine state: {e}")
            return {}
    
    def _restore_action_engine_state(self, state: Dict[str, Any]):
        """Restore action engine state"""
        try:
            if hasattr(self.action_engine, 'action_delay'):
                self.action_engine.action_delay = state.get('action_delay', 0.1)
            # Note: Don't restore safety state - that should remain as-is for security
        except Exception as e:
            self.logger.error(f"Failed to restore action engine state: {e}")
    
    def stop_agent_loop(self):
        """Cleanly stop the agent loop with graceful shutdown"""
        if not self.loop_active:
            return
        
        self.logger.info("Initiating graceful agent loop shutdown...")
        
        # Save current state before stopping
        self._save_agent_state()
        
        # Set shutdown flag
        self.loop_active = False
        self.agent_state.previous_mode = self.agent_state.mode
        self.agent_state.mode = "stopping"
        self.agent_state.transition_timestamp = datetime.now()
        
        # Stop resource monitoring
        self.resource_monitor.stop_monitoring()
        
        # Wait for current action to complete if one is in progress
        self._wait_for_current_action_completion()
        
        # Wait for loop thread to finish gracefully
        if self.loop_thread and self.loop_thread.is_alive():
            self.logger.info("Waiting for agent loop thread to complete...")
            self.loop_thread.join(timeout=5.0)
            
            if self.loop_thread.is_alive():
                self.logger.warning("Agent loop thread did not complete within timeout")
            else:
                self.logger.info("Agent loop thread completed successfully")
        
        # Update final state
        self.agent_state.mode = "idle"
        self.agent_state.current_objective = "Stopped"
        self.agent_state.last_update = datetime.now()
        
        self.logger.info("Agent loop stopped gracefully")
    
    def _wait_for_current_action_completion(self, timeout: float = 3.0):
        """Wait for current action to complete before shutdown"""
        try:
            start_time = time.time()
            
            # Check if action engine has a method to wait for completion
            if hasattr(self.action_engine, 'wait_for_completion'):
                self.logger.debug("Waiting for current action to complete...")
                self.action_engine.wait_for_completion(timeout)
            else:
                # Simple wait with periodic checks
                while (time.time() - start_time) < timeout:
                    # Check if we're in the middle of an action cycle
                    if hasattr(self, '_current_action_active') and self._current_action_active:
                        time.sleep(0.1)
                    else:
                        break
            
            self.logger.debug("Current action completion wait finished")
            
        except Exception as e:
            self.logger.error(f"Error waiting for action completion: {e}")
    
    def preserve_state_across_restart(self) -> Dict[str, Any]:
        """Preserve state for system restart scenarios"""
        try:
            preserved_state = {
                'agent_state': {
                    'mode': self.agent_state.mode,
                    'current_objective': self.agent_state.current_objective,
                    'loop_count': self.agent_state.loop_count,
                    'performance_metrics': self.performance_metrics.copy(),
                    'last_update': self.agent_state.last_update.isoformat()
                },
                'configuration': {
                    'loop_interval': self.loop_interval,
                    'cooldown_period': self.cooldown_period,
                    'config': self.config.copy() if isinstance(self.config, dict) else {}
                },
                'component_states': {
                    'vision_client': self._get_vision_client_state(),
                    'action_engine': self._get_action_engine_state()
                },
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info("State preserved for restart")
            return preserved_state
            
        except Exception as e:
            self.logger.error(f"Failed to preserve state for restart: {e}")
            return {}
    
    def restore_state_from_restart(self, preserved_state: Dict[str, Any]):
        """Restore state from previous session"""
        try:
            if not preserved_state:
                self.logger.info("No preserved state to restore")
                return
            
            # Restore agent state
            agent_state = preserved_state.get('agent_state', {})
            if agent_state:
                self.agent_state.current_objective = agent_state.get('current_objective', 'Restored from previous session')
                self.agent_state.loop_count = agent_state.get('loop_count', 0)
                
                # Restore performance metrics (selective)
                saved_metrics = agent_state.get('performance_metrics', {})
                for key, value in saved_metrics.items():
                    if key in ['total_cycles', 'successful_actions', 'failed_actions']:
                        self.performance_metrics[key] = value
            
            # Restore configuration
            config_data = preserved_state.get('configuration', {})
            if config_data:
                self.loop_interval = config_data.get('loop_interval', self.loop_interval)
                self.cooldown_period = config_data.get('cooldown_period', self.cooldown_period)
            
            # Restore component states
            component_states = preserved_state.get('component_states', {})
            if component_states:
                vision_state = component_states.get('vision_client')
                if vision_state:
                    self._restore_vision_client_state(vision_state)
                
                action_state = component_states.get('action_engine')
                if action_state:
                    self._restore_action_engine_state(action_state)
            
            self.logger.info("State restored from previous session")
            
        except Exception as e:
            self.logger.error(f"Failed to restore state from restart: {e}")
    
    def emergency_stop(self):
        """Emergency stop all agent operations"""
        self.action_engine.emergency_stop()
        self.agent_state.mode = "emergency"
        self.logger.warning("Emergency stop activated")
        
        # Announce via TTS if available
        if self.tts_pipeline:
            try:
                # Create a new event loop for this thread if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Schedule the TTS announcement
                loop.create_task(self._send_commentary_safe("Emergency stop activated!"))
            except Exception as e:
                self.logger.error(f"Failed to announce emergency stop: {e}")
    
    def reset_emergency_state(self):
        """Reset emergency state (manual intervention required)"""
        self.action_engine.reset_safety_lock()
        if self.agent_state.mode == "emergency":
            self.agent_state.mode = "active" if self.loop_active else "idle"
        self.logger.info("Emergency state reset")
    
    def get_agent_state(self) -> AgentState:
        """Get current agent state"""
        # Update performance metrics in state
        self.agent_state.performance_metrics = self.performance_metrics.copy()
        return self.agent_state
    
    def update_configuration(self, new_config: Dict[str, Any]):
        """Update agent configuration dynamically"""
        self.config.update(new_config)
        
        # Update intervals
        self.loop_interval = new_config.get('loop_interval', self.loop_interval)
        self.cooldown_period = new_config.get('cooldown_period', self.cooldown_period)
        
        # Update chat priority settings
        if 'chat_detection_enabled' in new_config:
            self.set_chat_detection_enabled(new_config['chat_detection_enabled'])
        
        if 'chat_timeout' in new_config:
            self.set_chat_timeout(new_config['chat_timeout'])
        
        self.logger.info("Agent configuration updated")
    
    def get_chat_priority_status(self) -> Dict[str, Any]:
        """Get current chat priority system status"""
        return {
            'chat_mode_active': self.agent_state.chat_mode_active,
            'chat_detection_enabled': self._chat_detection_enabled,
            'chat_timeout': self._chat_timeout,
            'last_chat_time': self._last_chat_time.isoformat() if self._last_chat_time else None,
            'time_since_last_chat': (
                (datetime.now() - self._last_chat_time).total_seconds() 
                if self._last_chat_time else None
            ),
            'auto_resume_in': (
                max(0, self._chat_timeout - (datetime.now() - self._last_chat_time).total_seconds())
                if self._last_chat_time and self.agent_state.chat_mode_active else None
            )
        }
    
    def _update_performance_metrics(self, cycle_time: float):
        """
        Update performance tracking metrics and log performance data.
        
        Requirements: 6.4 - Performance logging for optimization
        """
        self.performance_metrics['total_cycles'] += 1
        self.performance_metrics['last_cycle_time'] = cycle_time
        
        # Update average cycle time
        total_cycles = self.performance_metrics['total_cycles']
        current_avg = self.performance_metrics['average_cycle_time']
        self.performance_metrics['average_cycle_time'] = (
            (current_avg * (total_cycles - 1) + cycle_time) / total_cycles
        )
        
        # Log performance metrics periodically (every 10 cycles)
        if total_cycles % 10 == 0:
            success_rate = (
                self.performance_metrics['successful_actions'] / 
                max(1, self.performance_metrics['successful_actions'] + self.performance_metrics['failed_actions'])
            )
            self.logger.info(
                f"[PERF] Cycle #{total_cycles}: "
                f"avg_time={self.performance_metrics['average_cycle_time']:.3f}s, "
                f"success_rate={success_rate:.1%}, "
                f"vision_failures={self.performance_metrics['vision_failures']}, "
                f"action_failures={self.performance_metrics['action_failures']}"
            )
        
        # Log detailed debug info for each cycle
        self.logger.debug(
            f"[CYCLE] #{total_cycles}: time={cycle_time:.3f}s, "
            f"mode={self.agent_state.mode}, "
            f"last_action={self.agent_state.last_action.action_type if self.agent_state.last_action else 'none'}"
        )
    
    def _on_performance_scale(self, scale_factor: float, cpu_percent: float, memory_percent: float):
        """Callback for resource monitor performance scaling events"""
        try:
            # Apply scaling to loop intervals
            self.loop_interval = self.original_loop_interval * scale_factor
            self.cooldown_period = self.original_cooldown_period * scale_factor
            
            # Update performance metrics
            self.performance_metrics['resource_scaling_events'] += 1
            
            # Log scaling event
            self.logger.info(f"Performance scaled: {scale_factor:.1f}x due to CPU {cpu_percent:.1f}%, Memory {memory_percent:.1f}%")
            self.logger.info(f"New intervals: loop={self.loop_interval:.1f}s, cooldown={self.cooldown_period:.1f}s")
            
            # Announce significant scaling via TTS
            if scale_factor >= 2.0 and self.tts_pipeline:
                asyncio.create_task(self._send_commentary_safe(
                    f"Adjusting performance due to high system load. Slowing down operations."
                ))
            
        except Exception as e:
            self.logger.error(f"Error in performance scaling callback: {e}")
    
    async def _cleanup_temporary_memory(self):
        """Clean up temporary image data and other memory-intensive objects"""
        try:
            # Force garbage collection periodically
            import gc
            
            # Clean up every 10 cycles to avoid performance impact
            if self.performance_metrics['total_cycles'] % 10 == 0:
                collected = gc.collect()
                if collected > 0:
                    self.performance_metrics['memory_cleanup_events'] += 1
                    self.logger.debug(f"Memory cleanup: collected {collected} objects")
            
            # Clean up vision client temporary data if available
            if hasattr(self.vision_client, 'cleanup_temporary_data'):
                await self.vision_client.cleanup_temporary_data()
            
        except Exception as e:
            self.logger.error(f"Error during memory cleanup: {e}")
    
    def get_resource_metrics(self) -> Dict[str, Any]:
        """Get current resource usage metrics"""
        try:
            resource_summary = self.resource_monitor.get_performance_summary()
            
            # Combine with agent performance metrics
            return {
                'resource_monitor': resource_summary,
                'agent_performance': {
                    'total_cycles': self.performance_metrics['total_cycles'],
                    'success_rate': (
                        self.performance_metrics['successful_actions'] / 
                        max(1, self.performance_metrics['successful_actions'] + self.performance_metrics['failed_actions'])
                    ),
                    'average_cycle_time': self.performance_metrics['average_cycle_time'],
                    'vlm_requests_made': self.performance_metrics['vlm_requests_made'],
                    'vlm_requests_rate_limited': self.performance_metrics['vlm_requests_rate_limited'],
                    'resource_scaling_events': self.performance_metrics['resource_scaling_events'],
                    'memory_cleanup_events': self.performance_metrics['memory_cleanup_events'],
                    'current_intervals': {
                        'loop_interval': self.loop_interval,
                        'cooldown_period': self.cooldown_period,
                        'original_loop_interval': self.original_loop_interval,
                        'original_cooldown_period': self.original_cooldown_period
                    }
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting resource metrics: {e}")
            return {'error': str(e)}
    
    async def process_user_conversation(self, user_input: str) -> str:
        """
        Process user conversation with memory-enhanced responses.
        
        This method handles user conversations by:
        1. Storing the interaction in memory
        2. Generating memory-enhanced responses using EnhancedLLMClient
        3. Returning the AI response
        
        Args:
            user_input: User's input text
            
        Returns:
            AI response text
        """
        try:
            self.logger.info(f"Processing user conversation: '{user_input[:50]}...'")
            
            # Generate memory-enhanced response
            ai_response = await self.llm_client.generate_with_memory(
                prompt=user_input,
                return_structured=False,
                max_memories=5
            )
            
            # Store the interaction in memory if memory core is available
            if self.memory_core and self.memory_core.is_ready():
                try:
                    memory_id = self.memory_core.store_interaction(
                        user_input=user_input,
                        ai_response=ai_response,
                        metadata={
                            'source': 'agent_manager',
                            'conversation_type': 'user_chat'
                        }
                    )
                    
                    if memory_id:
                        self.logger.debug(f"Conversation stored in memory: {memory_id}")
                    else:
                        self.logger.warning("Failed to store conversation in memory")
                        
                except Exception as e:
                    self.logger.error(f"Failed to store conversation in memory: {e}")
                    # Continue without memory storage - don't fail the conversation
            
            self.logger.info(f"Generated response: '{ai_response[:50]}...'")
            return ai_response
            
        except Exception as e:
            self.logger.error(f"Failed to process user conversation: {e}")
            # Return a fallback response
            return "I'm having trouble processing your message right now. Please try again."
    
    def set_memory_core(self, memory_core: MemoryCore) -> None:
        """
        Set or update the memory core instance.
        
        Args:
            memory_core: MemoryCore instance for memory operations
        """
        self.memory_core = memory_core
        if self.llm_client:
            self.llm_client.set_memory_core(memory_core)
        self.logger.info("Memory core updated in Agent Manager")
    
    def enable_memory_features(self, enable: bool = True) -> None:
        """
        Enable or disable memory features.
        
        Args:
            enable: Whether to enable memory features
        """
        if self.llm_client:
            self.llm_client.enable_memory_features(enable)
        self.logger.info(f"Memory features {'enabled' if enable else 'disabled'} in Agent Manager")
    
    def get_memory_performance_stats(self) -> Dict[str, Any]:
        """
        Get memory integration performance statistics.
        
        Returns:
            Dictionary with memory performance metrics
        """
        stats = {}
        
        if self.llm_client:
            stats['llm_client'] = self.llm_client.get_memory_performance_stats()
        
        if self.memory_core:
            try:
                stats['memory_core'] = {
                    'is_ready': self.memory_core.is_ready(),
                    'memory_stats': self.memory_core.get_memory_stats().__dict__,
                    'concurrent_access_metrics': self.memory_core.get_concurrent_access_metrics(),
                    'storage_performance': self.memory_core.get_storage_performance_metrics()
                }
            except Exception as e:
                stats['memory_core'] = {'error': str(e)}
        
        return stats
        """Get comprehensive system status including resource metrics"""
        try:
            base_health = self.get_system_health()
            resource_metrics = self.get_resource_metrics()
            
            return {
                'agent_health': base_health,
                'resource_metrics': resource_metrics,
                'timestamp': datetime.now().isoformat(),
                'monitoring_active': self.resource_monitor.monitoring_active
            }
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive status: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def update_timing(self, loop_interval: float, cooldown_period: float):
        """Update agent loop timing parameters"""
        self.loop_interval = max(0.1, loop_interval)  # Minimum 0.1 seconds
        self.cooldown_period = max(0.0, cooldown_period)
        
        # Update original values for resource scaling
        self.original_loop_interval = self.loop_interval
        self.original_cooldown_period = self.cooldown_period
        
        self.logger.info(f"Agent timing updated: loop={self.loop_interval}s, cooldown={self.cooldown_period}s")
    
    def update_capture_region(self, capture_region: Optional[List[int]]):
        """Update screen capture region for vision client"""
        try:
            if hasattr(self.vision_client, 'update_capture_region'):
                self.vision_client.update_capture_region(capture_region)
            elif hasattr(self.vision_client, 'capture_region'):
                self.vision_client.capture_region = capture_region
            
            region_str = f"[{capture_region}]" if capture_region else "full screen"
            self.logger.info(f"Capture region updated: {region_str}")
            
        except Exception as e:
            self.logger.error(f"Failed to update capture region: {e}")

    def cleanup(self):
        """Clean up all resources"""
        self.stop_agent_loop()
        
        # Stop reflex engine if active
        if self.reflex_engine and hasattr(self.reflex_engine, 'stop'):
            self.reflex_engine.stop()
        
        self.resource_monitor.cleanup()
        self.vision_client.cleanup()
        self.action_engine.cleanup()
        self.logger.info("AgentManager cleanup complete")
    
    def process_vlm_command(self, command: Dict[str, Any]) -> None:
        """
        Process strategic commands from the VLM.
        
        Supported commands:
            {"action": "engage_auto", "target": "big-cookie", "game": "cookie-clicker"}
            {"action": "stop_reflex"}
            {"action": "switch_target", "target": "cursor-upgrade"}
        
        Args:
            command: Command dictionary from VLM
        """
        action = command.get('action')
        
        if action == 'engage_auto':
            self._handle_engage_auto(command)
        elif action == 'stop_reflex':
            self._handle_stop_reflex()
        elif action == 'switch_target':
            self._handle_switch_target(command)
        else:
            self.logger.warning(f"Unknown VLM command: {action}")
    
    def _handle_engage_auto(self, command: Dict[str, Any]):
        """Handle engage_auto command to start reflex engine."""
        try:
            game_name = command.get('game', 'cookie-clicker')
            target_name = command.get('target', 'big-cookie')
            action_type = command.get('action_type', 'click_repeat')
            
            # Load game profile and get template path
            from .game_knowledge import GameKnowledge
            game_knowledge = GameKnowledge()
            
            profile = game_knowledge.load_profile(game_name)
            if not profile:
                self.logger.error(f"Game profile not found: {game_name}")
                return
            
            # Get template path
            template_filename = profile.default_templates.get(target_name)
            if not template_filename:
                self.logger.error(f"Template not found in profile: {target_name}")
                return
            
            template_path = f"{profile.templates_path}/{template_filename}"
            
            # Initialize reflex engine if not already done
            if not self.reflex_engine:
                from .reflex_engine import ReflexEngine
                from .screen_capturer import ScreenCapturer
                
                screen_capturer = ScreenCapturer()
                self.reflex_engine = ReflexEngine(
                    self.action_engine,
                    screen_capturer,
                    safety_manager=self.safety_manager
                )
            
            # Start reflex engine
            if self.reflex_engine.start(template_path, action_type):
                self.logger.info(f"Reflex engine started: {target_name} in {game_name}")
                self.agent_state.current_objective = f"Auto-clicking {target_name}"
            else:
                self.logger.error("Failed to start reflex engine")
                
        except Exception as e:
            self.logger.error(f"Error handling engage_auto command: {e}")
    
    def _handle_stop_reflex(self):
        """Handle stop_reflex command to stop reflex engine."""
        if self.reflex_engine:
            self.reflex_engine.stop()
            self.logger.info("Reflex engine stopped")
            self.agent_state.current_objective = "Reflex engine stopped"
        else:
            self.logger.warning("No reflex engine to stop")
    
    def _handle_switch_target(self, command: Dict[str, Any]):
        """Handle switch_target command to change reflex target."""
        try:
            target_name = command.get('target')
            if not target_name:
                self.logger.error("No target specified in switch_target command")
                return
            
            if not self.reflex_engine or not self.reflex_engine._active:
                self.logger.error("Reflex engine not active, cannot switch target")
                return
            
            # Get current game profile (assume same game)
            # This is simplified - in production, track current game
            game_name = 'cookie-clicker'  # Default
            
            from .game_knowledge import GameKnowledge
            game_knowledge = GameKnowledge()
            
            profile = game_knowledge.load_profile(game_name)
            if not profile:
                self.logger.error(f"Game profile not found: {game_name}")
                return
            
            template_filename = profile.default_templates.get(target_name)
            if not template_filename:
                self.logger.error(f"Template not found: {target_name}")
                return
            
            template_path = f"{profile.templates_path}/{template_filename}"
            
            # Update template
            if self.reflex_engine.update_template(template_path):
                self.logger.info(f"Switched reflex target to: {target_name}")
                self.agent_state.current_objective = f"Auto-clicking {target_name}"
            else:
                self.logger.error("Failed to switch reflex target")
                
        except Exception as e:
            self.logger.error(f"Error handling switch_target command: {e}")
    
    def on_reflex_feedback(self, status: Dict[str, Any]) -> None:
        """
        Handle feedback from Reflex Engine (target lost, errors, etc.).
        Queues information for next VLM cycle.
        
        Args:
            status: Status dictionary from reflex engine
        """
        # Queue feedback for next VLM prompt
        if not status.get('target_found'):
            feedback = {
                'type': 'target_lost',
                'confidence': status.get('confidence', 0.0),
                'consecutive_failures': status.get('consecutive_failures', 0)
            }
            self._reflex_feedback_queue.append(feedback)
            self.logger.info("Target lost feedback queued for VLM")
    
    def _get_reflex_feedback_for_vlm(self) -> str:
        """
        Get reflex feedback formatted for VLM prompt.
        
        Returns:
            Formatted feedback string
        """
        if not self._reflex_feedback_queue:
            return ""
        
        feedback_parts = []
        for feedback in self._reflex_feedback_queue:
            if feedback['type'] == 'target_lost':
                feedback_parts.append(
                    f"[REFLEX] Target lost (confidence: {feedback['confidence']:.2f}, "
                    f"failures: {feedback['consecutive_failures']})"
                )
        
        # Clear queue after retrieving
        self._reflex_feedback_queue.clear()
        
        return " ".join(feedback_parts)
    
    def set_debugger(self, debugger):
        """
        Set the agent debugger instance for real-time data updates.
        
        Args:
            debugger: AgentDebugger instance to receive data updates
        """
        self._agent_debugger = debugger
        
        # Auto-initialize StepController when debugger is set
        self.initialize_debugger_step_controller()
        
        self.logger.info("Agent debugger connected for real-time data updates")
    
    def initialize_debugger_step_controller(self):
        """
        初始化调试器的 StepController，将 ActionEngine 实例传递给调试器
        
        Requirements: 3.1, 3.2 - Pass ActionEngine instance to debugger for step mode
        """
        if not self._agent_debugger:
            self.logger.warning("Cannot initialize StepController - no debugger set")
            return
        
        try:
            # Pass both AgentManager and ActionEngine to the debugger
            success = self._agent_debugger.auto_initialize_step_controller(self, self.action_engine)
            
            if success:
                self.logger.info("Debugger StepController initialized successfully")
                
                # Enable step mode by default when debugger is connected
                self._agent_debugger.set_step_mode(True)
                
            else:
                self.logger.error("Failed to initialize debugger StepController")
                
        except Exception as e:
            self.logger.error(f"Error initializing debugger StepController: {e}")
    
    def get_action_engine(self):
        """
        获取 ActionEngine 实例供调试器使用
        
        Returns:
            ActionEngine: 动作执行引擎实例
        """
        return self.action_engine
    
    def is_step_mode_active(self) -> bool:
        """
        检查是否处于单步调试模式
        
        Returns:
            bool: 是否启用了单步调试模式
        """
        return (self._agent_debugger is not None and 
                hasattr(self._agent_debugger, 'step_controller') and
                self._agent_debugger.step_controller is not None and
                self._agent_debugger.is_step_controller_ready())
    
    def pause_for_step_mode(self):
        """
        为单步调试模式暂停自动循环
        
        Requirements: 3.1, 3.2 - Pause automatic execution during step mode
        """
        if self.is_step_mode_active():
            self.logger.info("Pausing agent loop for step mode debugging")
            self.pause_for_chat()  # Reuse existing pause mechanism
            self.agent_state.mode = "step_debug"
            self.agent_state.current_objective = "Manual step debugging active"
    
    def resume_from_step_mode(self):
        """
        从单步调试模式恢复自动循环
        
        Requirements: 3.1, 3.2 - Resume automatic execution after step mode
        """
        if self.agent_state.mode == "step_debug":
            self.logger.info("Resuming agent loop from step mode debugging")
            self.resume_agent_loop()
            self.agent_state.current_objective = "Resumed from step debugging"


class SafetyManager:
    """Safety manager for emergency stop functionality"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SafetyManager")
        self.emergency_callback: Optional[Callable] = None
        self.emergency_active = False
        
        # Set up emergency hotkey (F9) if available
        try:
            import keyboard
            keyboard.add_hotkey('f9', self._trigger_emergency_stop)
            self.logger.info("Emergency hotkey (F9) registered")
        except ImportError:
            self.logger.warning("keyboard module not available - emergency hotkey disabled")
        except Exception as e:
            self.logger.error(f"Failed to register emergency hotkey: {e}")
    
    def set_emergency_callback(self, callback: Callable):
        """Set callback function to call when emergency stop is triggered"""
        self.emergency_callback = callback
        self.logger.info("Emergency stop callback registered")
    
    def _trigger_emergency_stop(self):
        """Internal method to trigger emergency stop"""
        self.emergency_active = True
        self.logger.warning("Emergency stop triggered via F9 hotkey")
        
        if self.emergency_callback:
            try:
                self.emergency_callback()
            except Exception as e:
                self.logger.error(f"Emergency callback failed: {e}")
    
    def reset_emergency_state(self):
        """Reset emergency state"""
        self.emergency_active = False
        self.logger.info("Emergency state reset")
    
    def is_emergency_active(self) -> bool:
        """Check if emergency stop is active"""
        return self.emergency_active