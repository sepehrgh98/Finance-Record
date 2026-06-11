from __future__ import annotations

from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
import os
from typing import Iterator


@contextmanager
def silence_third_party_output(
    *debug_env_vars: str,
) -> Iterator[None]:
    if any(_env_enabled(name) for name in debug_env_vars):
        with nullcontext():
            yield
        return

    with open(os.devnull, "w") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            yield


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
