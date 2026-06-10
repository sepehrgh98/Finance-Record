from __future__ import annotations

from enums.physical_file_type import PhysicalFileType
from models.document_context import DocumentContext


class FormatDetector:
    """
    Determines how a file should be read based only on its format.

    This node does not infer business meaning. It answers "what extractor should
    handle this file?", not "what kind of business document is this?".
    """

    EXTENSION_MAP = {
        ".pdf": PhysicalFileType.PDF,
        ".xlsx": PhysicalFileType.SPREADSHEET,
        ".xls": PhysicalFileType.SPREADSHEET,
        ".txt": PhysicalFileType.TEXT,
        ".csv": PhysicalFileType.CSV,
        ".html": PhysicalFileType.HTML,
        ".htm": PhysicalFileType.HTML,
        ".jpg": PhysicalFileType.IMAGE,
        ".jpeg": PhysicalFileType.IMAGE,
        ".png": PhysicalFileType.IMAGE,
    }

    def run(self, contexts: list[DocumentContext]) -> list[DocumentContext]:
        for context in contexts:
            context.physical_type = self._detect(context)

        return contexts

    def _detect(self, context: DocumentContext) -> PhysicalFileType:
        return self.EXTENSION_MAP.get(
            context.file_info.extension.lower(),
            PhysicalFileType.UNKNOWN,
        )
