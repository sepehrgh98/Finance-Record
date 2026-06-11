from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from services.analysis_progress import progress_store
from services.analyze_service import AnalyzeService


router = APIRouter()


@router.post("/analyze")
def analyze(
    files: list[UploadFile] = File(...),
    analysis_id: str | None = Form(default=None),
) -> dict:
    analysis_id = analysis_id or uuid4().hex
    progress_store.start(analysis_id)

    def update_progress(percent: int, message: str, detail: str = "") -> None:
        progress_store.update(
            analysis_id,
            percent=percent,
            message=message,
            detail=detail,
        )

    try:
        result = AnalyzeService().analyze_files(
            files,
            analysis_id=analysis_id,
            progress_callback=update_progress,
        )
        progress_store.complete(analysis_id, result["report_id"])
    except Exception as exc:
        progress_store.fail(analysis_id, str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "analysis_id": analysis_id,
                "error": str(exc),
            },
        )

    return {
        "success": True,
        "analysis_id": analysis_id,
        "report_id": result["report_id"],
    }


@router.get("/analyze/{analysis_id}/progress")
def get_analysis_progress(analysis_id: str):
    progress = progress_store.get(analysis_id)

    if progress is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "Analysis progress not found",
            },
        )

    return {
        "success": True,
        **progress,
    }
