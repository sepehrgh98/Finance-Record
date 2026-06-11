from __future__ import annotations

import re
from pathlib import Path

from ingestion.ocr.paddle_engine import PaddleEngine
from ingestion.ocr.tesseract_engine import TesseractEngine
from ingestion.ocr.vlm_engine import VLMEngine


class OCRService:
    def __init__(
        self,
        tesseract_engine: TesseractEngine | None = None,
        paddle_engine: PaddleEngine | None = None,
        vlm_engine: VLMEngine | None = None,
    ) -> None:
        self.tesseract_engine = tesseract_engine or TesseractEngine()
        self.paddle_engine = paddle_engine or PaddleEngine()
        self.vlm_engine = vlm_engine or VLMEngine()

    def extract_text(self, image_path: Path) -> dict:
        tesseract_result = self.tesseract_engine.extract_text(image_path)
        attempts = [tesseract_result]

        if self._is_quality_acceptable(tesseract_result):
            return self._build_result(tesseract_result, attempts)

        if (
            self.vlm_engine.enabled
            and self._image_has_document_shape(image_path)
        ):
            vlm_result = self.vlm_engine.extract_text(image_path)
            attempts.append(vlm_result)

            if self._is_quality_acceptable(vlm_result):
                return self._build_result(vlm_result, attempts)

        paddle_result = self.paddle_engine.extract_text(image_path)
        attempts.append(paddle_result)

        if self._is_quality_acceptable(paddle_result):
            return self._build_result(paddle_result, attempts)

        best_so_far = max(
            attempts,
            key=lambda result: self._quality_score(result),
        )
        document_like = (
            self._looks_document_like(best_so_far.get("text", ""))
            or self._image_has_document_shape(image_path)
        )

        if document_like and not any(
            attempt.get("engine") == self.vlm_engine.name
            for attempt in attempts
        ):
            vlm_result = self.vlm_engine.extract_text(image_path)
            attempts.append(vlm_result)

            if self._is_quality_acceptable(vlm_result):
                return self._build_result(vlm_result, attempts)

        best_result = max(
            attempts,
            key=lambda result: self._quality_score(result),
        )
        result = self._build_result(best_result, attempts)
        result["document_like"] = self._looks_document_like(result["text"])
        result["manual_review"] = result["document_like"]
        return result

    def _build_result(self, result: dict, attempts: list[dict]) -> dict:
        text = result.get("text", "")
        document_like = self._looks_document_like(text)

        return {
            "text": text,
            "engine": result.get("engine", ""),
            "word_count": self._word_count(text),
            "character_count": len(text.strip()),
            "confidence": result.get("confidence"),
            "document_like": document_like,
            "manual_review": False,
            "ocr_attempts": sum(attempt.get("attempts", 1) for attempt in attempts),
            "ocr_engines": [attempt.get("engine", "") for attempt in attempts],
            "successful_methods": [
                method
                for attempt in attempts
                for method in attempt.get("successful_methods", [])
            ],
            "method_word_counts": {
                method: count
                for attempt in attempts
                for method, count in attempt.get("method_word_counts", {}).items()
            },
            "preview": self._preview(text),
            "errors": [
                attempt.get("error")
                for attempt in attempts
                if attempt.get("error")
            ],
        }

    def _is_quality_acceptable(self, result: dict) -> bool:
        text = result.get("text", "")

        if self._word_count(text) == 0:
            return False

        if len(text.strip()) < 10:
            return False

        if self._looks_like_noise(text):
            return False

        if not self._has_document_signal(text):
            return False

        confidence = result.get("confidence")

        if result.get("engine") == "paddle" and confidence is not None:
            if confidence < 0.7:
                return False

        if confidence is not None and confidence < 0.35:
            return False

        return True

    def _quality_score(self, result: dict) -> float:
        text = result.get("text", "")
        word_count = self._word_count(text)
        character_count = len(text.strip())
        alpha_numeric_count = sum(character.isalnum() for character in text)
        non_space_count = sum(not character.isspace() for character in text)
        signal_ratio = alpha_numeric_count / max(non_space_count, 1)

        return word_count * 2 + character_count * 0.05 + signal_ratio * 10

    def _looks_like_noise(self, text: str) -> bool:
        stripped = text.strip()
        non_space_count = sum(not character.isspace() for character in stripped)

        if non_space_count == 0:
            return True

        alpha_numeric_count = sum(character.isalnum() for character in stripped)
        signal_ratio = alpha_numeric_count / non_space_count

        if signal_ratio < 0.45:
            return True

        tokens = re.findall(r"[A-Za-z0-9$]+", stripped)

        if not tokens:
            return True

        meaningful_tokens = [
            token
            for token in tokens
            if len(token) >= 2 and any(character.isalpha() for character in token)
        ]

        if len(tokens) <= 3 and len(meaningful_tokens) <= 1:
            return True

        return False

    def _has_document_signal(self, text: str) -> bool:
        normalized = text.lower()
        document_keywords = (
            "receipt",
            "recu",
            "reçu",
            "total",
            "subtotal",
            "sous-total",
            "tax",
            "tps",
            "tvq",
            "cash",
            "comptant",
            "change",
            "amount",
            "invoice",
            "date",
            "visa",
            "mastercard",
            "debit",
        )

        if any(keyword in normalized for keyword in document_keywords):
            return True

        amount_patterns = (
            r"\$\s*\d+([.,]\d{2})?",
            r"\b\d+[.,]\d{2}\b",
        )

        return any(
            re.search(pattern, normalized)
            for pattern in amount_patterns
        )

    def _looks_document_like(self, text: str) -> bool:
        normalized = text.lower()
        weak_document_keywords = (
            "receipt",
            "recu",
            "reçu",
            "total",
            "subtotal",
            "tax",
            "tps",
            "tvq",
            "cash",
            "comptant",
            "amount",
            "invoice",
            "check",
            "chek",
            "visa",
            "mastercard",
            "debit",
        )

        if any(keyword in normalized for keyword in weak_document_keywords):
            return True

        weak_patterns = (
            r"\$\s*\d*",
            r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b",
            r"\b\d+[.,]\d{2}\b",
        )

        return any(
            re.search(pattern, normalized)
            for pattern in weak_patterns
        )

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9$]+", text or ""))

    def _preview(self, text: str, max_chars: int = 220) -> str:
        preview = " ".join(text.split())

        if len(preview) <= max_chars:
            return preview

        return preview[: max_chars - 3].rstrip() + "..."

    def _image_has_document_shape(self, image_path: Path) -> bool:
        try:
            from PIL import Image, ImageOps

            with Image.open(image_path) as image:
                prepared = ImageOps.exif_transpose(image)
                width, height = prepared.size
        except Exception:
            return False

        longer_side = max(width, height)
        shorter_side = min(width, height)

        if shorter_side == 0:
            return False

        aspect_ratio = longer_side / shorter_side

        return longer_side >= 800 and 1.15 <= aspect_ratio <= 2.2
