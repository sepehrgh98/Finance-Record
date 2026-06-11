from __future__ import annotations

from datetime import datetime
import os


def pipeline_log(message: str) -> None:
    if os.getenv("PIPELINE_LOG", "1").strip().lower() in {"0", "false", "off"}:
        return

    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[pipeline {timestamp}] {message}", flush=True)
