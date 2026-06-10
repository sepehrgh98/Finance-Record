from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Iterable

from business_entities.invoice import Invoice
from enums.document_type import DocumentType
from enums.physical_file_type import PhysicalFileType
from config.settings import LLM_MODEL, LLM_PROVIDER
from llm.factory import build_llm_client
from models.business_context import BusinessContext
from models.receipt import Receipt
from models.transaction import Transaction
from nodes.business_parser import BusinessParserNode
from nodes.classifier import ClassifierNode
from nodes.content_preview import ContentPreviewExtractor
from nodes.discovery import DiscoveryNode
from reconciliation.reconciliation_engine import ReconciliationEngine
from repositories.report_repository import ReportRepository
from reporting.report_generator import ReportGenerator


class AnalyzeService:
    def analyze_files(
        self,
        uploaded_files,
    ) -> dict:
        with tempfile.TemporaryDirectory(prefix="rpg-analysis-") as temp_dir:
            workspace = Path(temp_dir)
            self._save_uploaded_files(uploaded_files, workspace)
            analysis_result = self._run_pipeline(workspace)
            repository = ReportRepository()

            try:
                report_id = repository.save_report(
                    report=analysis_result["report"],
                    invoices=analysis_result["invoices"],
                    transactions=analysis_result["transactions"],
                    receipts=analysis_result["receipts"],
                    reconciliation_report=analysis_result[
                        "reconciliation_report"
                    ],
                    ignored_files=analysis_result["ignored_files"],
                )
            finally:
                repository.close()

            return {"report_id": report_id}

    def analyze_directory(self, root_dir: str | Path) -> dict:
        return self._run_pipeline(root_dir)["report"]

    def _run_pipeline(self, root_dir: str | Path) -> dict:
        discovery = DiscoveryNode()
        content_extractor = ContentPreviewExtractor()
        classifier = ClassifierNode()
        business_parser = BusinessParserNode()

        contexts = discovery.run(root_dir)
        contexts = content_extractor.run(contexts)
        contexts = classifier.run(contexts)
        self._parse_note_contexts(contexts, business_parser)
        early_business_context = self._merge_business_contexts(contexts)
        self._attach_context_hints(
            contexts,
            early_business_context.context_hints,
        )
        contexts = classifier.run(contexts)
        contexts = business_parser.run(contexts)

        parsed_entities = [
            entity
            for context in contexts
            for entity in context.business_entities
        ]
        invoices = [
            entity
            for entity in parsed_entities
            if isinstance(entity, Invoice)
        ]
        transactions = [
            entity
            for entity in parsed_entities
            if isinstance(entity, Transaction)
        ]
        receipts = [
            entity
            for entity in parsed_entities
            if isinstance(entity, Receipt)
        ]
        business_context = self._merge_business_contexts(contexts)
        ignored_files = self._ignored_files(contexts)

        reconciliation_report = ReconciliationEngine(
            llm_client=build_llm_client(LLM_PROVIDER, LLM_MODEL),
        ).build_report(
            invoices=invoices,
            transactions=transactions,
            receipts=receipts,
            semantic_facts=business_context.semantic_facts,
            context_hints=business_context.context_hints,
        )

        report = ReportGenerator().generate(
            invoices=invoices,
            transactions=transactions,
            receipts=receipts,
            reconciliation_report=reconciliation_report,
            ignored_files=ignored_files,
            files_processed=len(contexts),
        )

        return {
            "report": report.to_dict(),
            "invoices": invoices,
            "transactions": transactions,
            "receipts": receipts,
            "reconciliation_report": reconciliation_report,
            "ignored_files": ignored_files,
        }

    def _save_uploaded_files(
        self,
        uploaded_files,
        workspace: Path,
    ) -> None:
        for index, uploaded_file in enumerate(uploaded_files):
            relative_path = self._safe_relative_path(
                uploaded_file.filename or f"upload-{index}"
            )
            target_path = workspace / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "wb") as output_file:
                uploaded_file.file.seek(0)
                shutil.copyfileobj(uploaded_file.file, output_file)

    def _safe_relative_path(self, filename: str) -> Path:
        parts = [
            part
            for part in Path(filename).parts
            if part not in {"", ".", ".."}
        ]

        if not parts:
            return Path("upload")

        return Path(*parts)

    def _merge_business_contexts(self, contexts: Iterable) -> BusinessContext:
        merged_business_context = BusinessContext()

        for context in contexts:
            business_context = context.metadata.get("business_context")

            if isinstance(business_context, BusinessContext):
                merged_business_context.semantic_facts.extend(
                    business_context.semantic_facts
                )
                merged_business_context.context_hints.extend(
                    business_context.context_hints
                )

        return merged_business_context

    def _parse_note_contexts(
        self,
        contexts: list,
        business_parser: BusinessParserNode,
    ) -> None:
        for context in contexts:
            if context.semantic_type == DocumentType.NOTE:
                business_parser.parse(context)

    def _attach_context_hints(
        self,
        contexts: list,
        context_hints: list,
    ) -> None:
        for context in contexts:
            context.metadata["context_hints"] = context_hints

    def _ignored_files(self, contexts: Iterable) -> list[dict]:
        ignored_files: list[dict] = []

        for context in contexts:
            if context.semantic_type != DocumentType.UNKNOWN:
                continue

            ignored_files.append(
                {
                    "filename": context.file_info.filename,
                    "reason": self._ignored_reason(context),
                    "classification_evidence": context.metadata.get(
                        "classification_evidence",
                        [],
                    ),
                    **self._ocr_diagnostics(context),
                }
            )

        return ignored_files

    def _ignored_reason(self, context) -> str:
        reason = context.classification_reason

        if context.physical_type != PhysicalFileType.IMAGE:
            return reason

        if (
            context.metadata.get("ocr_manual_review")
            and context.metadata.get("ocr_document_like")
        ):
            return "Handwritten or document-like image needs OCR review"

        return reason

    def _ocr_diagnostics(self, context) -> dict:
        if context.physical_type != PhysicalFileType.IMAGE:
            return {}

        return {
            "ocr_attempts": context.metadata.get("ocr_attempt_count", 0),
            "ocr_engines": context.metadata.get("ocr_engines", []),
            "ocr_word_count": context.metadata.get("ocr_word_count", 0),
            "ocr_character_count": context.metadata.get(
                "ocr_character_count",
                0,
            ),
            "ocr_engine": context.metadata.get("ocr_engine", ""),
            "ocr_preview": context.metadata.get("ocr_text_preview", ""),
            "ocr_document_like": context.metadata.get(
                "ocr_document_like",
                False,
            ),
            "ocr_manual_review": context.metadata.get(
                "ocr_manual_review",
                False,
            ),
        }
