"""
Action Engine for AI VTuber Vision-Action Agent

This module provides safe mouse and keyboard action execution with DirectX compatibility,
coordinate validation, and emergency stop mechanisms.
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime

try:
    import pydirectinput
    DIRECTINPUT_AVAILABLE = True
except ImportError:
    DIRECTINPUT_AVAILABLE = False
    logging.warning("pydirectinput not available, falling back to pyautogui")

import pyautogui
from .vision_client import AgentCommand
from .debug_overlay import DebugOverlay


@dataclass
class ActionResult:
    """Result of an action execution"""
    success: bool
    action_type: str
    target: Optional[Tuple[int, int]]
    error_message: Optional[str]
    execution_time: float
    timestamp: datetime


class ActionEngine:
    """Safe action execution engine with DirectX compatibility and safety validation"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ActionEngine with configuration
        
        Args:
            config: Configuration dictionary containing action settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Safety mechanisms
        self.safety_lock = threading.Event()
        self.safety_lock.set()  # Start in safe state
        self.action_lock = threading.Lock()
        
        # Action settings
        self.use_directinput = config.get('use_directinput', True) and DIRECTINPUT_AVAILABLE
        self.action_delay = config.get('action_delay', 0.1)
        self.click_duration = config.get('click_duration', 0.1)
        
        # Screen bounds for validation
        self.screen_bounds = self._get_screen_bounds()
        
        # Coordinate clamping (optional)
        self.clamp_region = config.get('clamp_region', None)
        
        # DPI scaling factor for coordinate normalization
        self.dpi_scale_factor = config.get('dpi_scale_factor', 1.0)
        
        # Action history for hallucination prevention
        self.action_history: List[Dict] = []
        self.max_history_size = 3  # Track last 3 actions for hallucination detection
        
        # Debug overlay for coordinate visualization
        overlay_config = config.get('debug_overlay', {})
        self.debug_overlay = DebugOverlay(overlay_config)
        if overlay_config.get('enabled', True):
            self.debug_overlay.start_overlay()
        
        # Drift vector tracking for debugger
        self.last_target_position: Optional[Tuple[int, int]] = None
        self.last_actual_position: Optional[Tuple[int, int]] = None
        self.debugger_callback: Optional[callable] = None
        
        # Configure input library
        if self.use_directinput:
            pydirectinput.FAILSAFE = True
            pydirectinput.PAUSE = self.action_delay
            self.logger.info(f"ActionEngine initialized with pydirectinput, DPI scale: {self.dpi_scale_factor}")
        else:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = self.action_delay
            self.logger.info(f"ActionEngine initialized with pyautogui fallback, DPI scale: {self.dpi_scale_factor}")
    
    def _get_screen_bounds(self) -> Tuple[int, int, int, int]:
        """Get current screen boundaries"""
        try:
            if self.use_directinput:
                # pydirectinput doesn't have size() method, use pyautogui
                width, height = pyautogui.size()
            else:
                width, height = pyautogui.size()
            
            return (0, 0, width, height)
        except Exception as e:
            self.logger.error(f"Failed to get screen bounds: {e}")
            # Default fallback
            return (0, 0, 1920, 1080)
    
    def convert_percentage_to_pixels(self, percent_x: float, percent_y: float) -> Tuple[int, int]:
        """
        Convert percentage coordinates (0.0-1.0) to logical pixel coordinates
        with DPI scaling applied.
        
        Args:
            percent_x: X coordinate as percentage (0.0-1.0)
            percent_y: Y coordinate as percentage (0.0-1.0)
            
        Returns:
            Tuple of (pixel_x, pixel_y) with DPI scaling applied
        """
        # Get screen dimensions
        _, _, screen_width, screen_height = self.screen_bounds
        
        # Convert percentage to logical pixels
        logical_x = percent_x * screen_width
        logical_y = percent_y * screen_height
        
        # Apply DPI scaling factor
        final_x = int(logical_x * self.dpi_scale_factor)
        final_y = int(logical_y * self.dpi_scale_factor)
        
        self.logger.debug(
            f"Coordinate conversion: percent({percent_x:.3f}, {percent_y:.3f}) -> "
            f"logical({logical_x:.1f}, {logical_y:.1f}) -> "
            f"final({final_x}, {final_y}) [DPI: {self.dpi_scale_factor}]"
        )
        
        return final_x, final_y
    
    def set_dpi_scale_factor(self, factor: float) -> None:
        """
        Set DPI scaling factor for coordinate calculations
        
        Args:
            factor: DPI scaling factor (e.g., 1.0, 1.25, 1.5)
        """
        # Validate range
        factor = max(0.5, min(3.0, factor))
        self.dpi_scale_factor = factor
        self.logger.info(f"DPI scale factor updated to {factor}")
    
    def set_debugger_callback(self, callback: callable) -> None:
        """
        Set callback function for debugger drift vector updates
        
        Args:
            callback: Function to call with (target_x, target_y, actual_x, actual_y)
        """
        self.debugger_callback = callback
        self.logger.info("Debugger callback set for drift vector tracking")
    
    def _record_actual_mouse_position(self) -> None:
        """
        Record the actual mouse position after action execution
        Used for drift vector calculation in debugger
        """
        try:
            import pyautogui
            actual_x, actual_y = pyautogui.position()
            self.last_actual_position = (actual_x, actual_y)
            
            # If we have both target and actual positions, notify debugger
            if (self.last_target_position and self.last_actual_position and 
                self.debugger_callback):
                target_x, target_y = self.last_target_position
                actual_x, actual_y = self.last_actual_position
                
                # Call debugger callback with drift vector data
                try:
                    self.debugger_callback(target_x, target_y, actual_x, actual_y)
                except Exception as e:
                    self.logger.error(f"Debugger callback failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to record actual mouse position: {e}")
    
    def get_dpi_scale_factor(self) -> float:
        """Get current DPI scaling factor"""
        return self.dpi_scale_factor
    
    def execute_command(self, command: AgentCommand) -> ActionResult:
        """
        Execute a single action command with safety checks
        
        Args:
            command: AgentCommand to execute
            
        Returns:
            ActionResult with execution details
        
        Requirements: 6.4 - Action execution logging
        """
        start_time = time.time()
        
        # Log incoming command
        self.logger.debug(
            f"[ACTION] Executing: type={command.action_type}, "
            f"target={command.target}, key={command.key}, "
            f"confidence={command.confidence:.2f}"
        )
        
        # Check safety lock
        if not self.safety_lock.is_set():
            self.logger.warning("[ACTION] Blocked by safety lock")
            return ActionResult(
                success=False,
                action_type=command.action_type,
                target=command.target,
                error_message="Safety lock active - actions disabled",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        # Thread safety
        with self.action_lock:
            try:
                # Check for hallucination (repeated actions)
                if self._is_hallucination(command):
                    self.logger.info(f"[ACTION] Hallucination blocked: {command.action_type} at {command.target}")
                    return ActionResult(
                        success=False,
                        action_type=command.action_type,
                        target=command.target,
                        error_message="Hallucination detected - repeated action blocked",
                        execution_time=time.time() - start_time,
                        timestamp=datetime.now()
                    )
                
                # Execute the action
                result = self._execute_action(command)
                
                # Record action in history
                self._record_action(command, result.success)
                
                result.execution_time = time.time() - start_time
                
                # Log result
                if result.success:
                    self.logger.debug(
                        f"[ACTION] Success: {command.action_type} completed in {result.execution_time:.3f}s"
                    )
                else:
                    self.logger.warning(
                        f"[ACTION] Failed: {command.action_type} - {result.error_message}"
                    )
                
                return result
                
            except Exception as e:
                self.logger.error(f"Action execution failed: {e}")
                return ActionResult(
                    success=False,
                    action_type=command.action_type,
                    target=command.target,
                    error_message=str(e),
                    execution_time=time.time() - start_time,
                    timestamp=datetime.now()
                )
    
    def _execute_action(self, command: AgentCommand) -> ActionResult:
        """Execute the specific action type"""
        action_type = command.action_type.lower()
        
        if action_type == "click":
            return self._execute_click(command)
        elif action_type == "keypress":
            return self._execute_keypress(command)
        elif action_type == "drag":
            return self._execute_drag(command)
        elif action_type == "scroll":
            return self._execute_scroll(command)
        elif action_type == "wait":
            return self._execute_wait(command)
        elif action_type == "none":
            return ActionResult(
                success=True,
                action_type=action_type,
                target=None,
                error_message=None,
                execution_time=0.0,
                timestamp=datetime.now()
            )
        else:
            return ActionResult(
                success=False,
                action_type=action_type,
                target=command.target,
                error_message=f"Unknown action type: {action_type}",
                execution_time=0.0,
                timestamp=datetime.now()
            )
    
    def _execute_click(self, command: AgentCommand) -> ActionResult:
        """Execute mouse click action with percentage coordinate support"""
        if not command.target:
            return ActionResult(
                success=False,
                action_type="click",
                target=None,
                error_message="Click action requires target coordinates",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        # Handle both percentage and pixel coordinates
        if len(command.target) == 2 and all(0.0 <= coord <= 1.0 for coord in command.target):
            # Percentage coordinates (0.0-1.0)
            percent_x, percent_y = command.target
            x, y = self.convert_percentage_to_pixels(percent_x, percent_y)
            self.logger.debug(f"Converted percentage coords ({percent_x:.3f}, {percent_y:.3f}) to pixels ({x}, {y})")
        else:
            # Legacy pixel coordinates or invalid format
            if hasattr(command, 'x') and hasattr(command, 'y') and command.x is not None and command.y is not None:
                # Use legacy pixel coordinates
                x, y = command.x, command.y
                self.logger.debug(f"Using legacy pixel coordinates ({x}, {y})")
            else:
                # Try to interpret target as pixel coordinates
                try:
                    x, y = int(command.target[0]), int(command.target[1])
                    self.logger.debug(f"Using target as pixel coordinates ({x}, {y})")
                except (ValueError, TypeError, IndexError):
                    return ActionResult(
                        success=False,
                        action_type="click",
                        target=command.target,
                        error_message=f"Invalid target coordinates: {command.target}",
                        execution_time=0.0,
                        timestamp=datetime.now()
                    )
        
        # Record target position for drift vector calculation
        self.last_target_position = (x, y)
        
        # Validate coordinates
        if not self.is_safe_coordinate(x, y):
            return ActionResult(
                success=False,
                action_type="click",
                target=(x, y),
                error_message=f"Coordinates ({x}, {y}) are outside safe bounds",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        try:
            if self.use_directinput:
                pydirectinput.click(x, y, duration=self.click_duration)
            else:
                pyautogui.click(x, y, duration=self.click_duration)
            
            # Record actual mouse position after click for drift vector
            self._record_actual_mouse_position()
            
            # Show debug overlay target
            self.debug_overlay.show_target(x, y, "click")
            
            self.logger.debug(f"Click executed at ({x}, {y})")
            return ActionResult(
                success=True,
                action_type="click",
                target=(x, y),
                error_message=None,
                execution_time=0.0,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                action_type="click",
                target=(x, y),
                error_message=str(e),
                execution_time=0.0,
                timestamp=datetime.now()
            )
    
    def _execute_keypress(self, command: AgentCommand) -> ActionResult:
        """Execute keyboard key press action"""
        if not command.key:
            return ActionResult(
                success=False,
                action_type="keypress",
                target=None,
                error_message="Keypress action requires key parameter",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        try:
            if self.use_directinput:
                pydirectinput.press(command.key)
            else:
                pyautogui.press(command.key)
            
            self.logger.debug(f"Key press executed: {command.key}")
            return ActionResult(
                success=True,
                action_type="keypress",
                target=None,
                error_message=None,
                execution_time=0.0,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                action_type="keypress",
                target=None,
                error_message=str(e),
                execution_time=0.0,
                timestamp=datetime.now()
            )
    
    def _execute_drag(self, command: AgentCommand) -> ActionResult:
        """Execute mouse drag action"""
        if not command.target or len(command.target) != 4:
            return ActionResult(
                success=False,
                action_type="drag",
                target=command.target,
                error_message="Drag action requires target coordinates [x1, y1, x2, y2]",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        x1, y1, x2, y2 = command.target
        
        # Record target position (end position) for drift vector calculation
        self.last_target_position = (x2, y2)
        
        # Validate both start and end coordinates
        if not self.is_safe_coordinate(x1, y1):
            return ActionResult(
                success=False,
                action_type="drag",
                target=(x1, y1, x2, y2),
                error_message=f"Start coordinates ({x1}, {y1}) are outside safe bounds",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        if not self.is_safe_coordinate(x2, y2):
            return ActionResult(
                success=False,
                action_type="drag",
                target=(x1, y1, x2, y2),
                error_message=f"End coordinates ({x2}, {y2}) are outside safe bounds",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        try:
            if self.use_directinput:
                pydirectinput.drag(x1, y1, x2, y2, duration=self.click_duration)
            else:
                pyautogui.drag(x1, y1, x2, y2, duration=self.click_duration)
            
            # Record actual mouse position after drag for drift vector
            self._record_actual_mouse_position()
            
            # Show debug overlay drag path
            self.debug_overlay.show_drag_path(x1, y1, x2, y2)
            
            self.logger.debug(f"Drag executed from ({x1}, {y1}) to ({x2}, {y2})")
            return ActionResult(
                success=True,
                action_type="drag",
                target=(x1, y1, x2, y2),
                error_message=None,
                execution_time=0.0,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                action_type="drag",
                target=(x1, y1, x2, y2),
                error_message=str(e),
                execution_time=0.0,
                timestamp=datetime.now()
            )
    
    def _execute_scroll(self, command: AgentCommand) -> ActionResult:
        """Execute mouse scroll action"""
        if not command.target:
            return ActionResult(
                success=False,
                action_type="scroll",
                target=None,
                error_message="Scroll action requires target coordinates and scroll direction",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        # Expect target to be [x, y, scroll_amount] where scroll_amount is positive for up, negative for down
        if len(command.target) < 3:
            return ActionResult(
                success=False,
                action_type="scroll",
                target=command.target,
                error_message="Scroll action requires [x, y, scroll_amount] format",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        x, y, scroll_amount = command.target[:3]
        
        # Validate coordinates
        if not self.is_safe_coordinate(x, y):
            return ActionResult(
                success=False,
                action_type="scroll",
                target=(x, y),
                error_message=f"Coordinates ({x}, {y}) are outside safe bounds",
                execution_time=0.0,
                timestamp=datetime.now()
            )
        
        try:
            if self.use_directinput:
                pydirectinput.scroll(int(scroll_amount), x=x, y=y)
            else:
                pyautogui.scroll(int(scroll_amount), x=x, y=y)
            
            # Show debug overlay target for scroll
            self.debug_overlay.show_target(x, y, "scroll")
            
            self.logger.debug(f"Scroll executed at ({x}, {y}) with amount {scroll_amount}")
            return ActionResult(
                success=True,
                action_type="scroll",
                target=(x, y, scroll_amount),
                error_message=None,
                execution_time=0.0,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                action_type="scroll",
                target=(x, y, scroll_amount),
                error_message=str(e),
                execution_time=0.0,
                timestamp=datetime.now()
            )
    
    def _execute_wait(self, command: AgentCommand) -> ActionResult:
        """Execute wait action"""
        wait_time = self.action_delay * 2  # Default wait time
        time.sleep(wait_time)
        
        return ActionResult(
            success=True,
            action_type="wait",
            target=None,
            error_message=None,
            execution_time=wait_time,
            timestamp=datetime.now()
        )
    
    def is_safe_coordinate(self, x: int, y: int) -> bool:
        """
        Validate coordinates are within safe bounds
        
        Args:
            x, y: Coordinates to validate
            
        Returns:
            True if coordinates are safe, False otherwise
        """
        # Check screen bounds
        min_x, min_y, max_x, max_y = self.screen_bounds
        if not (min_x <= x < max_x and min_y <= y < max_y):
            return False
        
        # Check clamp region if configured
        if self.clamp_region:
            clamp_x, clamp_y, clamp_w, clamp_h = self.clamp_region
            if not (clamp_x <= x < clamp_x + clamp_w and clamp_y <= y < clamp_y + clamp_h):
                return False
        
        return True
    
    def _is_hallucination(self, command: AgentCommand) -> bool:
        """
        Check if command appears to be a hallucination (repeated action)
        
        Args:
            command: Command to check
            
        Returns:
            True if likely hallucination, False otherwise
        """
        if not self.action_history or command.action_type != "click":
            return False
        
        # Whitelist: Allow calibration/test commands
        if hasattr(command, 'thought') and command.thought:
            thought_lower = command.thought.lower()
            if any(keyword in thought_lower for keyword in ['calibration', 'testing', 'test', 'debug']):
                self.logger.debug("Calibration/test command - bypassing hallucination check")
                return False
        
        # Check confidence threshold
        if hasattr(command, 'confidence') and command.confidence < 0.5:
            self.logger.warning(f"Low confidence action blocked: {command.confidence}")
            return True
        
        # Check for repeated clicks at same coordinates
        if len(self.action_history) >= 2:
            recent_clicks = [
                action for action in self.action_history[-2:]
                if action.get('action_type') == 'click' and action.get('success', False)
            ]
            
            if len(recent_clicks) >= 2:
                # Check if all recent clicks are at the same location
                targets = [action.get('target') for action in recent_clicks]
                if all(target == command.target for target in targets):
                    # Check time interval - allow if enough time has passed
                    last_time = recent_clicks[-1].get('timestamp')
                    if last_time and (datetime.now() - last_time).total_seconds() < 2.0:
                        self.logger.warning(f"Spam-clicking detected at {command.target}")
                        return True
        
        # Check last action for immediate repetition
        last_action = self.action_history[-1]
        if (last_action.get('action_type') == 'click' and 
            last_action.get('target') == command.target and
            last_action.get('success', False)):
            
            # Allow repetition if some time has passed (more than 2 seconds)
            last_time = last_action.get('timestamp')
            if last_time and (datetime.now() - last_time).total_seconds() < 2.0:
                self.logger.warning(f"Immediate repetition detected: click at {command.target}")
                return True
        
        return False
    
    def _record_action(self, command: AgentCommand, success: bool):
        """Record action in history for hallucination detection"""
        action_record = {
            'action_type': command.action_type,
            'target': command.target,
            'key': command.key,
            'success': success,
            'timestamp': datetime.now()
        }
        
        self.action_history.append(action_record)
        
        # Limit history size
        if len(self.action_history) > self.max_history_size:
            self.action_history.pop(0)
    
    def emergency_stop(self):
        """Immediately stop all actions and set safety lock"""
        self.safety_lock.clear()
        self.logger.warning("Emergency stop activated - all actions disabled")
    
    def reset_safety_lock(self):
        """Reset safety lock to allow actions (manual intervention required)"""
        self.safety_lock.set()
        self.logger.info("Safety lock reset - actions enabled")
    
    def is_safety_active(self) -> bool:
        """Check if safety lock is active"""
        return not self.safety_lock.is_set()
    
    def get_action_history(self) -> List[Dict]:
        """Get recent action history"""
        return self.action_history.copy()
    
    def get_action_history_string(self) -> str:
        """Get action history formatted as string for VLM prompts"""
        if not self.action_history:
            return "No recent actions"
        
        history_parts = []
        for action in self.action_history:
            action_type = action.get('action_type', 'unknown')
            target = action.get('target')
            success = action.get('success', False)
            
            if action_type == 'click' and target:
                x, y = target[:2]
                status = "✓" if success else "✗"
                history_parts.append(f"{status} Click({x},{y})")
            elif action_type == 'keypress':
                key = action.get('key', 'unknown')
                status = "✓" if success else "✗"
                history_parts.append(f"{status} Key({key})")
            elif action_type == 'drag' and target and len(target) >= 4:
                x1, y1, x2, y2 = target[:4]
                status = "✓" if success else "✗"
                history_parts.append(f"{status} Drag({x1},{y1}→{x2},{y2})")
            elif action_type == 'scroll' and target and len(target) >= 3:
                x, y, amount = target[:3]
                status = "✓" if success else "✗"
                history_parts.append(f"{status} Scroll({x},{y},{amount})")
            elif action_type == 'wait':
                status = "✓" if success else "✗"
                history_parts.append(f"{status} Wait")
        
        return " → ".join(history_parts)
    
    def cleanup(self):
        """Clean up resources"""
        self.emergency_stop()
        self.debug_overlay.cleanup()
        self.logger.info("ActionEngine cleanup complete")