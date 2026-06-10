from dataclasses import dataclass, field
from models.semantic_fact import SemanticFact


@dataclass
class BusinessContext:
    semantic_facts: list[SemanticFact] = field(default_factory=list)
