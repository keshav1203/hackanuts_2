import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

log = logging.getLogger(__name__)


def create_app_engine():
    db_url = settings.database_url
    if db_url.startswith("postgresql"):
        try:
            # Check if PostgreSQL server is reachable with a short timeout
            test_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=5,
                connect_args={"connect_timeout": 3},
            )
            with test_engine.connect() as conn:
                pass
            log.info("Successfully connected to PostgreSQL database at %s", db_url.split("@")[-1])
            return test_engine
        except Exception as exc:
            log.warning(
                "PostgreSQL unreachable (%s). Automatically falling back to local SQLite database (scaleai.db).",
                type(exc).__name__,
            )
            db_url = "sqlite:///./scaleai.db"

    return create_engine(
        db_url,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        pool_pre_ping=True,
    )


engine = create_app_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
