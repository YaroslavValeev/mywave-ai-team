# tests/test_dashboard_signed_link.py — подписанный ?link= для HTML Dashboard без X-API-Key
from fastapi.testclient import TestClient

from app.dashboard.app import app
from app.shared.dashboard_link import sign_task_link, verify_task_link


def test_sign_verify_task_link_roundtrip():
    tid = 42
    tok = sign_task_link(tid)
    assert tok
    assert verify_task_link(tid, tok)
    assert not verify_task_link(99, tok)
    assert not verify_task_link(tid, tok + "x")


def test_task_detail_allows_signed_link_without_header(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK signed link test")
    tok = sign_task_link(task.id)
    assert tok

    r = client.get(f"/tasks/{task.id}", params={"link": tok})
    assert r.status_code == 200
    assert "Task #" in r.text or str(task.id) in r.text


def test_task_detail_rejects_bad_link(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK bad link")
    r = client.get(f"/tasks/{task.id}", params={"link": "invalid-token"})
    assert r.status_code == 403


def test_post_approve_with_signed_link_query(db_session):
    from app.storage.repositories import TaskRepository

    client = TestClient(app, raise_server_exceptions=False)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK approve via link")
    repo.update_task(task.id, status="WAIT_OWNER", summary="x")
    tok = sign_task_link(task.id)

    r = client.post(f"/tasks/{task.id}/approve?link={tok}", follow_redirects=False)
    assert r.status_code == 303
    db_session.expire_all()
    assert repo.get_task(task.id).status == "DONE"
