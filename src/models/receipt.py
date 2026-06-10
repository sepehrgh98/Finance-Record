from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    merchant: str = ""
    date: str = ""
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    payment_method: str = ""
