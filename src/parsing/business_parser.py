from __future__ import annotations

from parsing.base_parser import BaseBusinessParser
from parsing.invoice_parser import InvoiceParser
from core.enums.document_type import DocumentType
from core.models.business_context import BusinessContext
from core.models.document_context import DocumentContext
from core.models.receipt import Receipt
from core.models.statement_result import StatementResult
from parsing.note_parser import NoteContextParser
from parsing.receipt_parser import ReceiptParser
from parsing.statement_parser import StatementParser
from core.utils.pipeline_logger import pipeline_log


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
            pipeline_log(f"parse skipped: {context.file_info.filename} already parsed")
            return context

        if context.semantic_type is None:
            return context

        parser = self.parsers.get(context.semantic_type)

        if parser is None:
            return context

        pipeline_log(
            "parse: "
            f"{context.file_info.filename} "
            f"semantic_type={context.semantic_type.value}"
        )
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

        pipeline_log(
            "parsed: "
            f"{context.file_info.filename} "
            f"entities={len(context.business_entities)} "
            f"business_context={isinstance(result, BusinessContext)}"
        )

        return context
    def _default_parsers(self) -> dict[DocumentType, BaseBusinessParser]:
        return {
            DocumentType.INVOICE: InvoiceParser(),
            DocumentType.STATEMENT: StatementParser(),
            DocumentType.RECEIPT: ReceiptParser(),
            DocumentType.NOTE: NoteContextParser(),
        }
