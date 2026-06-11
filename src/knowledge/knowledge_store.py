from __future__ import annotations

from pathlib import Path

from knowledge.knowledge import Knowledge


class KnowledgeStore:
    def __init__(
        self,
        knowledge: list[Knowledge] | None = None,
        analysis_id: str | None = None,
        report_id: int | None = None,
    ) -> None:
        self._knowledge = list(knowledge or [])
        self.analysis_id = analysis_id
        self.report_id = report_id

    def add_many(self, knowledge: list[Knowledge]) -> None:
        self._knowledge.extend(knowledge)

    def all(self) -> list[Knowledge]:
        return [
            *self._knowledge,
            *self._load_from_db(),
        ]

    def by_type(self, knowledge_type: str) -> list[Knowledge]:
        return [
            knowledge
            for knowledge in self.all()
            if knowledge.knowledge_type == knowledge_type
        ]

    def document_type_context_for_path(
        self,
        path: Path,
    ) -> list[Knowledge]:
        path_parts = {
            part.lower()
            for part in path.parts
        }

        matches: list[Knowledge] = []

        for knowledge in self.by_type("document_type_context"):
            folder = str(knowledge.payload.get("folder") or "").strip("/").lower()

            if folder and folder in path_parts:
                matches.append(knowledge)

        return matches

    def financial_context(self) -> list[Knowledge]:
        return self.by_type("financial_context")

    def announcements(self) -> list[Knowledge]:
        return self.by_type("announcement")

    def _load_from_db(self) -> list[Knowledge]:
        if self.analysis_id is None and self.report_id is None:
            return []

        from persistence.repositories.report_repository import ReportRepository

        repository = ReportRepository()

        try:
            if self.report_id is not None:
                return repository.get_knowledge_for_report(self.report_id)

            if self.analysis_id is not None:
                return repository.get_knowledge_for_analysis(self.analysis_id)
        finally:
            repository.close()

        return []
