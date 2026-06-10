from __future__ import annotations

from business_parsers.base_parser import BaseBusinessParser
from business_parsers.invoice_parser import InvoiceParser
from enums.document_type import DocumentType
from models.business_context import BusinessContext
from models.document_context import DocumentContext
from models.receipt import Receipt
from models.statement_result import StatementResult
from business_parsers.note_context_parser import NoteContextParser
from business_parsers.receipt_parser import ReceiptParser
from business_parsers.statement_parser import StatementParser


class BusinessParserNode:
    """
    Runs business parsers for semantically classified document contexts.
    """

    def __init__(
        self,
        parsers: dict[DocumentType, BaseBusinessParser] | None = None,
    ) -> None:
        self.parsers = parsers or self._default_parsers()

    def run(self, contexts: list[DocumentContext]) -> list[DocumentContext]:
        for context in contexts:
            self.parse(context)

        return contexts

    def parse(self, context: DocumentContext) -> DocumentContext:
        if "parser_result" in context.metadata:
            return context

        if context.semantic_type is None:
            return context

        parser = self.parsers.get(context.semantic_type)

        if parser is None:
            return context

        result = parser.parse(context)
        context.metadata["parser_result"] = result

        if isinstance(result, list):
            context.business_entities = result
        elif isinstance(result, StatementResult):
            context.business_entities = result.transactions
        elif isinstance(result, Receipt):
            context.business_entities = [result]
        elif isinstance(result, BusinessContext):
            context.metadata["business_context"] = result

        return context

    def _default_parsers(self) -> dict[DocumentType, BaseBusinessParser]:
        return {
            DocumentType.INVOICE: InvoiceParser(),
            DocumentType.STATEMENT: StatementParser(),
            DocumentType.RECEIPT: ReceiptParser(),
            DocumentType.NOTE: NoteContextParser(),
        }
