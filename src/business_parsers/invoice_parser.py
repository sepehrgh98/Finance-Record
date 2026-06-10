from __future__ import annotations

from business_entities.invoice import Invoice
from business_parsers.base_parser import BaseBusinessParser
from models.document_context import DocumentContext


class InvoiceParser(BaseBusinessParser):
    """
    Extracts invoice entities from document state, not file format.
    """

    def parse(self, context: DocumentContext) -> list[Invoice]:
        invoices = self._parse_tables(context)

        if invoices:
            return invoices

        return self._parse_text(context)

    def _parse_tables(self, context: DocumentContext) -> list[Invoice]:
        invoices: list[Invoice] = []

        for table in context.extracted_tables:
            headers = [
                self._normalize(header)
                for header in table.get("headers", [])
            ]

            for row in table.get("rows", []):
                row_map = {
                    headers[index]: value
                    for index, value in enumerate(row)
                    if index < len(headers)
                }

                client = row_map.get("client", "")
                amount = self._parse_amount(row_map.get("amount", ""))
                date_paid = row_map.get("date paid", "")
                status = self._payment_status(row_map)

                if client or amount is not None:
                    invoices.append(
                        Invoice(
                            client=client,
                            description=row_map.get("description", ""),
                            amount=amount,
                            date_sent=row_map.get("date sent", ""),
                            date_paid=date_paid,
                            status=status,
                        )
                    )

        return invoices

    def _parse_text(self, context: DocumentContext) -> list[Invoice]:
        if not context.extracted_text.strip():
            return []

        return [Invoice(status="unstructured")]

    def _payment_status(self, row_map: dict[str, str]) -> str:
        if row_map.get("date paid"):
            return "paid"

        if row_map.get("paid"):
            return "paid"

        return "outstanding"

    def _parse_amount(self, value: str) -> float | None:
        try:
            return float(str(value).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _normalize(self, value: str) -> str:
        return " ".join(value.strip().lower().replace("_", " ").split())
