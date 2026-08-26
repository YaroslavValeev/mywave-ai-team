from sqlalchemy import create_engine, text

from app.shared.migration_info import get_current_migration_version
from app.shared.release_info import get_release_info


def test_release_info_has_safe_defaults(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("APP_COMMIT_SHA", raising=False)
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_BUILD_TIMESTAMP", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_release_info() == {
        "version": "dev",
        "commit_sha": "unknown",
        "environment": "local",
        "build_timestamp": "unknown",
        "migration_version": "unknown",
    }


def test_release_info_reads_runtime_metadata(monkeypatch, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'release.db'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('007_intake_drafts')"))
    engine.dispose()

    monkeypatch.setenv("APP_VERSION", "v1.0.0")
    monkeypatch.setenv("APP_COMMIT_SHA", "abc123")
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_BUILD_TIMESTAMP", "2026-08-25T10:15:00Z")
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert get_release_info() == {
        "version": "v1.0.0",
        "commit_sha": "abc123",
        "environment": "production",
        "build_timestamp": "2026-08-25T10:15:00Z",
        "migration_version": "007_intake_drafts",
    }


def test_release_info_replaces_blank_metadata_with_defaults(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "  ")
    monkeypatch.setenv("APP_COMMIT_SHA", "")
    monkeypatch.setenv("APP_ENVIRONMENT", "\t")
    monkeypatch.setenv("APP_BUILD_TIMESTAMP", " ")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_release_info() == {
        "version": "dev",
        "commit_sha": "unknown",
        "environment": "local",
        "build_timestamp": "unknown",
        "migration_version": "unknown",
    }


def test_migration_version_has_no_database_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_current_migration_version() == "unknown"
    assert get_current_migration_version("invalid-database-url") == "unknown"


def test_migration_version_handles_database_without_alembic_table(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'unversioned.db'}"

    assert get_current_migration_version(database_url) == "unknown"


def test_system_release_endpoint_exposes_build_identity(client, auth_headers, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v1-test")
    monkeypatch.setenv("APP_COMMIT_SHA", "test-sha")
    monkeypatch.setenv("APP_BUILD_TIMESTAMP", "2026-08-27T10:00:00Z")
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = client.get("/api/system/release", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "version": "v1-test",
        "commit_sha": "test-sha",
        "environment": "test",
        "build_timestamp": "2026-08-27T10:00:00Z",
        "migration_version": "unknown",
    }
