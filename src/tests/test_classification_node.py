from __future__ import annotations

import unittest
from pathlib import Path

from enums.document_type import DocumentType
from enums.physical_file_type import PhysicalFileType
from models.context_hint import ContextHint
from models.document_context import DocumentContext
from models.file_info import FileInfo
from nodes.classifier import ClassifierNode


def make_context(
    *,
    filename: str,
    physical_type: PhysicalFileType,
    text: str = "",
    tables: list[dict] | None = None,
    metadata: dict | None = None,
) -> DocumentContext:
    return DocumentContext(
        file_info=FileInfo(
            path=Path(filename),
            filename=filename,
            extension=Path(filename).suffix,
            size_bytes=len(text.encode("utf-8")),
            sha256="test",
        ),
        physical_type=physical_type,
        extracted_text=text,
        extracted_tables=tables or [],
        metadata=metadata or {},
    )


def classify(context: DocumentContext) -> DocumentContext:
    return ClassifierNode()._classify_context(context)


class ClassificationNodeTests(unittest.TestCase):
    def assert_classified_as(
        self,
        context: DocumentContext,
        expected_type: DocumentType,
    ) -> DocumentContext:
        classified = classify(context)

        self.assertEqual(classified.semantic_type, expected_type)
        self.assertGreaterEqual(classified.classification_score, 0.15)
        self.assertTrue(classified.classification_reason)
        self.assertIn("classification_evidence", classified.metadata)
        return classified

    def test_invoice_spreadsheet_uses_headers_rows_and_statuses(self) -> None:
        context = make_context(
            filename="invoices.xlsx",
            physical_type=PhysicalFileType.SPREADSHEET,
            text="Sheet names: Invoices\nHeaders: client | amount | payment_status | date sent",
            tables=[
                {
                    "headers": ["client", "amount", "payment_status", "date_sent"],
                    "rows": [
                        ["GreenLoop", "1750.00", "paid", "2025-03-05"],
                        ["Atelier Nomade", "1500.00", "outstanding", ""],
                    ],
                }
            ],
            metadata={
                "sheet_names": ["Invoices"],
                "headers": ["client", "amount", "payment_status", "date_sent"],
            },
        )

        classified = self.assert_classified_as(context, DocumentType.INVOICE)

        self.assertIn("spreadsheet", classified.classification_reason)
        self.assertIn("amount-like invoice rows", classified.classification_reason)

    def test_invoice_pdf_text_uses_invoice_fields_not_file_format(self) -> None:
        context = make_context(
            filename="invoice-greenloop.pdf",
            physical_type=PhysicalFileType.PDF,
            text="""
            INVOICE # GL-002
            Client: GreenLoop Technologies
            Invoice Date: 03/15/2025
            Amount Due: $1,750.00
            Payment Status: outstanding
            """,
        )

        classified = self.assert_classified_as(context, DocumentType.INVOICE)

        self.assertIn("invoice text fields", classified.classification_reason)

    def test_invoice_image_ocr_text_can_classify_as_invoice(self) -> None:
        context = make_context(
            filename="invoice-photo.png",
            physical_type=PhysicalFileType.IMAGE,
            text="""
            Invoice Number INV-204
            Bill To: Nonna's Kitchen
            Date Sent: 02/14/2025
            Total: $600.00
            Paid
            """,
            metadata={"ocr_document_like": True},
        )

        self.assert_classified_as(context, DocumentType.INVOICE)

    def test_statement_pdf_uses_statement_anchors_and_amount_density(self) -> None:
        transaction_lines = "\n".join(
            [
                "Jan 03 GOOGLE *WORKSPACE 8.28",
                "Jan 06 ADOBE *CREATIVE CL 74.99",
                "Jan 10 NETFLIX.COM 16.99",
                "Jan 23 PETCO #4521 47.83",
                "Feb 14 ADOBE *CREATIVE CL -40.00",
                "Mar 14 STAPLES #0312 -32.49",
                "Mar 18 NAMECHEAP.COM 22.99",
                "Mar 28 POSTES CANADA 12.25",
            ]
        )
        context = make_context(
            filename="Visa_Statement_Q12025.pdf",
            physical_type=PhysicalFileType.PDF,
            text=f"""
            VISA Credit Card Statement
            Account Holder: Studio Example
            Statement Date: 03/31/2025
            Card Number ending 1234
            {transaction_lines}
            """,
        )

        classified = self.assert_classified_as(context, DocumentType.STATEMENT)

        self.assertIn("statement anchor", classified.classification_reason)
        self.assertIn("transaction-like", classified.classification_reason)

    def test_statement_does_not_get_misclassified_as_receipt(self) -> None:
        context = make_context(
            filename="statement-screenshot.png",
            physical_type=PhysicalFileType.IMAGE,
            text="""
            Mastercard statement
            Account Holder: Studio Example
            Statement Date: 03/31/2025
            Jan 01 Vendor A 10.00
            Jan 02 Vendor B 11.00
            Jan 03 Vendor C 12.00
            Jan 04 Vendor D 13.00
            Jan 05 Vendor E 14.00
            Jan 06 Vendor F 15.00
            Jan 07 Vendor G 16.00
            Jan 08 Vendor H 17.00
            Jan 09 Vendor I 18.00
            Jan 10 Vendor J 19.00
            """,
            metadata={"ocr_document_like": True},
        )

        self.assert_classified_as(context, DocumentType.STATEMENT)

    def test_receipt_text_pdf_uses_amount_date_payment_and_merchant(self) -> None:
        context = make_context(
            filename="cash-receipt.pdf",
            physical_type=PhysicalFileType.PDF,
            text="""
            BUREAU EN GROS
            Date 22/01/2025
            Subtotal $35.49
            Tax $5.31
            Total $40.80
            Cash
            Thank you
            """,
        )

        classified = self.assert_classified_as(context, DocumentType.RECEIPT)

        self.assertIn("payment method", classified.classification_reason)
        self.assertIn("merchant-like", classified.classification_reason)

    def test_receipt_vlm_extraction_is_strong_receipt_evidence(self) -> None:
        context = make_context(
            filename="artsupplies.jpeg",
            physical_type=PhysicalFileType.IMAGE,
            text="""
            receipt
            CHEN'S ART SUPPLY
            date 08/03/2025
            MARKERS (x6) 1 $18.50
            NOTEPAD (x1) 1 $9.00
            total $27.50
            E-TRANSFER
            """,
            metadata={
                "ocr_engine": "vlm",
                "ocr_word_count": 24,
                "ocr_document_like": True,
            },
        )

        classified = self.assert_classified_as(context, DocumentType.RECEIPT)

        self.assertEqual(classified.classification_score, 1.0)
        self.assertIn("VLM receipt", classified.classification_reason)

    def test_note_text_uses_filename_sections_and_language(self) -> None:
        context = make_context(
            filename="notes.txt",
            physical_type=PhysicalFileType.TEXT,
            text="""
            == invoices ==
            - greenloop still hasn't paid invoice 2
            [todo] renew business registration before june
            random:
            wish i could just throw my business docs at something
            """,
        )

        classified = self.assert_classified_as(context, DocumentType.NOTE)

        self.assertIn("filename hints", classified.classification_reason)
        self.assertIn("plain text", classified.classification_reason)

    def test_note_image_ocr_text_can_classify_as_note(self) -> None:
        context = make_context(
            filename="whiteboard-note.png",
            physical_type=PhysicalFileType.IMAGE,
            text="""
            Reminder:
            need to follow up with GreenLoop before Friday
            remember to send invoice draft
            """,
            metadata={"ocr_document_like": True},
        )

        self.assert_classified_as(context, DocumentType.NOTE)

    def test_irrelevant_image_becomes_unknown_with_specific_reason(self) -> None:
        context = make_context(
            filename="chat_gpt.jpg",
            physical_type=PhysicalFileType.IMAGE,
            text="abstract chat screenshot with no business document",
            metadata={"ocr_document_like": False},
        )

        classified = classify(context)

        self.assertEqual(classified.semantic_type, DocumentType.UNKNOWN)
        self.assertEqual(
            classified.classification_reason,
            "Image does not appear to contain a business document",
        )

    def test_document_like_ocr_failure_becomes_manual_review_unknown(self) -> None:
        context = make_context(
            filename="unreadable-receipt.jpg",
            physical_type=PhysicalFileType.IMAGE,
            text="RAOH PHA HO!",
            metadata={
                "ocr_document_like": True,
                "ocr_manual_review": True,
            },
        )

        classified = classify(context)

        self.assertEqual(classified.semantic_type, DocumentType.UNKNOWN)
        self.assertEqual(
            classified.classification_reason,
            "Document-like image detected but OCR failed across all engines",
        )

    def test_note_folder_hint_can_classify_ambiguous_document_image(self) -> None:
        context = make_context(
            filename="shoebox/receipts/ambiguous.jpeg",
            physical_type=PhysicalFileType.IMAGE,
            text="handwritten total 27.50 paid",
            metadata={
                "ocr_document_like": True,
                "context_hints": [
                    ContextHint(
                        hint_type="folder_document_type",
                        target="receipts",
                        value="receipt",
                        source_statement=(
                            "receipts of cash purchases are in the receipts/ folder"
                        ),
                    )
                ],
            },
        )

        classified = self.assert_classified_as(context, DocumentType.RECEIPT)

        self.assertIn("note-derived folder hint", classified.classification_reason)

    def test_note_folder_hint_does_not_force_irrelevant_image(self) -> None:
        context = make_context(
            filename="shoebox/receipts/chat_gpt.jpg",
            physical_type=PhysicalFileType.IMAGE,
            text="abstract chat screenshot with no business document",
            metadata={
                "ocr_document_like": False,
                "context_hints": [
                    ContextHint(
                        hint_type="folder_document_type",
                        target="receipts",
                        value="receipt",
                        source_statement=(
                            "receipts of cash purchases are in the receipts/ folder"
                        ),
                    )
                ],
            },
        )

        classified = classify(context)

        self.assertEqual(classified.semantic_type, DocumentType.UNKNOWN)
        self.assertEqual(
            classified.classification_reason,
            "Image does not appear to contain a business document",
        )


if __name__ == "__main__":
    unittest.main()
