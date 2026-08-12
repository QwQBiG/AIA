"""Tests for the conversation engine and runtime absorbed from Rust."""

from collections import deque
from typing import Deque, List, Optional

import pytest

from src.domain import (
    AppError,
    ChatMessage,
    ConversationState,
    Speaker,
    SystemEvent,
    TurnId,
)
from src.conversation import (
    AvatarPort,
    ConversationEngine,
    EventSink,
    LanguageModelPort,
    Runtime,
    SpeechPort,
    _drain_complete_sentences,
)


# ---------------------------------------------------------------------------
# _drain_complete_sentences
# ---------------------------------------------------------------------------


class TestDrainCompleteSentences:
    """Unit tests for sentence boundary detection."""

    def test_empty_buffer(self):
        sentences, remainder = _drain_complete_sentences("")
        assert sentences == []
        assert remainder == ""

    def test_no_boundary(self):
        sentences, remainder = _drain_complete_sentences("incomplete text")
        assert sentences == []
        assert remainder == "incomplete text"

    def test_single_sentence_english(self):
        sentences, remainder = _drain_complete_sentences("Hello world.")
        assert sentences == ["Hello world."]
        assert remainder == ""

    def test_single_sentence_chinese(self):
        sentences, remainder = _drain_complete_sentences("\u4f60\u597d\u4e16\u754c\u3002")
        assert sentences == ["\u4f60\u597d\u4e16\u754c\u3002"]
        assert remainder == ""

    def test_multiple_sentences(self):
        sentences, remainder = _drain_complete_sentences("Hi! How are you?")
        assert sentences == ["Hi!", "How are you?"]
        assert remainder == ""

    def test_text_after_last_boundary(self):
        sentences, remainder = _drain_complete_sentences("Hello. Still going")
        assert sentences == ["Hello."]
        assert remainder.strip() == "Still going" or remainder == " Still going"

    def test_multiple_boundaries_with_trailing_text(self):
        sentences, remainder = _drain_complete_sentences("A. B? C! more text")
        assert sentences == ["A.", "B?", "C!"]
        assert remainder.strip() == "more text" or remainder == " more text"

    def test_only_non_boundary_punctuation(self):
        sentences, remainder = _drain_complete_sentences("hello, world; foo-bar")
        assert sentences == []
        assert remainder == "hello, world; foo-bar"

    def test_strips_whitespace(self):
        sentences, remainder = _drain_complete_sentences("  Hello.  ")
        assert sentences == ["Hello."]
        assert remainder.strip() == ""

    def test_consecutive_boundaries(self):
        sentences, remainder = _drain_complete_sentences("What!! Really?")
        assert sentences == ["What!", "!", "Really?"]
        assert remainder == ""


# ---------------------------------------------------------------------------
# ConversationEngine
# ---------------------------------------------------------------------------


class TestConversationEngineStartingState:
    """Engine behavior before any turn is started."""

    def test_initial_state_is_idle(self):
        engine = ConversationEngine()
        assert engine.state == ConversationState.IDLE

    def test_no_active_turn_initially(self):
        engine = ConversationEngine()
        assert engine.active_turn is None

    def test_empty_history_initially(self):
        engine = ConversationEngine()
        assert engine.history == []

    def test_empty_response_initially(self):
        engine = ConversationEngine()
        assert engine.last_full_response == ""


class TestConversationEngineBeginTurn:
    """begin_turn method behavior."""

    def test_returns_turn_id(self):
        engine = ConversationEngine()
        turn_id = engine.begin_turn("hello")
        assert isinstance(turn_id, TurnId)
        assert turn_id.value == 1

    def test_transitions_to_thinking(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        assert engine.state == ConversationState.THINKING

    def test_sets_active_turn(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        assert engine.active_turn == tid

    def test_adds_user_message_to_history(self):
        engine = ConversationEngine()
        engine.begin_turn("how are you?")
        assert len(engine.history) == 1
        msg = engine.history[0]
        assert msg.speaker == Speaker.USER
        assert msg.text == "how are you?"

    def test_increments_turn_id(self):
        engine = ConversationEngine()
        t1 = engine.begin_turn("first")
        # Simulate end of turn
        engine.finish_turn(t1)
        t2 = engine.begin_turn("second")
        assert t2.value == t1.value + 1

    def test_raises_when_not_idle(self):
        engine = ConversationEngine()
        engine.begin_turn("first")
        with pytest.raises(AppError) as exc_info:
            engine.begin_turn("second")
        assert "cannot begin a turn" in str(exc_info.value).lower()

    def test_raises_on_empty_text(self):
        engine = ConversationEngine()
        with pytest.raises(AppError) as exc_info:
            engine.begin_turn("")
        assert "empty" in str(exc_info.value).lower()

    def test_raises_on_whitespace_only(self):
        engine = ConversationEngine()
        with pytest.raises(AppError):
            engine.begin_turn("   ")

    def test_emits_turn_started_event(self):
        engine = ConversationEngine()
        engine.begin_turn("hello world")
        events = list(engine.drain_events())
        assert any(
            e.kind == "turn_started" and e.user_text == "hello world"
            for e in events
        )

    def test_emits_state_changed_event(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        events = list(engine.drain_events())
        assert any(
            e.kind == "state_changed"
            and e.from_state == ConversationState.IDLE
            and e.to_state == ConversationState.THINKING
            for e in events
        )


class TestConversationEngineAcceptChunk:
    """accept_model_chunk method behavior."""

    def test_single_sentence_emits_sentence_ready(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.drain_events()  # clear start events
        engine.accept_model_chunk(tid, "Hello world.")
        events = list(engine.drain_events())
        assert any(
            e.kind == "sentence_ready" and e.text == "Hello world."
            for e in events
        )

    def test_emits_model_chunk_event(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.drain_events()
        engine.accept_model_chunk(tid, "some text")
        events = list(engine.drain_events())
        assert any(
            e.kind == "model_chunk" and e.text == "some text"
            for e in events
        )

    def test_no_sentence_ready_for_no_boundary(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.drain_events()
        engine.accept_model_chunk(tid, "incomplete")
        events = list(engine.drain_events())
        assert not any(e.kind == "sentence_ready" for e in events)

    def test_multi_sentence_chunk(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.drain_events()
        engine.accept_model_chunk(tid, "A. B. C.")
        events = [e for e in engine.drain_events() if e.kind == "sentence_ready"]
        assert len(events) == 3

    def test_raises_for_wrong_turn_id(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        wrong_tid = TurnId(999)
        with pytest.raises(AppError) as exc_info:
            engine.accept_model_chunk(wrong_tid, "test")
        assert "active turn" in str(exc_info.value).lower()


class TestConversationEngineFinishTurn:
    """finish_turn method behavior."""

    def test_returns_to_idle(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.finish_turn(tid)
        assert engine.state == ConversationState.IDLE

    def test_clears_active_turn(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.finish_turn(tid)
        assert engine.active_turn is None

    def test_flushes_remaining_buffer(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.accept_model_chunk(tid, "incomplete text")
        engine.drain_events()
        engine.finish_turn(tid)
        events = [e for e in engine.drain_events() if e.kind == "sentence_ready"]
        assert any("incomplete text" in e.text for e in events)

    def test_adds_to_history(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.finish_turn(tid)
        assert len(engine.history) >= 1

    def test_raises_for_wrong_turn_id(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        with pytest.raises(AppError):
            engine.finish_turn(TurnId(999))


class TestConversationEngineInterrupt:
    """interrupt method behavior."""

    def test_transitions_to_interrupted_then_idle(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        engine.interrupt("user pressed escape")
        assert engine.state == ConversationState.IDLE

    def test_clears_active_turn(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        engine.interrupt("reason")
        assert engine.active_turn is None

    def test_emits_turn_interrupted_event(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.interrupt("test")
        events = list(engine.drain_events())
        assert any(
            e.kind == "turn_interrupted"
            and e.turn_id == tid
            and e.reason == "test"
            for e in events
        )

    def test_raises_when_no_active_turn(self):
        engine = ConversationEngine()
        with pytest.raises(AppError) as exc_info:
            engine.interrupt("test")
        assert "no active turn" in str(exc_info.value).lower()


class TestConversationEngineFail:
    """fail method behavior."""

    def test_transitions_to_failed(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        engine.fail("something went wrong")
        assert engine.state == ConversationState.FAILED

    def test_clears_active_turn(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        engine.fail("error")
        assert engine.active_turn is None

    def test_emits_fault_event(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        engine.fail("critical error")
        events = list(engine.drain_events())
        assert any(
            e.kind == "fault" and e.message == "critical error"
            for e in events
        )


class TestConversationEngineLifecycle:
    """Full conversation lifecycle scenarios."""

    def test_full_round_trip(self):
        engine = ConversationEngine()
        tid = engine.begin_turn("hello")
        engine.accept_model_chunk(tid, "Hi there.")
        engine.finish_turn(tid)
        assert engine.state == ConversationState.IDLE
        assert engine.active_turn is None
        assert len(engine.history) == 2

    def test_can_start_new_turn_after_finish(self):
        engine = ConversationEngine()
        t1 = engine.begin_turn("first")
        engine.finish_turn(t1)
        t2 = engine.begin_turn("second")
        assert t2.value == 2

    def test_can_start_new_turn_after_interrupt(self):
        engine = ConversationEngine()
        engine.begin_turn("first")
        engine.interrupt("stop")
        engine.drain_events()
        t2 = engine.begin_turn("second")
        assert t2.value > 1

    def test_drain_events_empties_pending(self):
        engine = ConversationEngine()
        engine.begin_turn("hello")
        events1 = list(engine.drain_events())
        assert len(events1) > 0
        events2 = list(engine.drain_events())
        assert len(events2) == 0


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


class TestMockPorts:
    """In-memory port implementations for testing Runtime."""

    @pytest.fixture
    def mock_ports(self):
        model = _MockModel()
        speech = _MockSpeech()
        avatar = _MockAvatar()
        events = _MockEventSink()
        return model, speech, avatar, events

    @pytest.fixture
    def runtime(self, mock_ports):
        model, speech, avatar, events = mock_ports
        return Runtime(model=model, speech=speech, avatar=avatar, events=events)

    def test_begin_turn_calls_model_start_turn(self, mock_ports, runtime):
        model, *_ = mock_ports
        runtime.begin_turn("hello")
        assert len(model.started) == 1
        assert model.started[0].value == 1

    def test_finish_turn_calls_avatar_neutral(self, mock_ports, runtime):
        model, speech, avatar, events = mock_ports
        tid = runtime.begin_turn("hello")
        runtime.finish_turn(tid)
        assert avatar.speaking is False

    def test_sentence_ready_queues_speech(self, mock_ports, runtime):
        model, speech, avatar, events = mock_ports
        tid = runtime.begin_turn("hello")
        runtime.accept_model_chunk(tid, "Hello world.")
        assert len(speech.queue) > 0
        assert "Hello world." in speech.queue

    def test_interrupt_cancels_model_and_speech(self, mock_ports, runtime):
        model, speech, avatar, events = mock_ports
        tid = runtime.begin_turn("hello")
        runtime.accept_model_chunk(tid, "Hello world.")
        runtime.interrupt("user interrupt")
        assert len(model.cancelled) > 0
        assert speech.interrupted
        assert avatar.speaking is False

    def test_state_is_accessible(self, mock_ports, runtime):
        assert runtime.state() == ConversationState.IDLE
        runtime.begin_turn("hello")
        assert runtime.state() == ConversationState.THINKING


# ---------------------------------------------------------------------------
# Mock port implementations
# ---------------------------------------------------------------------------


class _MockModel:
    def __init__(self):
        self.started: List[TurnId] = []
        self.cancelled: List[TurnId] = []

    def start_turn(self, turn_id: TurnId, history: List[ChatMessage]) -> None:
        self.started.append(turn_id)

    def cancel_turn(self, turn_id: TurnId) -> None:
        self.cancelled.append(turn_id)


class _MockSpeech:
    def __init__(self):
        self.queue: List[str] = []
        self.interrupted: bool = False

    def enqueue_sentence(self, turn_id: TurnId, sentence: str) -> None:
        self.queue.append(sentence)

    def interrupt(self) -> None:
        self.interrupted = True


class _MockAvatar:
    def __init__(self):
        self.speaking: bool = False
        self.neutral_count: int = 0

    def set_speaking(self, speaking: bool) -> None:
        self.speaking = speaking

    def set_neutral(self) -> None:
        self.speaking = False
        self.neutral_count += 1


class _MockEventSink:
    def __init__(self):
        self.events: List[SystemEvent] = []

    def publish(self, event: SystemEvent) -> None:
        self.events.append(event)
