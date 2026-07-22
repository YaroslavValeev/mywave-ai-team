import time

from fastapi.testclient import TestClient

from app.dashboard.app import app


def test_background_pipeline_can_be_stopped_and_marks_task_rework(db_session, monkeypatch):
    from app.dashboard import api_router
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK остановить фоновый AI-Team")

    def slow_run(repo, task_id, source="api", control=None):
        repo.update_task(task_id, status="IN_PIPELINE", summary="Фоновый проход начался.")
        if control:
            control.set_phase("pipeline", message="Фоновый pipeline работает.", current_step="PM")
        for _ in range(60):
            time.sleep(0.02)
            if control:
                control.check_cancelled()
        repo.update_task(task_id, status="DONE", summary="Фоновый проход дошёл до конца.")
        return {"ok": True, "status": "DONE", "summary": "Фоновый проход дошёл до конца."}

    monkeypatch.setattr(api_router, "run_task_orchestration", slow_run)

    start_resp = client.post(f"/api/tasks/{task.id}/pipeline/start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["runner"]["state"] == "running"

    stop_resp = client.post(f"/api/tasks/{task.id}/pipeline/stop", headers=headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["runner"]["state"] == "stopping"

    final_runtime = None
    for _ in range(60):
        runtime_resp = client.get(f"/api/tasks/{task.id}/runtime", headers=headers)
        assert runtime_resp.status_code == 200
        final_runtime = runtime_resp.json()["runner"]
        if final_runtime["state"] == "cancelled":
            break
        time.sleep(0.05)

    assert final_runtime is not None
    assert final_runtime["state"] == "cancelled"

    task_resp = client.get(f"/api/tasks/{task.id}", headers=headers)
    assert task_resp.status_code == 200
    assert task_resp.json()["status"] == "REWORK"
    assert "остановлен пользователем" in (task_resp.json().get("summary") or "").lower()


def test_task_chat_returns_russian_team_messages_and_scene_history(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK обсудить риски и следующий шаг")
    repo.update_task(task.id, status="WAIT_OWNER", summary="Нужен owner review по итоговому verdict.")

    chat_resp = client.post(
        f"/api/tasks/{task.id}/chat",
        json={"message": "Что сейчас делает команда и какие риски самые важные?"},
        headers=headers,
    )

    assert chat_resp.status_code == 200
    payload = chat_resp.json()
    assert len(payload["messages"]) >= 3
    assert payload["messages"][0]["role"] == "owner"
    assert any(message["role"] == "team" for message in payload["messages"])
    assert any("риск" in message["text"].lower() or "миссия" in message["text"].lower() for message in payload["messages"])

    scene_resp = client.get(f"/api/tasks/{task.id}/scene", headers=headers)
    assert scene_resp.status_code == 200
    scene = scene_resp.json()
    assert scene["chat"]["can_send"] is True
    assert len(scene["chat"]["messages"]) >= 3
    assert "Что сейчас делает команда" in scene["chat"]["quick_prompts"][0]
