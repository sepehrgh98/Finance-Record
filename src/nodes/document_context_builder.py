from __future__ import annotations

from models.document_context import DocumentContext
from models.file_info import FileInfo


class DocumentContextBuilder:
    """
    Creates the initial document state from discovered file metadata.
    """

    def run(self, files: list[FileInfo]) -> list[DocumentContext]:
        return [
            DocumentContext(file_info=file_info)
            for file_info in files
        ]
