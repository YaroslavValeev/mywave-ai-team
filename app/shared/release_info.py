import os


def get_release_info() -> dict[str, str]:
    """Return public, non-secret metadata for runtime identification."""
    return {
        "version": (os.getenv("APP_VERSION") or "dev").strip(),
        "commit_sha": (os.getenv("APP_COMMIT_SHA") or "unknown").strip(),
        "environment": (os.getenv("APP_ENVIRONMENT") or "local").strip(),
    }
