from __future__ import annotations

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class UnknownExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        context.extracted_text = ""
        return context
