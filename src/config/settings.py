from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


# --------------------------------------------------
# LLM
# --------------------------------------------------

USE_LOCAL_LLM_FOR_NOTES = True


LLM_PROVIDER = "transformers"

LLM_MODEL = "Qwen/Qwen2.5-3B-Instruct"

# --------------------------------------------------
# Ollama
# --------------------------------------------------

OLLAMA_ENDPOINT = _env_str(
    "OLLAMA_ENDPOINT",
    "http://localhost:11434/api/generate",
)

