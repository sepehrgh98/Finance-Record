from __future__ import annotations

import unittest

from context.context_hint_builder import ContextHintBuilder
from models.semantic_fact import SemanticFact


class ContextHintBuilderTests(unittest.TestCase):
    def test_rule_creates_folder_document_type_hint(self) -> None:
        hints = ContextHintBuilder().build(
            [
                SemanticFact(
                    fact_type="rule",
                    statement="receipts of cash purchases are in the receipts/ folder",
                    entities=["receipts"],
                    confidence=0.95,
                )
            ]
        )

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].hint_type, "folder_document_type")
        self.assertEqual(hints[0].target, "receipts")
        self.assertEqual(hints[0].value, "receipt")
        self.assertEqual(hints[0].confidence, 0.95)

    def test_refund_claim_creates_entity_event_hint(self) -> None:
        hints = ContextHintBuilder().build(
            [
                SemanticFact(
                    fact_type="claim",
                    statement="adobe plan downgraded feb 14, refund came through (~$40)",
                    entities=["adobe plan", "feb 14", "$40"],
                    confidence=0.95,
                )
            ]
        )

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].hint_type, "entity_event")
        self.assertEqual(hints[0].value, "refund_context")
        self.assertEqual(hints[0].metadata["amounts"], [40.0])
        self.assertEqual(hints[0].metadata["dates"], ["feb 14"])


if __name__ == "__main__":
    unittest.main()
