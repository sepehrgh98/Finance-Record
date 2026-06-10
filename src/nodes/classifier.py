from __future__ import annotations

from classification.base_strategy import BaseClassificationStrategy
from classification.strategies.invoice_strategy import InvoiceStrategy
from classification.strategies.note_strategy import NoteStrategy
from classification.strategies.receipt_strategy import ReceiptStrategy
from classification.strategies.statement_strategy import StatementStrategy
from enums.document_type import DocumentType
from models.classification_result import ClassificationResult
from models.document_context import DocumentContext


class ClassifierNode:
    """
    Classifies extracted documents by semantic content only.

    The node depends only on the classification strategy interface, so adding
    future document types means adding another strategy class and injecting it.
    """

    def __init__(
        self,
        strategies: list[BaseClassificationStrategy] | None = None,
        classification_threshold: float = 0.15,
    ) -> None:
        self.classification_threshold = classification_threshold
        self.strategies = strategies or [
            InvoiceStrategy(),
            StatementStrategy(),
            NoteStrategy(),
            ReceiptStrategy(),
        ]

    def run(self, contexts: list[DocumentContext]) -> list[DocumentContext]:
        for context in contexts:
            self._classify_context(context)

        return contexts

    def _classify_context(
        self,
        context: DocumentContext,
    ) -> DocumentContext:
        results = [
            strategy.classify(context)
            for strategy in self.strategies
        ]
        best_result = self._select_best_result(results)

        if best_result is not None:
            context.semantic_type = best_result.document_type
            context.classification_score = best_result.score
            context.classification_reason = best_result.reason
            return context

        context.semantic_type = DocumentType.UNKNOWN
        context.classification_score = 0.0
        context.classification_reason = (
            "No classification strategy matched the document context"
        )
        return context

    def _select_best_result(
        self,
        results: list[ClassificationResult],
    ) -> ClassificationResult | None:
        candidates = [
            result
            for result in results
            if result.document_type is not None
        ]

        if not candidates:
            return None

        best_result = max(candidates, key=lambda result: result.score)

        if best_result.score < self.classification_threshold:
            return None

        return best_result
