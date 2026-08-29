"""auto_run on POST /api/tasks runs orchestration in one call."""

from __future__ import annotations


def test_create_task_auto_run_reaches_wait_owner(client, auth_headers, db_session, tmp_path, monkeypatch):
    from app.dashboard.api import common as api_common
    from app.orchestrator import court as court_module
    from app.orchestrator import pipeline as pipeline_module

    artifacts = tmp_path / "auto-run-artifacts"
    monkeypatch.setattr(api_common, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(court_module, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", artifacts)

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
