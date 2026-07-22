from unittest.mock import patch

from app.orchestrator.revenue_intent import detect_revenue_intent
from app.orchestrator.triage import run_triage


def test_revenue_intent_real_case_no_hash_prefix():
    """Реальный сценарий: текст без #TASK (как после нормализации / из UI)."""
    text = "Найти 3 клиентов на WakeSafari и получить первую оплату"
    assert detect_revenue_intent(text) is True


def test_detect_revenue_intent_clients_and_payment():
    assert detect_revenue_intent("#TASK Найти 3 клиентов на WakeSafari и получить первую оплату")
    assert detect_revenue_intent("получить revenue за квартал")
    assert not detect_revenue_intent("Починить баг на сайте лендинга")


@patch("app.orchestrator.triage.run_crewai_triage")
def test_revenue_override_beats_crewai_product_dev(mock_crewai):
    mock_crewai.return_value = {
        "domain": "PRODUCT_DEV",
        "task_type": "feature_delivery",
        "criticality": "MEDIUM",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PROD",
    }
    r = run_triage("#TASK Найти 3 клиентов и получить оплату")
    assert r["domain"] == "BUSINESS"
    assert r["task_type"] == "revenue_execution"
    assert r["revenue_intent_override"] is True
    assert r["plan_or_execute"] == "EXECUTE"


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_revenue_override_user_example(mock_crewai):
    r = run_triage("#TASK Найти 3 клиентов на WakeSafari и получить первую оплату")
    assert r["domain"] == "BUSINESS"
    assert r["task_type"] == "revenue_execution"
    assert r["revenue_intent_override"] is True


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_revenue_override_real_text_without_task_prefix(mock_crewai):
    r = run_triage("Найти 3 клиентов на WakeSafari и получить первую оплату")
    assert r["domain"] == "BUSINESS"
    assert r["task_type"] == "revenue_execution"
    assert r["revenue_intent_override"] is True


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_no_override_for_pure_product_bug(mock_crewai):
    r = run_triage("Починить баг на сайте лендинга")
    assert r["domain"] == "PRODUCT_DEV"
    assert r["revenue_intent_override"] is False
