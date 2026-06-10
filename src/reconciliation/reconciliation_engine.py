from __future__ import annotations

from dataclasses import fields, is_dataclass
import re
from typing import Any

from business_entities.invoice import Invoice
from models.context_hint import ContextHint
from models.receipt import Receipt
from models.semantic_fact import SemanticFact
from models.transaction import Transaction
from reconciliation.reconciliation_report import (
    Annotation,
    Finding,
    ReconciliationReport,
)


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

    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client

    def build_report(
        self,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        semantic_facts: list[SemanticFact],
        context_hints: list[ContextHint] | None = None,
    ) -> ReconciliationReport:
        report = ReconciliationReport()
        context_hints = context_hints or []

        for fact in semantic_facts:
            if fact.fact_type == "action_item":
                report.action_items.append(fact.statement)
                continue

            if fact.fact_type == "rule":
                report.rules.append(fact.statement)
                continue

            if fact.fact_type == "claim":
                report.annotations.extend(
                    self._annotations_for_claim(
                        fact,
                        invoices,
                        transactions,
                        receipts,
                    )
                )

        report.findings = self._findings_for_facts(
            semantic_facts,
            invoices,
            transactions,
            receipts,
            context_hints,
        )
        return report

    def _findings_for_facts(
        self,
        semantic_facts: list[SemanticFact],
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        context_hints: list[ContextHint] | None = None,
    ) -> list[Finding]:
        context_hints = context_hints or []

        if self.llm_client is not None:
            try:
                return self._llm_findings_for_facts(
                    semantic_facts,
                    invoices,
                    transactions,
                    receipts,
                    context_hints,
                )
            except Exception as exc:
                print(
                    "[reconciliation] LLM findings failed; "
                    f"using deterministic fallback: {exc}"
                )

        return self._deterministic_findings_for_facts(
            semantic_facts,
            invoices,
            transactions,
            receipts,
        )

    def _llm_findings_for_facts(
        self,
        semantic_facts: list[SemanticFact],
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
        context_hints: list[ContextHint],
    ) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple[str, str | None, str]] = set()

        for fact in semantic_facts:
            if fact.fact_type == "rule":
                continue

            annotations = (
                self._annotations_for_claim(
                    fact,
                    invoices,
                    transactions,
                    receipts,
                )
                if fact.fact_type == "claim"
                else []
            )

            candidate_findings = (
                [
                    self._llm_finding_for_fact(
                        fact,
                        annotation,
                        self._relevant_context_hints(fact, context_hints),
                    )
                    for annotation in annotations
                ]
                if annotations
                else [
                    self._llm_finding_for_fact(
                        fact,
                        None,
                        self._relevant_context_hints(fact, context_hints),
                    )
                ]
            )

            for finding in candidate_findings:
                if finding is None:
                    continue

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

    def _llm_finding_for_fact(
        self,
        fact: SemanticFact,
        annotation: Annotation | None,
        context_hints: list[ContextHint] | None = None,
    ) -> Finding | None:
        if self.llm_client is None:
            return None

        payload = self.llm_client.generate_json(
            system_prompt=self._finding_system_prompt(),
            user_prompt=self._finding_user_prompt(
                fact,
                annotation,
                context_hints or [],
            ),
        )

        if not payload.get("should_create_finding"):
            return None

        finding_type = self._safe_snake_case(
            payload.get("finding_type") or "review_item"
        )
        severity = self._choice(
            payload.get("severity"),
            {"low", "medium", "high"},
            "medium",
        )
        confidence = self._choice(
            payload.get("confidence"),
            {"low", "medium", "high"},
            "medium",
        )
        status = self._choice(
            payload.get("status"),
            {"open", "reviewed", "dismissed"},
            "open",
        )
        group = self._clean_text(payload.get("group")) or "General Review"
        title = self._clean_text(payload.get("title")) or "Review item"
        description = (
            self._clean_text(payload.get("description"))
            or "A note may require review."
        )
        suggested_action = (
            self._clean_text(payload.get("suggested_action"))
            or "Review the linked note and source document."
        )
        evidence = self._clean_string_list(payload.get("evidence"))

        if not evidence:
            evidence = [f"Source note: {fact.statement}"]

        return Finding(
            finding_type=finding_type,
            severity=severity,
            group=group,
            status=status,
            confidence=confidence,
            title=title,
            description=description,
            suggested_action=suggested_action,
            entity_type=annotation.entity_type if annotation else None,
            entity_id=annotation.entity_id if annotation else None,
            entity_name=annotation.entity_name if annotation else None,
            evidence=evidence,
        )

    def _finding_system_prompt(self) -> str:
        return """
You are a document reconciliation review engine.

Create generalized review findings from user notes and parsed document links.
You are not limited to a fixed taxonomy.

Rules:
- Use the linked entity only as context; do not modify it.
- Do not make final accounting, tax, legal, or payment conclusions.
- Prefer review language: "review", "confirm", "follow up", "check".
- If the note has no business, admin, recordkeeping, financial, sales, or compliance value, return should_create_finding=false.
- finding_type must be short snake_case and can be open-ended.
- group should be a human workflow label, such as Receivables, Money to Review, Records, Admin, Business Development, Compliance, or General Review.
- severity must be low, medium, or high.
- confidence must be low, medium, or high.
- status must be open.

Return ONLY valid JSON:

{
  "should_create_finding": true,
  "finding_type": "open_ended_snake_case",
  "group": "Workflow Group",
  "severity": "medium",
  "status": "open",
  "confidence": "medium",
  "title": "Short review title",
  "description": "One sentence explaining why this should be reviewed.",
  "suggested_action": "One concrete review action.",
  "evidence": ["Source note: ...", "Linked entity: ..."]
}

For ignored input:

{
  "should_create_finding": false
}
""".strip()

    def _finding_user_prompt(
        self,
        fact: SemanticFact,
        annotation: Annotation | None,
        context_hints: list[ContextHint],
    ) -> str:
        linked_entity = (
            {
                "entity_type": annotation.entity_type,
                "entity_id": annotation.entity_id,
                "entity_name": annotation.entity_name,
                "linked_note": annotation.note,
            }
            if annotation
            else None
        )

        return (
            "Semantic fact:\n"
            f"- fact_type: {fact.fact_type}\n"
            f"- statement: {fact.statement}\n"
            f"- entities: {fact.entities}\n\n"
            f"Linked parsed entity:\n{linked_entity}\n"
            f"Relevant context hints:\n{self._hint_payload(context_hints)}\n"
        )

    def _relevant_context_hints(
        self,
        fact: SemanticFact,
        context_hints: list[ContextHint],
    ) -> list[ContextHint]:
        fact_text = self._normalize(
            " ".join([fact.statement, *fact.entities])
        )
        relevant_hints: list[ContextHint] = []

        for hint in context_hints:
            if hint.hint_type != "entity_event":
                continue

            hint_text = self._normalize(
                " ".join([hint.source_statement, *hint.entities])
            )

            if (
                hint.source_statement == fact.statement
                or self._has_meaningful_token_overlap(fact_text, hint_text)
            ):
                relevant_hints.append(hint)

        return relevant_hints

    def _hint_payload(self, context_hints: list[ContextHint]) -> list[dict]:
        return [
            {
                "hint_type": hint.hint_type,
                "target": hint.target,
                "value": hint.value,
                "source_statement": hint.source_statement,
                "entities": hint.entities,
                "confidence": hint.confidence,
                "metadata": hint.metadata,
            }
            for hint in context_hints
        ]

    def _deterministic_findings_for_facts(
        self,
        semantic_facts: list[SemanticFact],
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
    ) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple[str, str | None, str]] = set()

        for fact in semantic_facts:
            matched_annotations = self._annotations_for_claim(
                fact,
                invoices,
                transactions,
                receipts,
            )
            refund_transaction_ids = {
                self._transaction_id(transaction)
                for transaction in transactions
                if (transaction.amount or 0.0) < 0.0
                or transaction.transaction_type == "refund"
            }
            candidate_findings = [
                *self._personal_expense_findings(fact, matched_annotations),
                *self._invoice_follow_up_findings(fact, matched_annotations),
                *self._refund_context_findings(
                    fact,
                    matched_annotations,
                    refund_transaction_ids,
                ),
                *self._sales_opportunity_findings(fact, matched_annotations),
                *self._admin_action_findings(fact, matched_annotations),
            ]

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

    def _annotations_for_claim(
        self,
        fact: SemanticFact,
        invoices: list[Invoice],
        transactions: list[Transaction],
        receipts: list[Receipt],
    ) -> list[Annotation]:
        annotations: list[Annotation] = []

        for invoice in invoices:
            if self._matches_entity(invoice, fact.entities, fact.statement):
                annotations.append(
                    Annotation(
                        entity_type="invoice",
                        entity_id=self._invoice_id(invoice),
                        entity_name=self._invoice_name(invoice),
                        note=fact.statement,
                    )
                )

        for transaction in transactions:
            if self._matches_entity(transaction, fact.entities, fact.statement):
                annotations.append(
                    Annotation(
                        entity_type="transaction",
                        entity_id=self._transaction_id(transaction),
                        entity_name=self._transaction_name(transaction),
                        note=fact.statement,
                    )
                )

        for receipt in receipts:
            if self._matches_entity(receipt, fact.entities, fact.statement):
                annotations.append(
                    Annotation(
                        entity_type="receipt",
                        entity_id=self._receipt_id(receipt),
                        entity_name=self._receipt_name(receipt),
                        note=fact.statement,
                    )
                )

        return annotations

    def _personal_expense_findings(
        self,
        fact: SemanticFact,
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
        fact: SemanticFact,
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
        fact: SemanticFact,
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
        fact: SemanticFact,
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
        fact: SemanticFact,
        annotations: list[Annotation],
    ) -> list[Finding]:
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

    def _choice(
        self,
        value: Any,
        allowed_values: set[str],
        default: str,
    ) -> str:
        normalized = self._normalize(value)
        return normalized if normalized in allowed_values else default

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""

        return re.sub(r"\s+", " ", str(value)).strip()

    def _clean_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        cleaned_values = [
            self._clean_text(item)
            for item in value
        ]
        return [
            item
            for item in cleaned_values
            if item
        ]

    def _matches_entity(
        self,
        entity: object,
        claim_entities: list[str],
        statement: str = "",
    ) -> bool:
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

        if isinstance(entity, Transaction):
            return self._matches_transaction_by_amount_and_date(
                entity,
                claim_entities,
                statement,
            )

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

    def _amounts_from_text(self, text: str) -> list[float]:
        amounts: list[float] = []

        for match in re.finditer(r"[$~() ]*(-?\d+(?:[.,]\d{2})?)", text):
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
