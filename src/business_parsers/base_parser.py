from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.document_context import DocumentContext


class BaseBusinessParser(ABC):
    """
    Interface for extracting business entities from enriched document state.
    """

    @abstractmethod
    def parse(self, context: DocumentContext) -> Any:
        """
        Return business entities found in the document context.
        """
