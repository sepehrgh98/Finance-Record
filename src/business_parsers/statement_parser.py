from __future__ import annotations

import re

from business_parsers.base_parser import BaseBusinessParser
from models.document_context import DocumentContext
from models.statement_result import StatementResult
from models.transaction import Transaction


class StatementParser(BaseBusinessParser):
    """
    Extracts card transactions from statement document content.

    This parser consumes extracted text from DocumentContext and never reads
    the source PDF directly.
    """

    TRANSACTION_PATTERN = re.compile(
        r"(?P<transaction_id>TXN-\d{4}-\d{3})\s+"
        r"(?P<date>[A-Za-z]{3}\s+\d{2})\s+"
        r"(?P<vendor>.+?)"
        r"(?:\s+(?P<amount>[−–-]?\$?\d[\d,]*\.\d{2}))?$"
    )

    AMOUNT_PATTERN = re.compile(r"(?P<amount>[−–-]?\$?\d[\d,]*\.\d{2})")

    def parse(self, context: DocumentContext) -> StatementResult:
        transactions = self._parse_transactions(context.extracted_text)

        return StatementResult(
            transactions=transactions,
            duplicate_transactions=self.find_duplicates(transactions),
            refunds=[
                transaction
                for transaction in transactions
                if transaction.transaction_type == "refund"
            ],
        )

    def find_duplicates(
        self,
        transactions: list[Transaction],
    ) -> list[Transaction]:
        seen_transaction_ids: set[str] = set()
        seen_composite_keys: set[tuple[str, str, float]] = set()
        duplicates: list[Transaction] = []

        for transaction in transactions:
            is_duplicate = False

            if transaction.transaction_id:
                if transaction.transaction_id in seen_transaction_ids:
                    is_duplicate = True

                seen_transaction_ids.add(transaction.transaction_id)

            if transaction.amount is not None:
                composite_key = (
                    transaction.date,
                    self._normalize_vendor(transaction.vendor),
                    transaction.amount,
                )

                if composite_key in seen_composite_keys:
                    is_duplicate = True

                seen_composite_keys.add(composite_key)

            if is_duplicate:
                duplicates.append(transaction)

        return duplicates

    def _parse_transactions(self, text: str) -> list[Transaction]:
        transactions: list[Transaction] = []
        pending_amount: float | None = None

        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())

            if not line:
                continue

            if self._looks_like_amount_only(line):
                pending_amount = self._parse_amount(line)
                continue

            match = self.TRANSACTION_PATTERN.search(line)

            if match is None:
                continue

            amount = self._parse_amount(match.group("amount") or "")

            if amount is None:
                amount = pending_amount

            pending_amount = None

            if amount is None:
                continue

            transactions.append(
                Transaction(
                    transaction_id=match.group("transaction_id"),
                    date=match.group("date"),
                    vendor=self._clean_vendor(match.group("vendor")),
                    amount=amount,
                    transaction_type=self._transaction_type(amount),
                )
            )

        return transactions

    def _looks_like_amount_only(self, line: str) -> bool:
        return self.AMOUNT_PATTERN.fullmatch(line) is not None

    def _parse_amount(self, value: str) -> float | None:
        match = self.AMOUNT_PATTERN.search(value.replace(",", ""))

        if match is None:
            return None

        normalized = (
            match.group("amount")
            .replace("$", "")
            .replace("−", "-")
            .replace("–", "-")
        )

        try:
            return float(normalized)
        except ValueError:
            return None

    def _transaction_type(self, amount: float) -> str:
        if amount < 0:
            return "refund"

        if amount > 0:
            return "purchase"

        return "unknown"

    def _clean_vendor(self, value: str) -> str:
        return value.strip()

    def _normalize_vendor(self, value: str) -> str:
        return " ".join(value.upper().split())
