from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from business_entities.invoice import Invoice
from models.receipt import Receipt
from models.transaction import Transaction
from reconciliation.reconciliation_report import ReconciliationReport
from reporting.report_models import FinalReport


class ReportGenerator:
    def generate(
        self,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        reconciliation_report: ReconciliationReport,
        ignored_files: list[dict],
        files_processed: int = 0,
    ) -> FinalReport:
        return FinalReport(
            metadata=self._metadata(
                files_processed,
                ignored_files,
            ),
            summary=self._summary(
                invoices,
                transactions,
                receipts,
                reconciliation_report,
            ),
            revenue=self._revenue(invoices),
            expenses=self._expenses(transactions, receipts),
            annotations=self._annotations(reconciliation_report),
            action_items=list(reconciliation_report.action_items),
            business_rules=list(reconciliation_report.rules),
            ignored_files=list(ignored_files),
        )

    def _metadata(
        self,
        files_processed: int,
        ignored_files: list[dict],
    ) -> dict:
        return {
            "analysis_date": datetime.now(timezone.utc).isoformat(),
            "files_processed": files_processed,
            "files_ignored": len(ignored_files),
            "reporting_period": "",
        }

    def _summary(
        self,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        reconciliation_report: ReconciliationReport,
    ) -> dict:
        return {
            "invoice_count": len(invoices),
            "transaction_count": len(transactions),
            "receipt_count": len(receipts),
            "annotation_count": len(
                self._annotations(reconciliation_report)
            ),
            "action_item_count": len(reconciliation_report.action_items),
        }

    def _revenue(self, invoices: list[Invoice]) -> dict:
        total_invoiced = self._sum_amounts(invoices)
        paid_invoices = [
            invoice
            for invoice in invoices
            if invoice.status.strip().lower() == "paid"
        ]
        outstanding_invoices = [
            invoice
            for invoice in invoices
            if invoice.status.strip().lower() == "outstanding"
        ]

        return {
            "total_invoiced": total_invoiced,
            "total_paid": self._sum_amounts(paid_invoices),
            "total_outstanding": self._sum_amounts(outstanding_invoices),
            "outstanding_invoices": [
                self._invoice_to_dict(invoice)
                for invoice in outstanding_invoices
            ],
        }

    def _expenses(
        self,
        transactions: list[Transaction],
        receipts: list[Receipt],
    ) -> dict:
        card_expenses = [
            transaction.amount or 0.0
            for transaction in transactions
            if (transaction.amount or 0.0) > 0.0
        ]
        refunds = [
            transaction.amount or 0.0
            for transaction in transactions
            if (transaction.amount or 0.0) < 0.0
        ]
        cash_expenses = [
            receipt.total or 0.0
            for receipt in receipts
            if receipt.payment_method.strip().lower() == "cash"
        ]

        return {
            "total_card_expenses": self._round_money(sum(card_expenses)),
            "total_cash_expenses": self._round_money(sum(cash_expenses)),
            "total_refunds": self._round_money(abs(sum(refunds))),
            "refunds": [
                self._refund_to_dict(transaction)
                for transaction in transactions
                if (transaction.amount or 0.0) < 0.0
            ],
        }

    def _annotations(
        self,
        reconciliation_report: ReconciliationReport,
    ) -> list[dict]:
        annotations: list[dict] = []
        seen: set[tuple[str, str, str]] = set()

        for annotation in reconciliation_report.annotations:
            key = (
                annotation.entity_type,
                annotation.entity_id,
                annotation.note,
            )

            if key in seen:
                continue

            seen.add(key)
            annotations.append(asdict(annotation))

        return annotations

    def _sum_amounts(self, invoices: list[Invoice]) -> float:
        return self._round_money(
            sum(invoice.amount or 0.0 for invoice in invoices)
        )

    def _round_money(self, value: float) -> float:
        return float(round(value, 2))

    def _invoice_to_dict(self, invoice: Invoice) -> dict:
        return {
            "client": invoice.client,
            "invoice_id": invoice.invoice_id,
            "description": invoice.description,
            "amount": invoice.amount or 0.0,
            "date_sent": invoice.date_sent,
            "date_paid": invoice.date_paid,
            "status": invoice.status,
        }

    def _refund_to_dict(self, transaction: Transaction) -> dict:
        return {
            "vendor": transaction.vendor,
            "amount": self._round_money(abs(transaction.amount or 0.0)),
            "date": transaction.date,
        }
