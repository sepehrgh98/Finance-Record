from dataclasses import dataclass

from core.models.transaction import Transaction


@dataclass
class StatementResult:
    transactions: list[Transaction]
    duplicate_transactions: list[Transaction]
    refunds: list[Transaction]
