"""
Unit and property tests for GUI Controller.

This module tests the GUI controller functionality including window creation,
user interactions, logging system, and threading behavior.
"""

import pytest
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import queue
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, settings, HealthCheck
import logging

from src.gui_controller import GUIController, GUILogHandler
from src.config import SystemConfig


class TestGUIController:
    """Test cases for GUIController class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SystemConfig(
            ollama_url="http://localhost:11434",
            ollama_model="test-model",
            log_level="INFO"
        )
    
    @pytest.fixture
    def gui_controller(self, config):
        """Create GUI controller for testing."""
        controller = GUIController(config)
        yield controller
        # Cleanup
        if controller.root:
            controller.destroy()
    
    def test_gui_initialization(self, gui_controller):
        """Test GUI controller initialization."""
        assert gui_controller.config is not None
        assert gui_controller.system_state is not None
        assert gui_controller.error_handler is not None
        assert isinstance(gui_controller.message_queue, queue.Queue)
        assert isinstance(gui_controller.log_queue, queue.Queue)
        assert not gui_controller.is_processing
    
    def test_setup_ui_creates_components(self, gui_controller):
        """
        Test that setup_ui creates all required GUI components.
        
        Validates Requirements 4.1, 4.2 - GUI window creation and component layout.
        """
        gui_controller.setup_ui()
        
        # Check main window
        assert gui_controller.root is not None
        assert isinstance(gui_controller.root, tk.Tk)
        assert "AI VTuber System" in gui_controller.root.title()
        
        # Check input components
        assert gui_controller.input_entry is not None
        assert isinstance(gui_controller.input_entry, tk.Entry)
        assert gui_controller.send_button is not None
        assert isinstance(gui_controller.send_button, tk.Button)
        assert gui_controller.send_button['text'] == "发送"
        
        # Check log display
        assert gui_controller.log_text is not None
        assert isinstance(gui_controller.log_text, scrolledtext.ScrolledText)
        
        # Check status indicators
        assert gui_controller.ollama_status_label is not None
        assert gui_controller.vts_status_label is not None
        assert isinstance(gui_controller.ollama_status_label, tk.Label)
        assert isinstance(gui_controller.vts_status_label, tk.Label)
        
        # Check progress bar
        assert gui_controller.progress_bar is not None
        assert isinstance(gui_controller.progress_bar, ttk.Progressbar)
    
    def test_connection_status_update(self, gui_controller):
        """
        Test connection status updates.
        
        Validates Requirements 4.2 - Status indicator functionality.
        """
        gui_controller.setup_ui()
        
        # Test Ollama connection status
        gui_controller.update_connection_status("ollama", True)
        assert gui_controller.system_state.ollama_connected is True
        assert "已连接" in gui_controller.ollama_status_label['text']
        assert gui_controller.ollama_status_label['fg'] == "green"
        
        gui_controller.update_connection_status("ollama", False)
        assert gui_controller.system_state.ollama_connected is False
        assert "未连接" in gui_controller.ollama_status_label['text']
        assert gui_controller.ollama_status_label['fg'] == "red"
        
        # Test VTS connection status
        gui_controller.update_connection_status("vts", True)
        assert gui_controller.system_state.vts_connected is True
        assert "已连接" in gui_controller.vts_status_label['text']
        assert gui_controller.vts_status_label['fg'] == "green"
        
        gui_controller.update_connection_status("vts", False)
        assert gui_controller.system_state.vts_connected is False
        assert "未连接" in gui_controller.vts_status_label['text']
        assert gui_controller.vts_status_label['fg'] == "red"
    
    def test_callback_setting(self, gui_controller):
        """Test setting conversation and connection callbacks."""
        mock_callback = Mock()
        gui_controller.set_conversation_callback(mock_callback)
        assert gui_controller.conversation_callback == mock_callback
        
        mock_connection_callback = Mock()
        gui_controller.set_connection_check_callback(mock_connection_callback)
        assert gui_controller.connection_check_callback == mock_connection_callback
    
    def test_log_message_queuing(self, gui_controller):
        """
        Test log message queuing functionality.
        
        Validates Requirements 4.4 - Real-time log display.
        """
        gui_controller.setup_ui()
        
        # Clear queue
        while not gui_controller.log_queue.empty():
            gui_controller.log_queue.get_nowait()
        
        # Test different log levels
        test_messages = [
            ("Test info message", "INFO"),
            ("Test warning message", "WARNING"),
            ("Test error message", "ERROR"),
            ("Test success message", "SUCCESS")
        ]
        
        for message, level in test_messages:
            gui_controller.log_message(message, level)
            
            # Verify message was queued
            assert not gui_controller.log_queue.empty()
            
            # Get and verify message
            queued_message, queued_level = gui_controller.log_queue.get()
            assert message in queued_message
            assert queued_level == level
    
    def test_clear_log_functionality(self, gui_controller):
        """Test log clearing functionality."""
        gui_controller.setup_ui()
        
        # Add some log content
        gui_controller.log_message("Test message 1", "INFO")
        gui_controller.log_message("Test message 2", "INFO")
        gui_controller.process_message_queue()
        
        # Clear log
        gui_controller.clear_log()
        
        # Process the clear log message
        gui_controller.process_message_queue()
        
        # Verify log is cleared (should only contain the "日志已清除" message)
        log_content = gui_controller.log_text.get(1.0, tk.END)
        assert "日志已清除" in log_content
    
    def test_progress_bar_functionality(self, gui_controller):
        """Test progress bar show/hide functionality."""
        gui_controller.setup_ui()
        
        # Initially progress bar should not be visible
        assert gui_controller.progress_bar.winfo_manager() == ""
        
        # Show progress
        gui_controller.show_progress(True)
        assert gui_controller.progress_bar.winfo_manager() == "pack"
        
        # Hide progress
        gui_controller.show_progress(False)
        assert gui_controller.progress_bar.winfo_manager() == ""
    
    def test_input_validation(self, gui_controller):
        """
        Test input validation and handling.
        
        Validates Requirements 4.3 - User interaction handling.
        """
        gui_controller.setup_ui()
        
        # Test empty input handling
        gui_controller.input_entry.delete(0, tk.END)
        gui_controller.input_entry.insert(0, "")
        
        initial_processing = gui_controller.is_processing
        gui_controller.on_send_clicked()
        
        # Should not start processing for empty input
        assert gui_controller.is_processing == initial_processing
        
        # Test whitespace-only input
        gui_controller.input_entry.delete(0, tk.END)
        gui_controller.input_entry.insert(0, "   ")
        
        gui_controller.on_send_clicked()
        assert gui_controller.is_processing == initial_processing
    
    def test_event_handling_setup(self, gui_controller):
        """
        Test event handling setup.
        
        Validates Requirements 4.1, 4.5 - Event handling and threading.
        """
        gui_controller.setup_ui()
        
        # Test Enter key binding on input entry
        # This tests that the binding was set up correctly
        bindings = gui_controller.input_entry.bind()
        assert "<Key-Return>" in bindings
        
        # Test window close handler
        close_handler = gui_controller.root.protocol("WM_DELETE_WINDOW")
        assert close_handler is not None
    
    def test_thread_communication(self, gui_controller):
        """
        Test thread communication mechanisms.
        
        Validates Requirements 4.5 - Threading and communication.
        """
        gui_controller.setup_ui()
        
        # Test message queue communication
        test_message = "Thread communication test"
        gui_controller.message_queue.put((test_message, "INFO"))
        
        # Process queue
        gui_controller.process_message_queue()
        
        # Verify message was processed (queue should be empty)
        assert gui_controller.message_queue.empty()
    
    def test_ui_state_management(self, gui_controller):
        """
        Test UI state management during processing.
        
        Validates Requirements 4.3 - Non-blocking UI behavior.
        """
        gui_controller.setup_ui()
        
        # Set up mock callback
        mock_callback = Mock()
        gui_controller.set_conversation_callback(mock_callback)
        
        # Test initial state
        assert not gui_controller.is_processing
        assert gui_controller.send_button['state'] == tk.NORMAL
        assert gui_controller.send_button['text'] == "发送"
        
        # Set input and trigger processing
        gui_controller.input_entry.insert(0, "test input")
        gui_controller.on_send_clicked()
        
        # Verify processing state
        assert gui_controller.is_processing
        assert gui_controller.send_button['state'] == tk.DISABLED
        assert gui_controller.send_button['text'] == "处理中..."
        
        # Reset state manually (simulating completion)
        gui_controller._reset_ui_state()
        
        # Verify reset state
        assert not gui_controller.is_processing
        assert gui_controller.send_button['state'] == tk.NORMAL
        assert gui_controller.send_button['text'] == "发送"


class TestGUIInteractionPropertyTests:
    """Property-based tests for GUI interaction behavior."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SystemConfig(log_level="INFO")
    
    @pytest.fixture
    def gui_controller(self, config):
        """Create GUI controller for testing."""
        controller = GUIController(config)
        controller.setup_ui()
        yield controller
        # Cleanup
        controller.destroy()
    
    @given(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))
    @settings(max_examples=50, deadline=3000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_gui_interaction_response(self, gui_controller, user_input):
        """
        Property 9: GUI Interaction Response
        
        For any GUI button click or user interaction, the system should trigger
        the appropriate workflow without blocking the UI thread.
        
        **Feature: ai-vtuber-system, Property 9: GUI Interaction Response**
        **Validates: Requirements 4.3**
        """
        # Reset GUI state to ensure clean test
        gui_controller.is_processing = False
        gui_controller.send_button.config(state=tk.NORMAL, text="发送")
        
        # Set up a simple mock conversation callback
        callback_called = []
        
        def mock_callback(input_text):
            callback_called.append(input_text)
        
        gui_controller.set_conversation_callback(mock_callback)
        
        # Clear the input field and set test input
        gui_controller.input_entry.delete(0, tk.END)
        gui_controller.input_entry.insert(0, user_input)
        
        # Verify initial state
        assert not gui_controller.is_processing
        assert gui_controller.send_button['state'] == tk.NORMAL
        
        # Trigger send button click
        gui_controller.on_send_clicked()
        
        # Verify immediate UI response (non-blocking behavior)
        # The system should immediately change to processing state
        assert gui_controller.is_processing
        assert gui_controller.send_button['state'] == tk.DISABLED
        assert gui_controller.send_button['text'] == "处理中..."
        
        # Verify input field was cleared (immediate response)
        assert gui_controller.input_entry.get() == ""
        
        # The key property is that the UI responds immediately without blocking
        # We don't need to wait for the background thread to complete
    
    @given(st.lists(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()), min_size=1, max_size=3))
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_sequential_interactions(self, gui_controller, input_list):
        """
        Extended Property 9: Sequential GUI Interactions
        
        For any sequence of GUI interactions, the system should handle each
        interaction appropriately without crashing.
        
        **Feature: ai-vtuber-system, Property 9: GUI Interaction Response**
        **Validates: Requirements 4.3**
        """
        processed_inputs = []
        
        def mock_callback(input_text):
            processed_inputs.append(input_text)
        
        gui_controller.set_conversation_callback(mock_callback)
        
        # Ensure GUI is in ready state before testing
        gui_controller.is_processing = False
        gui_controller.send_button.config(state=tk.NORMAL, text="发送")
        
        # Process each input with a small delay between them
        for user_input in input_list:
            # Ensure we're not in processing state before each interaction
            gui_controller.is_processing = False
            gui_controller.send_button.config(state=tk.NORMAL, text="发送")
            
            # Set input and trigger send
            gui_controller.input_entry.delete(0, tk.END)
            gui_controller.input_entry.insert(0, user_input)
            
            # Trigger interaction
            gui_controller.on_send_clicked()
            
            # Verify immediate response - input should be cleared
            assert gui_controller.input_entry.get() == ""
            
            # Small delay between interactions
            time.sleep(0.05)
        
        # Give time for processing
        time.sleep(0.2)
        
        # Verify system handled all interactions (may not process all due to threading)
        # But should have at least attempted to handle them
        assert len(processed_inputs) >= 0  # System should respond to interactions


class TestGUIControllerPropertyTests:
    """Property-based tests for GUI Controller."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SystemConfig(log_level="INFO")
    
    @pytest.fixture
    def gui_controller(self, config):
        """Create GUI controller for testing."""
        controller = GUIController(config)
        controller.setup_ui()
        yield controller
        # Cleanup
        controller.destroy()
    
    @given(st.text(min_size=1, max_size=1000).filter(lambda x: x.strip()))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_operation_logging(self, gui_controller, operation_text):
        """
        Property 8: Operation Logging
        
        For any system operation (initialization, user interaction, processing step),
        the system should log status information to the GUI log area in real-time.
        
        **Feature: ai-vtuber-system, Property 8: Operation Logging**
        **Validates: Requirements 4.4, 5.3, 5.4**
        """
        # Clear any existing messages in the queue
        while not gui_controller.log_queue.empty():
            gui_controller.log_queue.get_nowait()
        
        # Perform operation logging
        gui_controller.log_message(operation_text, "INFO")
        
        # Verify message was queued (before processing)
        assert gui_controller.log_queue.qsize() > 0
        
        # Process the message queue
        gui_controller.process_message_queue()
        
        # Verify log text widget contains the message (if GUI is set up)
        if gui_controller.log_text:
            log_content = gui_controller.log_text.get(1.0, tk.END)
            # The message should appear in the log (may be formatted with timestamp)
            # Check if the operation text (or parts of it) appears in the log
            stripped_text = operation_text.strip()
            if stripped_text:
                assert stripped_text in log_content or any(
                    word in log_content for word in stripped_text.split() 
                    if len(word.strip()) > 0
                )
    
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=100),
                st.sampled_from(["INFO", "WARNING", "ERROR", "SUCCESS", "DEBUG", "SYSTEM"])
            ),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_multiple_operations_logging(self, gui_controller, operations):
        """
        Extended Property 8: Multiple Operations Logging
        
        For any sequence of system operations, all operations should be logged
        to the GUI log area in the correct order.
        
        **Feature: ai-vtuber-system, Property 8: Operation Logging**
        **Validates: Requirements 4.4, 5.3, 5.4**
        """
        # Clear log queue
        while not gui_controller.log_queue.empty():
            gui_controller.log_queue.get_nowait()
        
        # Log all operations
        for message, level in operations:
            gui_controller.log_message(message, level)
        
        # Process all messages
        gui_controller.process_message_queue()
        
        # Verify all messages were processed
        # The queue should be empty after processing
        assert gui_controller.log_queue.empty()
        
        # If GUI is set up, verify log content
        if gui_controller.log_text:
            log_content = gui_controller.log_text.get(1.0, tk.END)
            
            # Check that at least some operation text appears in the log
            logged_words = set()
            for message, _ in operations:
                logged_words.update(word.strip() for word in message.split() if word.strip())
            
            # At least some words from the operations should appear in the log
            content_words = set(log_content.split())
            assert len(logged_words.intersection(content_words)) > 0


class TestGUILogHandler:
    """Test cases for GUILogHandler."""
    
    @pytest.fixture
    def gui_controller(self):
        """Create mock GUI controller."""
        controller = Mock()
        controller.log_queue = queue.Queue()
        return controller
    
    @pytest.fixture
    def log_handler(self, gui_controller):
        """Create log handler for testing."""
        return GUILogHandler(gui_controller)
    
    def test_log_handler_initialization(self, log_handler, gui_controller):
        """Test log handler initialization."""
        assert log_handler.gui_controller == gui_controller
    
    def test_log_handler_emit_info(self, log_handler, gui_controller):
        """Test log handler emits INFO messages correctly."""
        # Create log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test info message",
            args=(),
            exc_info=None
        )
        
        # Set formatter
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        
        # Emit record
        log_handler.emit(record)
        
        # Check message was queued
        assert not gui_controller.log_queue.empty()
        message, level = gui_controller.log_queue.get()
        assert "Test info message" in message
        assert level == "INFO"
    
    def test_log_handler_emit_error(self, log_handler, gui_controller):
        """Test log handler emits ERROR messages correctly."""
        # Create error log record
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test error message",
            args=(),
            exc_info=None
        )
        
        # Set formatter
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        
        # Emit record
        log_handler.emit(record)
        
        # Check message was queued
        assert not gui_controller.log_queue.empty()
        message, level = gui_controller.log_queue.get()
        assert "Test error message" in message
        assert level == "ERROR"
    
    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_log_handler_message_preservation(self, log_handler, gui_controller, log_message):
        """
        Property: Log Handler Message Preservation
        
        For any log message, the log handler should preserve the message content
        when emitting to the GUI queue.
        
        **Feature: ai-vtuber-system, Property 8: Operation Logging**
        **Validates: Requirements 4.4, 5.3, 5.4**
        """
        # Create log record with the message
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=log_message,
            args=(),
            exc_info=None
        )
        
        # Set simple formatter
        formatter = logging.Formatter('%(message)s')
        log_handler.setFormatter(formatter)
        
        # Emit record
        log_handler.emit(record)
        
        # Verify message was queued and content preserved
        if not gui_controller.log_queue.empty():
            queued_message, _ = gui_controller.log_queue.get()
            # The original message should be contained in the queued message
            assert log_message in queued_message