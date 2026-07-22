from unittest.mock import patch

from app.orchestrator.triage import run_triage


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_triage_wakesafari_strategy_not_product_dev(mock_crewai):
    # Без слов revenue override — только ивент/запуск (wakesafari → EVENTS).
    r = run_triage("Подготовить стратегию запуска WakeSafari на сезон 2026")
    assert r["domain"] == "EVENTS"
    assert r["task_type"] == "event_runbook"


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_triage_wakesafari_brand(mock_crewai):
    r = run_triage("Marketing wakesafari tickets")
    assert r["domain"] == "EVENTS"


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_triage_site_still_product(mock_crewai):
    r = run_triage("Починить баг на сайте лендинга")
    assert r["domain"] == "PRODUCT_DEV"
