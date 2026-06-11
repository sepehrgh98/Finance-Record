from __future__ import annotations

import re
from typing import Callable

from core.config.settings import (
    LLM_MODEL,
    LLM_PROVIDER,
)
from llm.base import BaseLLMClient
from core.models.business_context import BusinessContext
from knowledge.knowledge import Knowledge
from core.utils.knowledge_payload import sanitize_knowledge
from core.utils.pipeline_logger import pipeline_log


class LLMNoteContextParser:
    """
    Uses a local LLM to extract generic semantic facts statement by statement.
    """

    def __init__(
        self,
        client: BaseLLMClient | None = None,
        progress_callback: Callable[[int, str, str], None] | None = None,
    ) -> None:
        if client is None:
            from llm.factory import build_llm_client

            client = build_llm_client(
                provider=LLM_PROVIDER,
                model=LLM_MODEL,
            )

        self.client = client
        self.progress_callback = progress_callback
        pipeline_log(f"note parser LLM client: {type(self.client).__name__}")

    def parse(
        self,
        note_text: str,
    ) -> BusinessContext:
        business_context = BusinessContext()
        statements = self.split_note_into_statements(note_text)
        pipeline_log(f"note parser: {len(statements)} statements")

        for index, statement in enumerate(statements, start=1):
            self._emit_statement_progress(index, len(statements), statement)
            pipeline_log(f"note statement {index}/{len(statements)}: {statement[:100]}")
            parsed = self.parse_statement_with_knowledge(statement)

            if parsed is not None:
                business_context.knowledge.append(parsed)
                pipeline_log(
                    "knowledge: "
                    f"{parsed.knowledge_type} "
                    f"payload={parsed.payload}"
                )
            else:
                pipeline_log("knowledge: ignored")

        return business_context

    def _emit_statement_progress(
        self,
        index: int,
        total: int,
        statement: str,
    ) -> None:
        if self.progress_callback is None or total <= 0:
            return

        percent = 64 + int((9 * (index - 1)) / total)
        self.progress_callback(
            percent,
            "Understanding notes",
            f"{index}/{total}: {statement[:80]}",
        )

    def split_note_into_statements(self, note_text: str) -> list[str]:
        statements: list[str] = []

        for raw_line in note_text.splitlines():
            statement = raw_line.strip()

            if not statement:
                continue

            if self._is_section_header(statement):
                continue

            statement = re.sub(r"^\-\s*", "", statement)
            statement = re.sub(r"^\[(todo|done)\]\s*", "", statement, flags=re.I)
            statement = statement.strip()

            if statement:
                statements.append(statement)

        return statements

    def parse_statement(self, statement: str) -> Knowledge | None:
        return self.parse_statement_with_knowledge(statement)

    def parse_statement_with_knowledge(
        self,
        statement: str,
    ) -> Knowledge | None:
        system_prompt, user_prompt = self._build_prompts(statement)

        response = self.client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        knowledge = self._to_knowledge(response, statement)

        if knowledge is None:
            return None

        return knowledge

    def _is_section_header(self, statement: str) -> bool:
        normalized = statement.lower()

        if normalized == "random:":
            return True

        return bool(re.fullmatch(r"==\s*.+?\s*==", statement))

    def _build_prompts(
        self,
        statement: str,
    ) -> tuple[str, str]:
        system_prompt = """
You are a note knowledge extraction engine.

Classify the statement as exactly one knowledge category:
- document_type_context
- document_availability
- document_applicability
- financial_context
- announcement
- ignore

Knowledge category definitions:

document_type_context:
The statement provides information about the business meaning or location of documents.
Use document_type_context only when payload.document_type is one of:
invoice, statement, receipt, note.
Do not use document_type_context for charges, vendors, expenses, refunds, or payment status.

document_availability:
The statement indicates that a document should exist but is unavailable, lost, missing, duplicated, or invalid.

document_applicability:
The statement indicates whether a document should participate in the current analysis.

financial_context:
The statement provides financial interpretation or status information.

announcement:
The statement represents a reminder, task, follow-up, opportunity, question, or user-facing note.

ignore:
The statement contains no useful business information.

Knowledge priority order:
1. document_type_context
2. document_availability
3. document_applicability
4. financial_context
5. announcement
6. ignore

Do not output pipeline actions such as add_classification_hint or create_finding.
Extract referenced entities when possible.

Return ONLY valid JSON:

{
  "statement": "<original statement>",
  "knowledge_type": "financial_context",
  "confidence": 0.95,
  "payload": {
    "entities": ["entity1", "entity2"]
  }
}

Examples:

Input:
greenloop still hasn't paid invoice 2
Output:
{
  "statement": "greenloop still hasn't paid invoice 2",
  "knowledge_type": "financial_context",
  "confidence": 0.95,
  "payload": {
    "customer": "GreenLoop",
    "invoice_reference": "2",
    "status": "unpaid",
    "entities": ["GreenLoop", "invoice 2"]
  }
}

Input:
receipts of cash purchases are in the receipts folder
Output:
{
  "statement": "receipts of cash purchases are in the receipts folder",
  "knowledge_type": "document_type_context",
  "confidence": 0.95,
  "payload": {
    "folder": "receipts",
    "document_type": "receipt",
    "entities": ["receipts"]
  }
}

Input:
renew business registration before june
Output:
{
  "statement": "renew business registration before june",
  "knowledge_type": "announcement",
  "confidence": 0.95,
  "payload": {
    "announcement_type": "task",
    "entities": ["business registration"]
  }
}

Input:
netflix is also on this card.. need to move that to my personal one
Output:
{
  "statement": "netflix is also on this card.. need to move that to my personal one",
  "knowledge_type": "financial_context",
  "confidence": 0.95,
  "payload": {
    "merchant": "Netflix",
    "classification": "personal_expense",
    "suggested_action": "move_to_personal_card",
    "entities": ["Netflix"]
  }
}

Input:
need to figure out if my home office qualifies for a deduction this year
Output:
{
  "statement": "need to figure out if my home office qualifies for a deduction this year",
  "knowledge_type": "financial_context",
  "confidence": 0.95,
  "payload": {
    "topic": "home office deduction",
    "status": "needs_review",
    "entities": ["home office", "deduction"]
  }
}

Input:
wish i could just throw my business docs at something and get answers
Output:
{
  "statement": "",
  "knowledge_type": "ignore",
  "confidence": 0.95,
  "payload": {}
}
""".strip()

        user_prompt = f"""
Statement:
{statement}
""".strip()

        return system_prompt, user_prompt

    def _to_knowledge(
        self,
        response: dict,
        original_statement: str,
    ) -> Knowledge | None:
        knowledge_type = str(
            response.get("knowledge_type", "")
        ).strip()

        if knowledge_type not in self.allowed_knowledge_types:
            return None

        if knowledge_type == "ignore":
            return None

        statement = str(response.get("statement") or original_statement).strip()

        if not statement:
            return None

        payload = response.get("payload", {})

        if not isinstance(payload, dict):
            payload = {}

        knowledge_type, payload = sanitize_knowledge(
            knowledge_type,
            payload,
            statement,
        )

        if knowledge_type is None:
            return None

        return Knowledge(
            knowledge_type=knowledge_type,
            statement=statement,
            confidence=self._parse_confidence(response.get("confidence")),
            payload=payload,
        )

    def _parse_entities(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []

        return [
            str(entity).strip()
            for entity in value
            if str(entity).strip()
        ]

    def _parse_confidence(self, value: object) -> float | None:
        if value is None:
            return None

        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return None

        if confidence < 0.0 or confidence > 1.0:
            return None

        return confidence
    allowed_knowledge_types = {
        "document_type_context",
        "document_availability",
        "document_applicability",
        "financial_context",
        "announcement",
        "ignore",
    }
