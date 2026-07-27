from pathlib import Path


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

    assert resolve_status_after_approve(Outreach(), has_pr=False) == "EXECUTION_READY"
    assert resolve_status_after_approve(Other(), has_pr=False) == "DONE"
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
