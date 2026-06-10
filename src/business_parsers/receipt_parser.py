from __future__ import annotations

import re

from business_parsers.base_parser import BaseBusinessParser
from models.document_context import DocumentContext
from models.receipt import Receipt


class ReceiptParser(BaseBusinessParser):
    """
    Extracts receipt facts from OCR/extracted text already stored on context.

    This parser never runs OCR and never reads the original image file.
    """

    DATE_PATTERN = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
    MONEY_PATTERN = re.compile(
        r"[$]?\s*\d+(?:\s*[.,]\s*[0-9oO]{2})"
    )

    MERCHANT_STOP_WORDS = {
        "date",
        "heure",
        "caisse",
        "tel",
        "total",
        "subtotal",
        "sous-total",
        "tps",
        "tvq",
        "tax",
        "comptant",
        "monnaie",
        "trans",
        "merci",
        "cash",
        "change",
        "entrée",
        "sortie",
        "duree",
        "durée",
    }

    def parse(self, context: DocumentContext) -> Receipt | None:
        try:
            text = context.extracted_text or ""
            lines = self._clean_lines(text)

            merchant = self._extract_merchant(lines)
            date = self._extract_date(text)
            subtotal = self._extract_labeled_amount(lines, ("subtotal", "sous-total"))
            tax = self._extract_tax(lines)
            total = self._extract_total(lines)
            payment_method = self._extract_payment_method(text)

            if total is None or not (merchant or date):
                return None

            return Receipt(
                merchant=merchant,
                date=date,
                subtotal=subtotal,
                tax=tax,
                total=total,
                payment_method=payment_method,
            )
        except Exception:
            return None

    def _clean_lines(self, text: str) -> list[str]:
        lines: list[str] = []

        for raw_line in text.splitlines():
            line = " ".join(raw_line.strip().split())

            if line:
                lines.append(line)

        return lines

    def _extract_merchant(self, lines: list[str]) -> str:
        candidates: list[tuple[int, str]] = []

        for index, line in enumerate(lines[:80]):
            normalized = self._normalize_text(line)
            clean_line = self._strip_noise(line)

            if len(normalized) < 3:
                continue

            if any(character.isdigit() for character in clean_line):
                continue

            if "/" in clean_line or "\\" in clean_line:
                continue

            if self.DATE_PATTERN.search(line):
                continue

            if self.MONEY_PATTERN.search(line):
                continue

            if any(word in normalized for word in self.MERCHANT_STOP_WORDS):
                continue

            alpha_count = sum(character.isalpha() for character in clean_line)

            if alpha_count < 5:
                continue

            uppercase_ratio = sum(
                character.isupper()
                for character in clean_line
                if character.isalpha()
            ) / max(alpha_count, 1)
            allowed_count = sum(
                character.isalnum()
                or character.isspace()
                or character in "'&#.-"
                for character in clean_line
            )
            noise_ratio = 1 - (allowed_count / max(len(clean_line), 1))

            if noise_ratio > 0.2:
                continue

            score = alpha_count - index

            if uppercase_ratio > 0.6:
                score += 50

            candidates.append((score, clean_line))

        if not candidates:
            return ""

        return max(candidates, key=lambda candidate: candidate[0])[1]

    def _extract_date(self, text: str) -> str:
        match = self.DATE_PATTERN.search(text)
        return match.group(0) if match else ""

    def _extract_labeled_amount(
        self,
        lines: list[str],
        labels: tuple[str, ...],
    ) -> float | None:
        for line in lines:
            normalized = self._normalize_text(line)

            if any(label in normalized for label in labels):
                amount = self._parse_last_amount(line)

                if amount is not None:
                    return amount

        return None

    def _extract_tax(self, lines: list[str]) -> float | None:
        taxes: list[float] = []
        seen_tax_lines: set[str] = set()

        for line in lines:
            normalized = self._normalize_text(line)

            if any(label in normalized for label in ("tax", "tps", "tvq")):
                if normalized in seen_tax_lines:
                    continue

                seen_tax_lines.add(normalized)
                amount = self._parse_last_amount(line)

                if amount is not None:
                    taxes.append(amount)

        if not taxes:
            return None

        return round(sum(taxes), 2)

    def _extract_total(self, lines: list[str]) -> float | None:
        totals: list[float] = []

        for line in lines:
            normalized = self._normalize_text(line)

            if "subtotal" in normalized or "sous-total" in normalized:
                continue

            if "total" not in normalized and "ktotal" not in normalized:
                continue

            amount = self._parse_last_amount(line)

            if amount is not None:
                totals.append(amount)

        if not totals:
            return None

        return max(totals)

    def _extract_payment_method(self, text: str) -> str:
        normalized = self._normalize_text(text)

        if "comptant" in normalized or "cash" in normalized:
            return "cash"

        if "visa" in normalized:
            return "visa"

        if "mastercard" in normalized:
            return "mastercard"

        if "debit" in normalized:
            return "debit"

        return ""

    def _parse_amount(self, text: str) -> float | None:
        amounts = self._parse_amounts(text)

        if not amounts:
            return None

        return amounts[0]

    def _parse_last_amount(self, text: str) -> float | None:
        amounts = self._parse_amounts(text)

        if not amounts:
            return None

        return amounts[-1]

    def _parse_amounts(self, text: str) -> list[float]:
        amounts: list[float] = []

        for match in self.MONEY_PATTERN.finditer(text):
            if self._looks_like_percentage_match(text, match):
                continue

            amount_text = (
                match.group(0)
                .replace("$", "")
                .replace(" ", "")
                .replace(",", ".")
                .replace("O", "0")
                .replace("o", "0")
            )

            try:
                amounts.append(float(amount_text))
            except ValueError:
                continue

        return amounts

    def _looks_like_percentage_match(self, text: str, match: re.Match) -> bool:
        lookahead = text[match.end():match.end() + 3]
        lookbehind = text[max(0, match.start() - 2):match.start()]

        return "%" in lookahead or "(" in lookbehind

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.lower().split())

    def _strip_noise(self, text: str) -> str:
        return (
            text.strip(" *:-|\\/")
            .replace("$", "")
            .strip(" *:-|\\/")
        )
