# app/services/agent_specializations.py — Phase 10.4: domain-aware agent specialization
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

_SPEC_DIR = Path(__file__).resolve().parents[1] / "data" / "agent_specializations"
_SPEC_FILE = _SPEC_DIR / "specializations.yaml"
_CACHE: list[dict[str, Any]] | None = None


def _load_registry() -> list[dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    env_path = os.environ.get("AGENT_SPECIALIZATIONS_DIR", "").strip()
    path = Path(env_path) / "specializations.yaml" if env_path else _SPEC_FILE
    if not path.exists():
        _CACHE = _default_specializations()
        return _CACHE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        items = list((data.get("specializations") or {}).values())
        _CACHE = [i for i in items if isinstance(i, dict)]
        return _CACHE
    except Exception:
        _CACHE = _default_specializations()
        return _CACHE


def _default_specializations() -> list[dict[str, Any]]:
    """Fallback minimal profiles if YAML missing."""
    return [
        {"specialization_key": "general_pipeline", "domain_key": "general", "workflow_step": "pipeline",
         "execution_focus": "task execution", "expected_output_type": "handoff_summary", "guardrails": []},
        {"specialization_key": "general_roundtable", "domain_key": "general", "workflow_step": "roundtable",
         "execution_focus": "trade-offs, risks", "expected_output_type": "risk_table", "guardrails": []},
        {"specialization_key": "general_court", "domain_key": "general", "workflow_step": "court",
         "execution_focus": "judgement", "expected_output_type": "decision_rationale", "guardrails": []},
    ]


def list_specializations() -> list[dict[str, Any]]:
    """Список всех профилей из реестра."""
    return list(_load_registry())


def get_specialization(specialization_key: str) -> Optional[dict[str, Any]]:
    """Профиль по ключу."""
    for p in _load_registry():
        if p.get("specialization_key") == specialization_key:
            return dict(p)
    return None


def get_default_specialization_for_domain(domain_key: str, step: str) -> dict[str, Any]:
    """Профиль по (domain_key, step); при отсутствии — general_{step}."""
    step = (step or "").strip().lower() or "pipeline"
    domain_key = (domain_key or "general").strip() or "general"
    for p in _load_registry():
        if (p.get("domain_key") == domain_key and p.get("workflow_step") == step):
            return dict(p)
    for p in _load_registry():
        if p.get("domain_key") == "general" and p.get("workflow_step") == step:
            return dict(p)
    return {
        "specialization_key": f"general_{step}",
        "domain_key": "general",
        "workflow_step": step,
        "execution_focus": "task execution" if step == "pipeline" else ("trade-offs" if step == "roundtable" else "judgement"),
        "expected_output_type": "handoff_summary" if step == "pipeline" else ("risk_table" if step == "roundtable" else "decision_rationale"),
        "guardrails": [],
        "profile_name": f"General {step}",
    }


def suggest_specialization(
    task_id: int,
    step: str,
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """
    Подобрать specialization для (task_id, step). Использует effective domain.
    Возвращает: selected_specialization (dict), effective_domain, step, reason, matched_signals, fallback_used,
    expected_output_type, guardrails, execution_focus.
    """
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
    except ImportError:
        lane = get_default_specialization_for_domain("general", step)
        return {
            "selected_specialization": lane,
            "effective_domain": "general",
            "workflow_step": step,
            "selection_reason": "no workflow_domain_context",
            "matched_signals": [],
            "fallback_used": True,
            "expected_output_type": lane.get("expected_output_type", ""),
            "guardrails": lane.get("guardrails", []),
            "execution_focus": lane.get("execution_focus", ""),
        }
    effective = get_effective_domain_context(task_id, task_text)
    primary = effective.get("selected_primary_domain") or "general"
    profile = get_default_specialization_for_domain(primary, step)
    fallback_used = profile.get("domain_key") == "general" and primary != "general"
    reason = f"domain={primary}, step={step}" + (" (fallback: no match)" if fallback_used else " (matched)")
    return {
        "selected_specialization": profile,
        "effective_domain": primary,
        "workflow_step": step,
        "selection_reason": reason,
        "matched_signals": [],
        "fallback_used": fallback_used,
        "expected_output_type": profile.get("expected_output_type", ""),
        "guardrails": profile.get("guardrails", []),
        "execution_focus": profile.get("execution_focus", ""),
        "profile_name": profile.get("profile_name", profile.get("specialization_key", "")),
    }


def explain_specialization_choice(
    task_id: Optional[int] = None,
    step: str = "pipeline",
    task_text: Optional[str] = None,
) -> str:
    """Человекочитаемое объяснение выбора специализации."""
    if task_id is None and not task_text:
        return f"Step: {step}. No task context."
    result = suggest_specialization(task_id or 0, step, task_text)
    p = result.get("selected_specialization", {})
    name = p.get("profile_name") or p.get("specialization_key", "?")
    reason = result.get("selection_reason", "")
    fallback = " (fallback)" if result.get("fallback_used") else ""
    return f"Specialization: {name}{fallback}. {reason}"


def build_execution_lane(
    task_id: int,
    step: str,
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """Объект execution lane по контракту EXECUTION_LANE_MODEL."""
    sel = suggest_specialization(task_id, step, task_text)
    p = sel.get("selected_specialization", {})
    return {
        "task_id": task_id,
        "workflow_step": step,
        "effective_domain": sel.get("effective_domain", ""),
        "selected_specialization": p.get("specialization_key", ""),
        "execution_focus": sel.get("execution_focus", ""),
        "expected_output_type": sel.get("expected_output_type", ""),
        "guardrails": list(sel.get("guardrails", []))[:5],
        "selection_reason": sel.get("selection_reason", ""),
        "fallback_used": sel.get("fallback_used", False),
        "profile_summary": (p.get("summary") or "")[:200],
    }
