from __future__ import annotations

from ingestion.extractors.base import BaseContentExtractor
from ingestion.extractors.csv_extractor import CsvExtractor
from ingestion.extractors.html_extractor import HtmlExtractor
from ingestion.extractors.image_extractor import ImageExtractor
from ingestion.extractors.pdf_extractor import PdfExtractor
from ingestion.extractors.spreadsheet_extractor import SpreadsheetExtractor
from ingestion.extractors.text_extractor import TextExtractor
from ingestion.extractors.unknown_extractor import UnknownExtractor
from core.enums.physical_file_type import PhysicalFileType
from core.models.document_context import DocumentContext
from core.utils.pipeline_logger import pipeline_log


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
        pipeline_log(
            "extract: "
            f"{context.file_info.filename} "
            f"physical_type={getattr(context.physical_type, 'value', context.physical_type)}"
        )

        try:
            extractor.extract(context)
            pipeline_log(
                "extracted: "
                f"{context.file_info.filename} "
                f"text_chars={len(context.extracted_text or '')} "
                f"tables={len(context.extracted_tables)}"
            )
        except Exception as exc:
            context.extracted_text = ""
            pipeline_log(f"extract failed: {context.file_info.filename}: {exc}")

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
