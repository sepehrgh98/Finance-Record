from __future__ import annotations

import re

from enums.document_type import DocumentType
from models.context_hint import ContextHint
from models.semantic_fact import SemanticFact


class ContextHintBuilder:
    """
    Converts generic semantic facts into internal hints for later pipeline nodes.

    Hints are evidence, not truth. They may influence classification or
    reconciliation, but they should not overwrite extracted entities.
    """

    def build(self, semantic_facts: list[SemanticFact]) -> list[ContextHint]:
        hints: list[ContextHint] = []

        for fact in semantic_facts:
            hints.extend(self._folder_document_type_hints(fact))
            hints.extend(self._entity_event_hints(fact))

        return self._deduplicate(hints)

    def _folder_document_type_hints(
        self,
        fact: SemanticFact,
    ) -> list[ContextHint]:
        if fact.fact_type != "rule":
            return []

        statement = fact.statement.lower()
        document_type = self._document_type_from_statement(statement)

        if document_type is None:
            return []

        folders = self._folders_from_statement(statement)

        return [
            ContextHint(
                hint_type="folder_document_type",
                target=folder,
                value=document_type.value,
                source_statement=fact.statement,
                entities=list(fact.entities),
                confidence=fact.confidence,
            )
            for folder in folders
        ]

    def _entity_event_hints(
        self,
        fact: SemanticFact,
    ) -> list[ContextHint]:
        if fact.fact_type not in {"claim", "action_item"}:
            return []

        statement = fact.statement.lower()
        event_type = self._event_type_from_statement(statement)

        if event_type is None:
            return []

        return [
            ContextHint(
                hint_type="entity_event",
                target=", ".join(fact.entities),
                value=event_type,
                source_statement=fact.statement,
                entities=list(fact.entities),
                confidence=fact.confidence,
                metadata={
                    "amounts": self._amounts_from_text(statement),
                    "dates": self._dates_from_text(statement),
                },
            )
        ]

    def _document_type_from_statement(
        self,
        statement: str,
    ) -> DocumentType | None:
        if "receipt" in statement:
            return DocumentType.RECEIPT

        if "invoice" in statement:
            return DocumentType.INVOICE

        if "statement" in statement:
            return DocumentType.STATEMENT

        return None

    def _folders_from_statement(self, statement: str) -> list[str]:
        folders: list[str] = []

        for match in re.finditer(r"\b([a-z0-9_\-]+)/", statement):
            folder = match.group(1).strip().replace(" ", "_")

            if folder:
                folders.append(folder)

        for match in re.finditer(
            r"\b(?:in|inside|under)\s+(?:the\s+)?([a-z0-9_\- ]+)\s+folder\b",
            statement,
        ):
            folder = match.group(1).strip().replace(" ", "_")

            if folder:
                folders.append(folder)

        return [
            folder
            for folder in folders
            if folder not in {"the", "a", "an"}
        ]

    def _event_type_from_statement(self, statement: str) -> str | None:
        if any(term in statement for term in ("refund", "refunded", "returned")):
            return "refund_context"

        if any(
            term in statement
            for term in ("hasn't paid", "has not paid", "outstanding")
        ):
            return "payment_follow_up"

        if any(term in statement for term in ("paid", "payment came through")):
            return "payment_context"

        if any(term in statement for term in ("renew", "registration", "deduction")):
            return "admin_review"

        return None

    def _amounts_from_text(self, text: str) -> list[float]:
        amounts: list[float] = []

        for match in re.finditer(r"\$\s*(-?\d+(?:[.,]\d{2})?)", text):
            try:
                amounts.append(float(match.group(1).replace(",", "")))
            except ValueError:
                pass

        return amounts

    def _dates_from_text(self, text: str) -> list[str]:
        return re.findall(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
            r"\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
            text,
        )

    def _deduplicate(self, hints: list[ContextHint]) -> list[ContextHint]:
        deduplicated: list[ContextHint] = []
        seen: set[tuple[str, str, str, str]] = set()

        for hint in hints:
            key = (
                hint.hint_type,
                hint.target,
                hint.value,
                hint.source_statement,
            )

            if key in seen:
                continue

            seen.add(key)
            deduplicated.append(hint)

        return deduplicated
