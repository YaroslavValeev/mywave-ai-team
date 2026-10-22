import ast
import importlib.util
import json
import os
import secrets
import stat
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location(
    "owner_activation",
    Path(__file__).resolve().parents[2] / "scripts/server/activate_club_box_owner.py",
)
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


def test_approval_uses_canonical_server_path_on_windows_and_linux():
    assert (
        activation.PLAN["secret_folder"]
        == "/opt/mywave/ai-team-runtime/private/club-box"
    )
    assert (
        activation.plan_hash()
        == "b16464db3213341805d45c06d5be89db70a239bedae0099e0f5745bb779cc3e3"
    )


def test_profile_changes_only_app_auth_and_references_external_secret():
    original = {
        "services": {
            "app": {
                "image": "same",
                "environment": {"KEEP": "same"},
                "volumes": ["same"],
            },
            "other": {"env_file": ["shared.env"]},
        }
    }
    result = activation.render(original)
    app = result["services"]["app"]
    assert app["image"] == "same" and app["volumes"] == ["same"]
    assert result["services"]["other"] == original["services"]["other"]
    assert "env_file" not in original["services"]["app"]
    assert app["env_file"] == [str(activation.KEY_FILE)]
    env = app["environment"]
    assert env["WORKSPACE_ACCESS_ENABLED"] == "true"
    assert env["WORKSPACE_OWNER_PRINCIPAL_ID"] == ""
    assert json.loads(env["WORKSPACE_PRINCIPAL_BINDINGS_JSON"]) == [
        {"principal_id": "owner:yaroslav", "key_env": activation.KEY_ENV}
    ]
    assert activation.KEY_ENV not in env


def test_inline_shadowed_secret_is_rejected():
    with pytest.raises(RuntimeError, match="shadowed"):
        activation.render(
            {
                "services": {
                    "app": {"environment": {activation.KEY_ENV: "not-a-real-key"}}
                }
            }
        )


def test_generated_probe_is_valid_and_reads_both_keys_from_environment():
    ops = Mock()
    ops.command.return_value = b'{"status":200}'
    activation.probe(ops, "shared")
    code = ops.command.call_args.args[0][-1]
    ast.parse(code)
    assert "OWNER_API_KEY" in code and activation.KEY_ENV in code
    assert "__KEY__" not in code and "__URL__" not in code


def test_wrong_owner_gate_fails_before_operations_or_secrets(monkeypatch):
    ops = Mock()
    monkeypatch.setattr(activation, "load_ops", ops)
    monkeypatch.setattr(
        "sys.argv", ["activate", "--execute", "--owner-approved-plan", "wrong"]
    )
    with pytest.raises(RuntimeError, match="owner-approved"):
        activation.main()
    ops.assert_not_called()


def test_failed_auth_verification_restores_previous_same_image_profile(
    tmp_path, monkeypatch
):
    config = tmp_path / "candidate.json"
    original = json.dumps({"services": {"app": {"image": activation.IMAGE}}}).encode()
    config.write_bytes(original)
    monkeypatch.setattr(activation, "PRIVATE", tmp_path)
    key_file = tmp_path / "owner.env"
    key_file.write_text("synthetic fixture only")
    (tmp_path / "credential.json").write_text("{}")
    monkeypatch.setattr(activation, "KEY_FILE", key_file)
    monkeypatch.setattr(activation, "prepare_secret", lambda: True)
    monkeypatch.setattr(activation, "read_secret", lambda: "synthetic-dedicated")
    monkeypatch.setattr(activation, "wait_ready", Mock())
    monkeypatch.setattr(
        activation, "verify_access", Mock(side_effect=RuntimeError("failed test"))
    )
    ops = Mock()
    ops.COMPOSE = [None, None, config]
    ops.environment.return_value = {"OWNER_API_KEY": "synthetic-shared"}
    ops.compose.return_value = json.dumps(
        {
            "services": {
                "app": {"environment": {activation.KEY_ENV: "synthetic-dedicated"}}
            }
        }
    ).encode()
    ops.atomic_write.side_effect = lambda p, b: p.write_bytes(b)
    with pytest.raises(RuntimeError, match="same image restored"):
        activation.execute(ops)
    assert config.read_bytes() == original
    assert activation.wait_ready.call_args.args[1] is False


@pytest.fixture
def private_paths(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("Server POSIX permissions are qualified in Linux Docker")
    tmp_path.chmod(0o700)
    private = tmp_path / "private/club-box"
    monkeypatch.setattr(activation, "RUNTIME", tmp_path)
    monkeypatch.setattr(activation, "PRIVATE", private)
    monkeypatch.setattr(activation, "KEY_FILE", private / "owner.env")
    return private


def test_secret_is_generated_once_private_and_never_printed(private_paths, capsys):
    assert activation.prepare_secret() is True
    first = activation.read_secret()
    assert len(first) == 64
    assert activation.prepare_secret() is False
    assert activation.read_secret() == first
    assert stat.S_IMODE(private_paths.stat().st_mode) == 0o700
    assert stat.S_IMODE(activation.KEY_FILE.stat().st_mode) == 0o600
    assert first not in capsys.readouterr().out


def test_world_readable_credential_is_rejected(private_paths):
    activation.prepare_secret()
    activation.KEY_FILE.chmod(0o644)
    with pytest.raises(RuntimeError, match="permissions"):
        activation.read_secret()


def test_symlink_secret_and_wrong_metadata_are_left_untouched(private_paths, tmp_path):
    activation.prepare_secret()
    original = activation.KEY_FILE.read_bytes()
    metadata = private_paths / "credential.json"
    metadata.write_text("{}")
    with pytest.raises(RuntimeError, match="another plan"):
        activation.prepare_secret()
    assert activation.KEY_FILE.read_bytes() == original
    activation.KEY_FILE.unlink()
    activation.KEY_FILE.symlink_to(tmp_path / "outside")
    with pytest.raises(RuntimeError):
        activation.prepare_secret()


# Real HTTP fixtures use disposable databases, never production credentials.
from test_workspace_schema import engine, session  # noqa: E402,F401
from test_workspace_integration import configured, client, prefix  # noqa: E402,F401


@pytest.fixture
def owner_http(configured, session, monkeypatch):
    from sqlalchemy import select
    from app.storage.models import ProjectAccessGrant, WorkspaceMembership

    for model in (WorkspaceMembership, ProjectAccessGrant):
        session.scalar(select(model)).principal_id = "owner:yaroslav"
    session.commit()
    profile = activation.render({"services": {"app": {}}})
    for key, value in profile["services"]["app"]["environment"].items():
        monkeypatch.setenv(key, value)
    token = secrets.token_urlsafe(48)
    monkeypatch.setenv(activation.KEY_ENV, token)
    return configured, {"X-API-Key": token}


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("dedicated", 200),
        ("none", 403),
        ("wrong", 403),
        ("shared", 403),
        ("shared_cookie", 403),
    ],
)
def test_only_dedicated_owner_key_authenticates(owner_http, kind, expected):
    from app.shared.dashboard_session import sign_owner_session, COOKIE_NAME

    data, headers = owner_http
    if kind == "none":
        headers = {}
    elif kind == "wrong":
        headers = {"X-API-Key": secrets.token_urlsafe(48)}
    elif kind == "shared":
        headers = {"X-API-Key": os.environ["OWNER_API_KEY"]}
    browser = client()
    if kind == "shared_cookie":
        headers = {}
        browser.cookies.set(COOKIE_NAME, sign_owner_session())
    assert browser.get(prefix(data) + "/tasks", headers=headers).status_code == expected


def test_dedicated_key_has_no_cross_product_access(owner_http):
    data, headers = owner_http
    response = client().get(
        f"/api/workspaces/{data[1]}/projects/{data[2]+1}/tasks", headers=headers
    )
    assert response.status_code == 403


def test_revoked_owner_grant_is_denied_on_next_request(owner_http, session):
    from datetime import datetime
    from app.storage.models import ProjectAccessGrant

    data, headers = owner_http
    assert client().get(prefix(data) + "/tasks", headers=headers).status_code == 200
    session.get(ProjectAccessGrant, data[5]).revoked_at = datetime.utcnow()
    session.commit()
    assert client().get(prefix(data) + "/tasks", headers=headers).status_code == 403
