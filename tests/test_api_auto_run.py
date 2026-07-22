"""auto_run on POST /api/tasks runs orchestration in one call."""

from __future__ import annotations


def test_create_task_auto_run_reaches_wait_owner(client, auth_headers, db_session):
    r = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"owner_text": "#TASK auto_run unit", "auto_run": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True or body.get("status") in (
        "WAIT_OWNER",
        "DONE",
        "NEW",
    )
    # rule_based court path → WAIT_OWNER
    assert body.get("status") == "WAIT_OWNER"
    assert "report_path" in body or body.get("ok") is True
