from __future__ import annotations

import re

from parsing.base_parser import BaseBusinessParser
from core.models.document_context import DocumentContext
from core.models.statement_result import StatementResult
from core.models.transaction import Transaction


class StatementParser(BaseBusinessParser):
    """
    Extracts card transactions from statement document content.

    This parser consumes extracted text from DocumentContext and never reads
    the source PDF directly.
    """

    TRANSACTION_PATTERN = re.compile(
        r"(?:(?P<transaction_id>TXN-\d{4}-\d{3})\s+)?"
        r"(?P<date>[A-Za-z]{3}\s+\d{2})\s+"
        r"(?P<vendor>.+?)"
        r"(?:\s+(?P<amount>[−–-]?\$?\d[\d,]*\.\d{2}))?$"
    )
    NUMERIC_DATE_TRANSACTION_PATTERN = re.compile(
        r"(?:(?P<transaction_id>TXN-\d{4}-\d{3})\s+)?"
        r"(?P<date>\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s+"
        r"(?P<vendor>.+?)"
        r"(?:\s+(?P<amount>[−–-]?\$?\d[\d,]*\.\d{2}))?$"
    )

    AMOUNT_PATTERN = re.compile(r"(?P<amount>[−–-]?\$?\d[\d,]*\.\d{2})")
    SUMMARY_LABEL_PATTERN = re.compile(
        r"\b("
        r"credit\s+limit|"
        r"previous\s+account\s+balance|"
        r"purchases?\s*&\s*debits?|"
        r"total\s+account\s+balance|"
        r"minimum\s+payment|"
        r"payment\s+due|"
        r"available\s+credit|"
        r"interest\s+charges?|"
        r"fees?\s+charged"
        r")\b",
        re.IGNORECASE,
    )
    LEADING_DATE_PATTERN = re.compile(
        r"^("
        r"[A-Za-z]{3}\s+\d{1,2}|"
        r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
        r")\s+"
    )

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
        pending_match = None

        generated_index = 1

        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            line = self._strip_statement_summary_fragment(line)

            if not line:
                continue

            if self._looks_like_amount_only(line):
                amount = self._parse_amount(line)

                if pending_match is not None and amount is not None:
                    transactions.append(
                        self._transaction_from_match(
                            pending_match,
                            amount,
                            generated_index,
                        )
                    )
                    generated_index += 1
                    pending_match = None
                    pending_amount = None
                    continue

                pending_amount = amount
                continue

            match = self._match_transaction_line(line)

            if match is None:
                continue

            amount = self._parse_amount(match.group("amount") or "")

            if amount is None:
                amount = pending_amount

            pending_amount = None

            if amount is None:
                pending_match = match
                continue

            transactions.append(
                self._transaction_from_match(
                    match,
                    amount=amount,
                    generated_index=generated_index,
                )
            )
            generated_index += 1
            pending_match = None

        return transactions

    def _match_transaction_line(self, line: str):
        return (
            self.TRANSACTION_PATTERN.search(line)
            or self.NUMERIC_DATE_TRANSACTION_PATTERN.search(line)
        )

    def _looks_like_amount_only(self, line: str) -> bool:
        return self.AMOUNT_PATTERN.fullmatch(line) is not None

    def _strip_statement_summary_fragment(self, line: str) -> str:
        match = self.SUMMARY_LABEL_PATTERN.search(line)

        if match is None:
            return line

        prefix = line[: match.start()].strip()

        if prefix and self.AMOUNT_PATTERN.search(prefix):
            return prefix

        return ""

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

    def _generated_transaction_id(self, date: str, index: int) -> str:
        normalized_date = re.sub(r"\W+", "", date.upper()) or "UNKNOWN"
        return f"TXN-{normalized_date}-{index:03d}"

    def _transaction_from_match(
        self,
        match,
        amount: float,
        generated_index: int,
    ) -> Transaction:
        transaction_id = match.group("transaction_id")

        if not transaction_id:
            transaction_id = self._generated_transaction_id(
                match.group("date"),
                generated_index,
            )

        return Transaction(
            transaction_id=transaction_id,
            date=match.group("date"),
            vendor=self._clean_vendor(match.group("vendor")),
            amount=amount,
            transaction_type=self._transaction_type(amount),
        )

    def _clean_vendor(self, value: str) -> str:
        vendor = value.strip()

        while self.LEADING_DATE_PATTERN.search(vendor):
            vendor = self.LEADING_DATE_PATTERN.sub("", vendor, count=1).strip()

        return vendor

    def _normalize_vendor(self, value: str) -> str:
        return " ".join(value.upper().split())
