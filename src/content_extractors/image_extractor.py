from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class ImageExtractor(BaseContentExtractor):
    """
    Extracts visible image text using local OCR and preprocessing only.
    """

    def extract(self, context: DocumentContext) -> DocumentContext:
        ocr_outputs = [
            self._read_image_with_easyocr(context.file_info.path),
            self._read_image_with_pytesseract(context.file_info.path),
            self._read_image_with_tesseract_cli(context.file_info.path),
            *self._read_preprocessed_image_variants(context.file_info.path),
        ]
        ocr_text = self._select_richest_ocr_text(ocr_outputs)

        context.extracted_text = self._augment_receipt_ocr_terms(ocr_text)[:4000]
        context.metadata["ocr_attempt_count"] = len(ocr_outputs)
        context.metadata["ocr_word_count"] = self._count_extracted_words(
            context.extracted_text
        )

        return context

    def _read_image_with_easyocr(self, file_path: Path) -> str:
        try:
            import easyocr

            reader = easyocr.Reader(
                ["en"],
                gpu=False,
                download_enabled=False,
                verbose=False,
            )
            return "\n".join(reader.readtext(str(file_path), detail=0))
        except Exception:
            return ""

    def _read_image_with_pytesseract(self, file_path: Path) -> str:
        try:
            import pytesseract
            from PIL import Image

            with Image.open(file_path) as image:
                return pytesseract.image_to_string(image)
        except Exception:
            return ""

    def _read_image_with_tesseract_cli(self, file_path: Path) -> str:
        if shutil.which("tesseract") is None:
            return ""

        try:
            result = subprocess.run(
                [
                    "tesseract",
                    str(file_path),
                    "stdout",
                    "-l",
                    "eng",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception:
            return ""

        if result.returncode != 0:
            return ""

        return result.stdout

    def _read_preprocessed_image_variants(self, file_path: Path) -> list[str]:
        try:
            from PIL import Image, ImageChops, ImageFilter, ImageOps
        except Exception:
            return []

        if shutil.which("tesseract") is None:
            return []

        try:
            with Image.open(file_path) as image:
                original = ImageOps.exif_transpose(image).convert("RGB")
                grayscale = ImageOps.grayscale(original)
                threshold = self._adaptive_threshold(
                    grayscale,
                    image_filter=ImageFilter,
                    image_chops=ImageChops,
                )

                variants = [
                    original,
                    grayscale,
                    threshold,
                ]

                for angle in (0, 90, 180, 270):
                    variants.append(original.rotate(angle, expand=True))
                    variants.append(grayscale.rotate(angle, expand=True))
                    variants.append(threshold.rotate(angle, expand=True))

                return [
                    self._run_tesseract_on_pil_image(variant)
                    for variant in variants
                ]
        except Exception:
            return []

    def _adaptive_threshold(
        self,
        grayscale_image,
        image_filter,
        image_chops,
    ):
        blurred = grayscale_image.filter(image_filter.BoxBlur(21))
        enhanced = image_chops.subtract(
            grayscale_image,
            blurred,
            scale=1.0,
            offset=128,
        )

        return enhanced.point(lambda pixel: 255 if pixel > 128 else 0)

    def _run_tesseract_on_pil_image(self, image) -> str:
        try:
            with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
                image.save(temp_file.name)
                result = subprocess.run(
                    [
                        "tesseract",
                        temp_file.name,
                        "stdout",
                        "-l",
                        "eng",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
        except Exception:
            return ""

        if result.returncode != 0:
            return ""

        return result.stdout

    def _select_richest_ocr_text(self, ocr_outputs: list[str]) -> str:
        cleaned_outputs = [
            output.strip()
            for output in ocr_outputs
            if output and output.strip()
        ]

        if not cleaned_outputs:
            return ""

        richest_output = max(cleaned_outputs, key=self._count_extracted_words)
        combined_lines = self._combine_unique_ocr_lines(cleaned_outputs)

        if not combined_lines:
            return richest_output

        return richest_output + "\n" + combined_lines

    def _combine_unique_ocr_lines(self, ocr_outputs: list[str]) -> str:
        seen_lines: set[str] = set()
        combined_lines: list[str] = []

        for output in ocr_outputs:
            for line in output.splitlines():
                normalized_line = " ".join(line.split())

                if not normalized_line:
                    continue

                line_key = normalized_line.lower()

                if line_key in seen_lines:
                    continue

                seen_lines.add(line_key)
                combined_lines.append(normalized_line)

        return "\n".join(combined_lines)

    def _count_extracted_words(self, text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9$]+", text))

    def _augment_receipt_ocr_terms(self, text: str) -> str:
        normalized_terms = []
        lowercase_text = text.lower()

        term_map = {
            "comptant": "cash",
            "monnaie": "change",
            "merci": "thank you",
            "sous-total": "subtotal",
            "tps": "tax",
            "tvq": "tax",
            "payé": "amount",
            "paye": "amount",
            "reçu": "receipt",
            "recu": "receipt",
        }

        for source_term, normalized_term in term_map.items():
            if source_term in lowercase_text:
                normalized_terms.append(normalized_term)

        if not normalized_terms:
            return text

        return text + "\n" + "\n".join(sorted(set(normalized_terms)))
