# src/llm/factory.py

from llm.base import BaseLLMClient
from llm.ollama_client import OllamaLLMClient
from llm.transformers_client import TransformersLLMClient


def build_llm_client(provider: str, model: str) -> BaseLLMClient:
    provider = provider.lower().strip()

    if provider == "ollama":
        return OllamaLLMClient(model=model)

    if provider == "transformers":
        return TransformersLLMClient(model=model)

    raise ValueError(f"Unsupported LLM provider: {provider}")