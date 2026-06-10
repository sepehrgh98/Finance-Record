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


LLM_PROVIDER = "qwen_vl"

LLM_MODEL = _env_str(
    "LLM_MODEL",
    "Qwen/Qwen2.5-VL-3B-Instruct",
)

# --------------------------------------------------
# Local VLM OCR fallback
# --------------------------------------------------

USE_LOCAL_VLM_FOR_OCR = _env_bool(
    "USE_LOCAL_VLM_FOR_OCR",
    True,
)

VLM_MODEL = _env_str(
    "VLM_MODEL",
    LLM_MODEL,
)

VLM_LOCAL_FILES_ONLY = _env_bool(
    "VLM_LOCAL_FILES_ONLY",
    True,
)

# --------------------------------------------------
# Ollama
# --------------------------------------------------

OLLAMA_ENDPOINT = _env_str(
    "OLLAMA_ENDPOINT",
    "http://localhost:11434/api/generate",
)
