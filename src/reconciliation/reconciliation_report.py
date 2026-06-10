from dataclasses import dataclass, field


@dataclass
class Annotation:
    entity_type: str
    entity_id: str
    entity_name: str
    note: str


@dataclass
class ReconciliationReport:
    annotations: list[Annotation] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
