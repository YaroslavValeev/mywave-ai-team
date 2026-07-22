# Smart Intake v0 — слой нормализации + API + storage attach
import pytest

from app.intake import NormalizeIntakeRequest, normalize_intake, task_brief_to_owner_text
from app.intake.classify import rule_based_classify
from app.intake.schemas import IntakeAttachment, TaskBrief
from app.storage.repositories import TaskRepository


@pytest.fixture(autouse=True)
def _disable_intake_llm(monkeypatch):
    monkeypatch.setenv("INTAKE_USE_LLM", "false")


def test_normalize_api_error_text_decision_create():
    text = "У меня ошибка 401 при вызове API без заголовка X-API-Key, что делать?"
    r = normalize_intake(NormalizeIntakeRequest(text=text, source="api_test"))
    assert r.decision == "create"
    assert r.task_brief.input_summary
    assert r.intent_type == "task"


def test_normalize_noise_ok_reject():
    r = normalize_intake(NormalizeIntakeRequest(text="ок", source="telegram"))
    assert r.decision == "reject"
    assert r.intent_type == "noise"


def test_reply_context_attach():
    r = normalize_intake(
        NormalizeIntakeRequest(
            text="добавь в handler логирование duration_ms для /api/health",
            source="telegram",
            reply_context={"task_id": 42},
        )
    )
    assert r.decision == "attach"
    assert "42" in f"{r.task_brief.title} {r.task_brief.input_summary}"


def test_rule_based_after_stt_equivalent():
    """После STT приходит обычная строка — тот же rule_based путь."""
    req = NormalizeIntakeRequest(
        text="Нужно поправить конфиг nginx для прокси на dashboard",
        source="telegram",
    )
    r = rule_based_classify(req, req.text.strip(), None)
    assert r.decision == "create"


def test_attachment_description_in_combined():
    req = NormalizeIntakeRequest(
        text="",
        source="api_test",
        attachments=[IntakeAttachment(kind="image", description="Скриншот: форма логина с ошибкой валидации email")],
    )
    r = normalize_intake(req)
    assert r.decision == "create"
    assert "email" in r.task_brief.input_summary.lower() or "валидац" in r.task_brief.input_summary.lower()


def test_task_brief_to_owner_text_has_marker():
    brief = TaskBrief(title="T", goal="G", input_summary="S", desired_outcome="O")
    s = task_brief_to_owner_text(brief, original_input="raw")
    assert "#TASK" in s
    assert "SmartIntake" in s
    assert "raw" in s


def test_hash_task_api_path_still_create():
    """Регрессия: явный #TASK в теле API-нормализации остаётся задачей, не шумом."""
    r = normalize_intake(NormalizeIntakeRequest(text="#TASK проверить регрессию smart intake", source="api"))
    assert r.decision == "create"


def test_api_intake_normalize_401(client):
    r = client.post("/api/intake/normalize", json={"text": "hello", "source": "test"})
    assert r.status_code == 401


def test_api_intake_normalize_200(client, auth_headers, db_session):
    r = client.post(
        "/api/intake/normalize",
        headers=auth_headers,
        json={"text": "Сделать endpoint для health check", "source": "pytest"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["decision"] in ("create", "clarify", "attach", "reject")
    assert "task_brief" in data
    assert "confidence" in data
    assert "matched_project_id" in data
    assert "decision_reason" in data
    assert "memory_used" in data
    assert "owner_rule_keys_applied" in data
    assert isinstance(data["owner_rule_keys_applied"], list)
    assert "business_intent" in data
    assert "business_action" in data
    assert "gm_decision" in data
    gm = data["gm_decision"]
    assert gm is None or isinstance(gm, dict)
    if gm:
        assert gm.get("execution_mode") in ("quick", "light", "full")
        assert gm.get("action") in ("answer", "create_task", "attach", "clarify", "reject")


def test_append_owner_context(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK base")
    out = repo.append_owner_context(t.id, "[extra context block]")
    assert out is not None
    again = repo.get_task(t.id)
    assert again is not None
    assert "Smart Intake attach" in (again.owner_text or "")
    assert "[extra context block]" in (again.owner_text or "")
