# tests/test_gate_wait_owner.py — HF-3: WAIT_OWNER + кнопки + OWNER_APPROVED
import pytest

from app.shared.critical_flags import check_critical_execute, infer_flags_from_task
from app.bot.handlers import build_owner_buttons, build_owner_buttons_with_merged


def test_critical_execute_triggers_wait_owner():
    """Задача с prod_deploy или money_or_pricing → needs approval."""
    flags = infer_flags_from_task(
        domain="PRODUCT_DEV",
        task_type="deploy_prod",
        execute_gate="OWNER_APPROVAL_ALWAYS",
        plan_or_execute="EXECUTE",
    )
    assert check_critical_execute(flags) is True
    assert flags.get("prod_deploy") is True

    flags2 = infer_flags_from_task(
        domain="SPONSOR_PLATFORM",
        task_type="mvp_scoring",
        execute_gate="OWNER_APPROVAL_IF_CONTRACTS_OR_MONEY",
        plan_or_execute="EXECUTE",
    )
    assert check_critical_execute(flags2) is True


def test_buttons_contain_callbacks():
    """Keyboard содержит callbacks a:, r:, c:, f:."""
    kb = build_owner_buttons(task_id=42)
    markup = kb.as_markup()
    # InlineKeyboardMarkup has inline_keyboard
    rows = markup.inline_keyboard
    callbacks = []
    for row in rows:
        for btn in row:
            if btn.callback_data:
                callbacks.append(btn.callback_data)
    assert "a:42" in callbacks
    assert "r:42" in callbacks
    assert "c:42" in callbacks
    assert "f:42" in callbacks


def test_buttons_with_merged_contain_i_merged():
    """build_owner_buttons_with_merged содержит m: (I merged)."""
    kb = build_owner_buttons_with_merged(task_id=42)
    markup = kb.as_markup()
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]
    assert "m:42" in callbacks


def test_approve_flow_audit_and_decision(db_session):
    """Approve → DONE + OWNER_APPROVED audit + decision (HF-3)."""
    from app.storage.repositories import TaskRepository
    from app.storage.models import AuditEvent, Decision
    from app.shared.audit import log_audit, log_decision

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK deploy prod")
    repo.update_task(task.id, status="WAIT_OWNER")

    log_decision(repo, task.id, decision="a", owner_approval=True)
    log_audit(repo, "OWNER_APPROVED", task_id=task.id, payload={"decision": "approve"})
    repo.update_task(task.id, status="DONE")

    task_after = repo.get_task(task.id)
    assert task_after.status == "DONE"

    audits = db_session.query(AuditEvent).filter(AuditEvent.task_id == task.id).all()
    audit_types = [a.event_type for a in audits]
    assert "OWNER_APPROVED" in audit_types

    decisions = db_session.query(Decision).filter(Decision.task_id == task.id).all()
    assert any(d.decision == "a" and d.owner_approval for d in decisions)


def test_run_task_orchestration_keeps_wait_owner_when_roundtable_requires_it(db_session, tmp_path, monkeypatch):
    """Даже PLAN-задача остаётся в WAIT_OWNER, если roundtable явно требует owner gate."""
    from app.dashboard import api_router
    from app.orchestrator import sync_run as sync_run_module
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK studio bot admin")
    report_path = tmp_path / "final_report.md"
    report_path.write_text("# Report\n\ncontent", encoding="utf-8")

    monkeypatch.setattr(
        sync_run_module,
        "run_triage",
        lambda _text: {
            "domain": "CLIENTOPS",
            "task_type": "studio_bot_admin",
            "criticality": "HIGH",
            "plan_or_execute": "PLAN",
            "execute_gate": "OWNER_APPROVAL_IF_PII_OR_PROD",
        },
    )
    monkeypatch.setattr(sync_run_module, "run_pipeline", lambda *_args, **_kwargs: {"handoffs": [{"step": "PS", "payload": {}, "md_path": "ps.md"}]})
    monkeypatch.setattr(
        sync_run_module,
        "run_roundtable",
        lambda *_args, **_kwargs: {
            "risk_table": [{"issue": "owner gate", "owner_approval_needed": True}],
            "reviewers": ["SEC", "LEGAL"],
        },
    )
    monkeypatch.setattr(sync_run_module, "run_court", lambda *_args, **_kwargs: {"report_path": str(report_path), "summary": "summary"})

    result = api_router.run_task_orchestration(repo, task.id, source="test")

    assert result["status"] == "WAIT_OWNER"
    assert repo.get_task(task.id).status == "WAIT_OWNER"

    pending = repo.get_open_pending_approval(task.id)
    assert pending is not None
    assert pending.status == "REQUESTED"
    assert pending.decision_id is None
