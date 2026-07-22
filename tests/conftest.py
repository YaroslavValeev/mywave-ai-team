# tests/conftest.py — HF-4: SQLite in-memory, 0 skipped
import os

import pytest
from fastapi.testclient import TestClient

# До импорта приложения: SQLite в памяти и детерминированный ключ (не setdefault с хоста).
if not os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL") in ("postgresql+psycopg2://", "postgresql://"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OWNER_API_KEY"] = os.environ.get("PYTEST_OWNER_API_KEY", "test_key_for_smoke")
# Без вызовов LLM в CI: pytest по умолчанию rule_based (роли CrewAI не трогаем сеть).
os.environ.setdefault("ORCHESTRATION_ENGINE", "rule_based")

from app.dashboard.app import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    key = os.environ.get("OWNER_API_KEY", "test_key_for_smoke")
    return {"X-API-Key": key}


@pytest.fixture(scope="function")
def db_session():
    """Сессия БД — SQLite in-memory. Чистая схема перед каждым тестом."""
    from app.orchestrator.runtime import get_orchestration_runtime
    from app.storage.repositories import get_engine, get_session_factory
    from app.storage.models import Base

    get_orchestration_runtime().reset_for_tests()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = get_session_factory()
    with Session() as session:
        from app.owner_memory.seed import ensure_canonical_owner_memory
        from app.storage.repositories import TaskRepository

        ensure_canonical_owner_memory(TaskRepository(session))
        yield session
    get_orchestration_runtime().reset_for_tests()
