from types import SimpleNamespace

import pytest

from app.orchestrator.triage import run_triage
from app.orchestrator.triage_snapshot import canonical_triage_for_court, resync_triage_dict_from_store
from app.storage.repositories import TaskRepository


CLUB_BOX = (
    "#TASK Domain: PRODUCT_DEV, Type: feature_delivery.\n"
    "Упаковать Club Box для Windows. Не включать клиентские данные. "
    "Internal booking gateway — единственный writer коммерческой брони."
)


def test_explicit_route_beats_revenue_keywords_and_llm(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Owner route must not be replaced by an LLM")

    monkeypatch.setattr("app.orchestrator.triage.run_crewai_triage", forbidden)
    result = run_triage(CLUB_BOX)
    assert result["domain"] == "PRODUCT_DEV"
    assert result["task_type"] == "feature_delivery"
    assert result["plan_or_execute"] == "EXECUTE"
    assert result["revenue_intent_override"] is False
    assert result["triage_source"] == "owner_explicit"


def test_explicit_route_beats_project_aliases():
    result = run_triage("# TASK Domain: EVENTS, Type: event_runbook. Обсудить SnowPolia и оплату")
    assert (result["domain"], result["task_type"]) == ("EVENTS", "event_runbook")


@pytest.mark.parametrize("header", [
    "#TASK Domain: UNKNOWN, Type: feature_delivery.",
    "#TASK Domain: PRODUCT_DEV, Type: unknown.",
    "#TASK Domain: PRODUCT_DEV.",
])
def test_invalid_owner_route_is_not_silently_reclassified(header):
    with pytest.raises(ValueError):
        run_triage(header + " Найти клиентов и оплату")


def test_owner_route_beats_stale_revenue_in_court_and_store(db_session):
    stale = {
        "domain": "BUSINESS", "task_type": "revenue_execution",
        "revenue_intent_override": True, "agent_cluster": "MEDIA",
        "triage_source": "llm_normalized", "triage_validation_errors": ["stale"],
    }
    task = SimpleNamespace(owner_text=CLUB_BOX, business_action_json={"triage_meta": stale})
    court = canonical_triage_for_court(task, stale)
    repo = TaskRepository(db_session)
    stored = repo.create_task(owner_text=CLUB_BOX)
    repo.update_task(stored.id, domain="BUSINESS", task_type="revenue_execution",
                     business_action_json={"triage_meta": stale})
    resynced = resync_triage_dict_from_store(repo, stored.id, stale)
    for result in (court, resynced):
        assert result["domain"] == "PRODUCT_DEV"
        assert result["task_type"] == "feature_delivery"
        assert result["revenue_intent_override"] is False
        assert result["triage_source"] == "owner_explicit"
        assert result["triage_validation_errors"] == []
        assert result["agent_cluster"] != "MEDIA"
