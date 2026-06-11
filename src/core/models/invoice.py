from dataclasses import dataclass


@dataclass(frozen=True)
class Invoice:
    client: str = ""
    invoice_id: str = ""
    description: str = ""
    amount: float | None = None
    date_sent: str = ""
    date_paid: str = ""
    status: str = ""
