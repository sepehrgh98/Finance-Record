from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    transaction_id: str | None = None
    date: str = ""
    vendor: str = ""
    amount: float | None = None
    transaction_type: str = ""
