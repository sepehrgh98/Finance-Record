from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class SpreadsheetExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        try:
            with zipfile.ZipFile(context.file_info.path) as workbook:
                shared_strings = self._read_shared_strings(workbook)
                sheet_names = self._read_sheet_names(workbook)
                rows = self._read_sheet_rows(
                    workbook,
                    shared_strings,
                )
        except Exception:
            context.extracted_text = ""
            return context

        preview_parts = ["Sheet names: " + ", ".join(sheet_names)]

        if rows:
            preview_parts.append("Headers: " + " | ".join(rows[0]))
            context.extracted_tables.append(
                {
                    "sheet_name": sheet_names[0] if sheet_names else "",
                    "headers": rows[0],
                    "rows": rows[1:],
                }
            )

        for index, row in enumerate(rows[1:6], start=1):
            preview_parts.append(f"Row {index}: " + " | ".join(row))

        context.extracted_text = "\n".join(preview_parts)
        context.metadata["sheet_names"] = sheet_names

        if rows:
            context.metadata["headers"] = rows[0]

        return context

    def _read_shared_strings(self, workbook: zipfile.ZipFile) -> list[str]:
        try:
            root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
        except KeyError:
            return []

        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        strings: list[str] = []

        for item in root.findall("main:si", namespace):
            text = "".join(
                node.text or ""
                for node in item.findall(".//main:t", namespace)
            )
            strings.append(text)

        return strings

    def _read_sheet_names(self, workbook: zipfile.ZipFile) -> list[str]:
        root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        return [
            sheet.attrib.get("name", "")
            for sheet in root.findall(".//main:sheet", namespace)
            if sheet.attrib.get("name")
        ]

    def _read_sheet_rows(
        self,
        workbook: zipfile.ZipFile,
        shared_strings: list[str],
    ) -> list[list[str]]:
        root = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows: list[list[str]] = []

        for row in root.findall(".//main:row", namespace):
            values: list[str] = []

            for cell in row.findall("main:c", namespace):
                values.append(self._read_cell_value(cell, shared_strings, namespace))

            if any(values):
                rows.append(values)

        return rows

    def _read_cell_value(
        self,
        cell: ElementTree.Element,
        shared_strings: list[str],
        namespace: dict[str, str],
    ) -> str:
        value_node = cell.find("main:v", namespace)

        if value_node is None or value_node.text is None:
            return ""

        value = value_node.text

        if cell.attrib.get("t") == "s":
            try:
                return shared_strings[int(value)]
            except (IndexError, ValueError):
                return ""

        return re.sub(r"\.0$", "", value)
