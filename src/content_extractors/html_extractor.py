from __future__ import annotations

import html
from html.parser import HTMLParser

from content_extractors.base import BaseContentExtractor
from models.document_context import DocumentContext


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignored_tags = {"script", "style", "noscript"}
        self._ignore_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._ignored_tags:
            self._ignore_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._ignored_tags and self._ignore_depth:
            self._ignore_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignore_depth:
            text = data.strip()
            if text:
                self.parts.append(text)


class HtmlExtractor(BaseContentExtractor):
    def extract(self, context: DocumentContext) -> DocumentContext:
        parser = _VisibleTextParser()

        try:
            parser.feed(
                context.file_info.path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )
        except Exception:
            context.extracted_text = ""
            return context

        context.extracted_text = html.unescape(" ".join(parser.parts))[:4000]
        return context
