from __future__ import annotations

from ingestion.extractors.base import BaseContentExtractor
from core.models.document_context import DocumentContext
from ingestion.ocr.ocr_service import OCRService


class ImageExtractor(BaseContentExtractor):
    """
    Extracts visible image text using local OCR and preprocessing only.
    """

    def __init__(
        self,
        ocr_service: OCRService | None = None,
    ) -> None:
        self.ocr_service = ocr_service or OCRService()

    def extract(self, context: DocumentContext) -> DocumentContext:
        ocr_result = self.ocr_service.extract_text(context.file_info.path)

        context.extracted_text = self._augment_receipt_ocr_terms(
            ocr_result["text"]
        )[:4000]
        context.metadata["ocr_engine"] = ocr_result["engine"]
        context.metadata["ocr_attempt_count"] = ocr_result["ocr_attempts"]
        context.metadata["ocr_engines"] = ocr_result["ocr_engines"]
        context.metadata["ocr_word_count"] = ocr_result["word_count"]
        context.metadata["ocr_character_count"] = ocr_result["character_count"]
        context.metadata["ocr_confidence"] = ocr_result["confidence"]
        context.metadata["ocr_successful_methods"] = ocr_result[
            "successful_methods"
        ]
        context.metadata["ocr_output_word_counts"] = ocr_result[
            "method_word_counts"
        ]
        context.metadata["ocr_text_preview"] = ocr_result["preview"]
        context.metadata["ocr_document_like"] = ocr_result["document_like"]
        context.metadata["ocr_manual_review"] = ocr_result["manual_review"]
        context.metadata["ocr_errors"] = ocr_result["errors"]

        return context

    def _augment_receipt_ocr_terms(self, text: str) -> str:
        normalized_terms = []
        lowercase_text = text.lower()

        term_map = {
            "comptant": "cash",
            "monnaie": "change",
            "merci": "thank you",
            "sous-total": "subtotal",
            "tps": "tax",
            "tvq": "tax",
            "payé": "amount",
            "paye": "amount",
            "reçu": "receipt",
            "recu": "receipt",
        }

        for source_term, normalized_term in term_map.items():
            if source_term in lowercase_text:
                normalized_terms.append(normalized_term)

        if not normalized_terms:
            return text

        return text + "\n" + "\n".join(sorted(set(normalized_terms)))
