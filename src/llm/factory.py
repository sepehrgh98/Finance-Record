# src/llm/factory.py

from llm.base import BaseLLMClient
from llm.ollama_client import OllamaLLMClient
from llm.qwen_vl_client import QwenVLClient
from llm.transformers_client import TransformersLLMClient


def build_llm_client(provider: str, model: str) -> BaseLLMClient:
    provider = provider.lower().strip()

    if provider == "ollama":
        return OllamaLLMClient(model=model)

    if provider == "transformers":
        return TransformersLLMClient(model=model)

    if provider in {"qwen_vl", "qwen-vl", "vlm"}:
        return QwenVLClient(model=model)

    raise ValueError(f"Unsupported LLM provider: {provider}")
