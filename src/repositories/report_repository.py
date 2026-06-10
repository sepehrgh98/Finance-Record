from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from sqlalchemy.orm import Session

from business_entities.invoice import Invoice
from db.database import SessionLocal, init_db
from db.models import (
    ActionItemRecord,
    AnnotationRecord,
    BusinessRuleRecord,
    EntityRecord,
    IgnoredFileRecord,
    ReportRecord,
)
from models.receipt import Receipt
from models.transaction import Transaction
from reconciliation.reconciliation_report import ReconciliationReport


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
        )
        self._save_entities(
            report_record.id,
            "transaction",
            transactions,
            entity_lookup,
        )
        self._save_entities(
            report_record.id,
            "receipt",
            receipts,
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

    def _save_entities(
        self,
        report_id: int,
        entity_type: str,
        entities: list,
        entity_lookup: dict[tuple[str, str], list[int]],
    ) -> None:
        for entity in entities:
            entity_name = self._entity_name(entity_type, entity)
            entity_key = self._entity_key(entity_type, entity)
            record = EntityRecord(
                report_id=report_id,
                entity_type=entity_type,
                entity_name=entity_name,
                entity_data_json=json.dumps(self._to_dict(entity)),
            )
            self.db.add(record)
            self.db.flush()
            entity_lookup.setdefault((entity_type, entity_key), []).append(record.id)

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
