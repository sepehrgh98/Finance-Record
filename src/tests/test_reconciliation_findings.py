from __future__ import annotations

import unittest

from business_entities.invoice import Invoice
from models.semantic_fact import SemanticFact
from models.transaction import Transaction
from reconciliation.reconciliation_engine import ReconciliationEngine


class FakeFindingLLM:
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int = 30,
    ) -> dict:
        return {
            "should_create_finding": True,
            "finding_type": "billing_contact_update",
            "group": "Records",
            "severity": "low",
            "status": "open",
            "confidence": "high",
            "title": "Billing contact should be updated",
            "description": (
                "The linked client note mentions a billing contact change."
            ),
            "suggested_action": (
                "Review the client record and update the billing contact."
            ),
            "evidence": [
                "Source note: client changed their billing email",
                "Linked entity: Acme Studio",
            ],
        }


class ReconciliationFindingsTests(unittest.TestCase):
    def test_llm_can_create_open_ended_finding_type(self) -> None:
        report = ReconciliationEngine(llm_client=FakeFindingLLM()).build_report(
            invoices=[
                Invoice(
                    client="Acme Studio",
                    invoice_id="INV-1",
                    description="Design work",
                    amount=1200.0,
                    date_sent="3/1/25",
                    date_paid="",
                    status="outstanding",
                )
            ],
            transactions=[],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement="acme changed their billing email",
                    entities=["acme"],
                    confidence=0.95,
                )
            ],
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(
            report.findings[0].finding_type,
            "billing_contact_update",
        )
        self.assertEqual(report.findings[0].group, "Records")
        self.assertEqual(report.findings[0].entity_name, "Acme Studio")

    def test_personal_expense_finding_from_linked_transaction_note(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[
                Transaction(
                    transaction_id="TXN-0123-001",
                    date="Jan 23",
                    vendor="PETCO #4521",
                    amount=47.83,
                    transaction_type="purchase",
                )
            ],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement=(
                        "the petco charge was dog food for baxter, "
                        "used business card by accident"
                    ),
                    entities=["petco"],
                    confidence=0.95,
                )
            ],
        )

        self.assertEqual(len(report.annotations), 1)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(
            report.findings[0].finding_type,
            "possible_personal_expense",
        )
        self.assertEqual(report.findings[0].entity_name, "PETCO #4521")
        self.assertEqual(report.findings[0].group, "Money to Review")
        self.assertEqual(report.findings[0].status, "open")
        self.assertTrue(report.findings[0].suggested_action)

    def test_invoice_follow_up_finding_from_outstanding_note(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[
                Invoice(
                    client="Atelier Nomade",
                    invoice_id="",
                    description="Brand identity package",
                    amount=1500.0,
                    date_sent="3/22/25",
                    date_paid="",
                    status="outstanding",
                )
            ],
            transactions=[],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement=(
                        "atelier nomade invoice still outstanding, "
                        "they said early may"
                    ),
                    entities=["atelier nomade"],
                    confidence=0.95,
                )
            ],
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "invoice_follow_up")
        self.assertEqual(report.findings[0].severity, "high")
        self.assertEqual(report.findings[0].group, "Receivables")

    def test_refund_context_finding_from_negative_transaction_note(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[
                Transaction(
                    transaction_id="TXN-0214-001",
                    date="Feb 14",
                    vendor="ADOBE *CREATIVE CL",
                    amount=-40.0,
                    transaction_type="refund",
                )
            ],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement="adobe plan downgraded feb 14, refund came through",
                    entities=["adobe plan", "feb 14"],
                    confidence=0.95,
                )
            ],
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "refund_context")
        self.assertEqual(report.findings[0].entity_type, "transaction")
        self.assertEqual(report.findings[0].confidence, "high")

    def test_refund_context_does_not_cross_match_unrelated_refunds(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[
                Transaction(
                    transaction_id="TXN-0214-001",
                    date="Feb 14",
                    vendor="ADOBE *CREATIVE CL",
                    amount=-40.0,
                    transaction_type="refund",
                ),
                Transaction(
                    transaction_id="TXN-0314-001",
                    date="Mar 14",
                    vendor="STAPLES #0312",
                    amount=-32.49,
                    transaction_type="refund",
                ),
            ],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement="adobe plan downgraded feb 14, refund came through",
                    entities=["adobe plan", "feb 14", "$40"],
                    confidence=0.95,
                ),
                SemanticFact(
                    fact_type="claim",
                    statement=(
                        "returned the toner cartridge to staples, "
                        "refund came through mar 14"
                    ),
                    entities=["toner cartridge", "staples", "mar 14"],
                    confidence=0.95,
                ),
            ],
        )

        refund_findings = [
            finding
            for finding in report.findings
            if finding.finding_type == "refund_context"
        ]

        self.assertEqual(len(refund_findings), 2)
        self.assertEqual(
            {finding.entity_name for finding in refund_findings},
            {"ADOBE *CREATIVE CL", "STAPLES #0312"},
        )

        adobe_findings = [
            finding
            for finding in refund_findings
            if finding.entity_name == "ADOBE *CREATIVE CL"
        ]
        self.assertEqual(len(adobe_findings), 1)
        self.assertIn("adobe plan", adobe_findings[0].evidence[0])

    def test_transaction_can_match_by_amount_and_date_when_vendor_missing(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[
                Transaction(
                    transaction_id="TXN-0214-001",
                    date="Feb 14",
                    vendor="ADOBE *CREATIVE CL",
                    amount=-40.0,
                    transaction_type="refund",
                )
            ],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement="refund came through on feb 14 for about $40",
                    entities=["feb 14", "$40"],
                    confidence=0.95,
                )
            ],
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].entity_name, "ADOBE *CREATIVE CL")
        self.assertEqual(report.findings[0].finding_type, "refund_context")

    def test_standalone_admin_action_finding(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="action_item",
                    statement="renew business registration before june",
                    entities=["business registration"],
                    confidence=0.95,
                )
            ],
        )

        self.assertEqual(report.action_items, ["renew business registration before june"])
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(
            report.findings[0].finding_type,
            "admin_or_compliance_action",
        )
        self.assertIsNone(report.findings[0].entity_id)
        self.assertEqual(report.findings[0].group, "Admin")

    def test_generic_note_terms_do_not_match_random_transactions(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[
                Transaction(
                    transaction_id="TXN-0118-001",
                    date="Jan 18",
                    vendor="WAYMO BUSINESS *X MONTREAL",
                    amount=18.5,
                    transaction_type="purchase",
                ),
                Transaction(
                    transaction_id="TXN-0131-001",
                    date="Jan 31",
                    vendor="AMAZON.CA *OFFICE",
                    amount=33.47,
                    transaction_type="purchase",
                ),
            ],
            receipts=[],
            semantic_facts=[
                SemanticFact(
                    fact_type="claim",
                    statement=(
                        "the petco charge was dog food for baxter, "
                        "used business card by accident"
                    ),
                    entities=["petco", "business card"],
                    confidence=0.95,
                ),
                SemanticFact(
                    fact_type="claim",
                    statement=(
                        "need to figure out if my home office qualifies "
                        "for a deduction this year"
                    ),
                    entities=["home office"],
                    confidence=0.95,
                ),
                SemanticFact(
                    fact_type="action_item",
                    statement="reminder: renew business registration before june",
                    entities=["business registration"],
                    confidence=0.95,
                ),
            ],
        )

        entity_findings = [
            finding
            for finding in report.findings
            if finding.entity_name in {
                "WAYMO BUSINESS *X MONTREAL",
                "AMAZON.CA *OFFICE",
            }
        ]

        self.assertEqual(entity_findings, [])
        self.assertEqual(
            {
                finding.finding_type
                for finding in report.findings
            },
            {"admin_or_compliance_action"},
        )


if __name__ == "__main__":
    unittest.main()
