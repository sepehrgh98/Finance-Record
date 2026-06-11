from __future__ import annotations

import json

from core.config.settings import LLM_MODEL, LLM_PROVIDER
from llm.factory import build_llm_client


def main() -> None:
    print("=" * 60)
    print("LLM CONNECTION CHECK")
    print("=" * 60)

    client = build_llm_client(
        provider=LLM_PROVIDER,
        model=LLM_MODEL,
    )

    print(f"Provider : {LLM_PROVIDER}")
    print(f"Model    : {LLM_MODEL}")
    print()
    print("Checking availability...")

    available = client.is_available()
    print(f"Available: {available}")

    if not available:
        print(f"Error: {client.last_error}")
        return

    print()
    print("Running JSON generation check...")
    print()

    try:
        result = client.generate_json(
            system_prompt="Return only valid JSON.",
            user_prompt='{"status": "ok", "message": "hello from local llm"}',
        )
        print("SUCCESS")
        print()
        print("Parsed JSON:")
        print(json.dumps(result, indent=4, ensure_ascii=False))
    except Exception as exc:
        print("FAILED")
        print(exc)

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
