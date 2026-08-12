"""
Unit and property tests for error handling system.

Feature: ai-vtuber-system
"""

import asyncio
import logging
import os
import tempfile
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, assume

from src.error_handler import ErrorHandler


class TestErrorHandler:
    """Unit tests for ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.error_handler = ErrorHandler(self.logger)
    
    def test_error_handler_initialization(self):
        """Test ErrorHandler initialization."""
        # Test with provided logger
        handler = ErrorHandler(self.logger)
        assert handler.logger == self.logger
        assert handler.max_retries == 3
        assert handler.base_delay == 1.0
        assert handler.max_delay == 30.0
        assert handler.retry_counts == {}
        
        # Test with default logger
        handler_default = ErrorHandler()
        assert handler_default.logger is not None
    
    def test_network_error_handling(self):
        """Test network error handling and logging."""
        exception = ConnectionError("Network unreachable")
        context = {"url": "http://localhost:11434", "timeout": 30}
        
        self.error_handler.handle_network_error("ollama_connect", exception, context)
        
        # Verify logging calls
        self.logger.error.assert_called()
        self.logger.debug.assert_called()
        
        # Check retry count was updated
        assert self.error_handler.get_retry_count("network_ollama_connect") == 1
    
    def test_file_error_handling(self):
        """Test file system error handling."""
        exception = FileNotFoundError("File not found")
        file_path = "/nonexistent/path/file.txt"
        
        self.error_handler.handle_file_error(file_path, exception, "audio_save")
        
        # Verify logging calls
        self.logger.error.assert_called()
        self.logger.debug.assert_called()
    
    def test_thread_error_handling(self):
        """Test thread error handling with cleanup."""
        exception = RuntimeError("Thread crashed")
        cleanup_func = Mock()
        
        self.error_handler.handle_thread_error("audio_thread", exception, cleanup_func)
        
        # Verify cleanup was called
        cleanup_func.assert_called_once()
        
        # Verify logging
        self.logger.error.assert_called()
        self.logger.info.assert_called()
    
    def test_thread_error_handling_cleanup_failure(self):
        """Test thread error handling when cleanup fails."""
        exception = RuntimeError("Thread crashed")
        cleanup_func = Mock(side_effect=Exception("Cleanup failed"))
        
        self.error_handler.handle_thread_error("audio_thread", exception, cleanup_func)
        
        # Verify cleanup was attempted
        cleanup_func.assert_called_once()
        
        # Verify error logging for both original error and cleanup failure
        assert self.logger.error.call_count >= 2
    
    def test_retry_count_management(self):
        """Test retry count tracking and reset."""
        operation = "test_operation"
        
        # Initial count should be 0
        assert self.error_handler.get_retry_count(f"network_{operation}") == 0
        
        # Simulate some errors
        exception = Exception("Test error")
        self.error_handler.handle_network_error(operation, exception)
        self.error_handler.handle_network_error(operation, exception)
        
        # Check count increased
        assert self.error_handler.get_retry_count(f"network_{operation}") == 2
        
        # Reset count
        self.error_handler.reset_retry_count(f"network_{operation}")
        assert self.error_handler.get_retry_count(f"network_{operation}") == 0
    
    def test_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        # Test exponential growth
        delay_0 = self.error_handler._calculate_backoff_delay(0)
        delay_1 = self.error_handler._calculate_backoff_delay(1)
        delay_2 = self.error_handler._calculate_backoff_delay(2)
        
        assert delay_0 == 1.0  # base_delay * 2^0
        assert delay_1 == 2.0  # base_delay * 2^1
        assert delay_2 == 4.0  # base_delay * 2^2
        
        # Test max delay cap
        large_delay = self.error_handler._calculate_backoff_delay(10)
        assert large_delay == self.error_handler.max_delay
    
    def test_recoverable_error_detection(self):
        """Test detection of recoverable vs non-recoverable errors."""
        # Recoverable network errors
        assert self.error_handler.is_recoverable_error(ConnectionError("Connection failed"))
        assert self.error_handler.is_recoverable_error(TimeoutError("Request timeout"))
        
        # Recoverable file errors
        assert self.error_handler.is_recoverable_error(FileNotFoundError("File not found"))
        assert self.error_handler.is_recoverable_error(PermissionError("Access denied"))
        
        # Non-recoverable errors
        assert not self.error_handler.is_recoverable_error(ValueError("Invalid input"))
        assert not self.error_handler.is_recoverable_error(TypeError("Type mismatch"))
    
    def test_error_context_creation(self):
        """Test error context dictionary creation."""
        context = self.error_handler.create_error_context(
            operation="test_op",
            user_input="test message"
        )
        
        assert "timestamp" in context
        assert "system_info" in context
        assert context["operation"] == "test_op"
        assert context["user_input"] == "test message"
        assert "platform" in context["system_info"]
        assert "cwd" in context["system_info"]
    
    def test_operation_logging(self):
        """Test operation start and success logging."""
        operation = "test_operation"
        
        # Test operation start logging
        self.error_handler.log_operation_start(operation, param1="value1")
        self.logger.info.assert_called_with(f"Starting operation: {operation}")
        self.logger.debug.assert_called()
        
        # Test operation success logging
        self.error_handler.log_operation_success(operation, duration=1.5)
        success_call = [call for call in self.logger.info.call_args_list 
                       if "completed successfully" in str(call)]
        assert len(success_call) > 0


class TestRetryDecorator:
    """Tests for the retry decorator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.error_handler = ErrorHandler(self.logger)
    
    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async retry decorator with eventual success."""
        call_count = 0
        
        @self.error_handler.with_retry("test_async_op", max_retries=2)
        async def failing_async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await failing_async_func()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_max_retries_exceeded(self):
        """Test async retry decorator when max retries exceeded."""
        @self.error_handler.with_retry("test_async_op", max_retries=1)
        async def always_failing_async_func():
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            await always_failing_async_func()
    
    def test_sync_retry_success(self):
        """Test sync retry decorator with eventual success."""
        call_count = 0
        
        @self.error_handler.with_retry("test_sync_op", max_retries=2)
        def failing_sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = failing_sync_func()
        assert result == "success"
        assert call_count == 3
    
    def test_sync_retry_max_retries_exceeded(self):
        """Test sync retry decorator when max retries exceeded."""
        @self.error_handler.with_retry("test_sync_op", max_retries=1)
        def always_failing_sync_func():
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            always_failing_sync_func()


class TestErrorHandlingAndLoggingProperty:
    """Property-based tests for error handling and logging."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.error_handler = ErrorHandler(self.logger)
    
    @given(
        operation_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        error_message=st.text(min_size=1, max_size=200)
    )
    def test_error_handling_and_logging_property(self, operation_name, error_message):
        """
        Property 2: Error Handling and Logging
        For any system operation that fails (network, file, or other), the system should 
        capture the exception and log detailed error information to the GUI log area.
        
        Feature: ai-vtuber-system, Property 2: Error Handling and Logging
        Validates: Requirements 1.3, 2.3, 3.3, 5.1, 5.2, 5.5
        """
        # Filter operation name to be valid
        safe_operation = "".join(c for c in operation_name if c.isalnum() or c == '_')
        assume(len(safe_operation) > 0)
        
        # Test different types of exceptions
        test_exceptions = [
            ConnectionError(error_message),
            FileNotFoundError(error_message),
            TimeoutError(error_message),
            PermissionError(error_message),
            RuntimeError(error_message)
        ]
        
        for exception in test_exceptions:
            # Reset logger mock for each test
            self.logger.reset_mock()
            
            # Create error context
            context = self.error_handler.create_error_context(
                operation=safe_operation,
                error_type=type(exception).__name__
            )
            
            # Handle the error based on type
            if isinstance(exception, (ConnectionError, TimeoutError)):
                self.error_handler.handle_network_error(safe_operation, exception, context)
            elif isinstance(exception, (FileNotFoundError, PermissionError)):
                self.error_handler.handle_file_error("/test/path", exception, safe_operation)
            else:
                self.error_handler.handle_thread_error(safe_operation, exception)
            
            # Verify that error was logged
            assert self.logger.error.called, f"Error should be logged for {type(exception).__name__}"
            
            # Verify error message contains relevant information
            error_calls = [str(call) for call in self.logger.error.call_args_list]
            assert any(safe_operation in call or error_message in call for call in error_calls), \
                f"Error log should contain operation name or error message"
            
            # Verify debug information was logged
            assert self.logger.debug.called, f"Debug info should be logged for {type(exception).__name__}"
    
    @given(
        file_paths=st.lists(
            st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Po'))),
            min_size=1,
            max_size=5
        )
    )
    def test_file_error_logging_consistency(self, file_paths):
        """
        Test that file errors are consistently logged with absolute paths.
        This supports the file path consistency property.
        """
        for file_path in file_paths:
            # Create a safe file path
            safe_path = "".join(c for c in file_path if c.isalnum() or c in "._-/\\")
            if not safe_path:
                safe_path = "test_file.txt"
            
            # Reset logger mock
            self.logger.reset_mock()
            
            # Handle file error
            exception = FileNotFoundError(f"File not found: {safe_path}")
            self.error_handler.handle_file_error(safe_path, exception, "file_operation")
            
            # Verify error was logged
            assert self.logger.error.called
            
            # Verify absolute path was logged
            error_calls = [str(call) for call in self.logger.error.call_args_list]
            # Should contain absolute path information
            assert any("File path:" in call for call in error_calls)
    
    @given(
        retry_attempts=st.integers(min_value=0, max_value=10),
        operation_names=st.lists(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            min_size=1,
            max_size=3
        )
    )
    def test_retry_mechanism_consistency(self, retry_attempts, operation_names):
        """
        Test that retry mechanisms work consistently across different operations.
        """
        for operation_name in operation_names:
            safe_operation = "".join(c for c in operation_name if c.isalnum() or c == '_')
            assume(len(safe_operation) > 0)
            
            # Reset retry counts
            self.error_handler.retry_counts.clear()
            
            # Simulate multiple failures
            exception = ConnectionError("Network error")
            for attempt in range(min(retry_attempts, self.error_handler.max_retries + 1)):
                self.error_handler.handle_network_error(safe_operation, exception)
            
            # Verify retry count tracking
            expected_count = min(retry_attempts, self.error_handler.max_retries + 1)
            actual_count = self.error_handler.get_retry_count(f"network_{safe_operation}")
            assert actual_count == expected_count
            
            # Test retry count reset
            self.error_handler.reset_retry_count(f"network_{safe_operation}")
            assert self.error_handler.get_retry_count(f"network_{safe_operation}") == 0
    
    @given(
        thread_names=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        has_cleanup=st.booleans()
    )
    def test_thread_error_handling_property(self, thread_names, has_cleanup):
        """
        Test that thread errors are handled consistently with proper cleanup.
        """
        safe_thread_name = "".join(c for c in thread_names if c.isalnum() or c == '_')
        assume(len(safe_thread_name) > 0)
        
        # Reset logger mock
        self.logger.reset_mock()
        
        # Create cleanup function if needed
        cleanup_func = Mock() if has_cleanup else None
        
        # Handle thread error
        exception = RuntimeError("Thread error")
        self.error_handler.handle_thread_error(safe_thread_name, exception, cleanup_func)
        
        # Verify error was logged
        assert self.logger.error.called
        
        # Verify cleanup was called if provided
        if has_cleanup:
            cleanup_func.assert_called_once()
            # Should log cleanup success
            success_calls = [call for call in self.logger.info.call_args_list 
                           if "Cleanup completed" in str(call)]
            assert len(success_calls) > 0
        
        # Verify thread name appears in logs
        all_calls = [str(call) for call in self.logger.error.call_args_list + self.logger.info.call_args_list]
        assert any(safe_thread_name in call for call in all_calls)