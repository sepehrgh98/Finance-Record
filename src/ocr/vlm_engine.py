from __future__ import annotations

import json
import os
from pathlib import Path

from config.settings import USE_LOCAL_VLM_FOR_OCR, VLM_MODEL
from llm.qwen_vl_client import QwenVLClient


class VLMEngine:
    name = "vlm"
    max_image_dimension = 1280
    min_pixels = 256 * 28 * 28
    max_pixels = 1280 * 28 * 28

    def __init__(
        self,
        model: str = VLM_MODEL,
        enabled: bool = USE_LOCAL_VLM_FOR_OCR,
        client: QwenVLClient | None = None,
    ) -> None:
        self.model = model
        self.enabled = enabled
        self.client = client or QwenVLClient(model=model)

    def extract_text(self, image_path: Path) -> dict:
        if not self.enabled:
            return self._empty_result("Local VLM OCR fallback disabled")

        try:
            self._debug(f"starting local VLM OCR for {image_path}")
            content = self._generate(image_path)
            receipt_text = self._receipt_json_to_text(content)
            self._debug(
                "finished local VLM OCR: "
                f"{self._count_words(receipt_text)} words"
            )

            return {
                "engine": self.name,
                "text": receipt_text,
                "attempts": 1,
                "successful_methods": [self.name] if receipt_text.strip() else [],
                "method_word_counts": {
                    self.name: self._count_words(receipt_text),
                },
                "confidence": None,
                "error": "",
            }
        except Exception as exc:
            return self._empty_result(str(exc))

    def _generate(self, image_path: Path) -> str:
        prompt = """
Read this image as a possible handwritten receipt.

Return ONLY valid JSON. Do not use markdown.

Schema:
{
  "is_receipt": true,
  "merchant": "",
  "date": "",
  "items": [
    {"description": "", "quantity": "", "amount": 0.0}
  ],
  "total": 0.0,
  "payment_method": "",
  "notes": ""
}

If it is not a receipt or transaction record, return:
{
  "is_receipt": false,
  "merchant": "",
  "date": "",
  "items": [],
  "total": null,
  "payment_method": "",
  "notes": ""
}

Transcribe handwritten business receipt information as accurately as possible.
Do not invent missing values.
""".strip()
        return self.client.generate_image_text(
            image_path,
            prompt=prompt,
            min_pixels=self.min_pixels,
            max_pixels=self.max_pixels,
            max_image_dimension=self.max_image_dimension,
            max_new_tokens=256,
        )

    def _receipt_json_to_text(self, content: str) -> str:
        parsed = self._extract_json(content)

        if not parsed.get("is_receipt"):
            return ""

        lines = [
            "receipt",
            str(parsed.get("merchant", "")).strip(),
            f"date {str(parsed.get('date', '')).strip()}",
        ]

        for item in parsed.get("items", []):
            if not isinstance(item, dict):
                continue

            description = str(item.get("description", "")).strip()
            quantity = str(item.get("quantity", "")).strip()
            amount = item.get("amount")
            item_line = " ".join(
                value
                for value in [description, quantity, self._format_amount(amount)]
                if value
            )

            if item_line:
                lines.append(item_line)

        total = parsed.get("total")

        if total is not None:
            lines.append(f"total {self._format_amount(total)}")

        payment_method = str(parsed.get("payment_method", "")).strip()

        if payment_method:
            lines.append(payment_method)

        return "\n".join(line for line in lines if line)

    def _extract_json(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end == -1:
            return {}

        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            return {}

    def _format_amount(self, value) -> str:
        if value is None or value == "":
            return ""

        try:
            return f"${float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _empty_result(self, error: str) -> dict:
        self._debug(f"local VLM OCR unavailable: {error}")
        return {
            "engine": self.name,
            "text": "",
            "attempts": 1,
            "successful_methods": [],
            "method_word_counts": {self.name: 0},
            "confidence": None,
            "error": error,
        }

    def _count_words(self, text: str) -> int:
        import re

        return len(re.findall(r"[A-Za-z0-9$]+", text or ""))

    def _debug(self, message: str) -> None:
        if os.getenv("OCR_DEBUG") == "1":
            print(f"[ocr:vlm] {message}")
