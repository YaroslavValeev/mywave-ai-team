from pathlib import Path
from types import SimpleNamespace

import pytest


def test_task_wants_outreach_by_task_type():
    from app.orchestrator.execution_pack import task_wants_outreach_execute

    class T:
        task_type = "content_pipeline"
        business_action_json = {}
        handoffs = []

    assert task_wants_outreach_execute(T()) is True


def test_task_wants_outreach_by_cluster():
    from app.orchestrator.execution_pack import task_wants_outreach_execute

    class T:
        task_type = "other"
        business_action_json = {"triage_meta": {"agent_cluster": "MEDIA"}}
        handoffs = []

    assert task_wants_outreach_execute(T()) is True


def test_prepare_pack_writes_files(db_session, tmp_path, monkeypatch):
    from app.storage.repositories import TaskRepository
    from app.orchestrator import execution_pack as ep

    monkeypatch.setattr(ep, "ARTIFACTS_DIR", tmp_path)

    repo = TaskRepository(db_session)
    task = repo.create_task(
        owner_text="# TASK напиши дружелюбное сообщение участникам и собери контакты ParserNews"
    )
    repo.update_task(task.id, task_type="content_pipeline", status="WAIT_OWNER")
    repo.add_handoff(
        task_id=task.id,
        step_index=0,
        step_name="CONTENT",
        payload={
            "deliverable": {
                "kind": "message_draft",
                "title": "Черновик",
                "body_lines": ["Привет! Это команда MyWave 👋", "Будем рады видеть вас на воде!"],
            }
        },
    )
    task = repo.get_task(task.id)

    result = ep.prepare_outreach_execution_pack(repo, task.id, source="test")
    assert result["ok"] is True
    pack = Path(result["pack_path"])
    msg = Path(result["message_path"])
    assert pack.is_file()
    text = msg.read_text(encoding="utf-8")
    # Fresh content_intent wins over stale handoff body_lines
    assert "yclients.com/company/2043174" in text
    assert "yandex.ru/maps/org/mywave_wake" in text
    assert ">Озернинском</a>" in text
    assert ">тут</a>" in text
    assert "чемпион Москвы 2026" in text
    assert "мой ученик" in text
    assert "Привет! Это команда MyWave" in text
    refreshed = repo.get_task(task.id)
    ba = refreshed.business_action_json or {}
    assert ba.get("execution_ready") is True
    assert ba.get("execution_pack", {}).get("auto_send") is False


def test_resolve_status_after_approve():
    from app.orchestrator.execution_pack import resolve_status_after_approve

    class Outreach:
        task_type = "content_pipeline"
        business_action_json = {}
        handoffs = []

    class Other:
        task_type = "deploy_prod"
        business_action_json = {}
        handoffs = []

    class CodeExecution:
        task_type = "code_change"
        business_action_json = {"execution_request": {"executor": "code_pr"}}
        handoffs = []

    assert resolve_status_after_approve(Outreach(), has_pr=False) == "EXECUTION_READY"
    assert resolve_status_after_approve(Other(), has_pr=False) == "DONE"
    assert resolve_status_after_approve(CodeExecution(), has_pr=False) == "EXECUTION_READY"
    assert resolve_status_after_approve(Outreach(), has_pr=True) == "APPROVED_WAIT_MERGE"


def test_api_approve_creates_execution_pack(db_session, tmp_path, monkeypatch):
    from app.storage.repositories import TaskRepository
    from app.dashboard.api import common as api_common
    from app.orchestrator import execution_pack as ep

    monkeypatch.setattr(ep, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(api_common, "ARTIFACTS_DIR", tmp_path)

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK outreach ParserNews сообщение")
    repo.update_task(task.id, task_type="content_pipeline", status="WAIT_OWNER")
    repo.add_handoff(
        task_id=task.id,
        step_index=0,
        step_name="CONTENT",
        payload={
            "deliverable": {
                "kind": "message_draft",
                "body_lines": ["Привет тест"],
            }
        },
    )

    out = api_common.apply_owner_decision(repo, task.id, "approve", source="test")
    assert out["status"] == "EXECUTION_READY"
    assert out.get("execution_pack", {}).get("ok") is True
    assert Path(out["execution_pack"]["pack_path"]).is_file()


@pytest.mark.parametrize("execution_request", [{"executor": "code_pr"}, None])
def test_non_outreach_pack_has_no_side_effects(tmp_path, monkeypatch, execution_request):
    from app.orchestrator import execution_pack as ep

    task = SimpleNamespace(
        task_type="content_pipeline" if execution_request else "feature_delivery",
        business_action_json={"execution_request": execution_request} if execution_request else {},
        handoffs=[],
    )
    if execution_request:
        task.business_action_json["triage_meta"] = {"agent_cluster": "MEDIA"}
        task.handoffs = [SimpleNamespace(payload_json={"deliverable": {"kind": "message_draft"}})]
    monkeypatch.setattr(ep, "ARTIFACTS_DIR", tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Skipped pack must not read contacts or mutate task")

    monkeypatch.setattr(ep, "_find_contacts_csv", forbidden)
    repo = SimpleNamespace(get_task=lambda _: task, update_task=forbidden, add_audit_event=forbidden)
    assert ep.prepare_outreach_execution_pack(repo, 38) == {
        "ok": False, "reason": "not_outreach", "task_id": 38,
    }
    assert not list(tmp_path.iterdir())


def test_code_approval_does_not_prepare_outreach_pack(db_session, tmp_path, monkeypatch):
    import subprocess
    from app.storage.repositories import TaskRepository
    from app.dashboard.api import common as api_common
    from app.orchestrator import execution_pack as ep

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for command in (
        ["git", "init"],
        ["git", "config", "user.name", "Test"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "commit", "--allow-empty", "-m", "initial"],
    ):
        subprocess.run(command, cwd=workspace, check=True, capture_output=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    patch = artifacts / "approved.patch"
    patch.write_text("approved patch bytes")
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS", str(workspace))
    monkeypatch.setattr(ep, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(api_common, "ARTIFACTS_DIR", artifacts)

    def forbidden(*args, **kwargs):
        raise AssertionError("Code approval must not inspect contact lists")

    monkeypatch.setattr(ep, "_find_contacts_csv", forbidden)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Review approved code patch")
    repo.update_task(task.id, task_type="feature_delivery", status="WAIT_OWNER", business_action_json={
        "execution_request": {
            "executor": "code_pr", "mode": "patch",
            "workspace_path": str(workspace), "patch_path": str(patch),
        },
    })
    result = api_common.apply_owner_decision(repo, task.id, "approve", source="test")
    assert result["status"] == "EXECUTION_READY"
    assert "execution_pack" not in result
    assert "execution_pack" not in repo.get_task(task.id).business_action_json
    summary = repo.get_task(task.id).summary
    assert "Owner утвердил patch" in summary
    assert "message_to_send.txt" not in summary
    assert not (artifacts / "tasks" / f"task_{task.id}" / "execution").exists()
