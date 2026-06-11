from __future__ import annotations

from dataclasses import fields, is_dataclass
import re
from typing import Any

from core.enums.document_type import DocumentType
from core.enums.physical_file_type import PhysicalFileType
from knowledge.knowledge_store import KnowledgeStore
from core.models.document_context import DocumentContext
from knowledge.knowledge import Knowledge
from core.models.invoice import Invoice
from core.models.receipt import Receipt
from core.models.transaction import Transaction
from reconciliation.reconciliation_report import (
    Annotation,
    EntityEnrichment,
    Finding,
    ReconciliationReport,
    VirtualEntity,
)
from core.utils.pipeline_logger import pipeline_log


class ReconciliationEngine:
    GENERIC_ENTITY_TOKENS = {
        "account",
        "amount",
        "business",
        "card",
        "charge",
        "client",
        "date",
        "expense",
        "home",
        "invoice",
        "office",
        "paid",
        "payment",
        "plan",
        "refund",
        "registration",
        "transaction",
    }

    def apply_knowledge_review(
        self,
        contexts: list[DocumentContext],
        knowledge_store: KnowledgeStore,
        business_parser,
    ) -> list[DocumentContext]:
        pipeline_log(
            "knowledge review start: "
            f"contexts={len(contexts)}, knowledge={len(knowledge_store.all())}"
        )
        self._apply_document_type_context(
            contexts,
            knowledge_store,
            business_parser,
        )
        self._apply_document_applicability(contexts, knowledge_store)
        return contexts

    def build_report(
        self,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        knowledge_store: KnowledgeStore | None = None,
        extra_rules: list[str] | None = None,
    ) -> ReconciliationReport:
        report = ReconciliationReport()
        knowledge_store = knowledge_store or KnowledgeStore()
        extra_rules = extra_rules or []
        seen_rules: set[str] = set()
        pipeline_log(
            "reconciliation start: "
            f"invoices={len(invoices)}, "
            f"transactions={len(transactions)}, "
            f"receipts={len(receipts)}, "
            f"knowledge={len(knowledge_store.all())}"
        )

        for knowledge in knowledge_store.announcements():
            self._append_unique(report.action_items, knowledge.statement)

        for knowledge in knowledge_store.all():
            if self._is_actionable_unmatched_note(knowledge):
                self._append_unique(report.action_items, knowledge.statement)

        for knowledge in knowledge_store.by_type("document_type_context"):
            if knowledge.statement not in seen_rules:
                seen_rules.add(knowledge.statement)
                report.rules.append(knowledge.statement)

        for knowledge in knowledge_store.by_type("document_availability"):
            report.virtual_entities.extend(
                self._virtual_entities_for_knowledge(knowledge)
            )

        for knowledge in knowledge_store.financial_context():
            annotations = self._annotations_for_knowledge(
                knowledge,
                invoices,
                transactions,
                receipts,
            )
            report.annotations.extend(annotations)
            report.entity_enrichments.extend(
                self._enrichments_for_knowledge(knowledge, annotations)
            )

        for rule in extra_rules:
            if rule not in seen_rules:
                seen_rules.add(rule)
                report.rules.append(rule)

        report.findings = self._deduplicate_findings(
            self._findings_for_knowledge(
                invoices,
                transactions,
                receipts,
                knowledge_store,
            )
        )
        return report

    def _apply_document_type_context(
        self,
        contexts: list[DocumentContext],
        knowledge_store: KnowledgeStore,
        business_parser,
    ) -> None:
        for context in contexts:
            matching_knowledge = [
                knowledge
                for knowledge in knowledge_store.document_type_context_for_path(
                    context.file_info.path
                )
                if self._document_type_knowledge_can_apply(context, knowledge)
            ]

            if not matching_knowledge:
                continue

            knowledge = matching_knowledge[0]
            document_type = self._document_type_from_knowledge(knowledge)

            if document_type is None:
                continue

            classification_changed = context.semantic_type != document_type

            if classification_changed:
                context.metadata["knowledge_review_original_semantic_type"] = (
                    context.semantic_type.value
                    if context.semantic_type
                    else ""
                )
                context.semantic_type = document_type
                context.classification_score = max(
                    context.classification_score,
                    0.3,
                )
                context.classification_reason = (
                    "Reconciled with note-derived document knowledge: "
                    f"{knowledge.statement}"
                )
                context.metadata["classification_evidence"] = [
                    *context.metadata.get("classification_evidence", []),
                    f"Knowledge statement: {knowledge.statement}",
                ]
                context.metadata.pop("parser_result", None)
                context.business_entities = []
                pipeline_log(
                    "knowledge review reclassified: "
                    f"{context.file_info.filename} -> {document_type.value}"
                )

            if (
                classification_changed
                or "parser_result" not in context.metadata
            ):
                business_parser.parse(context)

    def _apply_document_applicability(
        self,
        contexts: list[DocumentContext],
        knowledge_store: KnowledgeStore,
    ) -> None:
        for knowledge in knowledge_store.by_type("document_applicability"):
            if knowledge.payload.get("applicable") is not False:
                continue

            for context in contexts:
                if not self._applicability_knowledge_matches_context(
                    knowledge,
                    context,
                ):
                    continue

                context.metadata["excluded_by_knowledge"] = True
                context.metadata["excluded_by_knowledge_statement"] = (
                    knowledge.statement
                )
                context.metadata["parser_result"] = []
                context.business_entities = []
                pipeline_log(
                    "knowledge review excluded: "
                    f"{context.file_info.filename} "
                    f"statement={knowledge.statement[:100]}"
                )

    def _document_type_knowledge_can_apply(
        self,
        context: DocumentContext,
        knowledge: Knowledge,
    ) -> bool:
        if context.semantic_type == DocumentType.NOTE:
            return False

        if context.physical_type != PhysicalFileType.IMAGE:
            return True

        if context.metadata.get("ocr_manual_review"):
            return False

        return bool(context.metadata.get("ocr_document_like"))

    def _document_type_from_knowledge(
        self,
        knowledge: Knowledge,
    ) -> DocumentType | None:
        value = str(knowledge.payload.get("document_type") or "").strip()

        try:
            return DocumentType(value)
        except ValueError:
            return None

    def _applicability_knowledge_matches_context(
        self,
        knowledge: Knowledge,
        context: DocumentContext,
    ) -> bool:
        targets = self._knowledge_target_terms(knowledge)

        if not targets:
            return False

        path_text = self._normalize("/".join(context.file_info.path.parts))
        semantic_type = (
            context.semantic_type.value
            if context.semantic_type is not None
            else ""
        )
        entity_text = self._normalize(
            " ".join(
                value
                for entity in context.business_entities
                for value in self._entity_values(entity)
            )
        )

        return any(
            target in path_text
            or target == self._normalize(context.file_info.filename)
            or target == self._normalize(semantic_type)
            or target in entity_text
            for target in targets
        )

    def _knowledge_target_terms(self, knowledge: Knowledge) -> list[str]:
        target_keys = (
            "target",
            "filename",
            "folder",
            "document_type",
            "merchant",
            "vendor",
            "customer",
            "client",
            "entity",
        )
        targets: list[str] = []

        for key in target_keys:
            value = knowledge.payload.get(key)

            if value is not None and str(value).strip():
                targets.append(self._normalize(value))

        payload_entities = knowledge.payload.get("entities")

        if isinstance(payload_entities, list):
            targets.extend(
                self._normalize(entity)
                for entity in payload_entities
                if str(entity).strip()
            )

        return [
            target
            for target in targets
            if target
        ]

    def _findings_for_knowledge(
        self,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        knowledge_store: KnowledgeStore | None = None,
    ) -> list[Finding]:
        knowledge_store = knowledge_store or KnowledgeStore()
        return self._deterministic_findings_for_knowledge(
            knowledge_store.financial_context(),
            invoices,
            transactions,
            receipts,
        )

    def _append_unique(self, values: list[str], value: str) -> None:
        if value and value not in values:
            values.append(value)

    def _virtual_entities_for_knowledge(
        self,
        knowledge: Knowledge,
    ) -> list[VirtualEntity]:
        payload = dict(knowledge.payload)
        status = self._normalize(payload.get("status"))
        text = self._normalize(knowledge.statement)

        if status not in {"missing", "lost", "unavailable", "destroyed", "invalid"}:
            if not any(
                term in text
                for term in ("missing", "lost", "unavailable", "destroyed")
            ):
                return []

        entity_type = self._virtual_entity_type(payload)
        entity_name = self._virtual_entity_name(payload, entity_type)
        entity_id = self._safe_snake_case(
            f"virtual {entity_type} {entity_name}"
        )
        data = {
            **payload,
            "document_available": False,
            "missing_document": True,
            "source": "knowledge",
            "source_statement": knowledge.statement,
        }

        return [
            VirtualEntity(
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                data=data,
            )
        ]

    def _virtual_entity_type(self, payload: dict) -> str:
        document_type = self._normalize(payload.get("document_type"))

        if document_type in {"invoice", "receipt", "statement"}:
            return document_type

        if payload.get("merchant") or payload.get("vendor"):
            return "receipt"

        if payload.get("customer") or payload.get("client"):
            return "invoice"

        return document_type or "document"

    def _virtual_entity_name(self, payload: dict, entity_type: str) -> str:
        for key in (
            "merchant",
            "vendor",
            "customer",
            "client",
            "entity",
            "target",
            "filename",
        ):
            value = payload.get(key)

            if value is not None and str(value).strip():
                return str(value).strip()

        return f"missing {entity_type}"

    def _enrichments_for_knowledge(
        self,
        knowledge: Knowledge,
        annotations: list[Annotation],
    ) -> list[EntityEnrichment]:
        return [
            EntityEnrichment(
                entity_type=annotation.entity_type,
                entity_id=annotation.entity_id,
                entity_name=annotation.entity_name,
                knowledge_type=knowledge.knowledge_type,
                statement=knowledge.statement,
                payload=dict(knowledge.payload),
            )
            for annotation in annotations
        ]

    def _deduplicate_findings(self, findings: list[Finding]) -> list[Finding]:
        deduplicated: list[Finding] = []
        seen: set[tuple[str, str | None, str]] = set()

        for finding in findings:
            key = (
                finding.finding_type,
                finding.entity_id,
                "|".join(finding.evidence),
            )

            if key in seen:
                continue

            seen.add(key)
            deduplicated.append(finding)

        return deduplicated

    def _entities_from_knowledge(self, knowledge: Knowledge) -> list[str]:
        entities: list[str] = []
        payload_entities = knowledge.payload.get("entities")

        if isinstance(payload_entities, list):
            entities.extend(
                str(entity).strip()
                for entity in payload_entities
                if str(entity).strip()
            )

        for key in (
            "merchant",
            "customer",
            "vendor",
            "target",
            "invoice_reference",
            "amount",
            "date",
        ):
            value = knowledge.payload.get(key)

            if value is not None and str(value).strip():
                entities.append(str(value).strip())

        deduplicated: list[str] = []
        seen: set[str] = set()

        for entity in entities:
            normalized = self._normalize(entity)

            if normalized in seen:
                continue

            seen.add(normalized)
            deduplicated.append(entity)

        return deduplicated

    def _deterministic_findings_for_knowledge(
        self,
        knowledge_items: list[Knowledge],
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
    ) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple[str, str | None, str]] = set()
        refund_transaction_ids = {
            self._transaction_id(transaction)
            for transaction in transactions
            if (transaction.amount or 0.0) < 0.0
            or transaction.transaction_type == "refund"
        }

        for knowledge in knowledge_items:
            matched_annotations = self._annotations_for_knowledge(
                knowledge,
                invoices,
                transactions,
                receipts,
            )
            candidate_findings = self._deterministic_findings_for_single_knowledge(
                knowledge,
                matched_annotations,
                refund_transaction_ids,
            )

            if not candidate_findings:
                continue

            for finding in candidate_findings:
                key = (
                    finding.finding_type,
                    finding.entity_id,
                    "|".join(finding.evidence),
                )

                if key in seen:
                    continue

                seen.add(key)
                findings.append(finding)

        return findings

    def _deterministic_findings_for_single_knowledge(
        self,
        knowledge: Knowledge,
        matched_annotations: list[Annotation],
        refund_transaction_ids: set[str],
    ) -> list[Finding]:
        return [
            *self._personal_expense_findings(knowledge, matched_annotations),
            *self._invoice_follow_up_findings(knowledge, matched_annotations),
            *self._refund_context_findings(
                knowledge,
                matched_annotations,
                refund_transaction_ids,
            ),
            *self._sales_opportunity_findings(knowledge, matched_annotations),
            *self._admin_action_findings(knowledge, matched_annotations),
        ]

    def _annotations_for_knowledge(
        self,
        knowledge: Knowledge,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
    ) -> list[Annotation]:
        annotations: list[Annotation] = []
        entities = self._entities_from_knowledge(knowledge)

        for invoice in invoices:
            if self._matches_entity(invoice, entities, knowledge.statement):
                annotations.append(
                    Annotation(
                        entity_type="invoice",
                        entity_id=self._invoice_id(invoice),
                        entity_name=self._invoice_name(invoice),
                        note=knowledge.statement,
                    )
                )

        for transaction in transactions:
            if self._matches_entity(transaction, entities, knowledge.statement):
                annotations.append(
                    Annotation(
                        entity_type="transaction",
                        entity_id=self._transaction_id(transaction),
                        entity_name=self._transaction_name(transaction),
                        note=knowledge.statement,
                    )
                )

        for receipt in receipts:
            if self._matches_entity(receipt, entities, knowledge.statement):
                annotations.append(
                    Annotation(
                        entity_type="receipt",
                        entity_id=self._receipt_id(receipt),
                        entity_name=self._receipt_name(receipt),
                        note=knowledge.statement,
                    )
                )

        return annotations

    def _personal_expense_findings(
        self,
        fact: Knowledge,
        annotations: list[Annotation],
    ) -> list[Finding]:
        text = self._normalize(fact.statement)
        matched_terms = self._matched_terms(
            text,
            (
                "personal",
                "business card by accident",
                "by accident",
                "dog food",
                "netflix",
            ),
        )

        if not matched_terms:
            return []

        transaction_annotations = [
            annotation
            for annotation in annotations
            if annotation.entity_type == "transaction"
        ]

        return [
            self._finding(
                finding_type="possible_personal_expense",
                severity="medium",
                group="Money to Review",
                confidence="high",
                title="Possible personal charge on business card",
                description=(
                    f"{annotation.entity_name} is linked to a note that may "
                    "indicate a personal charge."
                ),
                suggested_action=(
                    "Review the transaction and mark it personal if the note is correct."
                ),
                annotation=annotation,
                evidence=[
                    f"Linked note: {fact.statement}",
                    "Matched terms: " + ", ".join(matched_terms),
                ],
            )
            for annotation in transaction_annotations
        ]

    def _invoice_follow_up_findings(
        self,
        fact: Knowledge,
        annotations: list[Annotation],
    ) -> list[Finding]:
        text = self._normalize(fact.statement)
        matched_terms = self._matched_terms(
            text,
            (
                "hasn't paid",
                "still outstanding",
                "outstanding",
                "follow up",
                "has not paid",
            ),
        )

        if not matched_terms:
            return []

        invoice_annotations = [
            annotation
            for annotation in annotations
            if annotation.entity_type == "invoice"
        ]

        return [
            self._finding(
                finding_type="invoice_follow_up",
                severity="high",
                group="Receivables",
                confidence="high",
                title="Invoice follow-up needed",
                description=(
                    f"{annotation.entity_name} is linked to a note about "
                    "payment follow-up or outstanding status."
                ),
                suggested_action=(
                    "Review the invoice status and follow up with the client if unpaid."
                ),
                annotation=annotation,
                evidence=[
                    f"Linked note: {fact.statement}",
                    "Matched terms: " + ", ".join(matched_terms),
                ],
            )
            for annotation in invoice_annotations
        ]

    def _refund_context_findings(
        self,
        fact: Knowledge,
        annotations: list[Annotation],
        refund_transaction_ids: set[str],
    ) -> list[Finding]:
        text = self._normalize(fact.statement)
        matched_terms = self._matched_terms(
            text,
            (
                "refund",
                "refunded",
                "came through",
                "returned",
            ),
        )

        if not matched_terms:
            return []

        transaction_annotations = [
            annotation
            for annotation in annotations
            if annotation.entity_type == "transaction"
            and annotation.entity_id in refund_transaction_ids
        ]

        return [
            self._finding(
                finding_type="refund_context",
                severity="low",
                group="Money to Review",
                confidence="high",
                title="Refund context matched",
                description=(
                    f"{annotation.entity_name} is linked to a note about a refund."
                ),
                suggested_action=(
                    "Confirm the refund transaction matches the note and keep it for record context."
                ),
                annotation=annotation,
                evidence=[
                    f"Linked note: {fact.statement}",
                    "Matched terms: " + ", ".join(matched_terms),
                ],
            )
            for annotation in transaction_annotations
        ]

    def _sales_opportunity_findings(
        self,
        fact: Knowledge,
        annotations: list[Annotation],
    ) -> list[Finding]:
        text = self._normalize(fact.statement)
        matched_terms = self._matched_terms(
            text,
            (
                "upsell",
                "might need",
                "new signage",
                "opportunity",
                "motion graphics",
            ),
        )

        if not matched_terms:
            return []

        if annotations:
            return [
                self._finding(
                    finding_type="sales_opportunity",
                    severity="low",
                    group="Business Development",
                    confidence="medium",
                    title="Potential sales follow-up",
                    description=(
                        f"{annotation.entity_name} is linked to a note about "
                        "possible future work."
                    ),
                    suggested_action=(
                        "Consider adding this client opportunity to a follow-up list."
                    ),
                    annotation=annotation,
                    evidence=[
                        f"Linked note: {fact.statement}",
                        "Matched terms: " + ", ".join(matched_terms),
                    ],
                )
                for annotation in annotations
            ]

        return [
            Finding(
                finding_type="sales_opportunity",
                severity="low",
                group="Business Development",
                status="open",
                confidence="medium",
                title="Potential sales follow-up",
                description=(
                    "A note mentions possible future work, but it was not "
                    "linked to a parsed entity."
                ),
                suggested_action=(
                    "Review the note and decide whether to create a sales follow-up."
                ),
                evidence=[
                    f"Source note: {fact.statement}",
                    "Matched terms: " + ", ".join(matched_terms),
                ],
            )
        ]

    def _admin_action_findings(
        self,
        fact: Knowledge,
        annotations: list[Annotation],
    ) -> list[Finding]:
        if not annotations:
            return []

        text = self._normalize(fact.statement)
        matched_terms = self._matched_terms(
            text,
            (
                "business registration",
                "renew",
                "home office",
                "deduction",
                "compliance",
            ),
        )

        if not matched_terms:
            return []

        return [
            Finding(
                finding_type="admin_or_compliance_action",
                severity="medium",
                group="Admin",
                status="open",
                confidence="medium",
                title="Admin or compliance review item",
                description=(
                    "A note mentions administrative or compliance follow-up."
                ),
                suggested_action=(
                    "Review this admin item and handle it outside the document parser."
                ),
                evidence=[
                    f"Source note: {fact.statement}",
                    "Matched terms: " + ", ".join(matched_terms),
                ],
            )
        ]

    def _is_actionable_unmatched_note(self, knowledge: Knowledge) -> bool:
        text = self._normalize(knowledge.statement)
        payload_text = self._normalize(knowledge.payload)

        if knowledge.knowledge_type == "document_applicability" and (
            "personal card" in text
            or "move" in text
            and "personal" in text
            or "personal card" in payload_text
        ):
            return True

        if knowledge.knowledge_type == "financial_context" and (
            "personal card" in text
            or "move" in text
            and "personal" in text
        ):
            return True

        if knowledge.knowledge_type == "financial_context" and (
            "home office" in text
            and ("deduction" in text or "qualifies" in text)
        ):
            return True

        return False

    def _finding(
        self,
        finding_type: str,
        severity: str,
        group: str,
        confidence: str,
        title: str,
        description: str,
        suggested_action: str,
        annotation: Annotation,
        evidence: list[str],
    ) -> Finding:
        return Finding(
            finding_type=finding_type,
            severity=severity,
            group=group,
            status="open",
            confidence=confidence,
            title=title,
            description=description,
            suggested_action=suggested_action,
            entity_type=annotation.entity_type,
            entity_id=annotation.entity_id,
            entity_name=annotation.entity_name,
            evidence=evidence,
        )

    def _matched_terms(
        self,
        text: str,
        terms: tuple[str, ...],
    ) -> list[str]:
        return [
            term
            for term in terms
            if term in text
        ]

    def _safe_snake_case(self, value: Any) -> str:
        text = self._normalize(value)
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        text = re.sub(r"_+", "_", text)
        return text or "review_item"

    def _matches_entity(
        self,
        entity: object,
        claim_entities: list[str],
        statement: str = "",
    ) -> bool:
        if isinstance(entity, Transaction):
            text = " ".join([statement, *claim_entities])
            amounts = self._amounts_from_text(text)
            dates = self._date_terms_from_text(text)

            if dates and not self._transaction_date_matches(entity, dates):
                return False

            if amounts and dates:
                return self._matches_transaction_by_amount_and_date(
                    entity,
                    claim_entities,
                    statement,
                )

        entity_values = self._entity_values(entity)
        strong_claim_entities = [
            claim_entity
            for claim_entity in claim_entities
            if self._is_strong_claim_entity(claim_entity)
        ]

        for claim_entity in strong_claim_entities:
            normalized_claim = self._normalize(claim_entity)

            if not normalized_claim:
                continue

            for entity_value in entity_values:
                normalized_value = self._normalize(entity_value)

                if not normalized_value:
                    continue

                if (
                    normalized_claim in normalized_value
                    or normalized_value in normalized_claim
                    or self._has_meaningful_token_overlap(
                        normalized_claim,
                        normalized_value,
                    )
                ):
                    return True

        return False

    def _matches_transaction_by_amount_and_date(
        self,
        transaction: Transaction,
        claim_entities: list[str],
        statement: str,
    ) -> bool:
        text = " ".join([statement, *claim_entities])
        amounts = self._amounts_from_text(text)
        dates = self._date_terms_from_text(text)

        if transaction.amount is None or not amounts or not dates:
            return False

        amount_matches = any(
            abs(abs(transaction.amount) - abs(amount)) <= 1.0
            for amount in amounts
        )
        date_matches = any(
            self._normalize(date) in self._normalize(transaction.date)
            or self._normalize(transaction.date) in self._normalize(date)
            for date in dates
        )

        return amount_matches and date_matches

    def _transaction_date_matches(
        self,
        transaction: Transaction,
        dates: list[str],
    ) -> bool:
        return any(
            self._normalize(date) in self._normalize(transaction.date)
            or self._normalize(transaction.date) in self._normalize(date)
            for date in dates
        )

    def _amounts_from_text(self, text: str) -> list[float]:
        amounts: list[float] = []

        for match in re.finditer(
            r"(?:[$~]\s*|\(\s*[$~]?\s*)(-?\d+(?:[.,]\d{2})?)",
            text,
        ):
            raw_value = match.group(1).replace(",", "")

            try:
                amounts.append(float(raw_value))
            except ValueError:
                pass

        return amounts

    def _date_terms_from_text(self, text: str) -> list[str]:
        return re.findall(
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
            r"\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
            text.lower(),
        )

    def _is_strong_claim_entity(self, value: str) -> bool:
        normalized = self._normalize(value)

        if not normalized:
            return False

        if re.fullmatch(r"[$]?\s*-?\d+(?:[.,]\d{2})?", normalized):
            return False

        if re.fullmatch(
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\s*\d{1,2}"
            r"(?:[/-]\d{1,2})?(?:[/-]\d{2,4})?",
            normalized,
        ):
            return False

        tokens = self._meaningful_tokens(normalized)

        return bool(tokens)

    def _has_meaningful_token_overlap(
        self,
        normalized_claim: str,
        normalized_value: str,
    ) -> bool:
        claim_tokens = set(self._meaningful_tokens(normalized_claim))
        value_tokens = set(self._meaningful_tokens(normalized_value))

        if not claim_tokens or not value_tokens:
            return False

        return bool(claim_tokens & value_tokens)

    def _tokens(self, value: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", value.lower())

    def _meaningful_tokens(self, value: str) -> list[str]:
        return [
            token
            for token in self._tokens(value)
            if len(token) >= 4
            and not token.isdigit()
            and token not in self.GENERIC_ENTITY_TOKENS
        ]

    def _entity_values(self, entity: object) -> list[str]:
        if not is_dataclass(entity):
            return []

        values: list[str] = []

        for field in fields(entity):
            value = getattr(entity, field.name)

            if value is not None:
                values.append(str(value))

        return values

    def _invoice_id(self, invoice: Invoice) -> str:
        return (
            invoice.invoice_id
            or invoice.client
            or invoice.description
            or "invoice"
        )

    def _transaction_id(self, transaction: Transaction) -> str:
        return (
            transaction.transaction_id
            or transaction.vendor
            or "transaction"
        )

    def _receipt_id(self, receipt: Receipt) -> str:
        return " | ".join(
            value
            for value in [receipt.merchant, receipt.date]
            if value
        ) or "receipt"

    def _invoice_name(self, invoice: Invoice) -> str:
        return invoice.client or invoice.description or "invoice"

    def _transaction_name(self, transaction: Transaction) -> str:
        return transaction.vendor or "transaction"

    def _receipt_name(self, receipt: Receipt) -> str:
        return receipt.merchant or "receipt"

    def _normalize(self, value: Any) -> str:
        return str(value).strip().lower()
