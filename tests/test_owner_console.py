from fastapi.testclient import TestClient

from app.dashboard.app import app


def test_console_missions_page_renders(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK console mission")
    repo.update_task(task.id, status="WAIT_OWNER", summary="Нужен owner approve", business_type="revenue", impact_level="high")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/missions", headers={"X-API-Key": "test_key_for_smoke"})
    assert r.status_code == 200
    assert "Owner Operating Console" in r.text
    assert f"/mission/{task.id}" in r.text
    assert "REVENUE" in r.text or "Высокий" in r.text


def test_console_mission_detail_renders_workflow_and_actions(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK details")
    repo.update_task(task.id, status="WAIT_OWNER", summary="ready")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/mission/{task.id}", headers={"X-API-Key": "test_key_for_smoke"})
    assert r.status_code == 200
    assert "Ход работы" in r.text or "Workflow View" in r.text
    assert "Что делать сейчас" in r.text
    assert "/approve" in r.text
    assert "/pause" in r.text
    assert "/resume" in r.text


def test_console_workflow_endpoint(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK workflow endpoint")
    repo.update_task(task.id, status="IN_PIPELINE")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/workflow/{task.id}", headers={"X-API-Key": "test_key_for_smoke"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["workflow_id"] == f"wf-{task.id}"
    assert payload["task_id"] == task.id
    assert isinstance(payload["steps"], list)


def test_console_approve_json_updates_status(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK approve")
    repo.update_task(task.id, status="WAIT_OWNER", summary="approve me")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        "/approve",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={"task_id": task.id},
    )
    assert r.status_code == 200
    db_session.expire_all()
    assert repo.get_task(task.id).status == "DONE"


def test_console_pause_resume_cancel_json(monkeypatch, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK runtime control")
    repo.update_task(task.id, status="REWORK")

    class _FakeRuntime:
        def snapshot(self, _task_id):
            return {"is_active": True, "state": "running", "phase": "pipeline"}

        def request_stop(self, _task_id):
            return {"state": "stopping", "is_active": True}

    monkeypatch.setattr("app.dashboard.app.get_orchestration_runtime", lambda: _FakeRuntime())
    monkeypatch.setattr(
        "app.dashboard.app._start_background_resume",
        lambda _task_id, source="console_resume": {"run_id": "fake123", "state": "running", "source": source},
    )

    client = TestClient(app, raise_server_exceptions=False)

    pause_resp = client.post(
        "/pause",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={"task_id": task.id},
    )
    assert pause_resp.status_code == 200
    assert pause_resp.json()["ok"] is True

    resume_resp = client.post(
        "/resume",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={"task_id": task.id},
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["runner"]["run_id"] == "fake123"

    cancel_resp = client.post(
        "/cancel",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={"task_id": task.id},
    )
    assert cancel_resp.status_code == 200
    db_session.expire_all()
    assert repo.get_task(task.id).status == "ARCHIVED"



def test_console_execution_pack_page(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK execution pack")
    repo.update_task(
        task.id,
        business_type="revenue",
        business_action_json={
            "execution_pack": {
                "action_title": "Подготовить оффер WakeSafari",
                "why": "привлечь первых клиентов",
                "ready_steps": ["структура", "текст"],
                "artifacts": ["оффер.md"],
                "how_to_execute": "отправить партнёрам",
                "time_estimate": "45 минут",
                "expected_result": "первые заявки",
                "pack_type": "offer_pack",
            }
        },
    )

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/mission/{task.id}/execution-pack", headers={"X-API-Key": "test_key_for_smoke"})
    assert r.status_code == 200
    assert "ГОТОВОЕ ДЕЙСТВИЕ" in r.text
    assert "Подготовить оффер WakeSafari" in r.text


def test_execution_pack_action_feedback_flow(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK action feedback")
    repo.update_task(
        task.id,
        business_type="revenue",
        business_action_json={
            "execution_pack": {
                "action_title": "Подготовить оффер",
                "why": "привлечь лиды",
                "ready_steps": ["шаг 1"],
                "artifacts": ["offer.md"],
                "how_to_execute": "сделать",
                "time_estimate": "30 минут",
                "expected_result": "лиды",
                "pack_type": "offer_pack",
            }
        },
    )

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        f"/mission/{task.id}/execution-pack/action",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={
            "status": "done",
            "result_summary": "получили 2 лида",
            "owner_feedback": "сработало",
            "result_type": "lead",
            "result_value": "2",
        },
    )
    assert r.status_code == 200
    db_session.expire_all()
    t = repo.get_task(task.id)
    assert t and isinstance(t.business_action_json, dict)
    ai = t.business_action_json.get("action_instance")
    assert isinstance(ai, dict)
    assert ai.get("status") == "done"


def test_execution_pack_markdown_export(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK md export")
    repo.update_task(
        task.id,
        business_action_json={
            "execution_pack": {
                "action_title": "Лендинг",
                "why": "конверсия",
                "ready_steps": ["hero"],
                "artifacts": ["landing.md"],
                "how_to_execute": "опубликовать",
                "time_estimate": "1 час",
                "expected_result": "заявки",
                "pack_type": "landing_pack",
            }
        },
    )

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/mission/{task.id}/execution-pack.md", headers={"X-API-Key": "test_key_for_smoke"})
    assert r.status_code == 200
    assert "Execution Pack" in r.text
    assert "Лендинг" in r.text


def test_execution_pack_action_creates_lead_and_sale(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK revenue attribution")
    repo.update_task(
        task.id,
        business_type="revenue",
        business_action_json={
            "execution_pack": {
                "action_title": "Сделать оффер",
                "why": "получить клиентов",
                "ready_steps": ["шаг"],
                "artifacts": ["offer.md"],
                "how_to_execute": "send",
                "time_estimate": "20m",
                "expected_result": "лид",
                "pack_type": "offer_pack",
            },
            "action_instance": {
                "action_id": "act-1",
                "action_type": "offer_pack",
                "status": "in_progress",
                "started_at": "2026-01-01T00:00:00Z",
            },
        },
    )

    client = TestClient(app, raise_server_exceptions=False)
    r1 = client.post(
        f"/mission/{task.id}/execution-pack/action",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={
            "status": "done",
            "money_result": "lead",
            "result_type": "lead",
            "lead_channel": "telegram",
            "lead_notes": "горячий контакт",
            "lead_value_estimate": "50000",
        },
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/mission/{task.id}/execution-pack/action",
        headers={"X-API-Key": "test_key_for_smoke", "Content-Type": "application/json"},
        json={
            "status": "done",
            "money_result": "sale",
            "result_type": "sale",
            "sale_amount": "120000",
            "sale_notes": "закрыли сделку",
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    assert isinstance(body.get("revenue"), dict)
    assert body["revenue"].get("sales", 0) >= 1
    assert body["revenue"].get("revenue_total", 0) >= 120000


def test_execution_from_scenario_markdown_and_mission_shows_cursor_block(db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK dry-run")
    repo.update_task(
        task.id,
        status="EXECUTION_READY",
        business_action_json={
            "execution_from_scenario": {
                "selected_option": {"title": "MVP"},
                "project_structure": ["Tourism/Kazakhstan/"],
                "agent_tasks": [{"agent": "Collector", "task": "Find sources"}],
                "cursor_prompts": [{"agent": "collector", "prompt": "Do the first step"}],
                "system_note": "Run in Cursor",
            }
        },
    )

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(
        f"/mission/{task.id}/execution-from-scenario.md",
        headers={"X-API-Key": "test_key_for_smoke"},
    )
    assert r.status_code == 200
    assert "Cursor" in r.text or "Collector" in r.text

    r2 = client.get(f"/mission/{task.id}", headers={"X-API-Key": "test_key_for_smoke"})
    assert r2.status_code == 200
    assert "Подготовка к Cursor" in r2.text
    assert "exec-prompt-1" in r2.text or "Копировать" in r2.text


def test_task_detail_hides_old_verdict_when_execution_ready(db_session, tmp_path):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK stale verdict")
    verdict_path = tmp_path / "final_verdict.md"
    verdict_path.write_text("# old verdict", encoding="utf-8")
    repo.add_handoff(
        task.id,
        99,
        "COURT_VERDICT",
        {"document_role": "final_verdict"},
        str(verdict_path),
    )
    repo.update_task(
        task.id,
        status="EXECUTION_READY",
        business_action_json={
            "execution_from_scenario": {
                "cursor_prompts": [{"agent": "collector", "prompt": "Do step 1"}],
            }
        },
    )

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/tasks/{task.id}", headers={"X-API-Key": "test_key_for_smoke"})
    assert r.status_code == 200
    assert "найден старый court verdict" in r.text
    assert "Финальный вердикт суда" not in r.text
