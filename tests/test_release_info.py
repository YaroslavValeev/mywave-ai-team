from app.shared.release_info import get_release_info


def test_release_info_has_safe_defaults(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("APP_COMMIT_SHA", raising=False)
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)

    assert get_release_info() == {
        "version": "dev",
        "commit_sha": "unknown",
        "environment": "local",
    }


def test_release_info_reads_runtime_metadata(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v1.0.0")
    monkeypatch.setenv("APP_COMMIT_SHA", "abc123")
    monkeypatch.setenv("APP_ENVIRONMENT", "production")

    assert get_release_info() == {
        "version": "v1.0.0",
        "commit_sha": "abc123",
        "environment": "production",
    }
