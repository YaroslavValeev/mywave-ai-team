import pytest
from fastapi.testclient import TestClient

from app.dashboard.app import app
from app.storage.models import AuditEvent


SCENARIOS = [
    pytest.param(
        "SnowPolia",
        (
            "# TASK SnowPolia. Подготовить баланс экономики SnowCoin, ограничения против эксплойтов "
            "и измеримый план плейтеста настольной игры."
        ),
        "GAME",
        "economy_balance",
        {"PS", "DATA", "RC", "ARCH"},
        id="snowpolia",
    ),
    pytest.param(
        "Sponsorship Platform",
        (
            "# TASK Sponsorship Platform. Подготовить MVP intake, rule-based scoring спонсоров, "
            "отчётность и перечень договорных полей без отправки внешним контактам."
        ),
        "SPONSOR_PLATFORM",
        "mvp_scoring",
        {"PS", "ARCH", "DATA", "BE", "QA"},
        id="sponsorship-platform",
    ),
    pytest.param(
        "ExtremeMedia",
        (
            "# TASK ExtremeMedia. Выполнить сейчас подготовку MVP Judge Console и Evidence Pack: dataset v0, "
            "метрики v0, воспроизводимость и требования безопасности видео с людьми."
        ),
        "RND_EXTREME",
        "judge_console_mvp",
        {"ARCH", "ML_PROMPT", "BE", "DEVOPS", "QA"},
        id="extrememedia",
    ),
]


@pytest.mark.parametrize("project_name,brief,domain,task_type,expected_roles", SCENARIOS)
def test_v1_project_mission_reaches_usable_owner_result(
    db_session,
    tmp_path,
    monkeypatch,
    project_name,
    brief,
    domain,
    task_type,
    expected_roles,
):
    from app.dashboard.api import common as api_common
    from app.orchestrator import court as court_module
    from app.orchestrator import pipeline as pipeline_module

    artifacts = tmp_path / project_name.replace(" ", "_")
    monkeypatch.setattr(api_common, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(court_module, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", artifacts)

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}

    created = client.post("/api/tasks", json={"owner_text": brief}, headers=headers)
    assert created.status_code == 200
    task_id = created.json()["id"]

    run = client.post(f"/api/tasks/{task_id}/pipeline/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["status"] == "WAIT_OWNER"

    task = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert task.status_code == 200
    task_payload = task.json()
    assert task_payload["domain"] == domain
    assert task_payload["task_type"] == task_type

    artifacts_response = client.get(f"/api/tasks/{task_id}/artifacts", headers=headers)
    assert artifacts_response.status_code == 200
    role_codes = {row["step_name"] for row in artifacts_response.json()["artifacts"]}
    assert expected_roles.issubset(role_codes)

    documents = client.get(f"/api/tasks/{task_id}/documents", headers=headers)
    assert documents.status_code == 200
    kinds = [item["kind"] for item in documents.json()["documents"]]
    assert kinds[:2] == ["verdict", "report"]

    verdict = client.get(f"/api/tasks/{task_id}/documents/verdict", headers=headers)
    assert verdict.status_code == 200
    verdict_text = verdict.json()["content"]
    assert "Финальный вердикт суда" in verdict_text
    assert "Что делать владельцу прямо сейчас" in verdict_text
    assert "Что произойдёт после решения владельца" in verdict_text

    report = client.get(f"/api/tasks/{task_id}/documents/report", headers=headers)
    assert report.status_code == 200
    report_text = report.json()["content"]
    assert "Финальный отчёт AI-Team" in report_text
    assert "Краткое резюме" in report_text
    assert "Чек-лист приёмки" in report_text

    scene = client.get(f"/api/tasks/{task_id}/scene", headers=headers)
    assert scene.status_code == 200
    assert scene.json()["owner_actions"]["can_approve"] is True
    assert scene.json()["control_state"]["owner_waiting_for"]

    chat = client.post(
        f"/api/tasks/{task_id}/chat",
        json={"message": "Коротко объясните, что вы подготовили и что требуется от меня."},
        headers=headers,
    )
    assert chat.status_code == 200
    messages = chat.json()["messages"]
    assert any(item["role"] == "owner" for item in messages)
    assert any(item["role"] == "team" for item in messages)

    approved = client.post(f"/api/tasks/{task_id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "DONE"

    final_task = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert final_task.json()["status"] == "DONE"
    events = {
        row.event_type
        for row in db_session.query(AuditEvent).filter(AuditEvent.task_id == task_id).all()
    }
    assert {
        "triage_done",
        "pipeline_done",
        "roundtable_done",
        "orchestration_done",
        "OWNER_APPROVED",
    }.issubset(events)

    approved_documents = client.get(f"/api/tasks/{task_id}/documents", headers=headers)
    titles = [item["title"] for item in approved_documents.json()["documents"]]
    assert "Решение владельца" in titles
