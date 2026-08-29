import os

from app.shared.migration_info import get_current_migration_version


def _env_value(name: str, fallback: str) -> str:
    value = (os.getenv(name) or "").strip()
    return value or fallback


def get_release_info() -> dict[str, str]:
    """Return public, non-secret metadata for runtime identification."""
    return {
        "version": _env_value("APP_VERSION", "dev"),
        "commit_sha": _env_value("APP_COMMIT_SHA", "unknown"),
        "environment": _env_value("APP_ENVIRONMENT", "local"),
        "build_timestamp": _env_value("APP_BUILD_TIMESTAMP", "unknown"),
        "migration_version": get_current_migration_version(),
    }
