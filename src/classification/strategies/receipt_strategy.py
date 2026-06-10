from __future__ import annotations

import re

from classification.base_strategy import BaseClassificationStrategy
from enums.document_type import DocumentType
from models.classification_result import ClassificationResult
from models.document_context import DocumentContext


class ReceiptStrategy(BaseClassificationStrategy):
    KEYWORDS = (
        "receipt",
        "subtotal",
        "tax",
        "tps",
        "tvq",
        "gst",
        "hst",
        "pst",
        "total",
        "amount",
        "paid",
        "cash",
        "comptant",
        "change",
        "cashier",
        "terminal",
        "approved",
        "store",
        "merchant",
        "thank you",
        "merci",
        "reçu",
        "recu",
        "facture",
        "visa",
        "mastercard",
        "debit",
        "e-transfer",
    )

    def classify(
        self,
        context: DocumentContext,
    ) -> ClassificationResult:
        if context.metadata.get("ocr_manual_review"):
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        if self._looks_like_invoice(context.extracted_text):
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        if self._looks_like_card_statement(context.extracted_text):
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        if (
            context.metadata.get("ocr_engine") == "vlm"
            and context.metadata.get("ocr_word_count", 0) > 0
            and "receipt" in context.extracted_text.lower()
        ):
            evidence = ["Matched VLM receipt extraction"]
            return ClassificationResult(
                document_type=DocumentType.RECEIPT,
                score=1.0,
                reason="; ".join(evidence),
                evidence=evidence,
            )

        text = context.extracted_text.lower()
        matches = [keyword for keyword in self.KEYWORDS if keyword in text]
        amount_count = self._amount_count(context.extracted_text)
        has_date = self._has_date(context.extracted_text)
        has_payment_method = self._has_payment_method(text)
        has_merchant_like_line = self._has_merchant_like_line(context.extracted_text)
        document_like_ocr = bool(context.metadata.get("ocr_document_like"))

        if not matches and amount_count == 0:
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        score = min(
            1.0,
            (len(matches) / len(self.KEYWORDS) * 0.35)
            + (min(amount_count / 2, 1.0) * 0.25)
            + (0.15 if has_date else 0.0)
            + (0.10 if has_payment_method else 0.0)
            + (0.10 if has_merchant_like_line else 0.0)
            + (0.05 if document_like_ocr else 0.0),
        )

        if score == 0.0:
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        evidence: list[str] = []

        if matches:
            evidence.append(
                "Matched receipt keywords: " + ", ".join(matches)
            )

        if amount_count:
            evidence.append(f"Found {amount_count} amount-like values")

        if has_date:
            evidence.append("Found receipt-like date")

        if has_payment_method:
            evidence.append("Found payment method")

        if has_merchant_like_line:
            evidence.append("Found merchant-like header line")

        if document_like_ocr:
            evidence.append("OCR marked image/document text as document-like")

        return ClassificationResult(
            document_type=DocumentType.RECEIPT,
            score=score,
            reason="; ".join(evidence),
            evidence=evidence,
        )

    def _amount_count(self, text: str) -> int:
        return len(
            re.findall(r"\$?\s*\d+(?:[.,]\d{2})\b", text)
        )

    def _has_date(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|"
                r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
                r"\s+\d{1,2}\b",
                text.lower(),
            )
        )

    def _has_payment_method(self, text: str) -> bool:
        return any(
            term in text
            for term in (
                "cash",
                "comptant",
                "visa",
                "mastercard",
                "debit",
                "e-transfer",
            )
        )

    def _has_merchant_like_line(self, text: str) -> bool:
        for line in text.splitlines()[:5]:
            stripped = line.strip()

            if len(stripped) < 5:
                continue

            if any(character.isdigit() for character in stripped):
                continue

            alpha_count = sum(character.isalpha() for character in stripped)

            if alpha_count >= 5:
                return True

        return False

    def _looks_like_card_statement(self, text: str) -> bool:
        normalized = text.lower()
        statement_anchors = [
            anchor
            for anchor in (
                "statement",
                "credit card",
                "account holder",
                "statement date",
                "visa",
                "mastercard",
                "account number",
                "card number",
            )
            if anchor in normalized
        ]

        return len(statement_anchors) >= 2 and self._amount_count(text) >= 10

    def _looks_like_invoice(self, text: str) -> bool:
        normalized = text.lower()
        invoice_anchors = [
            anchor
            for anchor in (
                "invoice",
                "invoice number",
                "invoice #",
                "invoice id",
                "bill to",
                "amount due",
                "payment status",
            )
            if anchor in normalized
        ]

        return len(invoice_anchors) >= 2
