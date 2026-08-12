"""Create LLM client from config."""
from __future__ import annotations
def create_llm_client(config):
    backend = getattr(config, "llm_backend", "ollama")
    if backend == "koboldcpp":
        from .koboldcpp import KoboldCppClient
        return KoboldCppClient(getattr(config, "koboldcpp_url", "http://localhost:5001"), getattr(config, "koboldcpp_model", ""), max_context=getattr(config, "koboldcpp_max_context_length", 2048), max_len=getattr(config, "koboldcpp_max_length", 256), temp=getattr(config, "koboldcpp_temperature", 0.7))
    from .ollama import OllamaClient
    return OllamaClient(getattr(config, "ollama_url", "http://localhost:11434"), getattr(config, "ollama_model", "llama3"))
