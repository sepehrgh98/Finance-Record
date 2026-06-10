from __future__ import annotations

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class TextExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        try:
            context.extracted_text = context.file_info.path.read_text(
                encoding="utf-8",
                errors="ignore",
            )[:4000]
        except Exception:
            context.extracted_text = ""

        return context
