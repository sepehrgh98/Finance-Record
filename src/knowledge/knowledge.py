from dataclasses import dataclass, field
from typing import Any, Literal


KnowledgeType = Literal[
    "document_type_context",
    "document_availability",
    "document_applicability",
    "financial_context",
    "announcement",
    "ignore",
]


@dataclass(frozen=True)
class Knowledge:
    knowledge_type: KnowledgeType
    statement: str
    confidence: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
