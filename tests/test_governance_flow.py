from app.governance.owner_flow import on_orchestration_awaiting_owner
from app.storage.models import Approval
from app.storage.repositories import TaskRepository


def test_on_orchestration_awaiting_owner_idempotent(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK gate")
    on_orchestration_awaiting_owner(repo, task.id, "DONE")
    assert repo.get_open_pending_approval(task.id) is None

    on_orchestration_awaiting_owner(repo, task.id, "WAIT_OWNER")
    p1 = repo.get_open_pending_approval(task.id)
    assert p1 is not None
    assert p1.status == "REQUESTED"

    on_orchestration_awaiting_owner(repo, task.id, "WAIT_OWNER")
    p2 = repo.get_open_pending_approval(task.id)
    assert p2.id == p1.id


def test_add_decision_approve_resolves_pending(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK approve pending")
    repo.ensure_pending_owner_approval(task.id)
    repo.add_decision(task.id, "a", owner_approval=True)

    assert repo.get_open_pending_approval(task.id) is None
    rows = db_session.query(Approval).filter(Approval.task_id == task.id).all()
    assert len(rows) == 1
    assert rows[0].status == "APPROVED"
    assert rows[0].decision_id is not None


def test_add_decision_rework_resolves_pending_rejected(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK rework pending")
    repo.ensure_pending_owner_approval(task.id)
    repo.add_decision(task.id, "r", owner_approval=False)

    assert repo.get_open_pending_approval(task.id) is None
    rows = db_session.query(Approval).filter(Approval.task_id == task.id).all()
    assert len(rows) == 1
    assert rows[0].status == "REJECTED"


def test_execution_events_api_empty_and_auth(client, auth_headers, db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK exec events")

    r_no = client.get(f"/api/tasks/{task.id}/execution-events")
    assert r_no.status_code == 401

    r = client.get(f"/api/tasks/{task.id}/execution-events", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["task_id"] == task.id
    assert r.json()["events"] == []
