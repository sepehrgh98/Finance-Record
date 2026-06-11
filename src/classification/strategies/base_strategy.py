from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.classification_result import ClassificationResult
from core.models.document_context import DocumentContext


class BaseClassificationStrategy(ABC):
    """
    Interface for semantic document classification strategies.

    Strategies provide classification evidence only. The classifier owns
    thresholding and final routing decisions.
    """

    @abstractmethod
    def classify(
        self,
        context: DocumentContext,
    ) -> ClassificationResult:
        """
        Return classification evidence for this strategy.
        """
