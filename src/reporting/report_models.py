from dataclasses import dataclass


@dataclass
class FinalReport:
    metadata: dict
    summary: dict
    revenue: dict
    expenses: dict
    annotations: list[dict]
    action_items: list[str]
    business_rules: list[str]
    ignored_files: list[dict]

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata,
            "summary": self.summary,
            "revenue": self.revenue,
            "expenses": self.expenses,
            "annotations": self.annotations,
            "action_items": self.action_items,
            "business_rules": self.business_rules,
            "ignored_files": self.ignored_files,
        }
