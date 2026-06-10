from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class TesseractEngine:
    name = "tesseract"

    def extract_text(self, image_path: Path) -> dict:
        outputs = [
            self._read_image_with_pytesseract(image_path),
            self._read_image_with_tesseract_cli(image_path),
            *self._read_preprocessed_image_variants(image_path),
        ]
        text = self._select_richest_ocr_text(outputs)

        return {
            "engine": self.name,
            "text": text,
            "attempts": len(outputs),
            "successful_methods": [
                method
                for method, output in outputs
                if output and output.strip()
            ],
            "method_word_counts": {
                method: self._count_words(output)
                for method, output in outputs
            },
            "confidence": None,
        }

    def _read_image_with_pytesseract(self, file_path: Path) -> tuple[str, str]:
        try:
            import pytesseract
            from PIL import Image

            with Image.open(file_path) as image:
                return ("pytesseract", pytesseract.image_to_string(image))
        except Exception:
            return ("pytesseract", "")

    def _read_image_with_tesseract_cli(self, file_path: Path) -> tuple[str, str]:
        if shutil.which("tesseract") is None:
            return ("tesseract_cli", "")

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
            return ("tesseract_cli", "")

        if result.returncode != 0:
            return ("tesseract_cli", "")

        return ("tesseract_cli", result.stdout)

    def _read_preprocessed_image_variants(
        self,
        file_path: Path,
    ) -> list[tuple[str, str]]:
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
                    (
                        f"preprocessed_variant_{index}",
                        self._run_tesseract_on_pil_image(variant),
                    )
                    for index, variant in enumerate(variants)
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

    def _select_richest_ocr_text(self, outputs: list[tuple[str, str]]) -> str:
        cleaned_outputs = [
            output.strip()
            for _, output in outputs
            if output and output.strip()
        ]

        if not cleaned_outputs:
            return ""

        richest_output = max(cleaned_outputs, key=self._count_words)
        combined_lines = self._combine_unique_ocr_lines(cleaned_outputs)

        if not combined_lines:
            return richest_output

        return richest_output + "\n" + combined_lines

    def _combine_unique_ocr_lines(self, outputs: list[str]) -> str:
        seen_lines: set[str] = set()
        combined_lines: list[str] = []

        for output in outputs:
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

    def _count_words(self, text: str) -> int:
        import re

        return len(re.findall(r"[A-Za-z0-9$]+", text or ""))
