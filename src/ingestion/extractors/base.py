from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.document_context import DocumentContext


class BaseContentExtractor(ABC):
    """
    Interface for extracting semantic preview text from one file format.
    """

    @abstractmethod
    def extract(self, context: DocumentContext) -> DocumentContext:
        """
        Enrich and return the same document context.
        """
