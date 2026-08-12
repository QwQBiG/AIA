"""LLM adapter layer — Ollama and KoboldCpp backends."""

from .base import BaseLLMClient, StreamHandler
from .ollama import OllamaClient
from .koboldcpp import KoboldCppClient
from .factory import create_llm_client

__all__ = [
    "BaseLLMClient",
    "StreamHandler",
    "OllamaClient",
    "KoboldCppClient",
    "create_llm_client",
]
