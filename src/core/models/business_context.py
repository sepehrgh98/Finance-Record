from dataclasses import dataclass, field
from knowledge.knowledge import Knowledge


@dataclass
class BusinessContext:
    knowledge: list[Knowledge] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    manual_review_notes: list[str] = field(default_factory=list)
    suggested_updates: list[dict] = field(default_factory=list)
