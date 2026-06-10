from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from services.analyze_service import AnalyzeService


router = APIRouter()


@router.post("/analyze")
def analyze(
    files: list[UploadFile] = File(...),
) -> dict:
    try:
        result = AnalyzeService().analyze_files(files)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc),
            },
        )

    return {
        "success": True,
        "report_id": result["report_id"],
    }
