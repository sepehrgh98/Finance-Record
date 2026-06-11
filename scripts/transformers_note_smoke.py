from __future__ import annotations

from transformers import pipeline


def main() -> None:
    pipe = pipeline(
        "text-generation",
        model="Qwen/Qwen2.5-3B-Instruct",
        device_map="auto",
    )

    messages = [
        {
            "role": "system",
            "content": """
You are a note knowledge extraction engine.

Classify the statement as one of:
- document_type_context
- document_availability
- document_applicability
- financial_context
- announcement
- ignore

Return JSON only.
""",
        },
        {
            "role": "user",
            "content": """
the petco charge was dog food for baxter lol, used business card by accident
""",
        },
    ]

    result = pipe(
        messages,
        max_new_tokens=120,
    )

    print(result[0]["generated_text"][-1]["content"])


if __name__ == "__main__":
    main()
