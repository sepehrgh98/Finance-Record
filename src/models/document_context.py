from dataclasses import dataclass, field

from enums.document_type import DocumentType
from enums.physical_file_type import PhysicalFileType
from models.file_info import FileInfo


@dataclass
class DocumentContext:
    """
    Mutable document state enriched by each pipeline node.
    """

    file_info: FileInfo
    physical_type: PhysicalFileType | None = None
    extracted_text: str = ""
    extracted_tables: list[dict] = field(default_factory=list)
    semantic_type: DocumentType | None = None
    classification_score: float = 0.0
    classification_reason: str = ""
    business_entities: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
