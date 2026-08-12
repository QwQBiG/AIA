"""Tests for the domain types absorbed from Rust."""

import pytest

from src.domain import (
    AppError,
    AppErrorCategory,
    ChatMessage,
    ConversationState,
    HealthStatus,
    Speaker,
    SystemEvent,
    TurnId,
)


class TestConversationState:
    """ConversationState enum behavior."""

    def test_accepts_user_input_when_idle(self):
        assert ConversationState.IDLE.accepts_user_input() is True

    def test_accepts_user_input_when_listening(self):
        assert ConversationState.LISTENING.accepts_user_input() is True

    def test_accepts_user_input_when_interrupted(self):
        assert ConversationState.INTERRUPTED.accepts_user_input() is True

    def test_rejects_user_input_when_thinking(self):
        assert ConversationState.THINKING.accepts_user_input() is False

    def test_rejects_user_input_when_speaking(self):
        assert ConversationState.SPEAKING.accepts_user_input() is False

    def test_rejects_user_input_when_failed(self):
        assert ConversationState.FAILED.accepts_user_input() is False

    def test_rejects_user_input_when_stopped(self):
        assert ConversationState.STOPPED.accepts_user_input() is False


class TestAppError:
    """AppError creation and category behavior."""

    def test_configuration_error(self):
        err = AppError.configuration("invalid port")
        assert isinstance(err, AppError)
        assert err.category == AppErrorCategory.CONFIGURATION
        assert "invalid port" in str(err)
        assert "configuration" in str(err)

    def test_connectivity_error(self):
        err = AppError.connectivity("connection refused")
        assert err.category == AppErrorCategory.CONNECTIVITY

    def test_invalid_transition_error(self):
        err = AppError.invalid_transition("can't go from A to B")
        assert err.category == AppErrorCategory.INVALID_TRANSITION

    def test_safety_violation_error(self):
        err = AppError.safety_violation("emergency stop")
        assert err.category == AppErrorCategory.SAFETY_VIOLATION

    def test_unavailable_error(self):
        err = AppError.unavailable("service not found")
        assert err.category == AppErrorCategory.UNAVAILABLE

    def test_can_be_caught_as_exception(self):
        with pytest.raises(AppError) as exc_info:
            raise AppError.configuration("test")
        assert exc_info.value.category == AppErrorCategory.CONFIGURATION


class TestChatMessage:
    """ChatMessage creation and immutability."""

    def test_user_message(self):
        msg = ChatMessage(Speaker.USER, "hello")
        assert msg.speaker == Speaker.USER
        assert msg.text == "hello"

    def test_assistant_message(self):
        msg = ChatMessage(Speaker.ASSISTANT, "hi there")
        assert msg.speaker == Speaker.ASSISTANT

    def test_system_message(self):
        msg = ChatMessage(Speaker.SYSTEM, "system msg")
        assert msg.speaker == Speaker.SYSTEM

    def test_immutable(self):
        msg = ChatMessage(Speaker.USER, "test")
        with pytest.raises(AttributeError):
            msg.text = "changed"


class TestTurnId:
    """TurnId creation and string representation."""

    def test_creation(self):
        tid = TurnId(42)
        assert tid.value == 42

    def test_str_representation(self):
        assert str(TurnId(7)) == "7"

    def test_immutable(self):
        tid = TurnId(1)
        with pytest.raises(AttributeError):
            tid.value = 2


class TestSystemEvent:
    """SystemEvent factory class methods."""

    def test_turn_started(self):
        tid = TurnId(1)
        event = SystemEvent.turn_started(tid, "hello")
        assert event.kind == "turn_started"
        assert event.turn_id == tid
        assert event.user_text == "hello"

    def test_model_chunk(self):
        tid = TurnId(1)
        event = SystemEvent.model_chunk(tid, "some text")
        assert event.kind == "model_chunk"
        assert event.text == "some text"

    def test_sentence_ready(self):
        tid = TurnId(2)
        event = SystemEvent.sentence_ready(tid, "complete sentence.")
        assert event.kind == "sentence_ready"
        assert event.text == "complete sentence."

    def test_turn_finished(self):
        tid = TurnId(3)
        event = SystemEvent.turn_finished(tid, "full response text")
        assert event.kind == "turn_finished"
        assert event.full_text == "full response text"

    def test_turn_interrupted(self):
        tid = TurnId(4)
        event = SystemEvent.turn_interrupted(tid, "user interrupt")
        assert event.kind == "turn_interrupted"
        assert event.reason == "user interrupt"

    def test_state_changed(self):
        event = SystemEvent.state_changed(
            ConversationState.IDLE, ConversationState.THINKING
        )
        assert event.kind == "state_changed"
        assert event.from_state == ConversationState.IDLE
        assert event.to_state == ConversationState.THINKING

    def test_fault(self):
        event = SystemEvent.fault("something broke")
        assert event.kind == "fault"
        assert event.message == "something broke"


class TestHealthStatus:
    """HealthStatus factory methods."""

    def test_healthy(self):
        hs = HealthStatus.healthy("audio")
        assert hs.component == "audio"
        assert hs.ready is True
        assert hs.detail == ""

    def test_unhealthy_with_detail(self):
        hs = HealthStatus.unhealthy("ollama", "connection lost")
        assert hs.component == "ollama"
        assert hs.ready is False
        assert hs.detail == "connection lost"

    def test_unhealthy_without_detail(self):
        hs = HealthStatus.unhealthy("vts")
        assert hs.ready is False
        assert hs.detail == ""
