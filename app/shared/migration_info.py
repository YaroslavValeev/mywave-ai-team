import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


UNKNOWN_MIGRATION_VERSION = "unknown"


def _create_probe_engine(database_url: str) -> Engine:
    options: dict = {"pool_pre_ping": False}
    if database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        options["connect_args"] = {"connect_timeout": 2}
    return create_engine(database_url, **options)


def get_current_migration_version(database_url: str | None = None) -> str:
    """Read the applied Alembic revision without making DB health mandatory."""
    url = (database_url if database_url is not None else os.getenv("DATABASE_URL", "")).strip()
    if not url:
        return UNKNOWN_MIGRATION_VERSION

    engine: Engine | None = None
    try:
        engine = _create_probe_engine(url)
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).scalars()
            values = [
                str(revision).strip()
                for revision in revisions
                if revision is not None and str(revision).strip()
            ]
        return ",".join(values) or UNKNOWN_MIGRATION_VERSION
    except (SQLAlchemyError, OSError, ValueError):
        return UNKNOWN_MIGRATION_VERSION
    finally:
        if engine is not None:
            engine.dispose()
