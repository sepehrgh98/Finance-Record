from __future__ import annotations

from classification.base_strategy import BaseClassificationStrategy
from classification.strategies.invoice_strategy import InvoiceStrategy
from classification.strategies.note_strategy import NoteStrategy
from classification.strategies.receipt_strategy import ReceiptStrategy
from classification.strategies.statement_strategy import StatementStrategy
from enums.document_type import DocumentType
from enums.physical_file_type import PhysicalFileType
from models.classification_result import ClassificationResult
from models.context_hint import ContextHint
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
        hint_result = self._classification_hint_result(context)

        if hint_result is not None:
            results.append(hint_result)

        best_result = self._select_best_result(results)

        if best_result is not None:
            context.semantic_type = best_result.document_type
            context.classification_score = best_result.score
            context.classification_reason = best_result.reason
            context.metadata["classification_evidence"] = best_result.evidence
            return context

        context.semantic_type = DocumentType.UNKNOWN
        context.classification_score = 0.0
        context.classification_reason = self._unknown_reason(context)
        context.metadata["classification_evidence"] = []
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

    def _classification_hint_result(
        self,
        context: DocumentContext,
    ) -> ClassificationResult | None:
        hints = context.metadata.get("context_hints", [])
        matching_hints = [
            hint
            for hint in hints
            if isinstance(hint, ContextHint)
            and hint.hint_type == "folder_document_type"
            and self._hint_matches_path(hint, context)
            and self._hint_can_apply_to_context(context)
        ]

        if not matching_hints:
            return None

        hint = matching_hints[0]

        try:
            document_type = DocumentType(hint.value)
        except ValueError:
            return None

        return ClassificationResult(
            document_type=document_type,
            score=0.3,
            reason=(
                "Matched note-derived folder hint: "
                f"{hint.target}/ is likely {hint.value}"
            ),
            evidence=[
                f"Note rule: {hint.source_statement}",
                f"Path matched folder: {hint.target}/",
            ],
        )

    def _hint_matches_path(
        self,
        hint: ContextHint,
        context: DocumentContext,
    ) -> bool:
        target = hint.target.strip("/").lower()

        if not target:
            return False

        path_parts = [
            part.lower()
            for part in context.file_info.path.parts
        ]
        return target in path_parts

    def _hint_can_apply_to_context(self, context: DocumentContext) -> bool:
        if context.physical_type != PhysicalFileType.IMAGE:
            return True

        if context.metadata.get("ocr_manual_review"):
            return False

        return bool(context.metadata.get("ocr_document_like"))
