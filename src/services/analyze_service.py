from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from core.enums.document_type import DocumentType
from core.enums.physical_file_type import PhysicalFileType
from knowledge.knowledge_store import KnowledgeStore
from core.models.business_context import BusinessContext
from core.models.invoice import Invoice
from core.models.receipt import Receipt
from core.models.transaction import Transaction
from parsing.business_parser import BusinessParserNode
from classification.classifier import ClassifierNode
from ingestion.extractors.content_preview import ContentPreviewExtractor
from ingestion.discovery.discovery import DiscoveryNode
from reconciliation.reconciliation_engine import ReconciliationEngine
from persistence.repositories.report_repository import ReportRepository
from reporting.report_generator import ReportGenerator
from core.utils.pipeline_logger import pipeline_log


class AnalyzeService:
    def analyze_files(
        self,
        uploaded_files,
        analysis_id: str | None = None,
        progress_callback: Callable[[int, str, str], None] | None = None,
    ) -> dict:
        with tempfile.TemporaryDirectory(prefix="rpg-analysis-") as temp_dir:
            workspace = Path(temp_dir)
            analysis_id = analysis_id or uuid4().hex
            self._emit_progress(
                progress_callback,
                2,
                "Saving uploaded files",
            )
            pipeline_log("saving uploaded files")
            self._save_uploaded_files(uploaded_files, workspace)
            pipeline_log(f"uploaded files saved to {workspace}")
            self._emit_progress(
                progress_callback,
                8,
                "Uploaded files saved",
                str(workspace),
            )
            analysis_result = self._run_pipeline(
                workspace,
                analysis_id=analysis_id,
                progress_callback=progress_callback,
            )
            repository = ReportRepository()

            try:
                self._emit_progress(
                    progress_callback,
                    96,
                    "Saving report",
                    "Writing report and entities to SQLite",
                )
                pipeline_log("saving report to SQLite")
                report_id = repository.save_report(
                    report=analysis_result["report"],
                    invoices=analysis_result["invoices"],
                    transactions=analysis_result["transactions"],
                    receipts=analysis_result["receipts"],
                    reconciliation_report=analysis_result[
                        "reconciliation_report"
                    ],
                    ignored_files=analysis_result["ignored_files"],
                    analysis_id=analysis_result["analysis_id"],
                    knowledge=analysis_result["knowledge"],
                )
                pipeline_log(f"report saved with id={report_id}")
                self._emit_progress(
                    progress_callback,
                    98,
                    "Report saved",
                    f"Report #{report_id}",
                )
            finally:
                repository.close()

            return {"report_id": report_id}

    def analyze_directory(self, root_dir: str | Path) -> dict:
        return self._run_pipeline(root_dir, analysis_id=uuid4().hex)["report"]

    def _run_pipeline(
        self,
        root_dir: str | Path,
        analysis_id: str,
        progress_callback: Callable[[int, str, str], None] | None = None,
    ) -> dict:
        pipeline_log(f"analysis started: {root_dir}")
        discovery = DiscoveryNode()
        content_extractor = ContentPreviewExtractor()
        classifier = ClassifierNode()
        business_parser = BusinessParserNode()

        pipeline_log("node: discovery + physical type detection")
        self._emit_progress(
            progress_callback,
            10,
            "Discovering files",
        )
        contexts = discovery.run(root_dir)
        pipeline_log(f"discovered {len(contexts)} files")
        self._emit_progress(
            progress_callback,
            14,
            "Files discovered",
            f"{len(contexts)} files",
        )

        pipeline_log("node: content extraction / OCR")
        for index, context in enumerate(contexts, start=1):
            percent = self._scaled_progress(index - 1, len(contexts), 15, 50)
            self._emit_progress(
                progress_callback,
                percent,
                "Extracting document content",
                context.file_info.filename,
            )
            content_extractor.extract(context)
        self._emit_progress(
            progress_callback,
            50,
            "Document content extracted",
            f"{len(contexts)} files",
        )

        pipeline_log("node: initial classification")
        for index, context in enumerate(contexts, start=1):
            percent = self._scaled_progress(index - 1, len(contexts), 51, 62)
            self._emit_progress(
                progress_callback,
                percent,
                "Classifying documents",
                context.file_info.filename,
            )
            classifier._classify_context(context)
        self._emit_progress(
            progress_callback,
            62,
            "Documents classified",
        )

        pipeline_log("node: note knowledge extraction")
        self._emit_progress(
            progress_callback,
            64,
            "Understanding notes",
        )
        self._parse_note_contexts(
            contexts,
            business_parser,
            progress_callback,
        )
        early_business_context = self._merge_business_contexts(contexts)
        pipeline_log(
            "note knowledge objects: "
            f"{len(early_business_context.knowledge)}"
        )
        self._persist_analysis_knowledge(
            analysis_id,
            early_business_context.knowledge,
        )
        self._store_business_context_on_note_contexts(
            contexts,
            early_business_context,
        )
        self._apply_pre_parse_knowledge(
            contexts,
            early_business_context,
        )
        self._emit_progress(
            progress_callback,
            74,
            "Notes understood",
            f"{len(early_business_context.knowledge)} knowledge objects",
        )

        pipeline_log("node: business parsing")
        for index, context in enumerate(contexts, start=1):
            percent = self._scaled_progress(index - 1, len(contexts), 75, 84)
            self._emit_progress(
                progress_callback,
                percent,
                "Parsing business entities",
                context.file_info.filename,
            )
            business_parser.parse(context)
        self._emit_progress(
            progress_callback,
            84,
            "Business entities parsed",
        )

        knowledge_store = KnowledgeStore(analysis_id=analysis_id)
        reconciliation_engine = ReconciliationEngine()

        pipeline_log("node: reconciliation knowledge review")
        self._emit_progress(
            progress_callback,
            86,
            "Reconciling note knowledge",
        )
        contexts = reconciliation_engine.apply_knowledge_review(
            contexts=contexts,
            knowledge_store=knowledge_store,
            business_parser=business_parser,
        )

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
        pipeline_log(
            "parsed entities: "
            f"invoices={len(invoices)}, "
            f"transactions={len(transactions)}, "
            f"receipts={len(receipts)}, "
            f"ignored={len(ignored_files)}"
        )

        pipeline_log("node: reconciliation + review items")
        self._emit_progress(
            progress_callback,
            90,
            "Building review items",
        )
        reconciliation_report = reconciliation_engine.build_report(
            invoices=invoices,
            transactions=transactions,
            receipts=receipts,
            knowledge_store=knowledge_store,
            extra_rules=business_context.business_rules,
        )
        pipeline_log(
            "reconciliation output: "
            f"annotations={len(reconciliation_report.annotations)}, "
            f"review_items={len(reconciliation_report.findings)}, "
            f"action_items={len(reconciliation_report.action_items)}, "
            f"rules={len(reconciliation_report.rules)}"
        )

        pipeline_log("node: report generation")
        self._emit_progress(
            progress_callback,
            94,
            "Generating report",
        )
        report = ReportGenerator().generate(
            invoices=invoices,
            transactions=transactions,
            receipts=receipts,
            reconciliation_report=reconciliation_report,
            ignored_files=ignored_files,
            files_processed=len(contexts),
        )
        pipeline_log("analysis complete")

        return {
            "report": report.to_dict(),
            "invoices": invoices,
            "transactions": transactions,
            "receipts": receipts,
            "reconciliation_report": reconciliation_report,
            "ignored_files": ignored_files,
            "analysis_id": analysis_id,
            "knowledge": business_context.knowledge,
        }

    def _emit_progress(
        self,
        progress_callback: Callable[[int, str, str], None] | None,
        percent: int,
        message: str,
        detail: str = "",
    ) -> None:
        if progress_callback is None:
            return

        progress_callback(percent, message, detail)

    def _scaled_progress(
        self,
        current_index: int,
        total: int,
        start: int,
        end: int,
    ) -> int:
        if total <= 0:
            return start

        return start + int(((end - start) * current_index) / total)

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
            pipeline_log(f"save upload: {relative_path}")

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
                merged_business_context.knowledge.extend(
                    business_context.knowledge
                )
                merged_business_context.business_rules.extend(
                    business_context.business_rules
                )
                merged_business_context.manual_review_notes.extend(
                    business_context.manual_review_notes
                )
                merged_business_context.suggested_updates.extend(
                    business_context.suggested_updates
                )

        return merged_business_context

    def _parse_note_contexts(
        self,
        contexts: list,
        business_parser: BusinessParserNode,
        progress_callback: Callable[[int, str, str], None] | None = None,
    ) -> None:
        for context in contexts:
            if context.semantic_type == DocumentType.NOTE:
                context.metadata["progress_callback"] = progress_callback
                business_parser.parse(context)
                context.metadata.pop("progress_callback", None)

    def _persist_analysis_knowledge(
        self,
        analysis_id: str,
        knowledge: list,
    ) -> None:
        repository = ReportRepository()

        try:
            repository.save_knowledge_for_analysis(analysis_id, knowledge)
            pipeline_log(
                "persisted knowledge objects: "
                f"{len(knowledge)} analysis_id={analysis_id}"
            )
        finally:
            repository.close()

    def _store_business_context_on_note_contexts(
        self,
        contexts: list,
        business_context: BusinessContext,
    ) -> None:
        first_note_context_seen = False

        for context in contexts:
            if context.semantic_type != DocumentType.NOTE:
                continue

            if first_note_context_seen:
                context.metadata["business_context"] = BusinessContext()
                continue

            context.metadata["business_context"] = business_context
            first_note_context_seen = True

    def _apply_pre_parse_knowledge(
        self,
        contexts: list,
        business_context: BusinessContext,
    ) -> None:
        for knowledge in business_context.knowledge:
            if knowledge.knowledge_type != "document_type_context":
                continue

            payload = knowledge.payload
            document_type = str(payload.get("document_type") or "").lower()
            folder = str(payload.get("folder") or "").strip("/").lower()
            statement = knowledge.statement.lower()

            if document_type != "receipt" or not folder:
                continue

            if "cash" not in statement and "cash" not in str(payload).lower():
                continue

            for context in contexts:
                if context.semantic_type != DocumentType.RECEIPT:
                    continue

                path_parts = {
                    part.lower()
                    for part in context.file_info.path.parts
                }

                if folder not in path_parts:
                    continue

                normalized_text = context.extracted_text.lower()

                if "cash" in normalized_text or "comptant" in normalized_text:
                    continue

                context.extracted_text = f"{context.extracted_text}\ncash"
                context.metadata["payment_method_from_knowledge"] = True

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
