from fastapi import APIRouter
from fastapi.responses import JSONResponse

from repositories.report_repository import ReportRepository


router = APIRouter()


@router.get("/reports")
def list_reports() -> list[dict]:
    repository = ReportRepository()

    try:
        return repository.list_reports()
    finally:
        repository.close()


@router.get("/reports/{report_id}")
def get_report(report_id: int):
    repository = ReportRepository()

    try:
        report = repository.get_report(report_id)
    finally:
        repository.close()

    if report is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Report not found"},
        )

    return report


@router.get("/reports/{report_id}/entities")
def get_entities_for_report(report_id: int) -> list[dict]:
    repository = ReportRepository()

    try:
        return repository.get_entities_for_report(report_id)
    finally:
        repository.close()


@router.get("/entities/{entity_id}")
def get_entity(entity_id: int):
    repository = ReportRepository()

    try:
        result = repository.get_entity(entity_id)
    finally:
        repository.close()

    if result is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Entity not found"},
        )

    return result
