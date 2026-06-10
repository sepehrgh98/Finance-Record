from dataclasses import dataclass, field


@dataclass
class Annotation:
    entity_type: str
    entity_id: str
    entity_name: str
    note: str


@dataclass
class Finding:
    finding_type: str
    severity: str
    group: str
    status: str
    confidence: str
    title: str
    description: str
    suggested_action: str
    entity_type: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass
class ReconciliationReport:
    annotations: list[Annotation] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
