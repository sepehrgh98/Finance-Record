from __future__ import annotations

import unittest
from pathlib import Path

from core.enums.document_type import DocumentType
from core.enums.physical_file_type import PhysicalFileType
from knowledge.knowledge_store import KnowledgeStore
from core.models.document_context import DocumentContext
from core.models.business_context import BusinessContext
from core.models.file_info import FileInfo
from knowledge.knowledge import Knowledge
from core.models.invoice import Invoice
from core.models.transaction import Transaction
from parsing.business_parser import BusinessParserNode
from reconciliation.reconciliation_engine import ReconciliationEngine
from services.analyze_service import AnalyzeService


def store(*knowledge: Knowledge) -> KnowledgeStore:
    return KnowledgeStore(list(knowledge))


def financial(statement: str, **payload) -> Knowledge:
    return Knowledge(
        knowledge_type="financial_context",
        statement=statement,
        confidence=0.95,
        payload=payload,
    )


def make_context(
    filename: str,
    text: str,
    semantic_type: DocumentType | None = None,
) -> DocumentContext:
    return DocumentContext(
        file_info=FileInfo(
            path=Path(filename),
            filename=filename,
            extension=Path(filename).suffix,
            size_bytes=len(text.encode("utf-8")),
            sha256="test",
        ),
        physical_type=PhysicalFileType.IMAGE,
        extracted_text=text,
        semantic_type=semantic_type,
        metadata={"ocr_document_like": True},
    )


class ReconciliationFindingsTests(unittest.TestCase):
    def test_document_type_context_reclassifies_and_parses_in_review_stage(self) -> None:
        context = make_context(
            "shoebox/receipts/artsupplies.jpeg",
            "CHEN'S ART SUPPLY\nTOTAL $27.50\nCASH",
            semantic_type=DocumentType.UNKNOWN,
        )
        knowledge_store = store(
            Knowledge(
                knowledge_type="document_type_context",
                statement="receipts of cash purchases are in the receipts/ folder",
                payload={"folder": "receipts", "document_type": "receipt"},
            )
        )

        ReconciliationEngine().apply_knowledge_review(
            contexts=[context],
            knowledge_store=knowledge_store,
            business_parser=BusinessParserNode(),
        )

        self.assertEqual(context.semantic_type, DocumentType.RECEIPT)
        self.assertEqual(len(context.business_entities), 1)
        self.assertIn("knowledge", context.classification_reason.lower())

    def test_document_applicability_removes_matching_entities_in_review_stage(self) -> None:
        context = make_context(
            "shoebox/receipts/draft.jpeg",
            "DRAFT RECEIPT\nTOTAL $15.00\nCASH",
            semantic_type=DocumentType.RECEIPT,
        )
        parser = BusinessParserNode()
        parser.parse(context)
        self.assertEqual(len(context.business_entities), 1)

        ReconciliationEngine().apply_knowledge_review(
            contexts=[context],
            knowledge_store=store(
                Knowledge(
                    knowledge_type="document_applicability",
                    statement="ignore draft receipt",
                    payload={"applicable": False, "target": "draft"},
                )
            ),
            business_parser=parser,
        )

        self.assertEqual(context.business_entities, [])
        self.assertTrue(context.metadata["excluded_by_knowledge"])

    def test_document_availability_creates_virtual_missing_entity(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                Knowledge(
                    knowledge_type="document_availability",
                    statement="lost the Uber receipt",
                    payload={
                        "document_type": "receipt",
                        "merchant": "Uber",
                        "status": "missing",
                    },
                )
            ),
        )

        self.assertEqual(len(report.virtual_entities), 1)
        self.assertEqual(report.virtual_entities[0].entity_type, "receipt")
        self.assertEqual(report.virtual_entities[0].entity_name, "Uber")
        self.assertFalse(report.virtual_entities[0].data["document_available"])

    def test_cash_receipt_folder_knowledge_fills_missing_payment_method(self) -> None:
        context = make_context(
            "shoebox/receipts/artsupplies.jpeg",
            "receipt\nCHEN'S ART SUPPLY\ndate 08/03/2025\ntotal $27.50",
            semantic_type=DocumentType.RECEIPT,
        )
        business_context = BusinessContext(
            knowledge=[
                Knowledge(
                    knowledge_type="document_type_context",
                    statement="receipts of cash purchases are in the receipts/ folder",
                    payload={
                        "folder": "receipts",
                        "document_type": "receipt",
                    },
                )
            ],
        )

        AnalyzeService()._apply_pre_parse_knowledge([context], business_context)
        BusinessParserNode().parse(context)

        self.assertEqual(context.business_entities[0].payment_method, "cash")

    def test_financial_context_attaches_entity_enrichment(self) -> None:
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
            knowledge_store=store(
                financial(
                    "the petco charge was dog food for baxter",
                    merchant="petco",
                    classification="personal_expense",
                    entities=["petco"],
                )
            ),
        )

        self.assertEqual(len(report.entity_enrichments), 1)
        self.assertEqual(report.entity_enrichments[0].entity_name, "PETCO #4521")
        self.assertEqual(
            report.entity_enrichments[0].payload["classification"],
            "personal_expense",
        )

    def test_open_ended_notes_are_annotated_without_creating_findings(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[
                Invoice(
                    client="Acme Studio",
                    invoice_id="INV-1",
                    description="Design work",
                    amount=1200.0,
                    status="outstanding",
                )
            ],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                financial(
                    "acme changed their billing email",
                    customer="acme",
                    entities=["acme"],
                )
            ),
        )

        self.assertEqual(len(report.annotations), 1)
        self.assertEqual(report.annotations[0].entity_name, "Acme Studio")
        self.assertEqual(len(report.entity_enrichments), 1)
        self.assertEqual(report.findings, [])

    def test_deterministic_finding_exists_without_llm(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[
                Invoice(
                    client="GreenLoop Technologies",
                    description="Landing page redesign -- milestone 2",
                    amount=1750.0,
                    status="outstanding",
                )
            ],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                financial(
                    "greenloop still hasn't paid invoice 2 — follow up",
                    customer="greenloop",
                    invoice_reference="2",
                    status="unpaid",
                    entities=["greenloop", "invoice 2"],
                )
            ),
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "invoice_follow_up")

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
            knowledge_store=store(
                financial(
                    "the petco charge was dog food for baxter, used business card by accident",
                    merchant="petco",
                    classification="personal_expense",
                    entities=["petco"],
                )
            ),
        )

        self.assertEqual(len(report.annotations), 1)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "possible_personal_expense")
        self.assertEqual(report.findings[0].entity_name, "PETCO #4521")

    def test_invoice_follow_up_finding_from_outstanding_note(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[
                Invoice(
                    client="Atelier Nomade",
                    description="Brand identity package",
                    amount=1500.0,
                    status="outstanding",
                )
            ],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                financial(
                    "atelier nomade invoice still outstanding, they said early may",
                    customer="atelier nomade",
                    status="unpaid",
                    entities=["atelier nomade"],
                )
            ),
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "invoice_follow_up")
        self.assertEqual(report.findings[0].severity, "high")

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
            knowledge_store=store(
                financial(
                    "adobe plan downgraded feb 14, refund came through",
                    merchant="adobe",
                    event="refund",
                    date="feb 14",
                    entities=["adobe plan", "feb 14"],
                )
            ),
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "refund_context")
        self.assertEqual(report.findings[0].entity_type, "transaction")

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
            knowledge_store=store(
                financial(
                    "adobe plan downgraded feb 14, refund came through",
                    merchant="adobe",
                    event="refund",
                    amount=40,
                    date="feb 14",
                    entities=["adobe plan", "feb 14", "$40"],
                ),
                financial(
                    "returned the toner cartridge to staples, refund came through mar 14",
                    merchant="staples",
                    event="refund",
                    date="mar 14",
                    entities=["toner cartridge", "staples", "mar 14"],
                ),
            ),
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
            knowledge_store=store(
                financial(
                    "refund came through on feb 14 for about $40",
                    event="refund",
                    amount=40,
                    date="feb 14",
                    entities=["feb 14", "$40"],
                )
            ),
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].entity_name, "ADOBE *CREATIVE CL")

    def test_announcement_does_not_create_duplicate_finding(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                Knowledge(
                    knowledge_type="announcement",
                    statement="renew business registration before june",
                    payload={"announcement_type": "task"},
                )
            ),
        )

        self.assertEqual(report.action_items, ["renew business registration before june"])
        self.assertEqual(report.findings, [])

    def test_personal_card_move_note_becomes_action_item(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                financial(
                    "netflix is also on this card.. need to move that to my personal one",
                    merchant="netflix",
                    classification="personal_expense",
                    entities=["netflix"],
                )
            ),
        )

        self.assertEqual(
            report.action_items,
            ["netflix is also on this card.. need to move that to my personal one"],
        )

    def test_personal_card_move_note_can_create_personal_expense_finding(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[
                Transaction(
                    transaction_id="TXN-0201-001",
                    date="Feb 1",
                    vendor="NETFLIX.COM",
                    amount=18.99,
                    transaction_type="purchase",
                )
            ],
            receipts=[],
            knowledge_store=store(
                financial(
                    "netflix is also on this card.. need to move that to my personal one",
                    merchant="netflix",
                    classification="personal_expense",
                    entities=["netflix"],
                )
            ),
        )

        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].finding_type, "possible_personal_expense")
        self.assertEqual(report.findings[0].entity_name, "NETFLIX.COM")

    def test_home_office_deduction_note_becomes_action_item(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                financial(
                    "need to figure out if my home office qualifies for a deduction this year",
                    entities=["home office", "deduction"],
                )
            ),
        )

        self.assertEqual(
            report.action_items,
            [
                "need to figure out if my home office qualifies for a deduction this year"
            ],
        )

    def test_financial_knowledge_can_support_reconciliation_and_action_item(self) -> None:
        report = ReconciliationEngine().build_report(
            invoices=[
                Invoice(
                    client="GreenLoop Technologies",
                    description="Landing page redesign -- milestone 2",
                    amount=1750.0,
                    status="outstanding",
                )
            ],
            transactions=[],
            receipts=[],
            knowledge_store=store(
                financial(
                    "greenloop still hasn't paid invoice 2 — follow up",
                    customer="greenloop",
                    invoice_reference="2",
                    status="unpaid",
                    entities=["greenloop", "invoice 2"],
                ),
                Knowledge(
                    knowledge_type="announcement",
                    statement="greenloop still hasn't paid invoice 2 — follow up",
                    payload={"announcement_type": "follow_up"},
                ),
            ),
        )

        self.assertEqual(
            report.action_items,
            ["greenloop still hasn't paid invoice 2 — follow up"],
        )
        self.assertEqual(len(report.annotations), 1)
        self.assertEqual(report.annotations[0].entity_name, "GreenLoop Technologies")
        self.assertEqual(report.findings[0].finding_type, "invoice_follow_up")

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
            knowledge_store=store(
                financial(
                    "the petco charge was dog food for baxter, used business card by accident",
                    merchant="petco",
                    classification="personal_expense",
                    entities=["petco", "business card"],
                ),
                financial(
                    "need to figure out if my home office qualifies for a deduction this year",
                    entities=["home office"],
                ),
                Knowledge(
                    knowledge_type="announcement",
                    statement="reminder: renew business registration before june",
                    payload={"announcement_type": "task"},
                ),
            ),
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
        self.assertEqual(report.findings, [])
        self.assertEqual(
            report.action_items,
            [
                "reminder: renew business registration before june",
                "need to figure out if my home office qualifies for a deduction this year",
            ],
        )


if __name__ == "__main__":
    unittest.main()
