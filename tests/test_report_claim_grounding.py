import pytest

from app.orchestrator.court import _execution_gap_analysis
from app.orchestrator.pipeline import _build_handoff_payload


@pytest.mark.parametrize("owner_text", [
    "Проект Club Box: одна папка на другой компьютер Windows. Начать с inventory исходных компонентов.",
    "Упаковать проект Club Box. Новый владелец подключит аккаунты Google и API keys.",
    "Проект Club Box. Папка на флэшку. Секреты хранятся отдельно; создать мастер настройки.",
])
def test_packaging_brief_is_not_a_personal_project_catalogue(owner_text):
    assert _execution_gap_analysis(owner_text)["needs_external_access"] is False


@pytest.mark.parametrize("owner_text", [
    "Сделай список всех проектов на Local (компьютере), в OpenAI и Google",
    "Перечисли мои проекты в Google",
    "List my projects in OpenAI",
])
def test_real_external_project_catalogue_keeps_access_limitation(owner_text):
    assert _execution_gap_analysis(owner_text)["needs_external_access"] is True


def test_execute_mode_does_not_claim_an_execution_request_exists():
    payload = _build_handoff_payload(
        "PS", 39, {"domain": "PRODUCT_DEV", "task_type": "feature_delivery", "plan_or_execute": "EXECUTE"},
        "Create portable Club Box", [], [], "PM", None,
    )
    assert not any("Execution request is present" in value for value in payload["assumptions"])
    assert any("не подтверждает наличие готового execution_request" in value for value in payload["assumptions"])


def test_packaging_court_reports_real_gate_without_personal_catalogue(db_session, tmp_path, monkeypatch):
    from app.orchestrator import court
    from app.storage.repositories import TaskRepository

    monkeypatch.setattr(court, "ARTIFACTS_DIR", tmp_path)
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text=(
        "#TASK Domain: PRODUCT_DEV, Type: feature_delivery. "
        "Проект Club Box: папка для Windows, новый компьютер и аккаунты Google."
    ))
    court.run_court(task.id, {
        "domain": "PRODUCT_DEV", "task_type": "feature_delivery", "criticality": "MEDIUM",
        "plan_or_execute": "EXECUTE", "execute_gate": "OWNER_APPROVAL_IF_PROD",
    }, {"handoffs": []}, {"reviewers": [], "risk_table": [{"owner_approval_needed": True}]}, repo)
    for filename in ("final_report.md", "final_verdict.md"):
        text = (tmp_path / "tasks" / f"task_{task.id}" / "court" / filename).read_text(encoding="utf-8")
        assert "EXECUTION_READY" in text
        assert "либо сразу завершится" not in text
        assert "выгрузки списков проектов" not in text
        assert "Execution request is present" not in text
