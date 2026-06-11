from __future__ import annotations

import unittest
from pathlib import Path

from parsing.statement_parser import StatementParser
from core.enums.document_type import DocumentType
from core.enums.physical_file_type import PhysicalFileType
from core.models.document_context import DocumentContext
from core.models.file_info import FileInfo


def make_statement_context(text: str) -> DocumentContext:
    return DocumentContext(
        file_info=FileInfo(
            path=Path("statement.pdf"),
            filename="statement.pdf",
            extension=".pdf",
            size_bytes=len(text.encode("utf-8")),
            sha256="test",
        ),
        physical_type=PhysicalFileType.PDF,
        semantic_type=DocumentType.STATEMENT,
        extracted_text=text,
    )


class StatementParserTests(unittest.TestCase):
    def test_parses_original_txn_id_rows(self) -> None:
        result = StatementParser().parse(
            make_statement_context(
                """
                TXN-0103-001 Jan 03 GOOGLE *WORKSPACE 8.28
                TXN-0214-001 Feb 14 ADOBE *CREATIVE CL -40.00
                """
            )
        )

        self.assertEqual(len(result.transactions), 2)
        self.assertEqual(result.transactions[0].transaction_id, "TXN-0103-001")
        self.assertEqual(result.transactions[1].transaction_type, "refund")

    def test_parses_real_statement_rows_without_txn_ids(self) -> None:
        result = StatementParser().parse(
            make_statement_context(
                """
                Jan 03 GOOGLE *WORKSPACE 8.28
                Jan 06 ADOBE *CREATIVE CL $74.99
                Feb 14 ADOBE *CREATIVE CL -40.00
                """
            )
        )

        self.assertEqual(len(result.transactions), 3)
        self.assertEqual(result.transactions[0].transaction_id, "TXN-JAN03-001")
        self.assertEqual(result.transactions[1].vendor, "ADOBE *CREATIVE CL")
        self.assertEqual(result.transactions[1].amount, 74.99)
        self.assertEqual(result.transactions[2].transaction_type, "refund")

    def test_parses_numeric_date_statement_rows(self) -> None:
        result = StatementParser().parse(
            make_statement_context(
                """
                01/03/2025 GOOGLE *WORKSPACE 8.28
                02/14/2025 ADOBE *CREATIVE CL -40.00
                """
            )
        )

        self.assertEqual(len(result.transactions), 2)
        self.assertEqual(result.transactions[0].date, "01/03/2025")
        self.assertEqual(result.transactions[1].amount, -40.0)

    def test_parses_amount_on_following_line(self) -> None:
        result = StatementParser().parse(
            make_statement_context(
                """
                Jan 03 GOOGLE *WORKSPACE
                8.28
                Jan 06 ADOBE *CREATIVE CL
                $74.99
                """
            )
        )

        self.assertEqual(len(result.transactions), 2)
        self.assertEqual(result.transactions[0].vendor, "GOOGLE *WORKSPACE")
        self.assertEqual(result.transactions[0].amount, 8.28)
        self.assertEqual(result.transactions[1].amount, 74.99)

    def test_trims_statement_summary_fragments_after_transaction(self) -> None:
        result = StatementParser().parse(
            make_statement_context(
                """
                FEB 20 FEB 23 ARAMARK HALL 4 3234 MONTREAL QC $6.38 Credit limit $2,000.00
                FEB 25 FEB 26 RESTAURANR SHAMDOONI MONTREAL QC $52.87 Previous Account Balance $1,092.01
                FEB 26 FEB 27 PATISSERIE COCOBUN-CON MONTREAL QC $9.75 Purchases & debits $1,274.14
                MAR 01 MAR 02 ADONIS 21942 SEVILLE MONTREAL QC $8.99 Total Account Balance $336.15
                """
            )
        )

        self.assertEqual(len(result.transactions), 4)
        self.assertEqual(result.transactions[0].vendor, "ARAMARK HALL 4 3234 MONTREAL QC")
        self.assertEqual(result.transactions[0].amount, 6.38)
        self.assertEqual(result.transactions[1].amount, 52.87)
        self.assertEqual(result.transactions[2].amount, 9.75)
        self.assertEqual(result.transactions[3].amount, 8.99)


if __name__ == "__main__":
    unittest.main()
