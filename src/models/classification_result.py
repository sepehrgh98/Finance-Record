from dataclasses import dataclass

from enums.document_type import DocumentType


@dataclass(frozen=True)
class ClassificationResult:
    document_type: DocumentType | None
    score: float
    reason: str
