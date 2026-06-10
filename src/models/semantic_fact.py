from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class SemanticFact:
    fact_type: Literal["claim", "rule", "action_item"]
    statement: str
    entities: list[str] = field(default_factory=list)
    confidence: float | None = None
