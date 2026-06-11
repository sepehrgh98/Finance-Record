from dataclasses import dataclass, field

from core.enums.document_type import DocumentType


@dataclass(frozen=True)
class ClassificationResult:
    document_type: DocumentType | None
    score: float
    reason: str
    evidence: list[str] = field(default_factory=list)
