# src/llm/base.py

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    last_error: str

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int = 30,
    ) -> dict:
        pass