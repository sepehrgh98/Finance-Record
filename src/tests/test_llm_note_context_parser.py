from __future__ import annotations

import unittest

from parsing.llm_note_parser import LLMNoteContextParser


class FakeNoteLLM:
    last_error = ""

    def __init__(self, response: dict) -> None:
        self.response = response

    def is_available(self) -> bool:
        return True

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int = 30,
    ) -> dict:
        return self.response


class LLMNoteContextParserTests(unittest.TestCase):
    def test_invalid_document_type_context_becomes_financial_context(self) -> None:
        parser = LLMNoteContextParser(
            FakeNoteLLM(
                {
                    "statement": (
                        "the petco charge was dog food for baxter lol, "
                        "used business card by accident"
                    ),
                    "knowledge_type": "document_type_context",
                    "confidence": 0.93,
                    "payload": {
                        "document_type": "charge",
                        "entities": ["petco charge", "baxter"],
                    },
                }
            )
        )

        knowledge = parser.parse_statement(
            "the petco charge was dog food for baxter lol, "
            "used business card by accident"
        )

        self.assertIsNotNone(knowledge)
        self.assertEqual(knowledge.knowledge_type, "financial_context")
        self.assertNotIn("document_type", knowledge.payload)
        self.assertEqual(
            knowledge.payload["entities"],
            ["petco charge", "baxter"],
        )

    def test_valid_document_type_context_is_preserved(self) -> None:
        parser = LLMNoteContextParser(
            FakeNoteLLM(
                {
                    "statement": "receipts of cash purchases are in receipts/",
                    "knowledge_type": "document_type_context",
                    "confidence": 0.95,
                    "payload": {
                        "folder": "receipts/",
                        "document_type": "receipt",
                    },
                }
            )
        )

        knowledge = parser.parse_statement(
            "receipts of cash purchases are in receipts/"
        )

        self.assertIsNotNone(knowledge)
        self.assertEqual(knowledge.knowledge_type, "document_type_context")
        self.assertEqual(knowledge.payload["document_type"], "receipt")

    def test_personal_card_applicability_becomes_financial_context(self) -> None:
        parser = LLMNoteContextParser(
            FakeNoteLLM(
                {
                    "statement": (
                        "netflix is also on this card, need to move that "
                        "to my personal one"
                    ),
                    "knowledge_type": "document_applicability",
                    "confidence": 0.91,
                    "payload": {
                        "card": "this card",
                        "personal_card": "my personal one",
                        "document_type": "credit card",
                    },
                }
            )
        )

        knowledge = parser.parse_statement(
            "netflix is also on this card, need to move that to my personal one"
        )

        self.assertIsNotNone(knowledge)
        self.assertEqual(knowledge.knowledge_type, "financial_context")
        self.assertNotIn("document_type", knowledge.payload)
        self.assertEqual(knowledge.payload["card"], "this card")


if __name__ == "__main__":
    unittest.main()
