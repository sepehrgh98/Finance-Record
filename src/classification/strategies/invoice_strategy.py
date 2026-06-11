from __future__ import annotations

import re

from classification.strategies.base_strategy import BaseClassificationStrategy
from core.enums.document_type import DocumentType
from core.models.classification_result import ClassificationResult
from core.models.document_context import DocumentContext


class InvoiceStrategy(BaseClassificationStrategy):
    KEYWORDS = (
        "invoice",
        "invoice number",
        "invoice id",
        "client",
        "customer",
        "date sent",
        "date paid",
        "payment status",
        "amount due",
        "paid",
        "unpaid",
        "outstanding",
    )

    HEADER_ALIASES = {
        "invoice_id": (
            "invoice_id",
            "invoice id",
            "invoice number",
            "invoice #",
            "inv id",
        ),
        "amount": (
            "amount",
            "amount due",
            "total",
            "balance",
        ),
        "client": (
            "client",
            "customer",
            "bill to",
        ),
        "payment_status": (
            "payment status",
            "status",
            "paid",
            "date paid",
            "unpaid",
            "outstanding",
        ),
        "issue_date": (
            "issue date",
            "date issued",
            "invoice date",
            "date sent",
            "sent date",
        ),
    }

    def classify(
        self,
        context: DocumentContext,
    ) -> ClassificationResult:
        text = context.extracted_text.lower()
        keyword_matches = [keyword for keyword in self.KEYWORDS if keyword in text]
        header_matches = self._match_structured_headers(context)
        sheet_matches = self._match_sheet_names(context)
        row_count = self._table_row_count(context)
        amount_like_rows = self._amount_like_row_count(context)
        status_like_rows = self._status_like_row_count(context)
        text_field_matches = self._match_text_fields(text)
        money_count = self._money_count(context.extracted_text)
        date_count = self._date_count(text)

        score = self._score_evidence(
            header_matches=header_matches,
            sheet_matches=sheet_matches,
            keyword_matches=keyword_matches,
            row_count=row_count,
            amount_like_rows=amount_like_rows,
            status_like_rows=status_like_rows,
            text_field_matches=text_field_matches,
            money_count=money_count,
            date_count=date_count,
        )

        if score == 0.0:
            return ClassificationResult(
                document_type=None,
                score=0.0,
                reason="",
            )

        reason_parts: list[str] = []

        if header_matches:
            reason_parts.append(
                "Matched invoice-like spreadsheet headers: "
                + ", ".join(header_matches)
            )

        if sheet_matches:
            reason_parts.append(
                "Matched invoice-like sheet names: "
                + ", ".join(sheet_matches)
            )

        if keyword_matches:
            reason_parts.append(
                "Matched invoice keywords: "
                + ", ".join(keyword_matches)
            )

        if row_count:
            reason_parts.append(
                f"Found {row_count} spreadsheet data rows"
            )

        if amount_like_rows:
            reason_parts.append(
                f"Found {amount_like_rows} amount-like invoice rows"
            )

        if status_like_rows:
            reason_parts.append(
                f"Found {status_like_rows} payment-status rows"
            )

        if text_field_matches:
            reason_parts.append(
                "Matched invoice text fields: "
                + ", ".join(text_field_matches)
            )

        if money_count:
            reason_parts.append(
                f"Found {money_count} invoice amount-like values"
            )

        if date_count:
            reason_parts.append(
                f"Found {date_count} invoice date-like values"
            )

        return ClassificationResult(
            document_type=DocumentType.INVOICE,
            score=score,
            reason="; ".join(reason_parts),
            evidence=reason_parts,
        )

    def _match_structured_headers(self, context: DocumentContext) -> list[str]:
        headers: list[str] = []

        for table in context.extracted_tables:
            headers.extend(table.get("headers", []))

        headers.extend(context.metadata.get("headers", []))
        normalized_headers = [self._normalize(header) for header in headers]
        matches: list[str] = []

        for semantic_field, aliases in self.HEADER_ALIASES.items():
            if any(
                alias in normalized_headers
                for alias in aliases
            ):
                matches.append(semantic_field)

        return matches

    def _match_sheet_names(self, context: DocumentContext) -> list[str]:
        sheet_names = context.metadata.get("sheet_names", [])
        matches = []

        for sheet_name in sheet_names:
            normalized_sheet_name = self._normalize(sheet_name)
            if "invoice" in normalized_sheet_name:
                matches.append(sheet_name.strip())

        return matches

    def _score_evidence(
        self,
        header_matches: list[str],
        sheet_matches: list[str],
        keyword_matches: list[str],
        row_count: int,
        amount_like_rows: int,
        status_like_rows: int,
        text_field_matches: list[str],
        money_count: int,
        date_count: int,
    ) -> float:
        # Structured fields are stronger invoice evidence than keyword hits
        # because they describe the extracted document schema.
        header_score = len(header_matches) / len(self.HEADER_ALIASES)
        sheet_score = min(len(sheet_matches), 1)
        keyword_score = len(keyword_matches) / len(self.KEYWORDS)
        row_score = min(row_count / 3, 1.0)
        amount_score = min(amount_like_rows / 3, 1.0)
        status_score = min(status_like_rows / 3, 1.0)
        text_field_score = min(len(text_field_matches) / 4, 1.0)
        money_score = min(money_count / 2, 1.0)
        date_score = min(date_count / 2, 1.0)

        return min(
            1.0,
            (header_score * 0.42)
            + (sheet_score * 0.08)
            + (keyword_score * 0.12)
            + (row_score * 0.08)
            + (amount_score * 0.08)
            + (status_score * 0.05)
            + (text_field_score * 0.13)
            + (money_score * 0.07)
            + (date_score * 0.05)
        )

    def _normalize(self, value: str) -> str:
        return " ".join(value.strip().lower().replace("_", " ").split())

    def _table_row_count(self, context: DocumentContext) -> int:
        return sum(
            len(table.get("rows", []))
            for table in context.extracted_tables
        )

    def _amount_like_row_count(self, context: DocumentContext) -> int:
        count = 0

        for table in context.extracted_tables:
            for row in table.get("rows", []):
                if any(
                    re.search(r"\b\d{2,}(?:[.,]\d{2})?\b", str(value))
                    for value in row
                ):
                    count += 1

        return count

    def _status_like_row_count(self, context: DocumentContext) -> int:
        statuses = {"paid", "unpaid", "outstanding", "pending"}
        count = 0

        for table in context.extracted_tables:
            for row in table.get("rows", []):
                normalized_values = {
                    self._normalize(str(value))
                    for value in row
                }

                if normalized_values & statuses:
                    count += 1

        return count

    def _match_text_fields(self, text: str) -> list[str]:
        field_patterns = {
            "invoice_anchor": r"\binvoice\b|\binvoice\s*(number|#|id)\b",
            "client": r"\b(client|customer|bill to)\b",
            "amount": r"\b(amount due|total|balance)\b",
            "date": r"\b(invoice date|date sent|date issued|due date)\b",
            "status": r"\b(paid|unpaid|outstanding|payment status)\b",
        }

        return [
            name
            for name, pattern in field_patterns.items()
            if re.search(pattern, text)
        ]

    def _money_count(self, text: str) -> int:
        return len(
            re.findall(r"\$?\s*\d+(?:[.,]\d{2})\b", text)
        )

    def _date_count(self, text: str) -> int:
        return len(
            re.findall(
                r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|"
                r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
                r"\s+\d{1,2}\b",
                text,
            )
        )
