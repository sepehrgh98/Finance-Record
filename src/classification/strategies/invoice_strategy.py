from __future__ import annotations

from classification.base_strategy import BaseClassificationStrategy
from enums.document_type import DocumentType
from models.classification_result import ClassificationResult
from models.document_context import DocumentContext


class InvoiceStrategy(BaseClassificationStrategy):
    KEYWORDS = (
        "invoice",
        "invoice number",
        "invoice id",
        "client",
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

        score = self._score_evidence(
            header_matches=header_matches,
            sheet_matches=sheet_matches,
            keyword_matches=keyword_matches,
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

        return ClassificationResult(
            document_type=DocumentType.INVOICE,
            score=score,
            reason="; ".join(reason_parts),
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
    ) -> float:
        # Structured fields are stronger invoice evidence than keyword hits
        # because they describe the extracted document schema.
        header_score = len(header_matches) / len(self.HEADER_ALIASES)
        sheet_score = min(len(sheet_matches), 1)
        keyword_score = len(keyword_matches) / len(self.KEYWORDS)

        return min(
            1.0,
            (header_score * 0.75)
            + (sheet_score * 0.10)
            + (keyword_score * 0.15),
        )

    def _normalize(self, value: str) -> str:
        return " ".join(value.strip().lower().replace("_", " ").split())
