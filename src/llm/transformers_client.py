from __future__ import annotations

import json

from transformers import pipeline

from llm.base import BaseLLMClient


class TransformersLLMClient(BaseLLMClient):
    """
    Local HuggingFace Transformers client.

    Uses only local open-source models.
    No APIs.
    No sign-ups.
    No network calls after model download.
    """

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-3B-Instruct",
    ) -> None:
        self.model = model
        self.last_error = ""

        try:
            self._pipeline = pipeline(
                task="text-generation",
                model=model,
                device_map="auto",
            )
        except Exception as exc:
            self.last_error = str(exc)
            self._pipeline = None

    def is_available(self) -> bool:
        return self._pipeline is not None

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int = 30,
    ) -> dict:
        if self._pipeline is None:
            raise RuntimeError(
                "Transformers pipeline is not initialized"
            )

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        try:
            result = self._pipeline(
                messages,
                max_new_tokens=512,
                do_sample=False,
            )

            generated_text = (
                result[0]["generated_text"][-1]["content"]
                .strip()
            )

            print("\n" + "=" * 80)
            print("RAW MODEL OUTPUT")
            print("=" * 80)
            print(generated_text)
            print("=" * 80 + "\n")

        except Exception as exc:
            self.last_error = str(exc)

            raise RuntimeError(
                "Local Transformers generation failed"
            ) from exc

        parsed = self._extract_json(generated_text)

        if not isinstance(parsed, dict):
            self.last_error = (
                "Generated JSON must be an object"
            )
            raise ValueError(self.last_error)

        return parsed

    def _extract_json(
        self,
        generated_text: str,
    ) -> dict:
        try:
            return json.loads(generated_text)

        except json.JSONDecodeError:
            pass

        start = generated_text.find("{")
        end = generated_text.rfind("}")

        if start == -1 or end == -1:
            self.last_error = (
                "Model did not return valid JSON"
            )
            raise ValueError(self.last_error)

        try:
            return json.loads(
                generated_text[start : end + 1]
            )

        except json.JSONDecodeError as exc:
            self.last_error = (
                "Model did not return valid JSON"
            )
            raise ValueError(self.last_error) from exc