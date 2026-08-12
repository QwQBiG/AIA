"""
Error Handler for unified error management.

This module provides centralized error handling, logging, and recovery mechanisms
for the AI VTuber system. It handles network errors, file system errors, and
threading errors with appropriate retry strategies and graceful degradation.
"""

import asyncio
import logging
import time
import traceback
from typing import Optional, Callable, Any, Dict, List
from functools import wraps
from pathlib import Path
import os


class ErrorHandler:
    """
    Unified error handler for the AI VTuber system.
    
    Provides centralized error handling with retry mechanisms, logging,
    and graceful degradation strategies for different types of errors.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the error handler.
        
        Args:
            logger: Logger instance to use for error reporting
        """
        self.logger = logger or logging.getLogger(__name__)
        self.retry_counts: Dict[str, int] = {}
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay for exponential backoff
        self.max_delay = 30.0  # Maximum delay between retries
        
        # Enhanced error tracking for emotional intelligence features
        self.feature_failure_counts: Dict[str, int] = {}
        self.feature_failure_thresholds = {
            "emotional_intelligence": 5,
            "voice_cloning": 3,
            "expression_control": 5,
            "structured_response_parsing": 10
        }
        self.disabled_features: Dict[str, float] = {}  # feature -> disable_timestamp
        self.feature_disable_duration = 300.0  # 5 minutes
        
        # Graceful degradation tracking
        self.degradation_active = False
        self.basic_functionality_errors = 0
        self.max_basic_errors = 3
        
    def handle_network_error(self, operation: str, exception: Exception, 
                           context: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle network-related errors with logging and retry tracking.
        
        Args:
            operation: Description of the operation that failed
            exception: The exception that occurred
            context: Additional context information
        """
        error_key = f"network_{operation}"
        retry_count = self.retry_counts.get(error_key, 0)
        
        # Log the error with full context
        self.logger.error(
            f"Network error in {operation} (attempt {retry_count + 1}): {str(exception)}"
        )
        self.logger.debug(f"Network error traceback: {traceback.format_exc()}")
        
        if context:
            self.logger.debug(f"Error context: {context}")
        
        # Update retry count
        self.retry_counts[error_key] = retry_count + 1
        
        # Log retry strategy
        if retry_count < self.max_retries:
            delay = self._calculate_backoff_delay(retry_count)
            self.logger.info(f"Will retry {operation} in {delay:.1f} seconds")
        else:
            self.logger.error(f"Max retries exceeded for {operation}, entering degraded mode")
    
    def handle_file_error(self, file_path: str, exception: Exception, 
                         operation: str = "file_operation") -> None:
        """
        Handle file system errors with logging and alternative strategies.
        
        Args:
            file_path: Path to the file that caused the error
            exception: The exception that occurred
            operation: Description of the file operation
        """
        abs_path = os.path.abspath(file_path) if file_path else "unknown"
        
        # Log detailed file error information
        self.logger.error(
            f"File system error in {operation}: {str(exception)}"
        )
        self.logger.error(f"File path: {abs_path}")
        self.logger.debug(f"File error traceback: {traceback.format_exc()}")
        
        # Check file/directory existence and permissions
        if file_path:
            try:
                path_obj = Path(abs_path)
                parent_dir = path_obj.parent
                
                self.logger.debug(f"File exists: {path_obj.exists()}")
                self.logger.debug(f"Parent directory exists: {parent_dir.exists()}")
                
                if parent_dir.exists():
                    self.logger.debug(f"Parent directory writable: {os.access(parent_dir, os.W_OK)}")
                    
            except Exception as e:
                self.logger.debug(f"Error checking file path details: {e}")
        
        # Suggest alternative locations for temporary files
        if "temp" in operation.lower() or "tmp" in abs_path.lower():
            self._suggest_alternative_temp_locations()
    
    def handle_thread_error(self, thread_name: str, exception: Exception,
                          cleanup_func: Optional[Callable] = None) -> None:
        """
        Handle threading errors with cleanup and reporting.
        
        Args:
            thread_name: Name of the thread where error occurred
            exception: The exception that occurred
            cleanup_func: Optional cleanup function to call
        """
        # Log thread error with full details
        self.logger.error(
            f"Thread error in {thread_name}: {str(exception)}"
        )
        self.logger.debug(f"Thread error traceback: {traceback.format_exc()}")
        
        # Attempt cleanup if provided
        if cleanup_func:
            try:
                cleanup_func()
                self.logger.info(f"Cleanup completed for thread {thread_name}")
            except Exception as cleanup_error:
                self.logger.error(
                    f"Cleanup failed for thread {thread_name}: {cleanup_error}"
                )
    
    def with_retry(self, operation: str, max_retries: Optional[int] = None):
        """
        Decorator for automatic retry with exponential backoff.
        
        Args:
            operation: Name of the operation for logging
            max_retries: Maximum number of retries (uses default if None)
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                retries = max_retries or self.max_retries
                last_exception = None
                
                for attempt in range(retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        if attempt < retries:
                            delay = self._calculate_backoff_delay(attempt)
                            self.logger.warning(
                                f"Attempt {attempt + 1} failed for {operation}: {e}. "
                                f"Retrying in {delay:.1f}s"
                            )
                            await asyncio.sleep(delay)
                        else:
                            self.handle_network_error(operation, e)
                            raise
                
                # This should never be reached, but just in case
                raise last_exception
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                retries = max_retries or self.max_retries
                last_exception = None
                
                for attempt in range(retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        if attempt < retries:
                            delay = self._calculate_backoff_delay(attempt)
                            self.logger.warning(
                                f"Attempt {attempt + 1} failed for {operation}: {e}. "
                                f"Retrying in {delay:.1f}s"
                            )
                            time.sleep(delay)
                        else:
                            self.handle_network_error(operation, e)
                            raise
                
                # This should never be reached, but just in case
                raise last_exception
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def reset_retry_count(self, operation: str) -> None:
        """
        Reset retry count for a specific operation.
        
        Args:
            operation: Operation name to reset
        """
        if operation in self.retry_counts:
            del self.retry_counts[operation]
            self.logger.debug(f"Reset retry count for {operation}")
    
    def get_retry_count(self, operation: str) -> int:
        """
        Get current retry count for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Current retry count
        """
        return self.retry_counts.get(operation, 0)
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
    
    def _suggest_alternative_temp_locations(self) -> None:
        """
        Suggest alternative temporary file locations when default fails.
        """
        import tempfile
        
        alternative_locations = [
            tempfile.gettempdir(),
            os.path.expanduser("~/tmp"),
            os.path.expanduser("~/AppData/Local/Temp") if os.name == 'nt' else "/tmp",
            "./temp"
        ]
        
        self.logger.info("Suggested alternative temporary file locations:")
        for location in alternative_locations:
            try:
                if os.path.exists(location) and os.access(location, os.W_OK):
                    self.logger.info(f"  ✓ {location} (writable)")
                else:
                    self.logger.info(f"  ✗ {location} (not accessible)")
            except Exception:
                self.logger.info(f"  ? {location} (cannot check)")
    
    def create_error_context(self, **kwargs) -> Dict[str, Any]:
        """
        Create error context dictionary for detailed logging.
        
        Args:
            **kwargs: Context key-value pairs
            
        Returns:
            Context dictionary
        """
        context = {
            "timestamp": time.time(),
            "system_info": {
                "platform": os.name,
                "cwd": os.getcwd()
            }
        }
        context.update(kwargs)
        return context
    
    def log_operation_start(self, operation: str, **context) -> None:
        """
        Log the start of an operation for tracking.
        
        Args:
            operation: Operation name
            **context: Additional context information
        """
        self.logger.info(f"Starting operation: {operation}")
        if context:
            self.logger.debug(f"Operation context: {context}")
    
    def log_operation_success(self, operation: str, duration: Optional[float] = None) -> None:
        """
        Log successful completion of an operation.
        
        Args:
            operation: Operation name
            duration: Operation duration in seconds
        """
        message = f"Operation completed successfully: {operation}"
        if duration is not None:
            message += f" (took {duration:.2f}s)"
        
        self.logger.info(message)
        
        # Reset retry count on success
        self.reset_retry_count(operation)
    
    def is_recoverable_error(self, exception: Exception) -> bool:
        """
        Determine if an error is recoverable and should be retried.
        
        Args:
            exception: The exception to check
            
        Returns:
            True if error is recoverable, False otherwise
        """
        # Network errors that are typically recoverable
        recoverable_network_errors = [
            "ConnectionError", "TimeoutError", "ConnectTimeout",
            "ReadTimeout", "ConnectionRefusedError", "TemporaryFailure"
        ]
        
        # File errors that might be recoverable
        recoverable_file_errors = [
            "PermissionError", "FileNotFoundError", "IsADirectoryError"
        ]
        
        exception_name = type(exception).__name__
        exception_str = str(exception).lower()
        
        # Check for recoverable network errors
        if any(error.lower() in exception_name.lower() or 
               error.lower() in exception_str for error in recoverable_network_errors):
            return True
        
        # Check for recoverable file errors (but not all file errors)
        if any(error.lower() in exception_name.lower() for error in recoverable_file_errors):
            return True
        
        # Specific patterns in error messages
        recoverable_patterns = [
            "connection reset", "connection aborted", "network unreachable",
            "temporary failure", "service unavailable", "timeout"
        ]
        
        if any(pattern in exception_str for pattern in recoverable_patterns):
            return True
        
    def handle_feature_failure(self, feature_name: str, exception: Exception, 
                             operation: str = "unknown") -> bool:
        """
        Handle feature-specific failures with tracking and temporary disabling.
        
        This method implements requirements 5.3, 6.4, and 6.5 for graceful degradation
        and error rate tracking with temporary feature disabling.
        
        Args:
            feature_name: Name of the feature that failed
            exception: The exception that occurred
            operation: Description of the operation that failed
            
        Returns:
            bool: True if feature should be temporarily disabled, False otherwise
        """
        # Log the feature failure
        self.logger.error(
            f"Feature failure in {feature_name} ({operation}): {str(exception)}"
        )
        self.logger.debug(f"Feature failure traceback: {traceback.format_exc()}")
        
        # Update failure count
        current_count = self.feature_failure_counts.get(feature_name, 0) + 1
        self.feature_failure_counts[feature_name] = current_count
        
        # Check if threshold exceeded
        threshold = self.feature_failure_thresholds.get(feature_name, 5)
        
        if current_count >= threshold:
            # Temporarily disable the feature
            self.disabled_features[feature_name] = time.time()
            self.logger.warning(
                f"Feature '{feature_name}' temporarily disabled due to {current_count} failures "
                f"(threshold: {threshold}). Will re-enable in {self.feature_disable_duration/60:.1f} minutes."
            )
            return True
        else:
            self.logger.info(
                f"Feature '{feature_name}' failure count: {current_count}/{threshold}"
            )
            return False
    
    def is_feature_disabled(self, feature_name: str) -> bool:
        """
        Check if a feature is currently disabled due to failures.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            bool: True if feature is disabled, False if available
        """
        if feature_name not in self.disabled_features:
            return False
        
        disable_time = self.disabled_features[feature_name]
        elapsed = time.time() - disable_time
        
        if elapsed >= self.feature_disable_duration:
            # Re-enable the feature
            del self.disabled_features[feature_name]
            self.feature_failure_counts[feature_name] = 0  # Reset failure count
            self.logger.info(f"Feature '{feature_name}' re-enabled after {elapsed/60:.1f} minutes")
            return False
        
        return True
    
    def handle_basic_functionality_error(self, operation: str, exception: Exception) -> bool:
        """
        Handle errors in basic conversation functionality.
        
        This method ensures basic conversation functionality is always available
        according to requirement 5.3.
        
        Args:
            operation: Description of the basic operation that failed
            exception: The exception that occurred
            
        Returns:
            bool: True if system should enter degraded mode, False otherwise
        """
        self.basic_functionality_errors += 1
        
        self.logger.error(
            f"Basic functionality error in {operation}: {str(exception)} "
            f"(error count: {self.basic_functionality_errors}/{self.max_basic_errors})"
        )
        
        if self.basic_functionality_errors >= self.max_basic_errors:
            if not self.degradation_active:
                self.degradation_active = True
                self.logger.critical(
                    f"System entering degraded mode due to {self.basic_functionality_errors} "
                    f"basic functionality errors. Enhanced features will be disabled."
                )
                
                # Disable all enhanced features when basic functionality fails
                current_time = time.time()
                for feature in self.feature_failure_thresholds.keys():
                    self.disabled_features[feature] = current_time
                
                return True
        
        return False
    
    def reset_basic_functionality_errors(self) -> None:
        """
        Reset basic functionality error count after successful operation.
        """
        if self.basic_functionality_errors > 0:
            self.logger.info("Basic functionality restored, resetting error count")
            self.basic_functionality_errors = 0
            
            if self.degradation_active:
                self.degradation_active = False
                self.logger.info("System exiting degraded mode")
    
    def get_feature_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all features and error tracking.
        
        Returns:
            Dict containing feature status, failure counts, and system health
        """
        current_time = time.time()
        
        feature_status = {}
        for feature in self.feature_failure_thresholds.keys():
            is_disabled = self.is_feature_disabled(feature)
            failure_count = self.feature_failure_counts.get(feature, 0)
            threshold = self.feature_failure_thresholds[feature]
            
            status = {
                "enabled": not is_disabled,
                "failure_count": failure_count,
                "failure_threshold": threshold,
                "health_percentage": max(0, 100 - (failure_count / threshold * 100))
            }
            
            if is_disabled:
                disable_time = self.disabled_features[feature]
                remaining_time = self.feature_disable_duration - (current_time - disable_time)
                status["re_enable_in_seconds"] = max(0, remaining_time)
            
            feature_status[feature] = status
        
        return {
            "features": feature_status,
            "degradation_active": self.degradation_active,
            "basic_functionality_errors": self.basic_functionality_errors,
            "max_basic_errors": self.max_basic_errors,
            "system_health": "degraded" if self.degradation_active else "normal"
        }
    
    def ensure_graceful_degradation(self, feature_name: str, fallback_func: Callable, 
                                  *args, **kwargs) -> Any:
        """
        Ensure graceful degradation by using fallback when feature is disabled.
        
        Args:
            feature_name: Name of the feature to check
            fallback_func: Function to call if feature is disabled
            *args, **kwargs: Arguments to pass to fallback function
            
        Returns:
            Result of fallback function if feature disabled, None otherwise
        """
        if self.is_feature_disabled(feature_name):
            self.logger.info(f"Using fallback for disabled feature: {feature_name}")
            try:
                return fallback_func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Fallback function failed for {feature_name}: {e}")
                return None
        
        return None