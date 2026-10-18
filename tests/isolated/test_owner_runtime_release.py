import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "scripts/server/release_owner_runtime_20261018.py"
)
spec = importlib.util.spec_from_file_location("pinned_release", SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_success_persists_only_candidate_configs(tmp_path):
    first, second = tmp_path / "release.yml", tmp_path / "execution.yml"
    first.write_bytes(b"old-release")
    second.write_bytes(b"old-execution")
    up, old = Mock(), Mock()
    result = release.apply_release(
        {first: b"new-release", second: b"new-execution"},
        up,
        lambda: {"verified": True},
        old,
    )
    assert result == {"verified": True}
    assert first.read_bytes() == b"new-release"
    assert second.read_bytes() == b"new-execution"
    up.assert_called_once()
    old.assert_not_called()


def test_failed_readiness_restores_both_configs_and_previous_app(tmp_path):
    first, second = tmp_path / "release.yml", tmp_path / "execution.yml"
    first.write_bytes(b"old-release")
    second.write_bytes(b"old-execution")
    up, old = Mock(), Mock()
    with pytest.raises(RuntimeError, match="previous app and configuration restored"):
        release.apply_release(
            {first: b"new-release", second: b"new-execution"},
            up,
            Mock(side_effect=RuntimeError("readiness failed")),
            old,
        )
    assert first.read_bytes() == b"old-release"
    assert second.read_bytes() == b"old-execution"
    assert up.call_count == 2
    old.assert_called_once()


def test_failed_rollback_is_never_reported_as_restored(tmp_path):
    config = tmp_path / "release.yml"
    config.write_bytes(b"old")
    with pytest.raises(RuntimeError, match="rollback verification failed"):
        release.apply_release(
            {config: b"new"},
            Mock(),
            Mock(side_effect=RuntimeError()),
            Mock(side_effect=RuntimeError()),
        )
    assert config.read_bytes() == b"old"


@pytest.mark.parametrize(
    "changed",
    [
        {"source_sha": "wrong"},
        {"image_id": "wrong"},
        {"pytest_exit": 1},
        {"tests": {"tests": 378, "errors": 0, "failures": 1, "skipped": 1}},
    ],
)
def test_mismatched_qualification_blocks_rollout(changed):
    proof = {
        "source_sha": release.SOURCE_SHA,
        "image_id": release.IMAGE_ID,
        "base_image_id": release.BASE_ID,
        "pytest_exit": 0,
        "tests": {"tests": 378, "errors": 0, "failures": 0, "skipped": 1},
    }
    release.check_proof(proof)
    proof.update(changed)
    with pytest.raises(RuntimeError, match="qualification"):
        release.check_proof(proof)


def test_execution_without_exact_owner_gate_stops_before_preflight(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["release", "--execute", "--owner-approved-sha", "wrong"]
    )
    prepare = Mock()
    monkeypatch.setattr(release, "prepare", prepare)
    with pytest.raises(SystemExit) as error:
        release.main()
    assert error.value.code == 2
    prepare.assert_not_called()


@pytest.mark.parametrize(
    "target",
    [
        "/app",
        "/app/app",
        "/app/app/orchestrator",
        "/app/packages/shared-core",
        "/app/src/code.py",
    ],
)
def test_code_mounts_cannot_misrepresent_image_identity(target):
    with pytest.raises(RuntimeError, match="source-code mount"):
        release.verify_source_mounts([{"Destination": target}])


def test_artifacts_and_execution_workspace_mounts_are_preserved():
    release.verify_source_mounts(
        [{"Destination": "/app/app/artifacts"}, {"Destination": "/execution/ai-team"}]
    )
