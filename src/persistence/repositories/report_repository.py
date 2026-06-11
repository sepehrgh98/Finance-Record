from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from sqlalchemy.orm import Session

from persistence.database import (
    SessionLocal,
    init_db,
    is_readonly_database_error,
    recover_database_connection,
)
from persistence.models import (
    ActionItemRecord,
    AnnotationRecord,
    BusinessRuleRecord,
    EntityRecord,
    IgnoredFileRecord,
    KnowledgeRecord,
    ReportRecord,
)
from knowledge.knowledge import Knowledge
from core.models.invoice import Invoice
from core.models.receipt import Receipt
from core.models.transaction import Transaction
from reconciliation.reconciliation_report import ReconciliationReport
from core.utils.knowledge_payload import sanitize_knowledge


class ReportRepository:
    def __init__(self, db: Session | None = None) -> None:
        init_db()
        self.db = db or SessionLocal()
        self._owns_session = db is None

    def close(self) -> None:
        if self._owns_session:
            self.db.close()

    def save_report(
        self,
        report: dict,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        reconciliation_report: ReconciliationReport,
        ignored_files: list[dict],
        analysis_id: str | None = None,
        knowledge: list[Knowledge] | None = None,
    ) -> int:
        return self._with_readonly_recovery(
            lambda: self._save_report(
                report,
                invoices,
                transactions,
                receipts,
                reconciliation_report,
                ignored_files,
                analysis_id,
                knowledge,
            )
        )

    def _save_report(
        self,
        report: dict,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        reconciliation_report: ReconciliationReport,
        ignored_files: list[dict],
        analysis_id: str | None = None,
        knowledge: list[Knowledge] | None = None,
    ) -> int:
        report_record = ReportRecord(
            report_json=json.dumps(report),
        )
        self.db.add(report_record)
        self.db.flush()

        entity_lookup: dict[tuple[str, str], list[int]] = {}
        self._save_entities(
            report_record.id,
            "invoice",
            invoices,
            entity_lookup,
            reconciliation_report,
        )
        self._save_entities(
            report_record.id,
            "transaction",
            transactions,
            entity_lookup,
            reconciliation_report,
        )
        self._save_entities(
            report_record.id,
            "receipt",
            receipts,
            entity_lookup,
            reconciliation_report,
        )
        self._save_virtual_entities(
            report_record.id,
            reconciliation_report,
            entity_lookup,
        )

        self._save_annotations(
            report_record.id,
            reconciliation_report,
            entity_lookup,
        )
        self._save_action_items(report_record.id, reconciliation_report.action_items)
        self._save_business_rules(report_record.id, reconciliation_report.rules)
        self._save_ignored_files(report_record.id, ignored_files)
        self._attach_or_save_knowledge(
            report_record.id,
            analysis_id,
            knowledge or [],
        )

        self.db.commit()
        return int(report_record.id)

    def get_report(self, report_id: int) -> dict | None:
        record = self.db.get(ReportRecord, report_id)

        if record is None:
            return None

        return json.loads(record.report_json)

    def list_reports(self) -> list[dict]:
        records = (
            self.db.query(ReportRecord)
            .order_by(ReportRecord.created_at.desc())
            .all()
        )

        return [
            {
                "id": record.id,
                "created_at": record.created_at.isoformat(),
            }
            for record in records
        ]

    def get_entities_for_report(self, report_id: int) -> list[dict]:
        records = (
            self.db.query(EntityRecord)
            .filter(EntityRecord.report_id == report_id)
            .order_by(EntityRecord.entity_type, EntityRecord.entity_name)
            .all()
        )

        return [
            {
                "id": record.id,
                "entity_type": record.entity_type,
                "entity_name": record.entity_name,
                "data": json.loads(record.entity_data_json),
            }
            for record in records
        ]

    def get_entity(self, entity_id: int) -> dict | None:
        record = self.db.get(EntityRecord, entity_id)

        if record is None:
            return None

        entity = json.loads(record.entity_data_json)
        annotations = [
            annotation.note
            for annotation in (
                self.db.query(AnnotationRecord)
                .filter(AnnotationRecord.entity_id == entity_id)
                .order_by(AnnotationRecord.id)
                .all()
            )
        ]

        return {
            "entity": {
                "id": record.id,
                "entity_type": record.entity_type,
                "entity_name": record.entity_name,
                "data": entity,
            },
            "annotations": annotations,
            "action_items": self._related_action_items(record),
        }

    def save_knowledge_for_analysis(
        self,
        analysis_id: str,
        knowledge: list[Knowledge],
    ) -> None:
        self._with_readonly_recovery(
            lambda: self._save_knowledge_for_analysis(analysis_id, knowledge)
        )

    def _save_knowledge_for_analysis(
        self,
        analysis_id: str,
        knowledge: list[Knowledge],
    ) -> None:
        existing = (
            self.db.query(KnowledgeRecord)
            .filter(KnowledgeRecord.analysis_id == analysis_id)
            .all()
        )

        for record in existing:
            self.db.delete(record)

        for item in knowledge:
            sanitized = self._sanitized_knowledge(item)

            if sanitized is None:
                continue

            self.db.add(
                KnowledgeRecord(
                    analysis_id=analysis_id,
                    knowledge_type=sanitized.knowledge_type,
                    statement=sanitized.statement,
                    confidence=sanitized.confidence,
                    payload_json=json.dumps(sanitized.payload),
                )
            )

        self.db.commit()

    def _with_readonly_recovery(self, operation):
        try:
            return operation()
        except Exception as error:
            if not is_readonly_database_error(error):
                raise

            self._recover_session()
            return operation()

    def _recover_session(self) -> None:
        self.db.rollback()

        if self._owns_session:
            self.db.close()

        recover_database_connection()

        if self._owns_session:
            self.db = SessionLocal()

    def get_knowledge_for_analysis(self, analysis_id: str) -> list[Knowledge]:
        records = (
            self.db.query(KnowledgeRecord)
            .filter(KnowledgeRecord.analysis_id == analysis_id)
            .order_by(KnowledgeRecord.id)
            .all()
        )
        return [self._knowledge_from_record(record) for record in records]

    def get_knowledge_for_report(self, report_id: int) -> list[Knowledge]:
        records = (
            self.db.query(KnowledgeRecord)
            .filter(KnowledgeRecord.report_id == report_id)
            .order_by(KnowledgeRecord.id)
            .all()
        )
        return [self._knowledge_from_record(record) for record in records]

    def _save_entities(
        self,
        report_id: int,
        entity_type: str,
        entities: list,
        entity_lookup: dict[tuple[str, str], list[int]],
        reconciliation_report: ReconciliationReport,
    ) -> None:
        enrichments_by_key = self._entity_enrichments_by_key(
            reconciliation_report,
        )

        for entity in entities:
            entity_name = self._entity_name(entity_type, entity)
            entity_key = self._entity_key(entity_type, entity)
            data = self._to_dict(entity)
            data["document_available"] = True
            data["knowledge_enrichment"] = enrichments_by_key.get(
                (entity_type, entity_key),
                [],
            )
            record = EntityRecord(
                report_id=report_id,
                entity_type=entity_type,
                entity_name=entity_name,
                entity_data_json=json.dumps(data),
            )
            self.db.add(record)
            self.db.flush()
            entity_lookup.setdefault((entity_type, entity_key), []).append(record.id)

    def _save_virtual_entities(
        self,
        report_id: int,
        reconciliation_report: ReconciliationReport,
        entity_lookup: dict[tuple[str, str], list[int]],
    ) -> None:
        seen: set[tuple[str, str]] = set()

        for virtual_entity in reconciliation_report.virtual_entities:
            key = (virtual_entity.entity_type, virtual_entity.entity_id)

            if key in seen:
                continue

            seen.add(key)
            data = dict(virtual_entity.data)
            data["document_available"] = False
            data.setdefault("missing_document", True)
            record = EntityRecord(
                report_id=report_id,
                entity_type=virtual_entity.entity_type,
                entity_name=virtual_entity.entity_name,
                entity_data_json=json.dumps(data),
            )
            self.db.add(record)
            self.db.flush()
            entity_lookup.setdefault(key, []).append(record.id)

    def _save_annotations(
        self,
        report_id: int,
        reconciliation_report: ReconciliationReport,
        entity_lookup: dict[tuple[str, str], list[int]],
    ) -> None:
        seen: set[tuple[int, str]] = set()

        for annotation in reconciliation_report.annotations:
            entity_ids = entity_lookup.get(
                (annotation.entity_type, annotation.entity_id),
                [],
            )

            for entity_id in entity_ids:
                key = (entity_id, annotation.note)

                if key in seen:
                    continue

                seen.add(key)
                self.db.add(
                    AnnotationRecord(
                        report_id=report_id,
                        entity_id=entity_id,
                        note=annotation.note,
                    )
                )

    def _save_action_items(self, report_id: int, action_items: list[str]) -> None:
        for text in action_items:
            self.db.add(ActionItemRecord(report_id=report_id, text=text))

    def _save_business_rules(self, report_id: int, rules: list[str]) -> None:
        for text in rules:
            self.db.add(BusinessRuleRecord(report_id=report_id, text=text))

    def _save_ignored_files(self, report_id: int, ignored_files: list[dict]) -> None:
        for ignored_file in ignored_files:
            self.db.add(
                IgnoredFileRecord(
                    report_id=report_id,
                    filename=ignored_file.get("filename", ""),
                    reason=ignored_file.get("reason", ""),
                )
            )

    def _attach_or_save_knowledge(
        self,
        report_id: int,
        analysis_id: str | None,
        knowledge: list[Knowledge],
    ) -> None:
        attached = False

        if analysis_id:
            updated = (
                self.db.query(KnowledgeRecord)
                .filter(KnowledgeRecord.analysis_id == analysis_id)
                .update({KnowledgeRecord.report_id: report_id})
            )
            attached = bool(updated)

        if attached:
            return

        for item in knowledge:
            sanitized = self._sanitized_knowledge(item)

            if sanitized is None:
                continue

            self.db.add(
                KnowledgeRecord(
                    report_id=report_id,
                    analysis_id=analysis_id,
                    knowledge_type=sanitized.knowledge_type,
                    statement=sanitized.statement,
                    confidence=sanitized.confidence,
                    payload_json=json.dumps(sanitized.payload),
                )
            )

    def _related_action_items(self, entity_record: EntityRecord) -> list[str]:
        action_items = (
            self.db.query(ActionItemRecord)
            .filter(ActionItemRecord.report_id == entity_record.report_id)
            .order_by(ActionItemRecord.id)
            .all()
        )
        normalized_name = entity_record.entity_name.lower()

        return [
            action_item.text
            for action_item in action_items
            if normalized_name
            and (
                normalized_name in action_item.text.lower()
                or any(
                    token in action_item.text.lower()
                    for token in normalized_name.split()
                    if len(token) >= 4
                )
            )
        ]

    def _entity_enrichments_by_key(
        self,
        reconciliation_report: ReconciliationReport,
    ) -> dict[tuple[str, str], list[dict]]:
        grouped: dict[tuple[str, str], list[dict]] = {}
        seen: set[tuple[str, str, str]] = set()

        for enrichment in reconciliation_report.entity_enrichments:
            key = (enrichment.entity_type, enrichment.entity_id)
            seen_key = (
                enrichment.entity_type,
                enrichment.entity_id,
                enrichment.statement,
            )

            if seen_key in seen:
                continue

            seen.add(seen_key)
            grouped.setdefault(key, []).append(
                {
                    "knowledge_type": enrichment.knowledge_type,
                    "statement": enrichment.statement,
                    "payload": enrichment.payload,
                }
            )

        return grouped

    def _entity_name(self, entity_type: str, entity: object) -> str:
        if entity_type == "invoice":
            return entity.client or entity.description or "invoice"

        if entity_type == "transaction":
            return entity.vendor or "transaction"

        if entity_type == "receipt":
            return entity.merchant or "receipt"

        return entity_type

    def _entity_key(self, entity_type: str, entity: object) -> str:
        if entity_type == "invoice":
            return entity.invoice_id or entity.client or entity.description or "invoice"

        if entity_type == "transaction":
            return entity.transaction_id or entity.vendor or "transaction"

        if entity_type == "receipt":
            return " | ".join(
                value
                for value in [entity.merchant, entity.date]
                if value
            ) or "receipt"

        return self._entity_name(entity_type, entity)

    def _to_dict(self, value: Any) -> dict:
        if is_dataclass(value):
            return asdict(value)

        if isinstance(value, dict):
            return value

        return dict(value)

    def _knowledge_from_record(self, record: KnowledgeRecord) -> Knowledge:
        knowledge_type, payload = sanitize_knowledge(
            record.knowledge_type,
            json.loads(record.payload_json or "{}"),
            record.statement,
        )

        if knowledge_type is None:
            knowledge_type = "ignore"
            payload = {}

        return Knowledge(
            knowledge_type=knowledge_type,
            statement=record.statement,
            confidence=record.confidence,
            payload=payload,
        )

    def _sanitized_knowledge(self, knowledge: Knowledge) -> Knowledge | None:
        knowledge_type, payload = sanitize_knowledge(
            knowledge.knowledge_type,
            knowledge.payload,
            knowledge.statement,
        )

        if knowledge_type is None:
            return None

        return Knowledge(
            knowledge_type=knowledge_type,
            statement=knowledge.statement,
            confidence=knowledge.confidence,
            payload=payload,
        )
