from unittest.mock import patch

from app.orchestrator.triage import run_triage


@patch("app.orchestrator.triage.run_crewai_triage", return_value={})
def test_triage_marketing_plan_not_product_dev(mock_crewai):
    r = run_triage(
        'У меня есть проект "MyWave Wake", создай для него маркетинговый-рекламный план за 0 рублей.'
    )
    assert r["domain"] == "MEDIA_OPS"
    assert r["task_type"] == "marketing_plan"
    assert r.get("marketing_plan_override") is True
    assert r["plan_or_execute"] == "PLAN"


@patch("app.orchestrator.triage.run_crewai_triage", return_value={"domain": "PRODUCT_DEV", "task_type": "feature_delivery"})
def test_triage_marketing_locks_crewai_domain(mock_crewai):
    r = run_triage("#TASK Marketing plan for MyWave Wake zero budget")
    assert r["domain"] == "MEDIA_OPS"
    assert r["task_type"] == "marketing_plan"


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
