from pathlib import Path
import stat

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config.settings import RPG_DATABASE_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_database_path(path: str) -> Path:
    database_path = Path(path).expanduser()

    if database_path.is_absolute():
        return database_path

    return PROJECT_ROOT / database_path


DATABASE_PATH = _resolve_database_path(RPG_DATABASE_PATH)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
Base = declarative_base()


def ensure_database_path() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DATABASE_PATH.exists():
        return

    mode = DATABASE_PATH.stat().st_mode

    if mode & stat.S_IWUSR:
        return

    DATABASE_PATH.chmod(mode | stat.S_IWUSR)


def is_readonly_database_error(error: BaseException) -> bool:
    if not isinstance(error, OperationalError):
        return False

    return "readonly database" in str(error).lower()


def recover_database_connection() -> None:
    engine.dispose()
    init_db()


def init_db() -> None:
    from persistence import models  # noqa: F401

    ensure_database_path()
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
