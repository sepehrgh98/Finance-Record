from __future__ import annotations

import re

from classification.strategies.base_strategy import BaseClassificationStrategy
from core.enums.document_type import DocumentType
from core.models.classification_result import ClassificationResult
from core.models.document_context import DocumentContext


class StatementStrategy(BaseClassificationStrategy):
    KEYWORDS = (
        "statement",
        "credit card",
        "account holder",
        "transaction",
        "merchant",
        "statement date",
        "statement period",
        "purchase",
        "purchases",
        "payment",
        "payments",
        "refund",
        "credit",
        "debit",
        "balance",
        "account number",
        "card number",
        "visa",
        "mastercard",
        "amex",
    )

    def classify(
        self,
        context: DocumentContext,
    ) -> ClassificationResult:
        text = context.extracted_text.lower()
        matches = [keyword for keyword in self.KEYWORDS if keyword in text]
        transaction_like_lines = self._transaction_like_line_count(
            context.extracted_text
        )
        amount_count = self._amount_count(context.extracted_text)
        statement_anchor_count = len(
            [
                keyword
                for keyword in (
                    "statement",
                    "credit card",
                    "account holder",
                    "statement date",
                    "visa",
                    "mastercard",
                    "account number",
                    "card number",
                )
                if keyword in text
            ]
        )
        score = min(
            1.0,
            (len(matches) / len(self.KEYWORDS) * 0.45)
            + (min(transaction_like_lines / 8, 1.0) * 0.30)
            + (min(amount_count / 12, 1.0) * 0.15)
            + (min(statement_anchor_count / 3, 1.0) * 0.10),
        )

        if not matches and transaction_like_lines == 0 and statement_anchor_count == 0:
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        evidence: list[str] = []

        if matches:
            evidence.append(
                "Matched statement keywords: " + ", ".join(matches)
            )

        if transaction_like_lines:
            evidence.append(
                f"Found {transaction_like_lines} transaction-like lines"
            )

        if amount_count:
            evidence.append(
                f"Found {amount_count} statement amount-like values"
            )

        if statement_anchor_count:
            evidence.append(
                f"Found {statement_anchor_count} statement anchor signals"
            )

        return ClassificationResult(
            document_type=DocumentType.STATEMENT,
            score=score,
            reason="; ".join(evidence),
            evidence=evidence,
        )

    def _transaction_like_line_count(self, text: str) -> int:
        count = 0

        for line in text.splitlines():
            normalized = " ".join(line.split())

            if not normalized:
                continue

            has_date = bool(
                re.search(
                    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
                    r"\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
                    normalized.lower(),
                )
            )
            has_amount = bool(
                re.search(r"-?\$?\s*\d+[.,]\d{2}\b", normalized)
            )

            if has_date and has_amount:
                count += 1

        return count

    def _amount_count(self, text: str) -> int:
        return len(
            re.findall(r"-?\$?\s*\d+[.,]\d{2}\b", text)
        )
