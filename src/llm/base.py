"""Abstract base for all LLM client backends."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict, Optional, Protocol, runtime_checkable


_EMOTION_TAG_RE = re.compile(r"^\s*\[(\w+)\]\s*")

_VALID_EMOTIONS = frozenset({"neutral", "happy", "angry", "sad", "surprised"})


@runtime_checkable
class StreamHandler(Protocol):
    """Callback protocol for streaming token reception."""
    def on_emotion_detected(self, emotion: str) -> None:
        pass
    def on_token_received(self, token: str) -> None:
        pass
    def on_stream_complete(self) -> None:
        pass


def extract_emotion_tag(text: str) -> tuple[Optional[str], str]:
    """Extract an ``[emotion]`` tag from the start of *text*."""
    m = _EMOTION_TAG_RE.match(text)
    if m and m.group(1).lower() in _VALID_EMOTIONS:
        tag = m.group(1).lower()
        return tag, text[m.end():]
    return None, text


def parse_structured_response(raw: str) -> Dict[str, str]:
    """Parse a JSON-structured ``{"emotion": text":  response.

    Falls back to ``{"emotion": "neutral", "text": raw}`` on failure.
    """
    import json
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "text" in data:
            emotion = data.get("emotion", "neutral")
            return {"emotion": emotion if emotion in _VALID_EMOTIONS else "neutral", "text": str(data["text"])}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return {"emotion": "neutral", "text": raw}


class BaseLLMClient(ABC):
    """Abstract LLM client that all backends implement."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._connected = False

    # -- Subclass API --------------------------------------------------------

    @abstractmethod
    async def connect(self) -> bool:
        """Probe the backend and return True if reachable."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release any resources held by the client."""

    @abstractmethod
    async def generate_response(
        self, message: str, *, return_structured: bool = False
    ) -> str | Dict[str, str]:
        """Non-streaming generation."""

    @abstractmethod
    async def generate_response_stream(
        self, message: str, handler: StreamHandler
    ) -> str:
        """Streaming generation.

        Tokens are delivered via handler. Returns the complete response text.
        """

    # -- Concrete helpers ----------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected

    def clear_cache(self) -> None:
        pass

    async def generate_response_stream_with_fallback(
        self, message: str, handler: StreamHandler
    ) -> str:
        """Try streaming first; fall back to non-streaming on failure."""
        try:
            return await self.generate_response_stream(message, handler)
        except Exception:
            return await self._fallback_to_non_streaming(message, handler)

    async def _fallback_to_non_streaming(
        self, message: str, handler: StreamHandler
    ) -> str:
        response = await self.generate_response(message, return_structured=True)
        if isinstance(response, dict):
            emotion = response.get("emotion", "neutral")
            text = response.get("text", "")
        else:
            emotion = "neutral"
            text = str(response)
        handler.on_emotion_detected(emotion)
        handler.on_token_received(text)
        handler.on_stream_complete()
        return text

    # -- Emotion / structure helpers -----------------------------------------

    @staticmethod
    def _extract_emotion_tag(text: str) -> tuple[Optional[str], str]:
        return extract_emotion_tag(text)

    @staticmethod
    def _parse_structured_response(raw: str) -> Dict[str, str]:
        return parse_structured_response(raw)
