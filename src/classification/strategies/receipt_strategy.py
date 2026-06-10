from __future__ import annotations

from classification.base_strategy import BaseClassificationStrategy
from enums.document_type import DocumentType
from models.classification_result import ClassificationResult
from models.document_context import DocumentContext


class ReceiptStrategy(BaseClassificationStrategy):
    KEYWORDS = (
        "receipt",
        "subtotal",
        "tax",
        "total",
        "amount",
        "cash",
        "change",
        "store",
        "merchant",
        "thank you",
        "visa",
        "mastercard",
        "debit",
    )

    def classify(
        self,
        context: DocumentContext,
    ) -> ClassificationResult:
        text = context.extracted_text.lower()
        matches = [keyword for keyword in self.KEYWORDS if keyword in text]
        score = len(matches) / len(self.KEYWORDS)

        if not matches:
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        return ClassificationResult(
            document_type=DocumentType.RECEIPT,
            score=score,
            reason=f"Matched receipt keywords: {', '.join(matches)}",
        )
