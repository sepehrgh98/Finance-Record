from __future__ import annotations

from typing import Any

from core.enums.document_type import DocumentType


VALID_DOCUMENT_TYPE_VALUES = {
    document_type.value
    for document_type in DocumentType
    if document_type != DocumentType.UNKNOWN
}


def sanitize_knowledge(
    knowledge_type: str,
    payload: dict[str, Any],
    statement: str = "",
) -> tuple[str | None, dict[str, Any]]:
    normalized_payload = dict(payload)
    normalized_type = str(knowledge_type or "").strip()

    if "document_type" not in normalized_payload:
        if should_be_financial_context(normalized_type, statement, normalized_payload):
            return "financial_context", normalized_payload

        return normalized_type, normalized_payload

    document_type = normalize_document_type(normalized_payload.get("document_type"))

    if document_type is not None:
        normalized_payload["document_type"] = document_type
        return normalized_type, normalized_payload

    normalized_payload.pop("document_type", None)

    if should_be_financial_context(normalized_type, statement, normalized_payload):
        return "financial_context", normalized_payload

    if normalized_type == "document_type_context":
        if looks_like_financial_context(statement, normalized_payload):
            return "financial_context", normalized_payload

        return None, {}

    return normalized_type, normalized_payload


def should_be_financial_context(
    knowledge_type: str,
    statement: str,
    payload: dict[str, Any],
) -> bool:
    if knowledge_type != "document_applicability":
        return False

    normalized_statement = statement.lower()
    normalized_payload = " ".join(
        str(value).lower()
        for value in payload.values()
        if value is not None
    )
    combined = f"{normalized_statement} {normalized_payload}"

    return (
        "personal card" in combined
        or (
            "personal" in combined
            and any(term in combined for term in ("card", "charge", "expense", "move"))
        )
    )


def normalize_document_type(value: object) -> str | None:
    normalized = str(value or "").strip().lower().replace(" ", "_")

    if normalized in VALID_DOCUMENT_TYPE_VALUES:
        return normalized

    return None


def looks_like_financial_context(
    statement: str,
    payload: dict[str, Any],
) -> bool:
    normalized_statement = statement.lower()
    financial_terms = {
        "card",
        "charge",
        "expense",
        "invoice",
        "paid",
        "payment",
        "personal",
        "refund",
        "unpaid",
    }

    if any(term in normalized_statement for term in financial_terms):
        return True

    financial_payload_keys = {
        "amount",
        "card",
        "customer",
        "merchant",
        "refund_amount",
        "refund_status",
        "status",
        "vendor",
    }

    return any(key in payload for key in financial_payload_keys)
