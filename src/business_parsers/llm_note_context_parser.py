from __future__ import annotations

import re

from config.settings import (
    LLM_MODEL,
    LLM_PROVIDER,
)
from llm.base import BaseLLMClient
from models.business_context import BusinessContext
from models.semantic_fact import SemanticFact


class LLMNoteContextParser:
    """
    Uses a local LLM to extract generic semantic facts statement by statement.
    """

    def __init__(
        self,
        client: BaseLLMClient | None = None,
    ) -> None:
        if client is None:
            from llm.factory import build_llm_client

            client = build_llm_client(
                provider=LLM_PROVIDER,
                model=LLM_MODEL,
            )

        self.client = client

        print(
            f"LLM client: {type(self.client).__name__}"
        )

    def parse(
        self,
        note_text: str,
    ) -> BusinessContext:
        business_context = BusinessContext()

        for statement in self.split_note_into_statements(note_text):
            semantic_fact = self.parse_statement(statement)

            if semantic_fact is not None:
                business_context.semantic_facts.append(semantic_fact)

        return business_context

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

    def parse_statement(self, statement: str) -> SemanticFact | None:
        system_prompt, user_prompt = self._build_prompts(statement)

        response = self.client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return self._to_semantic_fact(response)

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
You are a semantic extraction engine.

Classify the statement as exactly one of:
- claim
- rule
- action_item
- ignore

Definitions:

claim:
A statement asserted by the user that may affect interpretation of other documents.

rule:
A statement that defines how documents, receipts, invoices, folders, or records should be interpreted.

action_item:
A task, reminder, follow-up, opportunity, compliance action, or future work item.

ignore:
Jokes, wishes, opinions, commentary, or statements with no business value.

Extract referenced entities when possible.

Return ONLY valid JSON:

{
  "fact_type": "claim",
  "statement": "<original statement>",
  "entities": ["entity1", "entity2"],
  "confidence": 0.95
}


""".strip()

        user_prompt = f"""
Statement:
{statement}
""".strip()

        return system_prompt, user_prompt

    def _to_semantic_fact(
        self,
        response: dict,
    ) -> SemanticFact | None:
        fact_type = str(response.get("fact_type", "")).strip()

        if fact_type == "ignore":
            return None

        if fact_type not in {"claim", "rule", "action_item"}:
            return None

        statement = str(response.get("statement", "")).strip()

        if not statement:
            return None

        return SemanticFact(
            fact_type=fact_type,
            statement=statement,
            entities=self._parse_entities(response.get("entities", [])),
            confidence=self._parse_confidence(
                response.get("confidence")
            ),
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
