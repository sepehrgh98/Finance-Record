from dataclasses import dataclass, field
from models.context_hint import ContextHint
from models.semantic_fact import SemanticFact


@dataclass
class BusinessContext:
    semantic_facts: list[SemanticFact] = field(default_factory=list)
    context_hints: list[ContextHint] = field(default_factory=list)
