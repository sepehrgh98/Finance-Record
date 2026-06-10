from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from business_entities.invoice import Invoice
from models.receipt import Receipt
from models.semantic_fact import SemanticFact
from models.transaction import Transaction
from reconciliation.reconciliation_report import Annotation, ReconciliationReport


class ReconciliationEngine:
    def build_report(
        self,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        semantic_facts: list[SemanticFact],
    ) -> ReconciliationReport:
        report = ReconciliationReport()

        for fact in semantic_facts:
            if fact.fact_type == "action_item":
                report.action_items.append(fact.statement)
                continue

            if fact.fact_type == "rule":
                report.rules.append(fact.statement)
                continue

            if fact.fact_type == "claim":
                report.annotations.extend(
                    self._annotations_for_claim(
                        fact,
                        invoices,
                        transactions,
                        receipts,
                    )
                )

        return report

    def _annotations_for_claim(
        self,
        fact: SemanticFact,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
    ) -> list[Annotation]:
        annotations: list[Annotation] = []

        for invoice in invoices:
            if self._matches_entity(invoice, fact.entities):
                annotations.append(
                    Annotation(
                        entity_type="invoice",
                        entity_id=self._invoice_id(invoice),
                        entity_name=self._invoice_name(invoice),
                        note=fact.statement,
                    )
                )

        for transaction in transactions:
            if self._matches_entity(transaction, fact.entities):
                annotations.append(
                    Annotation(
                        entity_type="transaction",
                        entity_id=self._transaction_id(transaction),
                        entity_name=self._transaction_name(transaction),
                        note=fact.statement,
                    )
                )

        for receipt in receipts:
            if self._matches_entity(receipt, fact.entities):
                annotations.append(
                    Annotation(
                        entity_type="receipt",
                        entity_id=self._receipt_id(receipt),
                        entity_name=self._receipt_name(receipt),
                        note=fact.statement,
                    )
                )

        return annotations

    def _matches_entity(
        self,
        entity: object,
        claim_entities: list[str],
    ) -> bool:
        entity_values = self._entity_values(entity)

        for claim_entity in claim_entities:
            normalized_claim = self._normalize(claim_entity)

            if not normalized_claim:
                continue

            for entity_value in entity_values:
                normalized_value = self._normalize(entity_value)

                if not normalized_value:
                    continue

                if (
                    normalized_claim in normalized_value
                    or normalized_value in normalized_claim
                ):
                    return True

        return False

    def _entity_values(self, entity: object) -> list[str]:
        if not is_dataclass(entity):
            return []

        values: list[str] = []

        for field in fields(entity):
            value = getattr(entity, field.name)

            if value is not None:
                values.append(str(value))

        return values

    def _invoice_id(self, invoice: Invoice) -> str:
        return (
            invoice.invoice_id
            or invoice.client
            or invoice.description
            or "invoice"
        )

    def _transaction_id(self, transaction: Transaction) -> str:
        return (
            transaction.transaction_id
            or transaction.vendor
            or "transaction"
        )

    def _receipt_id(self, receipt: Receipt) -> str:
        return " | ".join(
            value
            for value in [receipt.merchant, receipt.date]
            if value
        ) or "receipt"

    def _invoice_name(self, invoice: Invoice) -> str:
        return invoice.client or invoice.description or "invoice"

    def _transaction_name(self, transaction: Transaction) -> str:
        return transaction.vendor or "transaction"

    def _receipt_name(self, receipt: Receipt) -> str:
        return receipt.merchant or "receipt"

    def _normalize(self, value: Any) -> str:
        return str(value).strip().lower()
