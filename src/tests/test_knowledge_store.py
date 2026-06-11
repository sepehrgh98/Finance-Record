import unittest

from knowledge.knowledge_store import KnowledgeStore
from knowledge.knowledge import Knowledge
from persistence.repositories.report_repository import ReportRepository


class KnowledgeStoreTests(unittest.TestCase):
    def test_store_loads_knowledge_by_analysis_id_from_database(self) -> None:
        analysis_id = "test-analysis-knowledge-store"
        repository = ReportRepository()

        try:
            repository.save_knowledge_for_analysis(
                analysis_id,
                [
                    Knowledge(
                        knowledge_type="financial_context",
                        statement="adobe refund came through",
                        confidence=0.95,
                        payload={"merchant": "Adobe", "event": "refund"},
                    )
                ],
            )
        finally:
            repository.close()

        store = KnowledgeStore(analysis_id=analysis_id)
        knowledge = store.financial_context()

        self.assertEqual(len(knowledge), 1)
        self.assertEqual(knowledge[0].statement, "adobe refund came through")
        self.assertEqual(knowledge[0].payload["merchant"], "Adobe")


if __name__ == "__main__":
    unittest.main()
