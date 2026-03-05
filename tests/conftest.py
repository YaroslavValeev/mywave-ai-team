# tests/conftest.py — HF-4: SQLite in-memory, 0 skipped
import os
import pytest

# Smoke tests: SQLite + OWNER_API_KEY
if not os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL") in ("postgresql+psycopg2://", "postgresql://"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")


@pytest.fixture(scope="function")
def db_session():
    """Сессия БД — SQLite in-memory. Чистая схема перед каждым тестом."""
    from app.storage.repositories import get_engine, get_session_factory
    from app.storage.models import Base

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = get_session_factory()
    with Session() as session:
        yield session
