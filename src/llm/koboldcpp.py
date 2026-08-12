"""KoboldCpp LLM backend."""
from __future__ import annotations
import json, logging, re
import aiohttp
from .base import BaseLLMClient, StreamHandler
logger = logging.getLogger(__name__)
_SSE_RE = re.compile(r"data:\s*(\{.*\})")
class KoboldCppClient(BaseLLMClient):
    def __init__(self, base_url="http://localhost:5001", model="", *, max_context=2048, max_len=256, temp=0.7, timeout=120):
        super().__init__(base_url, model or "koboldcpp")
        self._max_context = max_context
        self._max_len = max_len
        self._temp = temp
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = None
    async def connect(self) -> bool:
        try:
            s = await self._get_session()
            async with s.get(f"{self.base_url}/api/v1/model", timeout=5) as r:
                self._connected = r.status == 200
        except Exception as e:
            logger.warning("KoboldCpp connect: %s", e)
            self._connected = False
        return self._connected
    async def disconnect(self):
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
    async def generate_response(self, message, *, return_structured=False):
        prompt = self._prompt(message, use_system=return_structured)
        payload = self._payload(prompt, stream=False)
        s = await self._get_session()
        async with s.post(f"{self.base_url}/api/v1/generate", json=payload, timeout=self._timeout) as r:
            if r.status != 200:
                raise RuntimeError(f"KoboldCpp HTTP {r.status}")
            d = await r.json()
            text = (d.get("results") or [{}])[0].get("text", "")
        return self._parse_structured_response(text) if return_structured else text
    async def generate_response_stream(self, message, handler):
        prompt = self._prompt(message, use_system=True)
        payload = self._payload(prompt, stream=True)
        full, emotion_detected, buf = "", False, ""
        s = await self._get_session()
        async with s.post(f"{self.base_url}/api/v1/generate", json=payload, timeout=self._timeout) as r:
            async for line in r.content:
                t = line.decode("utf-8", errors="replace").strip()
                if not t:
                    continue
                m = _SSE_RE.search(t)
                if not m:
                    continue
                try:
                    ev = json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
                tok = ""
                if "token" in ev:
                    tok = ev["token"].get("text", "") if isinstance(ev["token"], dict) else (ev["token"] if isinstance(ev["token"], str) else "")
                elif "results" in ev and ev["results"]:
                    tok = ev["results"][0].get("text", "")
                if not tok:
                    continue
                full += tok
                if not emotion_detected:
                    buf += tok
                    em, rest = self._extract_emotion_tag(buf)
                    if em:
                        emotion_detected = True
                        handler.on_emotion_detected(em)
                        if rest:
                            handler.on_token_received(rest)
                    elif len(buf) > 20:
                        emotion_detected = True
                        handler.on_emotion_detected("neutral")
                        handler.on_token_received(buf)
                else:
                    handler.on_token_received(tok)
        if not emotion_detected and buf:
            handler.on_emotion_detected("neutral")
            handler.on_token_received(buf)
        handler.on_stream_complete()
        _, clean = self._extract_emotion_tag(full)
        return clean or full
    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session
    def _prompt(self, msg, *, use_system=False):
        if use_system:
            return f"System: You are a VTuber named Aina.\nUser: {msg}\nAssistant:"
        return f"User: {msg}\nAssistant:"
    def _payload(self, prompt, *, stream):
        return {"prompt": prompt, "max_context_length": self._max_context, "max_length": self._max_len, "temperature": self._temp, "stream": stream}
