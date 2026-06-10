from __future__ import annotations

from content_extractors.base import BaseContentExtractor
from content_extractors.csv_extractor import CsvExtractor
from content_extractors.html_extractor import HtmlExtractor
from content_extractors.image_extractor import ImageExtractor
from content_extractors.pdf_extractor import PdfExtractor
from content_extractors.spreadsheet_extractor import SpreadsheetExtractor
from content_extractors.text_extractor import TextExtractor
from content_extractors.unknown_extractor import UnknownExtractor
from enums.physical_file_type import PhysicalFileType
from models.document_context import DocumentContext


class ContentPreviewExtractor:
    """
    Orchestrates format-specific extractors.

    Add support for a new file format by creating another BaseContentExtractor
    implementation and registering it in the extractor map.
    """

    def __init__(
        self,
        extractors: dict[PhysicalFileType, BaseContentExtractor] | None = None,
    ) -> None:
        self.extractors = extractors or self._default_extractors()
        self.unknown_extractor = UnknownExtractor()

    def run(self, contexts: list[DocumentContext]) -> list[DocumentContext]:
        for context in contexts:
            self.extract(context)

        return contexts

    def extract(self, context: DocumentContext) -> DocumentContext:
        extractor = self.extractors.get(
            context.physical_type,
            self.unknown_extractor,
        )

        try:
            extractor.extract(context)
        except Exception:
            context.extracted_text = ""

        return context

    def _default_extractors(self) -> dict[PhysicalFileType, BaseContentExtractor]:
        return {
            PhysicalFileType.TEXT: TextExtractor(),
            PhysicalFileType.CSV: CsvExtractor(),
            PhysicalFileType.HTML: HtmlExtractor(),
            PhysicalFileType.SPREADSHEET: SpreadsheetExtractor(),
            PhysicalFileType.PDF: PdfExtractor(),
            PhysicalFileType.IMAGE: ImageExtractor(),
        }
