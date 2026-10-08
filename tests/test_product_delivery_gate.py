import asyncio
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.orchestrator.execution_pack import resolve_status_after_approve, task_wants_outreach_execute
from app.storage.repositories import TaskRepository


BRIEF = "#TASK Domain: PRODUCT_DEV, Type: feature_delivery. Упаковать Club Box для Windows"


@pytest.mark.parametrize("task_type", ["feature_delivery", "software_bugfix", "deploy_prod"])
def test_product_delivery_approval_cannot_complete_task(task_type):
    task = SimpleNamespace(domain="PRODUCT_DEV", task_type=task_type, business_action_json={}, handoffs=[])
    assert resolve_status_after_approve(task, has_pr=False) == "EXECUTION_READY"
    assert resolve_status_after_approve(task, has_pr=True) == "APPROVED_WAIT_MERGE"


def test_owner_product_route_blocks_stale_revenue_completion():
    task = SimpleNamespace(owner_text=BRIEF, domain="BUSINESS", task_type="revenue_execution",
                           business_action_json={"triage_meta": {"agent_cluster": "MEDIA"}}, handoffs=[])
    assert resolve_status_after_approve(task, has_pr=False) == "EXECUTION_READY"
    assert task_wants_outreach_execute(task) is False


def test_product_plan_approval_api_waits_for_execution(client, auth_headers, db_session, tmp_path, monkeypatch):
    from app.dashboard.api import common
    from app.orchestrator import execution_pack

    monkeypatch.setattr(common, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(execution_pack, "ARTIFACTS_DIR", tmp_path)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text=BRIEF)
    repo.update_task(task.id, domain="PRODUCT_DEV", task_type="feature_delivery", status="WAIT_OWNER")
    response = client.post(f"/api/tasks/{task.id}/approve", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTION_READY"
    assert "execution_pack" not in response.json()
    db_session.expire_all()
    fresh = repo.get_task(task.id)
    assert fresh.status != "DONE"
    assert "execution_request" in fresh.summary
    scene = client.get(f"/api/tasks/{task.id}/scene", headers=auth_headers).json()
    assert scene["execution"]["can_start"] is False


def test_telegram_product_result_has_no_revenue_prompts(monkeypatch):
    from app.bot import handlers

    task = SimpleNamespace(owner_text=BRIEF, domain="PRODUCT_DEV", task_type="feature_delivery",
        business_action_json={"execution_pack": {"pack_type": "generic_pack"},
                              "exploration": {"exploration_mode": True, "options": [{"id": "sales"}]}})
    repo = SimpleNamespace(get_task=lambda _: task)
    monkeypatch.setattr(handlers, "get_session_factory", lambda: lambda: nullcontext(None))
    monkeypatch.setattr(handlers, "TaskRepository", lambda _: repo)
    monkeypatch.setattr(handlers, "run_sync_orchestration", lambda *args, **kwargs: {"status": "WAIT_OWNER", "summary": "Inventory pending"})
    monkeypatch.setattr(handlers, "_format_mission_gm_footer", lambda *args: "Panel")

    def forbidden(*args):
        raise AssertionError("Product delivery must not emit revenue or daily-feedback prompts")

    monkeypatch.setattr(handlers, "format_owner_delivery_note", forbidden)
    monkeypatch.setattr(handlers, "build_growth_insight", forbidden)
    messages = []

    async def capture(bot, chat_id, text, **kwargs):
        messages.append((text, kwargs.get("reply_markup")))

    monkeypatch.setattr(handlers, "send_with_retry", capture)
    asyncio.run(handlers._run_orchestration(39, 1, object()))
    assert len(messages) == 1
    text, keyboard = messages[0]
    assert "Реализация ещё не подтверждена" in text
    assert "На сегодня" not in text
    assert "Готово к действию" not in text
    assert keyboard is not None
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "a:39" in callbacks
    assert not any(callback and callback.startswith("ep:") for callback in callbacks)


def test_product_orchestration_without_risks_still_requires_owner(client, auth_headers, db_session, tmp_path, monkeypatch):
    from app.dashboard.api import common
    from app.orchestrator import court, pipeline, sync_run

    for module in (common, court, pipeline):
        monkeypatch.setattr(module, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(sync_run, "check_critical_execute", lambda _: False)
    monkeypatch.setattr(sync_run, "owner_memory_enabled", lambda: False)
    monkeypatch.setattr(sync_run, "run_roundtable", lambda *args, **kwargs: {"risk_table": []})

    def forbidden(*args, **kwargs):
        raise AssertionError("Product delivery must not generate a generic business pack")

    monkeypatch.setattr(sync_run, "ensure_execution_pack_for_task", forbidden)
    monkeypatch.setattr(sync_run, "ensure_action_instance_blob", forbidden)
    response = client.post("/api/tasks", headers=auth_headers, json={"owner_text": BRIEF, "auto_run": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "WAIT_OWNER"
