from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ContextHint:
    hint_type: Literal["folder_document_type", "entity_event"]
    target: str
    value: str
    source_statement: str
    entities: list[str] = field(default_factory=list)
    confidence: float | None = None
    metadata: dict = field(default_factory=dict)
