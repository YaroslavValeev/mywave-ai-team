from fastapi.testclient import TestClient

from app.dashboard.app import app


def test_api_events_filters_cursor_and_redacts(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)

    task1 = repo.create_task(owner_text="# TASK первая миссия")
    task2 = repo.create_task(owner_text="# TASK вторая миссия")

    repo.add_audit_event("task_created", task_id=task1.id, payload={"source": "api", "status_after": "NEW"})
    repo.add_audit_event("api_request", task_id=task1.id, payload={"api_key": "SECRET_SHOULD_NOT_LEAK_1234567890"})
    repo.add_audit_event(
        "OWNER_REWORK",
        task_id=task1.id,
        payload={"decision": "rework", "status_after": "REWORK", "api_key": "SECRET_SHOULD_NOT_LEAK_1234567890"},
    )
    repo.add_audit_event("task_created", task_id=task2.id, payload={"source": "api", "status_after": "NEW"})

    response = client.get("/api/events?limit=10", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("mission_id") is None
    event_types = [event["event_type"] for event in payload["events"]]
    assert event_types == ["task_created", "OWNER_REWORK", "task_created"]
    assert "api_request" not in event_types
    assert "SECRET_SHOULD_NOT_LEAK_1234567890" not in response.text
    assert payload["events"][1]["status_after"] == "REWORK"

    after_id = payload["events"][0]["id"]
    filtered = client.get(f"/api/events?task_id={task1.id}&after_id={after_id}&limit=10", headers=headers)

    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload.get("mission_id") == task1.id
    assert [event["event_type"] for event in filtered_payload["events"]] == ["OWNER_REWORK"]
    assert filtered_payload["last_event_id"] == filtered_payload["events"][-1]["id"]


def test_task_scene_contains_live_metadata(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)

    task = repo.create_task(owner_text="# TASK проверить live metadata")
    repo.update_task(task.id, status="APPROVED_WAIT_MERGE", pr_url="https://github.com/example/repo/pull/42")
    repo.add_audit_event("task_created", task_id=task.id, payload={"source": "api", "status_after": "NEW"})
    repo.add_audit_event(
        "OWNER_APPROVED",
        task_id=task.id,
        payload={"decision": "approve", "status_after": "APPROVED_WAIT_MERGE"},
    )

    response = client.get(f"/api/tasks/{task.id}/scene", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["live"]["last_event_id"] >= 1
    assert data["live"]["poll_interval_ms"] == 4000
    assert data["live"]["has_open_pr"] is True
    assert data["live"]["can_auto_refresh"] is True
    assert data["owner_actions"]["can_approve"] is False
    assert data["owner_actions"]["can_mark_merged"] is True
    assert "ручной merge" in data["control_state"]["owner_waiting_for"]
    assert "Подтверждение merge" in data["owner_actions"]["merged_reason"] or "merge" in data["owner_actions"]["merged_reason"]


def test_task_scene_owner_actions_are_phase_gated(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)

    task = repo.create_task(owner_text="# TASK owner action gate")
    repo.update_task(task.id, status="NEW")

    response = client.get(f"/api/tasks/{task.id}/scene", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["runner"]["can_start"] is True
    assert data["owner_actions"]["can_approve"] is False
    assert data["owner_actions"]["can_clarify"] is False
    assert data["owner_actions"]["can_rework"] is False
    assert "Сейчас задача ещё не запускалась" in data["owner_actions"]["summary"]
    assert "Можно запускать новый проход AI-Team" in data["runner"]["start_reason"]


def test_task_scene_exposes_verdict_and_report_documents(db_session, tmp_path):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)

    task = repo.create_task(owner_text="# TASK проверить документы суда")
    report_path = tmp_path / "final_report.md"
    verdict_path = tmp_path / "final_verdict.md"
    handoff_path = tmp_path / "pm.md"
    report_path.write_text("# Report\n\nhello", encoding="utf-8")
    verdict_path.write_text("# Verdict\n\ncanonical", encoding="utf-8")
    handoff_path.write_text("# PM\n\nhandoff", encoding="utf-8")

    repo.update_task(task.id, status="WAIT_OWNER", report_path=str(report_path), summary="court summary")
    repo.add_handoff(task.id, 0, "PM", {"summary": ["handoff summary"]}, str(handoff_path))
    repo.add_handoff(
        task.id,
        1,
        "COURT_VERDICT",
        {"document_role": "final_verdict", "summary": ["Каноничное решение команды после суда."]},
        str(verdict_path),
    )

    response = client.get(f"/api/tasks/{task.id}/scene", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert [item["kind"] for item in data["documents"][:2]] == ["verdict", "report"]
    assert data["documents"][0]["title"] == "Финальный вердикт суда"
    assert data["documents"][0]["path"].endswith("final_verdict.md")


def test_office_routes_render_shell_and_deeplink(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK office deep link")

    office_resp = client.get("/office", headers=headers)
    scene_resp = client.get(f"/office/tasks/{task.id}", headers=headers)
    asset_resp = client.get("/static/game.js")
    css_resp = client.get("/static/game.css")

    assert office_resp.status_code == 200
    assert "/static/game.css" in office_resp.text
    assert "/static/game.js" in office_resp.text
    assert scene_resp.status_code == 200
    assert f'data-initial-task-id="{task.id}"' in scene_resp.text
    assert asset_resp.status_code == 200
    assert "Лента штаба" in asset_resp.text
    assert "Штабный эфир" in asset_resp.text
    assert "Сейчас по-настоящему" in asset_resp.text
    assert "Прогресс миссии" in asset_resp.text
    assert "Последний важный переход" in asset_resp.text
    assert "Маршрут кадра" in asset_resp.text
    assert "data-open-document-key" in asset_resp.text
    assert "Запустить AI-Team" in asset_resp.text
    assert "Остановить live" in asset_resp.text
    assert "Вернуться к миссии" in asset_resp.text
    assert "Остановить AI-Team" in asset_resp.text
    assert "Чат с командой" in asset_resp.text
    assert "Написать команде" in asset_resp.text
    assert "К чату команды" in asset_resp.text
    assert "Добавить входные файлы" in asset_resp.text
    assert "Добавить файл в миссию" in asset_resp.text
    assert 'task-attachment-input' in asset_resp.text
    assert 'mission-attachment-input' in asset_resp.text
    assert 'data-action="upload-attachments"' in asset_resp.text
    assert "Скачать док. созданный командой" in asset_resp.text
    assert "Финальный вердикт отдельно" in asset_resp.text
    assert "Короткий диалог команды" in asset_resp.text
    assert "Что делать владельцу прямо сейчас" in asset_resp.text
    assert "только реальные owner/control actions для текущей фазы" in asset_resp.text
    assert 'data-action="create-task"' in asset_resp.text
    assert 'data-action="run-pipeline"' in asset_resp.text
    assert 'data-action="stop-pipeline"' in asset_resp.text
    assert 'data-action="send-chat"' in asset_resp.text
    assert 'data-owner-action="approve"' in asset_resp.text
    assert 'data-owner-action="rework"' in asset_resp.text
    assert 'data-owner-action="clarify"' in asset_resp.text
    assert 'data-owner-action="merged"' in asset_resp.text
    assert 'data-download-document-key' in asset_resp.text
    assert 'data-open-document-key' in asset_resp.text
    assert "interactive-layer" in asset_resp.text
    assert "captureDraftSnapshot" in asset_resp.text
    assert "restoreDraftSnapshot" in asset_resp.text
    assert "mission-chat-input" in asset_resp.text
    assert "task-composer-input" in asset_resp.text
    assert "focusin" in asset_resp.text
    assert "lockUntil" in asset_resp.text
    assert "Запуск AI-Team" in asset_resp.text
    assert "Доработка / уточнение / merge" in asset_resp.text
    assert '}[status] || ["reception", "worklane", "owner"]' in asset_resp.text
    assert css_resp.status_code == 200
    assert ".stage-hero" in css_resp.text
    assert ".persona-avatar" in css_resp.text
    assert ".current-state-card" in css_resp.text
    assert ".chat-panel" in css_resp.text
    assert ".process-meter" in css_resp.text
    assert ".action-stage" in css_resp.text
    assert ".dialog-bubble" in css_resp.text
    assert ".transition-lane" in css_resp.text
    assert ".frame-route-step" in css_resp.text
    assert ".is-live-paused" in css_resp.text
    assert ".room-mode-triage" in css_resp.text
    assert ".interactive-layer" in css_resp.text
    assert "touch-action: manipulation" in css_resp.text
    assert "scroll-margin-bottom" in css_resp.text
    assert ".task-action-bar" in css_resp.text
    assert ".upload-card" in css_resp.text
    assert "@media (max-width: 640px)" in css_resp.text
    assert "grid-template-columns: 1fr;" in css_resp.text
