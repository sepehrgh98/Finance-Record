from __future__ import annotations

from classification.strategies.base_strategy import BaseClassificationStrategy
from core.enums.document_type import DocumentType
from core.enums.physical_file_type import PhysicalFileType
from core.models.classification_result import ClassificationResult
from core.models.document_context import DocumentContext


class NoteStrategy(BaseClassificationStrategy):
    KEYWORDS = (
        "follow up",
        "reminder",
        "todo",
        "[todo]",
        "[done]",
        "need to",
        "remember",
        "note",
        "notes",
        "rule:",
        "reminder:",
        "random",
        "still hasn't paid",
        "hasn't paid",
        "should",
        "before",
    )
    FILENAME_HINTS = (
        "note",
        "notes",
        "todo",
        "reminder",
        "context",
    )

    def classify(
        self,
        context: DocumentContext,
    ) -> ClassificationResult:
        text = context.extracted_text.lower()
        matches = [keyword for keyword in self.KEYWORDS if keyword in text]
        filename_matches = [
            hint
            for hint in self.FILENAME_HINTS
            if hint in context.file_info.filename.lower()
        ]
        section_count = self._section_header_count(context.extracted_text)
        natural_language_lines = self._natural_language_line_count(
            context.extracted_text
        )
        is_text_file = context.physical_type == PhysicalFileType.TEXT
        score = min(
            1.0,
            (len(matches) / len(self.KEYWORDS) * 0.45)
            + (min(len(filename_matches), 1) * 0.20)
            + (min(section_count / 2, 1.0) * 0.10)
            + (min(natural_language_lines / 4, 1.0) * 0.15)
            + (0.10 if is_text_file else 0.0),
        )

        if score == 0.0:
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        evidence: list[str] = []

        if matches:
            evidence.append(
                "Matched note keywords: " + ", ".join(matches)
            )

        if filename_matches:
            evidence.append(
                "Matched note filename hints: " + ", ".join(filename_matches)
            )

        if section_count:
            evidence.append(f"Found {section_count} note section headers")

        if natural_language_lines:
            evidence.append(
                f"Found {natural_language_lines} natural-language note lines"
            )

        if is_text_file:
            evidence.append("File is plain text")

        return ClassificationResult(
            document_type=DocumentType.NOTE,
            score=score,
            reason="; ".join(evidence),
            evidence=evidence,
        )

    def _section_header_count(self, text: str) -> int:
        import re

        return len(
            re.findall(r"(?m)^\s*(==\s*.+?\s*==|[a-z][a-z\s_-]+:)\s*$", text.lower())
        )

    def _natural_language_line_count(self, text: str) -> int:
        count = 0

        for line in text.splitlines():
            stripped = line.strip()

            if len(stripped.split()) < 4:
                continue

            if any(
                marker in stripped.lower()
                for marker in (" i ", " my ", " need ", " follow ", " paid", "before")
            ):
                count += 1

        return count
