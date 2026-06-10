from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from llm.base import BaseLLMClient


class OllamaLLMClient(BaseLLMClient):
    """
    Local Ollama client.

    Uses localhost only, no API keys, and no external network services.
    """

    def __init__(
        self,
        model: str = "llama3.2:3b",
        endpoint: str = "http://localhost:11434/api/generate",
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.last_error = ""

    def is_available(self) -> bool:
        try:
            self.generate_json(
                'Return only this JSON object: {"ok": true}',
                timeout_seconds=2,
            )
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def generate_json(
        self,
        prompt: str,
        timeout_seconds: int = 30,
    ) -> dict:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, URLError, json.JSONDecodeError) as exc:
            self.last_error = str(exc)
            raise RuntimeError("Local Ollama request failed") from exc

        generated_text = response_body.get("response", "")

        if not isinstance(generated_text, str):
            self.last_error = "Ollama response did not contain text"
            raise ValueError(self.last_error)

        try:
            parsed = json.loads(generated_text)
        except json.JSONDecodeError as exc:
            self.last_error = "Ollama response was not valid JSON"
            raise ValueError(self.last_error) from exc

        if not isinstance(parsed, dict):
            self.last_error = "Ollama JSON response must be an object"
            raise ValueError(self.last_error)

        return parsed