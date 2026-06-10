from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


class PaddleEngine:
    name = "paddle"

    def extract_text(self, image_path: Path) -> dict:
        try:
            from paddleocr import PaddleOCR

            self._debug(f"starting lightweight OCR for {image_path}")
            ocr = PaddleOCR(
                lang="en",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_det_limit_side_len=736,
            )
            with self._prepared_image_path(image_path) as prepared_path:
                self._debug(f"prepared image path: {prepared_path}")
                result = ocr.predict(str(prepared_path))
            lines, confidences = self._extract_lines_and_confidences(result)
            text = "\n".join(lines)
            confidence = (
                sum(confidences) / len(confidences)
                if confidences
                else None
            )
            self._debug(
                "finished lightweight OCR: "
                f"{len(lines)} lines, {self._count_words(text)} words"
            )

            return {
                "engine": self.name,
                "text": text,
                "attempts": 1,
                "successful_methods": [self.name] if text.strip() else [],
                "method_word_counts": {
                    self.name: self._count_words(text),
                },
                "confidence": confidence,
                "error": "",
            }
        except Exception as exc:
            return {
                "engine": self.name,
                "text": "",
                "attempts": 1,
                "successful_methods": [],
                "method_word_counts": {self.name: 0},
                "confidence": None,
                "error": str(exc),
            }

    def _prepared_image_path(self, image_path: Path):
        return _PreparedImagePath(image_path)

    def _extract_lines_and_confidences(self, result: Any) -> tuple[list[str], list[float]]:
        lines: list[str] = []
        confidences: list[float] = []

        self._extract_from_new_result(result, lines, confidences)

        if lines:
            return lines, confidences

        # PaddleOCR 2.x returns pages shaped like:
        # [[box, [text, confidence]], ...]
        for page in result or []:
            for item in page or []:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue

                text_info = item[1]

                if not isinstance(text_info, (list, tuple)) or not text_info:
                    continue

                text = str(text_info[0]).strip()

                if text:
                    lines.append(text)

                if len(text_info) > 1:
                    try:
                        confidences.append(float(text_info[1]))
                    except (TypeError, ValueError):
                        pass

        return lines, confidences

    def _extract_from_new_result(
        self,
        result: Any,
        lines: list[str],
        confidences: list[float],
    ) -> None:
        for page in self._as_iterable(result):
            data = self._as_mapping(page)

            if not data:
                continue

            rec_texts = data.get("rec_texts") or data.get("texts")
            rec_scores = data.get("rec_scores") or data.get("scores")

            if isinstance(rec_texts, list):
                for text in rec_texts:
                    cleaned = str(text).strip()

                    if cleaned:
                        lines.append(cleaned)

            if isinstance(rec_scores, list):
                for score in rec_scores:
                    try:
                        confidences.append(float(score))
                    except (TypeError, ValueError):
                        pass

            single_text = data.get("text")

            if isinstance(single_text, str) and single_text.strip():
                lines.append(single_text.strip())

            single_score = data.get("confidence") or data.get("score")

            if single_score is not None:
                try:
                    confidences.append(float(single_score))
                except (TypeError, ValueError):
                    pass

    def _as_iterable(self, result: Any) -> list[Any]:
        if result is None:
            return []

        if isinstance(result, list):
            return result

        if isinstance(result, tuple):
            return list(result)

        return [result]

    def _as_mapping(self, value: Any) -> dict:
        if isinstance(value, dict):
            return value

        if hasattr(value, "json"):
            json_value = value.json

            if isinstance(json_value, dict):
                result = json_value.get("res", json_value)

                if isinstance(result, dict):
                    return result

        if hasattr(value, "to_dict"):
            try:
                result = value.to_dict()

                if isinstance(result, dict):
                    return result.get("res", result)
            except Exception:
                return {}

        return {}

    def _count_words(self, text: str) -> int:
        import re

        return len(re.findall(r"[A-Za-z0-9$]+", text or ""))

    def _debug(self, message: str) -> None:
        if os.getenv("OCR_DEBUG") == "1":
            print(f"[ocr:paddle] {message}")


class _PreparedImagePath:
    max_dimension = 1200

    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path
        self.temp_file = None

    def __enter__(self) -> Path:
        try:
            from PIL import Image, ImageOps

            with Image.open(self.image_path) as image:
                prepared = ImageOps.exif_transpose(image).convert("RGB")
                prepared.thumbnail(
                    (self.max_dimension, self.max_dimension),
                    Image.Resampling.LANCZOS,
                )

                self.temp_file = tempfile.NamedTemporaryFile(
                    suffix=".png",
                    delete=False,
                )
                prepared.save(self.temp_file.name)
                self.temp_file.close()
                return Path(self.temp_file.name)
        except Exception:
            return self.image_path

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self.temp_file:
            return

        try:
            Path(self.temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass
