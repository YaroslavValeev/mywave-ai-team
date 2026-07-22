# Owner Memory / Rules Engine
import os

import pytest

from app.intake.schemas import NormalizeIntakeResponse, TaskBrief
from app.owner_memory.schemas import ExecutionRuleContext, OwnerRuleItemPublic, OwnerRulesBundle
from app.owner_memory.rules_engine import apply_rules_to_execution, apply_rules_to_intake
from app.shared.critical_flags import infer_flags_from_task


def _bundle_with_keys(*keys: str) -> OwnerRulesBundle:
    rules = [
        OwnerRuleItemPublic(
            id=i + 1,
            kind="rule",
            item_key=k,
            text=k,
            tier="canonical",
            scope="execution",
            strength=1.0,
            weight=1.0,
            priority_rank=10,
        )
        for i, k in enumerate(keys)
    ]
    return OwnerRulesBundle(owner_key="default", rules=rules, preferences=[], priorities=[])


def test_intake_clarify_on_ambiguous_projects(monkeypatch):
    monkeypatch.setenv("OWNER_MEMORY_ENABLED", "true")
    resp = NormalizeIntakeResponse(
        intent_type="task",
        confidence=0.9,
        task_brief=TaskBrief(title="x", input_summary="y"),
        needs_clarification=False,
        clarifying_questions=[],
        decision="create",
        decision_reason="classifier:create;ctx:ambiguous_projects",
    )
    b = _bundle_with_keys("prefer_clarify_over_wrong_autocreate")
    out, eng = apply_rules_to_intake(resp, bundle=b)
    assert out.decision == "clarify"
    assert out.needs_clarification is True
    assert "prefer_clarify_over_wrong_autocreate" in eng.item_keys_applied


def test_execution_critical_flags_force_wait(monkeypatch):
    monkeypatch.setenv("OWNER_MEMORY_ENABLED", "true")
    flags = infer_flags_from_task(
        domain="X",
        task_type="deploy_prod",
        execute_gate="prod",
        plan_or_execute="EXECUTE",
    )
    ctx = ExecutionRuleContext(
        plan_or_execute="EXECUTE",
        domain="X",
        task_type="deploy_prod",
        execute_gate="prod",
        flags=flags,
        needs_approval_base=False,
        task_id=1,
    )
    b = _bundle_with_keys("critical_execution_requires_owner")
    needs, eng = apply_rules_to_execution(ctx, bundle=b)
    assert needs is True
    assert "critical_execution_requires_owner" in eng.item_keys_applied


def test_execution_respects_base_approval(monkeypatch):
    monkeypatch.setenv("OWNER_MEMORY_ENABLED", "true")
    flags = {f: False for f in ("prod_deploy", "public_publish", "money_or_pricing", "pii_or_sensitive", "legal_commitment")}
    ctx = ExecutionRuleContext(
        plan_or_execute="PLAN",
        flags=flags,
        needs_approval_base=True,
    )
    b = _bundle_with_keys("critical_execution_requires_owner")
    needs, _ = apply_rules_to_execution(ctx, bundle=b)
    assert needs is True


def test_owner_memory_disabled_short_circuit(monkeypatch):
    monkeypatch.setenv("OWNER_MEMORY_ENABLED", "false")
    resp = NormalizeIntakeResponse(
        intent_type="task",
        confidence=0.9,
        task_brief=TaskBrief(),
        decision="create",
    )
    b = _bundle_with_keys("prefer_clarify_over_wrong_autocreate")
    out, eng = apply_rules_to_intake(resp, bundle=b)
    assert out.decision == resp.decision
    assert eng.item_keys_applied == []


def test_writer_inferred_stub(db_session, monkeypatch):
    monkeypatch.setenv("OWNER_MEMORY_INFERRED_WRITE", "true")
    from app.owner_memory.writer import write_inferred_pattern
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    write_inferred_pattern(repo, item_key="test_pattern", text="inferred note")
    rows = repo.list_owner_memory_items("default", active_only=True, scopes=None)
    keys = [r.item_key for r in rows]
    assert "test_pattern" in keys
    row = next(r for r in rows if r.item_key == "test_pattern")
    assert row.tier == "inferred"
    assert row.is_confirmed is False
