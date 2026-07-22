# Применение правил владельца к intake / execution
from __future__ import annotations

from app.intake.schemas import NormalizeIntakeResponse
from app.shared.critical_flags import check_critical_execute
from app.owner_memory.schemas import (
    ExecutionRuleContext,
    IntakeRuleContext,
    OwnerRuleEngineResult,
    OwnerRulesBundle,
)
from app.owner_memory.service import OwnerMemoryService, owner_memory_enabled


def _rule_keys(bundle: OwnerRulesBundle) -> set[str]:
    return {r.item_key for r in bundle.rules}


def explain_rule_effects(result: OwnerRuleEngineResult) -> dict:
    return {
        "hard_blocks": result.hard_blocks,
        "soft_preferences": result.soft_preferences,
        "decision_adjustments": result.decision_adjustments,
        "reasoning_summary": result.reasoning_summary,
        "item_keys_applied": result.item_keys_applied,
        "requires_wait_owner": result.requires_wait_owner,
    }


def apply_rules_to_intake(
    resp: NormalizeIntakeResponse,
    *,
    bundle: OwnerRulesBundle,
) -> tuple[NormalizeIntakeResponse, OwnerRuleEngineResult]:
    """Корректирует решение intake по правилам/предпочтениям владельца."""
    result = OwnerRuleEngineResult()
    if not owner_memory_enabled():
        return resp, result

    keys = _rule_keys(bundle)
    applied: list[str] = []
    soft: list[str] = []
    adj: list[str] = []
    new_resp = resp

    ctx = IntakeRuleContext(
        decision=resp.decision,
        confidence=resp.confidence,
        needs_clarification=resp.needs_clarification,
        decision_reason=resp.decision_reason or "",
        matched_project_id=resp.matched_project_id,
    )

    clarify_pref = "prefer_clarify_over_wrong_autocreate" in keys
    if clarify_pref:
        soft.append("prefer_clarify_over_wrong_autocreate")
        applied.append("prefer_clarify_over_wrong_autocreate")
        ambiguous = "ambiguous_projects" in (ctx.decision_reason or "")
        low_conf_create = ctx.confidence < 0.48 and ctx.decision == "create"
        if resp.decision == "clarify" or resp.needs_clarification:
            result.reasoning_summary = "Owner prefers clarify over wrong autocreate; intake already in clarify."
        elif ambiguous or low_conf_create:
            adj.append("prefer_clarify_over_autocreate")
            extra_q = "По правилам владельца: при сомнениях лучше уточнить, чем создать неверную миссию."
            qs = list(resp.clarifying_questions)
            if extra_q not in qs:
                qs.insert(0, extra_q)
            new_resp = resp.model_copy(
                update={
                    "decision": "clarify",
                    "needs_clarification": True,
                    "clarifying_questions": qs[:5],
                    "confidence": min(resp.confidence, 0.55),
                }
            )
            result.hard_blocks.append("intake_clarify_mandatory")
            result.reasoning_summary = (
                "Owner rule prefer_clarify_over_wrong_autocreate: ambiguity or low confidence on create → clarify."
            )

    seen_soft: set[str] = set(soft)
    for p in bundle.preferences:
        if p.item_key not in seen_soft:
            soft.append(p.item_key)
            seen_soft.add(p.item_key)
    for pr in bundle.priorities:
        pk = f"priority:{pr.item_key}"
        if pk not in seen_soft:
            soft.append(pk)
            seen_soft.add(pk)

    result.soft_preferences = soft
    result.decision_adjustments = adj
    result.item_keys_applied = applied
    return new_resp, result


def apply_rules_to_execution(
    ctx: ExecutionRuleContext,
    *,
    bundle: OwnerRulesBundle,
) -> tuple[bool, OwnerRuleEngineResult]:
    """
    Возвращает (needs_approval_effective, engine_result).
    Не ослабляет базовый needs_approval_base — только усиливает.
    """
    result = OwnerRuleEngineResult()
    if not owner_memory_enabled():
        return ctx.needs_approval_base, result

    keys = _rule_keys(bundle)
    extra = False
    applied: list[str] = []
    dom = (ctx.domain or "").lower()
    tt = (ctx.task_type or "").lower()
    eg = (ctx.execute_gate or "").lower()

    if "critical_execution_requires_owner" in keys and check_critical_execute(ctx.flags):
        extra = True
        applied.append("critical_execution_requires_owner")
        result.decision_adjustments.append("set_requires_approval_true")
        result.reasoning_summary += " critical_execution_requires_owner."

    if "public_publish_requires_owner" in keys and (
        ctx.flags.get("public_publish") is True or "publish" in tt or "publish" in eg
    ):
        extra = True
        applied.append("public_publish_requires_owner")

    if "security_requires_owner_approval" in keys and (
        "security" in dom or "security" in tt or "secret" in eg or "credential" in eg
    ):
        extra = True
        applied.append("security_requires_owner_approval")

    if "strategy_change_requires_owner" in keys and ("strategy" in tt or "strategy" in dom):
        extra = True
        applied.append("strategy_change_requires_owner")

    if "idea_scenario_change_requires_owner" in keys and (
        "scenario" in tt or "product_vision" in tt or "vision" in dom
    ):
        extra = True
        applied.append("idea_scenario_change_requires_owner")

    result.item_keys_applied = applied
    result.requires_wait_owner = extra
    if extra:
        result.hard_blocks.extend(applied)
        result.reasoning_summary = (
            (result.reasoning_summary or "").strip()
            + " Owner rules require WAIT_OWNER for this execution profile."
        ).strip()

    return ctx.needs_approval_base or extra, result


def apply_owner_layer_to_normalize_response(
    resp: NormalizeIntakeResponse,
    repo,
    owner_key: str = "default",
) -> tuple[NormalizeIntakeResponse, OwnerRuleEngineResult]:
    """Сборка bundle + apply_rules_to_intake."""
    if not owner_memory_enabled():
        empty = OwnerRuleEngineResult()
        return resp, empty
    svc = OwnerMemoryService(repo, owner_key)
    bundle = svc.build_owner_rules_bundle(context_scopes=["intake", "governance", "global"])
    return apply_rules_to_intake(resp, bundle=bundle)
