from __future__ import annotations

import csv

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class CsvExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        lines: list[str] = []
        rows: list[list[str]] = []

        try:
            with context.file_info.path.open(
                "r",
                encoding="utf-8",
                errors="ignore",
                newline="",
            ) as f:
                reader = csv.reader(f)
                for index, row in enumerate(reader):
                    if index >= 50:
                        break
                    rows.append(row)
                    lines.append(", ".join(row))
        except Exception:
            context.extracted_text = ""
            return context

        context.extracted_text = "\n".join(lines)

        if rows:
            context.extracted_tables.append(
                {
                    "headers": rows[0],
                    "rows": rows[1:],
                }
            )

        return context
