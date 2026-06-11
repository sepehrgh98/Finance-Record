from __future__ import annotations

from ingestion.extractors.base import BaseContentExtractor
from core.models.document_context import DocumentContext


class UnknownExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        context.extracted_text = ""
        return context
