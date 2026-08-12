"""Pure conversation state machine and port protocols.

Absorbed and adapted from the Rust ai-ex-core crate.
Provides the deterministic conversation engine with trait-based
port abstractions for testability.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Iterable, List, Optional, Protocol, runtime_checkable

from .domain import (
    AppError,
    ChatMessage,
    ConversationState,
    Speaker,
    SystemEvent,
    TurnId,
)


# -- Port Protocols (from Rust ai-ex-core) ----------------------------------


@runtime_checkable
class LanguageModelPort(Protocol):
    """Port for communicating with a language model."""

    def start_turn(self, turn_id: TurnId, history: List[ChatMessage]) -> None:
        """Start generating a response for the given turn."""

    def cancel_turn(self, turn_id: TurnId) -> None:
        """Cancel an ongoing generation."""


@runtime_checkable
class SpeechPort(Protocol):
    """Port for text-to-speech output."""

    def enqueue_sentence(self, turn_id: TurnId, sentence: str) -> None:
        """Enqueue a sentence for speech synthesis."""

    def interrupt(self) -> None:
        """Interrupt and clear the speech queue."""


@runtime_checkable
class AvatarPort(Protocol):
    """Port for controlling a virtual avatar."""

    def set_speaking(self, speaking: bool) -> None:
        """Set the avatar speaking state."""

    def set_neutral(self) -> None:
        """Reset the avatar to neutral expression."""


@runtime_checkable
class EventSink(Protocol):
    """Port for publishing system events."""

    def publish(self, event: SystemEvent) -> None:
        """Publish a system event."""


# -- Sentence Boundary Detection ---------------------------------------------

_SENTENCE_END_CHARS = frozenset("\u3002\uff01\uff1f.!?")


def _drain_complete_sentences(buffer: str) -> tuple[list[str], str]:
    if not buffer:
        return [], ""

    boundaries: list[int] = []
    for i, ch in enumerate(buffer):
        if ch in _SENTENCE_END_CHARS:
            boundaries.append(i + 1)

    if not boundaries:
        return [], buffer

    sentences: list[str] = []
    prev = 0
    for pos in boundaries:
        candidate = buffer[prev:pos].strip()
        if candidate:
            sentences.append(candidate)
        prev = pos

    remainder = buffer[boundaries[-1]:].strip()
    return sentences, remainder


# -- Conversation Engine -----------------------------------------------------


class ConversationEngine:
    """Pure conversation state machine.

    Manages conversation turns, state transitions, and sentence boundary
    detection. Closely mirrors the Rust ConversationEngine in ai-ex-core.
    """

    def __init__(self) -> None:
        self.state: ConversationState = ConversationState.IDLE
        self._next_turn_id: int = 1
        self._active_turn: Optional[TurnId] = None
        self._history: List[ChatMessage] = []
        self._pending_events: Deque[SystemEvent] = deque()
        self._buffer: str = ""
        self._response_sentences: List[str] = []
        self._last_full_response: str = ""

    @property
    def active_turn(self) -> Optional[TurnId]:
        return self._active_turn

    @property
    def history(self) -> List[ChatMessage]:
        return list(self._history)

    @property
    def last_full_response(self) -> str:
        return self._last_full_response

    # -- Public API ----------------------------------------------------------

    def begin_turn(self, user_text: str) -> TurnId:
        if not self.state.accepts_user_input():
            raise AppError.invalid_transition(
                f"cannot begin a turn while state is {self.state.name}"
            )
        text = user_text.strip()
        if not text:
            raise AppError.configuration("user input must not be empty")
        turn_id = TurnId(self._next_turn_id)
        self._next_turn_id += 1
        self._history.append(ChatMessage(Speaker.USER, text))
        self._active_turn = turn_id
        self._buffer = ""
        self._response_sentences = []
        self._transition_to(ConversationState.THINKING)
        self._pending_events.append(SystemEvent.turn_started(turn_id, text))
        return turn_id

    def accept_model_chunk(self, turn_id: TurnId, text: str) -> None:
        self._ensure_active_turn(turn_id)
        self._buffer += text
        sentences, self._buffer = _drain_complete_sentences(self._buffer)
        for sentence in sentences:
            self._response_sentences.append(sentence)
            self._pending_events.append(
                SystemEvent.sentence_ready(turn_id, sentence)
            )
        self._pending_events.append(
            SystemEvent.model_chunk(turn_id, text)
        )

    def finish_turn(self, turn_id: TurnId) -> None:
        self._ensure_active_turn(turn_id)
        remaining = self._buffer.strip()
        if remaining:
            self._response_sentences.append(remaining)
            self._pending_events.append(
                SystemEvent.sentence_ready(turn_id, remaining)
            )
        full_text = "".join(self._response_sentences)
        if self._response_sentences:
            self._history.append(ChatMessage(Speaker.ASSISTANT, full_text))
        self._last_full_response = full_text
        self._active_turn = None
        self._buffer = ""
        self._response_sentences = []
        self._pending_events.append(
            SystemEvent.turn_finished(turn_id, full_text)
        )
        self._transition_to(ConversationState.IDLE)

    def interrupt(self, reason: str) -> None:
        if self._active_turn is None:
            raise AppError.invalid_transition(
                "there is no active turn to interrupt"
            )
        turn_id = self._active_turn
        self._pending_events.append(
            SystemEvent.turn_interrupted(turn_id, reason)
        )
        self._active_turn = None
        self._buffer = ""
        self._response_sentences = []
        self._transition_to(ConversationState.INTERRUPTED)
        self._transition_to(ConversationState.IDLE)

    def fail(self, message: str) -> None:
        self._pending_events.append(SystemEvent.fault(message))
        self._active_turn = None
        self._buffer = ""
        self._response_sentences = []
        self._transition_to(ConversationState.FAILED)

    def drain_events(self) -> Iterable[SystemEvent]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def _ensure_active_turn(self, turn_id: TurnId) -> None:
        if self._active_turn != turn_id:
            raise AppError.invalid_transition(
                f"event belongs to turn {turn_id}, "
                f"but active turn is {self._active_turn}"
            )

    def _transition_to(self, target: ConversationState) -> None:
        if self.state == target:
            return
        previous = self.state
        self.state = target
        self._pending_events.append(
            SystemEvent.state_changed(previous, target)
        )


# -- Runtime Orchestrator ----------------------------------------------------


class Runtime:
    """Binds the conversation engine to infrastructure ports.

    Adapters receive normalized events; they do not mutate conversation state.
    """

    def __init__(
        self,
        model: LanguageModelPort,
        speech: SpeechPort,
        avatar: AvatarPort,
        events: EventSink,
    ) -> None:
        self._engine = ConversationEngine()
        self._model = model
        self._speech = speech
        self._avatar = avatar
        self._events = events

    @property
    def engine(self) -> ConversationEngine:
        return self._engine

    def state(self) -> ConversationState:
        return self._engine.state

    def begin_turn(self, user_text: str) -> TurnId:
        turn_id = self._engine.begin_turn(user_text)
        self._model.start_turn(turn_id, self._engine.history)
        self._flush_events()
        return turn_id

    def accept_model_chunk(self, turn_id: TurnId, text: str) -> None:
        self._engine.accept_model_chunk(turn_id, text)
        self._flush_events()

    def finish_turn(self, turn_id: TurnId) -> None:
        self._engine.finish_turn(turn_id)
        self._flush_events()

    def interrupt(self, reason: str) -> None:
        if self._engine.active_turn is None:
            raise AppError.invalid_transition(
                "there is no active turn to interrupt"
            )
        turn_id = self._engine.active_turn
        self._model.cancel_turn(turn_id)
        self._speech.interrupt()
        self._avatar.set_neutral()
        self._engine.interrupt(reason)
        self._flush_events()

    def _flush_events(self) -> None:
        for event in self._engine.drain_events():
            if event.kind == "sentence_ready" and event.turn_id is not None:
                self._speech.enqueue_sentence(event.turn_id, event.text)
                self._avatar.set_speaking(True)
            elif event.kind in ("turn_finished", "turn_interrupted"):
                self._avatar.set_neutral()
            self._events.publish(event)
