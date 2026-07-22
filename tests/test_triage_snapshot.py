from types import SimpleNamespace

from app.orchestrator.triage_snapshot import canonical_triage_for_court, resync_triage_dict_from_store
from app.storage.repositories import TaskRepository


def test_resync_exploration_mode_true_overrides_stale_meta_false(db_session):
    """meta.exploration_mode=false не должен затирать свежий triage True / detect по тексту."""
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Запустить направление и проверить гипотезу")
    repo.update_task(
        task.id,
        business_action_json={"triage_meta": {"exploration_mode": False, "domain": "PRODUCT_DEV", "task_type": "feature_delivery"}},
    )
    out = resync_triage_dict_from_store(
        repo,
        task.id,
        {"exploration_mode": True, "domain": "PRODUCT_DEV", "task_type": "feature_delivery"},
    )
    assert out["exploration_mode"] is True

    out2 = resync_triage_dict_from_store(
        repo,
        task.id,
        {"exploration_mode": False, "domain": "PRODUCT_DEV", "task_type": "feature_delivery"},
    )
    assert out2["exploration_mode"] is True


def test_canonical_triage_revenue_lock_over_stale_events_meta():
    """Устаревший triage_meta.domain=EVENTS не должен перебить revenue по owner_text."""
    task = SimpleNamespace(
        owner_text="#TASK Найти 3 клиентов на WakeSafari и получить первую оплату",
        domain="EVENTS",
        task_type="event_runbook",
        criticality="MEDIUM",
        plan_or_execute="PLAN",
        business_action_json={
            "triage_meta": {
                "revenue_intent_override": False,
                "domain": "EVENTS",
                "task_type": "event_runbook",
                "criticality": "MEDIUM",
                "plan_or_execute": "PLAN",
                "execute_gate": "OWNER_APPROVAL_IF_PROD",
            }
        },
    )
    bad = {"domain": "PRODUCT_DEV", "task_type": "feature_delivery", "revenue_intent_override": False}
    out = canonical_triage_for_court(task, bad)
    assert out["domain"] == "BUSINESS"
    assert out["task_type"] == "revenue_execution"
    assert out["revenue_intent_override"] is True


def test_canonical_triage_revenue_lock_over_stale_product_dev():
    task = SimpleNamespace(
        owner_text="#TASK Найти 3 клиентов и получить оплату",
        domain="PRODUCT_DEV",
        task_type="feature_delivery",
        criticality="MEDIUM",
        plan_or_execute="PLAN",
        business_action_json={
            "triage_meta": {
                "revenue_intent_override": True,
                "domain": "BUSINESS",
                "task_type": "revenue_execution",
                "criticality": "HIGH",
                "plan_or_execute": "EXECUTE",
                "execute_gate": "OWNER_APPROVAL_IF_CONTRACTS_OR_MONEY",
            }
        },
    )
    bad = {"domain": "PRODUCT_DEV", "task_type": "feature_delivery", "criticality": "LOW", "plan_or_execute": "PLAN"}
    out = canonical_triage_for_court(task, bad)
    assert out["domain"] == "BUSINESS"
    assert out["task_type"] == "revenue_execution"
    assert out["revenue_intent_override"] is True
