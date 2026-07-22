from fastapi.testclient import TestClient

from app.dashboard.app import app


def test_dashboard_task_detail_shows_actions_and_artifact_link(db_session, tmp_path):
    """Task detail показывает owner actions и ссылки на артефакт."""
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK проверить handoff")
    artifact_path = tmp_path / "test_dashboard_handoff.md"
    artifact_path.write_text("# Handoff\n\ncontent", encoding="utf-8")
    repo.add_handoff(task.id, 0, "PM", {"summary": ["ok"]}, str(artifact_path))

    handoff = repo.get_task(task.id).handoffs[0]
    r = client.get(f"/tasks/{task.id}", headers={"X-API-Key": "test_key_for_smoke"})

    assert r.status_code == 200
    assert f"/tasks/{task.id}/approve" in r.text
    assert f"/tasks/{task.id}/artifacts/{handoff.id}" in r.text


def test_dashboard_task_detail_shows_i_merged_when_pr_present(db_session):
    """Task detail показывает I merged для APPROVED_WAIT_MERGE."""
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK confirm merge")
    repo.update_task(task.id, status="APPROVED_WAIT_MERGE", pr_url="https://github.com/example/repo/pull/1")

    r = client.get(f"/tasks/{task.id}", headers={"X-API-Key": "test_key_for_smoke"})

    assert r.status_code == 200
    assert f"/tasks/{task.id}/merged" in r.text


def test_dashboard_approve_redirects_and_updates_status(db_session):
    """POST approve из Dashboard редиректит и обновляет статус."""
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK закрыть задачу")
    repo.update_task(task.id, status="WAIT_OWNER", summary="Нужен owner decision")

    r = client.post(
        f"/tasks/{task.id}/approve",
        headers={"X-API-Key": "test_key_for_smoke"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/tasks/{task.id}")
    db_session.expire_all()
    assert repo.get_task(task.id).status == "DONE"


def test_dashboard_artifact_view_renders_content(db_session, tmp_path):
    """Страница артефакта показывает содержимое markdown файла."""
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK открыть артефакт")
    artifact_path = tmp_path / "test_dashboard_detail.md"
    artifact_path.write_text("# Report\n\nhello", encoding="utf-8")
    repo.add_handoff(task.id, 0, "ARCH", {"summary": ["hello"]}, str(artifact_path))

    handoff = repo.get_task(task.id).handoffs[0]
    r = client.get(
        f"/tasks/{task.id}/artifacts/{handoff.id}",
        headers={"X-API-Key": "test_key_for_smoke"},
    )

    assert r.status_code == 200
    assert "Artifact" in r.text
    assert "hello" in r.text


def test_dashboard_mark_merged_redirects_and_updates_status(db_session):
    """POST merged из Dashboard переводит задачу в DONE."""
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK merged")
    repo.update_task(task.id, status="APPROVED_WAIT_MERGE", pr_url="https://github.com/example/repo/pull/1")

    r = client.post(
        f"/tasks/{task.id}/merged",
        headers={"X-API-Key": "test_key_for_smoke"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    db_session.expire_all()
    assert repo.get_task(task.id).status == "DONE"


def test_dashboard_verdict_download_route_returns_attachment(db_session, tmp_path):
    """Verdict document можно открыть и скачать отдельным route."""
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK открыть verdict")
    report_path = tmp_path / "final_report.md"
    verdict_path = tmp_path / "final_verdict.md"
    report_path.write_text("# Report\n\nsummary", encoding="utf-8")
    verdict_path.write_text("# Verdict\n\nteam decision", encoding="utf-8")
    repo.update_task(task.id, status="WAIT_OWNER", report_path=str(report_path), summary="summary")
    repo.add_handoff(
        task.id,
        1,
        "COURT_VERDICT",
        {"document_role": "final_verdict", "summary": ["Команда зафиксировала финальное решение."]},
        str(verdict_path),
    )

    view_resp = client.get(f"/tasks/{task.id}/documents/verdict", headers={"X-API-Key": "test_key_for_smoke"})
    download_resp = client.get(f"/tasks/{task.id}/documents/verdict/download", headers={"X-API-Key": "test_key_for_smoke"})

    assert view_resp.status_code == 200
    assert "Финальный вердикт суда" in view_resp.text
    assert download_resp.status_code == 200
    assert "attachment" in download_resp.headers.get("content-disposition", "").lower()
    assert "final_verdict.md" in download_resp.headers.get("content-disposition", "")
