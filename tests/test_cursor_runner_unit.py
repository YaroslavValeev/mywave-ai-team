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


def test_merge_gateway_secrets_respects_existing_gh(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "already_set")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    from app.runners.cursor_runner.local_env import merge_gateway_secrets_into_env

    m = merge_gateway_secrets_into_env({"CUSTOM": "1"})
    assert m.get("GH_TOKEN") == "already_set"
    assert m.get("CUSTOM") == "1"
