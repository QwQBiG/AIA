"""Ollama LLM backend implementation."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, List

import aiohttp

from .base import BaseLLMClient, StreamHandler


logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """LLM client for Ollama API (``/api/chat`` and ``/api/tags``)."""

    SYSTEM_PROMPT_JSON = (
        "You are a VTuber named Aina. "
        "Respond in JSON: {\"emotion\": \"neutral|happy|angry|sad|surprised\", \"text\": \"...\"}"
    )
    SYSTEM_PROMPT_STREAM = (
        "You are a VTuber named Aina. "
        "Start every response with an emotion tag: [neutral], [happy], [angry], [sad], or [surprised]."
    )

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        *,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(base_url, model)
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    # -- Connection lifecycle -------------------------------------------------

    async def connect(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags", timeout=5) as resp:
                self._connected = resp.status == 200
        except Exception as exc:
            logger.warning("Ollama connect failed: %s", exc)
            self._connected = False
        return self._connected

    async def disconnect(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._connected = False

    # -- Generation -----------------------------------------------------------

    async def generate_response(
        self, message: str, *, return_structured: bool = False
    ) -> str | Dict[str, str]:
        if not message.strip():
            raise ValueError("Message cannot be empty")

        messages: List[dict] = []
        if return_structured:
            messages.append({"role": "system", "content": self.SYSTEM_PROMPT_JSON})
        messages.append({"role": "user", "content": message})

        payload = {"model": self.model, "messages": messages, "stream": False}
        session = await self._get_session()

        async with session.post(f"{self.base_url}/api/chat", json=payload, timeout=self._timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama API error: HTTP {resp.status}")
            result = await resp.json()
            text = (result.get("message") or {}).get("content", "")

        if return_structured:
            parsed = self._parse_structured_response(text)
            return parsed
        return text

    async def generate_response_stream(
        self, message: str, handler: StreamHandler
    ) -> str:
        if not message.strip():
            raise ValueError("Message cannot be empty")

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT_STREAM},
            {"role": "user", "content": message},
        ]
        payload = {"model": self.model, "messages": messages, "stream": True}

        session = await self._get_session()
        full_response = ""
        emotion_detected = False
        emotion_buffer = ""

        async with session.post(f"{self.base_url}/api/chat", json=payload, timeout=self._timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama API error: HTTP {resp.status}")

            async for raw_line in resp.content:
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                token = (data.get("message") or {}).get("content", "")
                if not token:
                    if data.get("done"):
                        break
                    continue

                full_response += token

                if not emotion_detected:
                    emotion_buffer += token
                    emotion, remaining = self._extract_emotion_tag(emotion_buffer)
                    if emotion:
                        emotion_detected = True
                        handler.on_emotion_detected(emotion)
                        if remaining:
                            handler.on_token_received(remaining)
                    elif len(emotion_buffer) > 20:
                        emotion_detected = True
                        handler.on_emotion_detected("neutral")
                        handler.on_token_received(emotion_buffer)
                else:
                    handler.on_token_received(token)

        if not emotion_detected and emotion_buffer:
            handler.on_emotion_detected("neutral")
            handler.on_token_received(emotion_buffer)

        handler.on_stream_complete()
        _, clean = self._extract_emotion_tag(full_response)
        return clean if clean else full_response

    # -- Internal helpers -----------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session
