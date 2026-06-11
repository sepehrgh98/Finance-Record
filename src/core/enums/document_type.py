from enum import Enum


class DocumentType(Enum):
    INVOICE = "invoice"
    STATEMENT = "statement"
    RECEIPT = "receipt"
    NOTE = "note"
    UNKNOWN = "unknown"
