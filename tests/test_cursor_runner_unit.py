# Unit-тесты Cursor runner: разбор argv и gateway env (без реального cursor в PATH).


def test_build_cursor_argv_empty_uses_version():
    from app.runners.cursor_runner.runner import build_cursor_argv

    argv = build_cursor_argv("", binary="/custom/cursor")
    assert argv == ["/custom/cursor", "--version"]


def test_build_cursor_argv_custom_args():
    from app.runners.cursor_runner.runner import build_cursor_argv

    argv = build_cursor_argv("tunnel --help", binary="/bin/cursor")
    assert argv[0] == "/bin/cursor"
    assert argv[1] == "tunnel"
    assert argv[-1] == "--help"


def test_build_cursor_argv_passes_when_first_token_is_cursor():
    from app.runners.cursor_runner.runner import build_cursor_argv

    argv = build_cursor_argv("cursor --version", binary="/ignored/cursor")
    assert argv[0] == "cursor"
    assert argv[1] == "--version"


def test_get_runner_config_has_cursor_binary():
    from app.runners.cursor_runner.runner import get_runner_config

    cfg = get_runner_config()
    assert "cursor_binary" in cfg
    assert "timeout_sec" in cfg


def test_resolve_cursor_binary_respects_cursor_cli(monkeypatch, tmp_path):
    fake = tmp_path / "cursor.cmd"
    fake.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("CURSOR_CLI", str(fake))
    from app.runners.cursor_runner.runner import resolve_cursor_binary

    assert resolve_cursor_binary() == str(fake.resolve())


def test_smoke_cursor_version_when_binary_exists():
    """Live smoke: cursor --version via runner. Skips if binary missing (CI without Cursor)."""
    import asyncio
    from pathlib import Path

    from app.runners.cursor_runner.runner import get_runner_config, run_cursor_cli

    cfg = get_runner_config()
    if not cfg.get("cursor_binary_exists"):
        import pytest

        pytest.skip("cursor CLI not installed / not on PATH")

    code, out, err = asyncio.run(run_cursor_cli(str(Path(".").resolve()), "", timeout_sec=30))
    assert code == 0, f"cursor --version failed: exit={code} stderr={err!r}"
    assert out.strip(), "expected non-empty version stdout"
