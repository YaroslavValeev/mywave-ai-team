from unittest.mock import patch

import asyncio
from types import SimpleNamespace

from app.bot import handlers
from app.orchestrator.exploration import detect_exploration_intent
from app.orchestrator import sync_run
from app.orchestrator.sync_run import run_sync_orchestration
from app.storage.repositories import TaskRepository


def test_detect_exploration_intent_project_idea():
    assert detect_exploration_intent("Я бы хотел создать проект Tourism агрегатор")
    assert detect_exploration_intent("Хочу запустить направление и проверить гипотезу")
    assert detect_exploration_intent("Предложите варианты реализации MVP по новому направлению")
    assert not detect_exploration_intent("Найти 3 клиентов и получить первую оплату")


def test_detect_exploration_intent_allows_client_goal_in_hypothesis_prompt():
    """Цель «первых клиентов» в формулировке про гипотезу/варианты не должна отключать exploration."""
    text = (
        "#TASK Я хочу запустить направление Tourism для Казахстана.\n"
        "Хочу проверить гипотезу — можно ли быстро собрать витрину туров.\n"
        "Предложите 2–3 варианта запуска.\n"
        "Цель: получить первых клиентов, а не строить большую платформу."
    )
    assert detect_exploration_intent(text)


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_pauses_for_exploration_options(mock_crewai, db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Я бы хотел создать проект агрегатор туров по странам")
    result = run_sync_orchestration(repo, task.id, source="api")
    assert result is not None
    assert result["status"] == "WAIT_OWNER"
    assert "выберите сценарий" in result["summary"].lower()
    stored = repo.get_task(task.id)
    assert stored.status == "WAIT_OWNER"
    ex = (stored.business_action_json or {}).get("exploration") or {}
    assert ex.get("exploration_mode") is True
    assert isinstance(ex.get("options"), list) and len(ex["options"]) >= 2
    assert not ex.get("selected_option_id")


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_repeat_wait_owner_skips_pipeline_and_triage(mock_crewai, db_session, monkeypatch):
    """Повторный POST /pipeline/run при WAIT_OWNER + сценарии без выбора не должен вызывать pipeline/court."""

    def _pipeline_forbidden(*_a, **_kwargs):
        raise AssertionError("pipeline не должен вызываться при повторном run до выбора сценария")

    triage_calls = {"n": 0}
    real_triage = sync_run.run_triage

    def _counting_triage(text):
        triage_calls["n"] += 1
        return real_triage(text)

    monkeypatch.setattr("app.orchestrator.sync_run.run_pipeline", _pipeline_forbidden)
    monkeypatch.setattr("app.orchestrator.sync_run.run_triage", _counting_triage)

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Предложите варианты проверки гипотезы по новому направлению")
    first = run_sync_orchestration(repo, task.id, source="api")
    assert first and first["status"] == "WAIT_OWNER"
    assert triage_calls["n"] == 1

    second = run_sync_orchestration(repo, task.id, source="api_pipeline_repeat")
    assert second and second["status"] == "WAIT_OWNER"
    assert triage_calls["n"] == 1
    assert "выберите сценарий" in (second.get("summary") or "").lower()


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_exploration_when_triage_meta_false(mock_crewai, db_session, monkeypatch):
    """Устаревший triage_meta.exploration_mode=false не должен вести в pipeline до выбора сценария."""

    def _pipeline_must_not_run(*_args, **_kwargs):
        raise AssertionError("pipeline не должен вызываться до выбора сценария exploration")

    monkeypatch.setattr("app.orchestrator.sync_run.run_pipeline", _pipeline_must_not_run)

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Предложите варианты проверки гипотезы по новому направлению")
    repo.update_task(task.id, business_action_json={"triage_meta": {"exploration_mode": False}})
    result = run_sync_orchestration(repo, task.id, source="api")
    assert result is not None
    assert result["status"] == "WAIT_OWNER"
    assert "выберите сценарий" in result["summary"].lower()


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_exploration_for_variants_prompt(mock_crewai, db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Запустить направление Tourism, проверить гипотезу и предложите варианты MVP")
    result = run_sync_orchestration(repo, task.id, source="api")
    assert result is not None
    assert result["status"] == "WAIT_OWNER"
    assert "выберите сценарий" in result["summary"].lower()


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_reads_selected_option_aliases(mock_crewai, db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Я бы хотел создать проект агрегатор туров по странам")
    first = run_sync_orchestration(repo, task.id, source="api")
    assert first and first["status"] == "WAIT_OWNER"

    t = repo.get_task(task.id)
    ba = dict(t.business_action_json or {})
    ex = dict(ba.get("exploration") or {})
    ex["scenario_id"] = "s1"
    ba["exploration"] = ex
    repo.update_task(task.id, business_action_json=ba, status="TRIAGED")

    monkeypatch.setattr(
        "app.orchestrator.sync_run.run_pipeline",
        lambda *_args, **_kwargs: {"handoffs": [{"step": "PM", "decisions": [], "assumptions": [], "open_questions": []}]},
    )
    monkeypatch.setattr(
        "app.orchestrator.sync_run.run_roundtable",
        lambda *_args, **_kwargs: {"risk_table": [], "reviewers": ["RC"]},
    )
    monkeypatch.setattr(
        "app.orchestrator.sync_run.run_court",
        lambda *_args, **_kwargs: {"report_path": "tmp.md", "summary": "ok"},
    )

    second = run_sync_orchestration(repo, task.id, source="api")
    assert second is not None
    stored = repo.get_task(task.id)
    exr = (stored.business_action_json or {}).get("execution_from_scenario")
    assert isinstance(exr, dict)


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_continues_after_scenario_selection(mock_crewai, db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Я бы хотел создать проект агрегатор туров по странам")
    first = run_sync_orchestration(repo, task.id, source="api")
    assert first and first["status"] == "WAIT_OWNER"

    t = repo.get_task(task.id)
    ba = dict(t.business_action_json or {})
    ex = dict(ba.get("exploration") or {})
    ex["selected_option_id"] = "s1"
    ba["exploration"] = ex
    repo.update_task(task.id, business_action_json=ba, status="TRIAGED")

    def _pipeline_forbidden(*_a, **_kwargs):
        raise AssertionError("pipeline не должен вызываться после dry-run exploration execution")

    monkeypatch.setattr("app.orchestrator.sync_run.run_pipeline", _pipeline_forbidden)
    monkeypatch.setattr("app.orchestrator.sync_run.run_roundtable", _pipeline_forbidden)
    monkeypatch.setattr("app.orchestrator.sync_run.run_court", _pipeline_forbidden)

    second = run_sync_orchestration(repo, task.id, source="api")
    assert second is not None
    assert second["status"] == "EXECUTION_READY"
    assert second.get("reason") == "execution_ready"
    assert "execution" in (second.get("summary") or "").lower() or "cursor" in (second.get("summary") or "").lower()
    stored = repo.get_task(task.id)
    assert stored.status == "EXECUTION_READY"
    exr = (stored.business_action_json or {}).get("execution_from_scenario")
    assert isinstance(exr, dict)
    assert exr.get("auto_run") is False
    assert isinstance(exr.get("project_structure"), list) and exr["project_structure"]
    assert isinstance(exr.get("agent_tasks"), list) and exr["agent_tasks"]
    assert isinstance(exr.get("cursor_prompts"), list) and exr["cursor_prompts"]
    assert "Можно запускать через Cursor" in str(exr.get("system_note") or "")


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_sync_run_execution_ready_repeat_skips_triage_and_pipeline(mock_crewai, db_session, monkeypatch):
    """Повторный run при EXECUTION_READY не должен снова гонять triage/pipeline."""

    def _forbidden(*_a, **_kwargs):
        raise AssertionError("не должен вызываться при повторном run в EXECUTION_READY")

    triage_calls = {"n": 0}
    real_triage = sync_run.run_triage

    def _counting_triage(text):
        triage_calls["n"] += 1
        return real_triage(text)

    monkeypatch.setattr("app.orchestrator.sync_run.run_triage", _counting_triage)
    monkeypatch.setattr("app.orchestrator.sync_run.run_pipeline", _forbidden)
    monkeypatch.setattr("app.orchestrator.sync_run.run_roundtable", _forbidden)
    monkeypatch.setattr("app.orchestrator.sync_run.run_court", _forbidden)

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Я бы хотел создать проект агрегатор туров по странам")
    first = run_sync_orchestration(repo, task.id, source="api")
    assert first and first["status"] == "WAIT_OWNER"
    assert triage_calls["n"] == 1

    t = repo.get_task(task.id)
    ba = dict(t.business_action_json or {})
    ex = dict(ba.get("exploration") or {})
    ex["selected_option_id"] = "s1"
    ba["exploration"] = ex
    repo.update_task(task.id, business_action_json=ba, status="TRIAGED")

    second = run_sync_orchestration(repo, task.id, source="api")
    assert second and second["status"] == "EXECUTION_READY"
    assert triage_calls["n"] == 2

    third = run_sync_orchestration(repo, task.id, source="api_repeat")
    assert third and third["status"] == "EXECUTION_READY"
    assert triage_calls["n"] == 2


def test_api_exploration_select_fallback(client, auth_headers, db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Я бы хотел создать проект Tourism")
    repo.update_task(
        task.id,
        status="WAIT_OWNER",
        business_action_json={
            "exploration": {
                "exploration_mode": True,
                "options": [{"id": "s1", "title": "MVP"}],
                "recommended_option_id": "s1",
            }
        },
    )
    called = {"ok": False}

    def fake_run(repo_arg, task_id_arg, source="api", control=None):
        called["ok"] = True
        assert task_id_arg == task.id
        return {"ok": True, "status": "WAIT_OWNER", "report_path": "x.md", "summary": "ok"}

    monkeypatch.setattr("app.dashboard.api_router.run_task_orchestration", fake_run)
    r = client.post(
        "/api/exploration/select",
        headers=auth_headers,
        json={"task_id": task.id, "option_id": "s1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["selected_option_id"] == "s1"
    assert called["ok"] is True
    db_session.expire_all()
    updated = repo.get_task(task.id)
    ex = (updated.business_action_json or {}).get("exploration") or {}
    assert ex.get("selected_option_id") == "s1"


def test_telegram_scenario_callback_sets_selection_and_triggers_execution(db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Я бы хотел создать проект Tourism")
    repo.update_task(
        task.id,
        status="WAIT_OWNER",
        business_action_json={
            "exploration": {
                "exploration_mode": True,
                "options": [{"id": "s1", "title": "MVP"}],
            }
        },
    )
    sent = {"count": 0}
    spawned = {"count": 0}

    async def fake_send(*_args, **_kwargs):
        sent["count"] += 1
        return True

    def fake_create_task(coro):
        spawned["count"] += 1
        coro.close()
        return None

    monkeypatch.setattr(handlers, "send_with_retry", fake_send)
    monkeypatch.setattr(handlers.asyncio, "create_task", fake_create_task)

    class DummyCallback:
        def __init__(self):
            self.data = f"sc:{task.id}:s1"
            self.message = SimpleNamespace(chat=SimpleNamespace(id=12345))
            self.bot = object()

        async def answer(self, *_args, **_kwargs):
            return None

    asyncio.run(handlers.handle_scenario_callback(DummyCallback()))
    db_session.expire_all()
    updated = repo.get_task(task.id)
    ex = (updated.business_action_json or {}).get("exploration") or {}
    assert ex.get("selected_option_id") == "s1"
    assert sent["count"] >= 1
    assert spawned["count"] == 1
