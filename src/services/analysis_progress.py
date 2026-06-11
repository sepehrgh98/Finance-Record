from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class AnalysisProgressStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._progress: dict[str, dict[str, Any]] = {}

    def start(self, analysis_id: str) -> None:
        self.update(
            analysis_id,
            status="running",
            percent=1,
            message="Preparing upload workspace",
        )

    def update(
        self,
        analysis_id: str,
        *,
        status: str = "running",
        percent: int | None = None,
        message: str,
        detail: str = "",
        report_id: int | None = None,
        error: str = "",
    ) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "detail": detail,
        }

        with self._lock:
            current = self._progress.get(
                analysis_id,
                {
                    "analysis_id": analysis_id,
                    "status": "pending",
                    "percent": 0,
                    "message": "",
                    "detail": "",
                    "events": [],
                    "report_id": None,
                    "error": "",
                },
            )
            current["status"] = status
            current["message"] = message
            current["detail"] = detail
            current["error"] = error

            if percent is not None:
                current["percent"] = max(
                    current.get("percent", 0),
                    min(100, max(0, int(percent))),
                )

            if report_id is not None:
                current["report_id"] = report_id

            current["events"] = [*current.get("events", []), event][-40:]
            self._progress[analysis_id] = current

    def complete(self, analysis_id: str, report_id: int) -> None:
        self.update(
            analysis_id,
            status="complete",
            percent=100,
            message="Report ready",
            detail=f"Report #{report_id}",
            report_id=report_id,
        )

    def fail(self, analysis_id: str, error: str) -> None:
        self.update(
            analysis_id,
            status="error",
            percent=100,
            message="Analysis failed",
            detail=error,
            error=error,
        )

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self._lock:
            progress = self._progress.get(analysis_id)

            if progress is None:
                return None

            return deepcopy(progress)


progress_store = AnalysisProgressStore()
