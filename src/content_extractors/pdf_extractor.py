from __future__ import annotations

import subprocess

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class PdfExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        try:
            result = subprocess.run(
                [
                    "gs",
                    "-q",
                    "-dNOPAUSE",
                    "-dBATCH",
                    "-dFirstPage=1",
                    "-dLastPage=2",
                    "-sDEVICE=txtwrite",
                    "-sOutputFile=-",
                    str(context.file_info.path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            context.extracted_text = ""
            return context

        if result.returncode != 0:
            context.extracted_text = ""
            return context

        context.extracted_text = result.stdout
        return context
