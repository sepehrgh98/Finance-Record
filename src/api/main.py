import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.analyze import router as analyze_router
from api.routes.reports import router as reports_router
from persistence.database import init_db


class ProgressAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not (
            "GET /analyze/" in message
            and "/progress HTTP/" in message
        )


logging.getLogger("uvicorn.access").addFilter(ProgressAccessLogFilter())

app = FastAPI(title="RPG Document Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(analyze_router)
app.include_router(reports_router)
