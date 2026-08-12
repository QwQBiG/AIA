"""Domain types shared by all AIex components.

Absorbed and adapted from the Rust ai-ex-domain crate.
Provides the foundational types used throughout the system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


# ── Conversation State ──────────────────────────────────────────────────────


class ConversationState(Enum):
    """Possible states of the conversation engine (from Rust ai-ex-domain)."""

    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    INTERRUPTED = auto()
    FAILED = auto()
    STOPPED = auto()

    def accepts_user_input(self) -> bool:
        """Return True if this state can accept user input."""
        return self in (
            ConversationState.IDLE,
            ConversationState.LISTENING,
            ConversationState.INTERRUPTED,
        )


# ── Error Types ─────────────────────────────────────────────────────────────


class AppErrorCategory(Enum):
    """Error categories mirroring Rust AppError variants."""

    CONFIGURATION = "configuration"
    CONNECTIVITY = "connectivity"
    INVALID_TRANSITION = "invalid_state_transition"
    SAFETY_VIOLATION = "safety_violation"
    UNAVAILABLE = "unavailable"


class AppError(Exception):
    """Unified domain error (from Rust ai-ex-domain)."""

    def __init__(self, category: AppErrorCategory, message: str) -> None:
        self.category = category
        self.message = message
        super().__init__(f"{category.value}: {message}")

    @classmethod
    def configuration(cls, message: str) -> AppError:
        return cls(AppErrorCategory.CONFIGURATION, message)

    @classmethod
    def connectivity(cls, message: str) -> AppError:
        return cls(AppErrorCategory.CONNECTIVITY, message)

    @classmethod
    def invalid_transition(cls, message: str) -> AppError:
        return cls(AppErrorCategory.INVALID_TRANSITION, message)

    @classmethod
    def safety_violation(cls, message: str) -> AppError:
        return cls(AppErrorCategory.SAFETY_VIOLATION, message)

    @classmethod
    def unavailable(cls, message: str) -> AppError:
        return cls(AppErrorCategory.UNAVAILABLE, message)


# ── Message Types ───────────────────────────────────────────────────────────


class Speaker(Enum):
    """Who produced a message (from Rust ai-ex-domain)."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True)
class ChatMessage:
    """A single message in a conversation (from Rust)."""

    speaker: Speaker
    text: str


@dataclass(frozen=True)
class TurnId:
    """Unique identifier for a conversation turn (from Rust)."""

    value: int

    def __str__(self) -> str:
        return str(self.value)


# ── System Events ───────────────────────────────────────────────────────────


@dataclass
class SystemEvent:
    """Events emitted during a conversation turn (from Rust ai-ex-domain).

    Uses a 'kind' string discriminator with optional fields, matching the
    Rust SystemEvent enum pattern for flexibility.
    """

    kind: str
    turn_id: Optional[TurnId] = None
    text: str = ""
    user_text: str = ""
    full_text: str = ""
    reason: str = ""
    from_state: Optional[ConversationState] = None
    to_state: Optional[ConversationState] = None
    message: str = ""

    @classmethod
    def turn_started(cls, turn_id: TurnId, user_text: str) -> SystemEvent:
        return cls(kind="turn_started", turn_id=turn_id, user_text=user_text)

    @classmethod
    def model_chunk(cls, turn_id: TurnId, text: str) -> SystemEvent:
        return cls(kind="model_chunk", turn_id=turn_id, text=text)

    @classmethod
    def sentence_ready(cls, turn_id: TurnId, text: str) -> SystemEvent:
        return cls(kind="sentence_ready", turn_id=turn_id, text=text)

    @classmethod
    def turn_finished(cls, turn_id: TurnId, full_text: str) -> SystemEvent:
        return cls(kind="turn_finished", turn_id=turn_id, full_text=full_text)

    @classmethod
    def turn_interrupted(cls, turn_id: TurnId, reason: str) -> SystemEvent:
        return cls(kind="turn_interrupted", turn_id=turn_id, reason=reason)

    @classmethod
    def state_changed(cls, from_state: ConversationState, to_state: ConversationState) -> SystemEvent:
        return cls(
            kind="state_changed",
            from_state=from_state,
            to_state=to_state,
        )

    @classmethod
    def fault(cls, message: str) -> SystemEvent:
        return cls(kind="fault", message=message)


# ── Health Status ───────────────────────────────────────────────────────────


@dataclass
class HealthStatus:
    """Health check result for a system component (from Rust)."""

    component: str
    ready: bool
    detail: str = ""

    @classmethod
    def healthy(cls, component: str) -> HealthStatus:
        """Create a healthy status."""
        return cls(component=component, ready=True)

    @classmethod
    def unhealthy(cls, component: str, detail: str = "") -> HealthStatus:
        """Create an unhealthy status with optional detail."""
        return cls(component=component, ready=False, detail=detail)
