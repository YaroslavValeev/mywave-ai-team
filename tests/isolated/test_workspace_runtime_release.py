import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


spec = importlib.util.spec_from_file_location(
    "workspace_release",
    Path(__file__).resolve().parents[2]
    / "scripts/server/release_workspace_runtime_20261021.py",
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize(
    "state",
    [
        {"migration": "009", "active": 0, "scoped_schema": True, "scoped_records": 0},
        {"migration": "007", "active": 1, "scoped_schema": False, "scoped_records": 0},
        {"migration": "007", "active": 0, "scoped_schema": True, "scoped_records": 1},
    ],
)
def test_changed_schema_or_active_mission_blocks_cutover(state):
    with pytest.raises(RuntimeError):
        release.check_idle(state)


def test_idle_007_baseline_is_accepted():
    release.check_idle(
        {"migration": "007", "active": 0, "scoped_schema": False, "scoped_records": 0}
    )


@pytest.mark.parametrize(
    "state",
    [
        {"migration": "009", "scoped_schema": True, "scoped_records": 0},
        {"migration": "008", "scoped_schema": True, "scoped_records": 0},
        {"migration": "007", "scoped_schema": True, "scoped_records": 4},
    ],
)
def test_old_app_never_restarted_after_schema_change(monkeypatch, state):
    compose, write, ready = Mock(), Mock(), Mock()
    monkeypatch.setattr(release, "compose", compose)
    monkeypatch.setattr(release, "atomic_write", write)
    monkeypatch.setattr(release, "wait_ready", ready)
    monkeypatch.setattr(release, "db_state", lambda: state)
    with pytest.raises(RuntimeError, match="MAINTENANCE REQUIRED"):
        release.recover(b"old configuration")
    compose.assert_called_once_with("stop", "-t", "30", "app")
    write.assert_not_called()
    ready.assert_not_called()


def test_007_recovery_restores_previous_configuration_and_checks_readiness(monkeypatch):
    compose, write, ready = Mock(), Mock(), Mock()
    monkeypatch.setattr(release, "compose", compose)
    monkeypatch.setattr(release, "atomic_write", write)
    monkeypatch.setattr(release, "wait_ready", ready)
    monkeypatch.setattr(
        release,
        "db_state",
        lambda: {"migration": "007", "scoped_schema": False, "scoped_records": 0},
    )
    assert "restored and verified" in release.recover(b"old")
    write.assert_called_once_with(release.COMPOSE[2], b"old")
    ready.assert_called_once_with(release.OLD_IMAGE, release.OLD_SOURCE, "007")
    assert compose.call_count == 2


def test_wrong_owner_gate_fails_before_inspecting_production(monkeypatch):
    inspect = Mock()
    monkeypatch.setattr(release, "inspect", inspect)
    monkeypatch.setattr(
        "sys.argv", ["release", "--execute", "--owner-approved-sha", "wrong"]
    )
    with pytest.raises(SystemExit) as error:
        release.main()
    assert error.value.code == 2
    inspect.assert_not_called()


@pytest.mark.parametrize(
    "value", ["2020-01-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00"]
)
def test_stale_or_future_proof_is_rejected(value):
    with pytest.raises(RuntimeError):
        release.check_age(value)


def test_backup_checksum_rejects_changed_dump_and_path_escape(tmp_path):
    (tmp_path / "database.dump").write_bytes(b"changed")
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  database.dump\n")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        release.verify_sums(tmp_path)
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  ../private\n")
    with pytest.raises(RuntimeError, match="Unsafe checksum filename"):
        release.verify_sums(tmp_path)


def test_image_profile_disables_intake_and_keeps_build_identity(monkeypatch, tmp_path):
    profile = {
        "services": {
            "app": {
                "image": "old",
                "environment": {"KEEP": "same"},
                "volumes": ["unchanged"],
            }
        }
    }
    path = tmp_path / "candidate.yml"
    path.write_text("old")
    monkeypatch.setattr(release, "COMPOSE", [None, None, path])
    monkeypatch.setattr(
        release, "command", lambda *a, **kw: json.dumps(profile).encode()
    )
    monkeypatch.setattr(
        release,
        "inspect",
        lambda name: {
            "Config": {
                "Env": [
                    "APP_COMMIT_SHA=" + release.SOURCE,
                    "APP_VERSION=qualified",
                    "APP_BUILD_TIMESTAMP=2026-10-19T19:43:52Z",
                ]
            }
        },
    )
    actual = json.loads(release.new_profile({}))["services"]["app"]
    assert actual["image"] == release.IMAGE
    assert actual["volumes"] == ["unchanged"]
    assert actual["environment"]["KEEP"] == "same"
    assert actual["environment"]["WORKSPACE_ACCESS_ENABLED"] == "false"
    assert actual["environment"]["WORKSPACE_PRINCIPAL_BINDINGS_JSON"] == "[]"
    assert actual["environment"]["WORKSPACE_OWNER_PRINCIPAL_ID"] == ""
    assert actual["environment"]["APP_BUILD_TIMESTAMP"] == "2026-10-19T19:43:52Z"


def test_source_mount_injection_is_rejected():
    with pytest.raises(RuntimeError, match="mounts"):
        release.check_mounts(
            [{"Type": "bind", "Source": "/tmp/source", "Destination": "/app/app"}]
        )


def test_missing_same_token_singleton_is_rejected(monkeypatch):
    monkeypatch.setattr(
        release,
        "command",
        lambda args: (
            b"one two"
            if args[1] == "ps"
            else json.dumps(
                [
                    {
                        "Name": "/ai-team-app-1",
                        "Config": {"Env": ["TELEGRAM_BOT_TOKEN=synthetic"]},
                    },
                    {"Name": "/competing", "Config": {"Env": ["BOT_TOKEN=synthetic"]}},
                ]
            ).encode()
        ),
    )
    with pytest.raises(RuntimeError, match="Another running container"):
        release.check_pollers({"Config": {"Env": ["TELEGRAM_BOT_TOKEN=synthetic"]}})
