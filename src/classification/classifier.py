from __future__ import annotations

from classification.strategies.base_strategy import BaseClassificationStrategy
from classification.strategies.invoice_strategy import InvoiceStrategy
from classification.strategies.note_strategy import NoteStrategy
from classification.strategies.receipt_strategy import ReceiptStrategy
from classification.strategies.statement_strategy import StatementStrategy
from core.enums.document_type import DocumentType
from core.enums.physical_file_type import PhysicalFileType
from core.models.classification_result import ClassificationResult
from core.models.document_context import DocumentContext
from core.utils.pipeline_logger import pipeline_log


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
            context.metadata["classification_evidence"] = best_result.evidence
            pipeline_log(
                "classified: "
                f"{context.file_info.filename} -> "
                f"{best_result.document_type.value} "
                f"score={best_result.score:.2f} "
                f"reason={best_result.reason}"
            )
            return context

        context.semantic_type = DocumentType.UNKNOWN
        context.classification_score = 0.0
        context.classification_reason = self._unknown_reason(context)
        context.metadata["classification_evidence"] = []
        pipeline_log(
            "classified: "
            f"{context.file_info.filename} -> unknown "
            f"reason={context.classification_reason}"
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

    def _unknown_reason(self, context: DocumentContext) -> str:
        if not (context.extracted_text or "").strip():
            return "No text or structured content could be extracted"

        if context.physical_type == PhysicalFileType.IMAGE:
            if context.metadata.get("ocr_manual_review"):
                return "Document-like image detected but OCR failed across all engines"

            if not context.metadata.get("ocr_document_like"):
                return "Image does not appear to contain a business document"

        return "No classification strategy matched the document context"
