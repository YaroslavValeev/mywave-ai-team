# app/services/domain_prompt_profiles.py — Phase 10.2: step-specific domain prompt profiles
from __future__ import annotations

from typing import Any, Optional

from app.services.workflow_domain_context import get_effective_domain_context
from app.services.domain_context_packs import build_context_pack

STEP_PIPELINE = "pipeline"
STEP_ROUNDTABLE = "roundtable"
STEP_COURT = "court"

# Policy: max chars per step (DOMAIN_STEP_CONTEXT_POLICY)
MAX_PIPELINE = 800
MAX_ROUNDTABLE = 600
MAX_COURT = 500


def _pack_to_compact(
    pack: dict[str, Any],
    included_sections: list[str],
    max_chars: int,
) -> str:
    """Собрать компактный текст из секций pack с лимитом символов."""
    if not pack:
        return ""
    parts = []
    name = pack.get("canonical_name") or pack.get("domain_key") or ""
    if "summary" in included_sections and pack.get("summary"):
        parts.append((pack.get("summary") or "").strip())
    if "strengths" in included_sections and pack.get("strengths"):
        parts.append("Ключевые слова: " + ", ".join((pack.get("strengths") or [])[:8]))
    if "typical_tasks" in included_sections and pack.get("typical_tasks"):
        tasks = pack.get("typical_tasks") or []
        parts.append("Типичные задачи: " + ", ".join(str(t) for t in tasks[:5]))
    if "methods" in included_sections and pack.get("methods"):
        parts.append("Методы: " + ", ".join(str(m) for m in (pack.get("methods") or [])[:5]))
    text = "\n".join(parts).strip()
    return (text[:max_chars] + "…") if len(text) > max_chars else text


def _build_profile(
    step: str,
    primary_domain: Optional[str],
    secondary_domains: list[str],
    compact_context: str,
    step_specific_focus: str,
    selection_reason: str,
    included_sections: list[str],
    excluded_sections: list[str],
    context_profile_type: str,
    effective_ctx: dict[str, Any],
) -> dict[str, Any]:
    """Собрать объект профиля по контракту DOMAIN_PROMPT_PROFILE_MODEL."""
    profile_key = f"{step}_{context_profile_type}"
    return {
        "workflow_step": step,
        "prompt_profile_key": profile_key,
        "primary_domain": primary_domain,
        "secondary_domains": secondary_domains,
        "context_profile_type": context_profile_type,
        "compact_context": compact_context,
        "step_specific_focus": step_specific_focus,
        "included_sections": included_sections,
        "excluded_sections": excluded_sections,
        "selection_reason": selection_reason,
        "domain_override": effective_ctx.get("domain_override", False),
        "domain_override_reason": effective_ctx.get("domain_override_reason") or "",
    }


def build_pipeline_domain_prompt(
    task_id: int,
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """Domain prompt для pipeline: execution, methods, typical tasks. До ~800 символов."""
    effective = get_effective_domain_context(task_id, task_text)
    primary = effective.get("selected_primary_domain")
    if not primary:
        return _build_profile(
            STEP_PIPELINE, None, [], "",
            "No domain", effective.get("context_selection_reason", "fallback"),
            [], ["summary", "strengths", "typical_tasks"], "execution", effective,
        )
    pack = build_context_pack(primary)
    included = ["summary", "strengths", "typical_tasks", "methods"]
    excluded = ["interaction_style", "not_for"]
    compact = _pack_to_compact(pack, included, MAX_PIPELINE)
    return _build_profile(
        STEP_PIPELINE,
        primary,
        effective.get("selected_secondary_domains") or [],
        compact,
        "task execution, methods, typical tasks",
        effective.get("context_selection_reason") or "auto",
        included,
        excluded,
        "execution",
        effective,
    )


def build_roundtable_domain_prompt(
    task_id: int,
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """Domain prompt для roundtable: viewpoints, trade-offs. До ~600 символов."""
    effective = get_effective_domain_context(task_id, task_text)
    primary = effective.get("selected_primary_domain")
    if not primary:
        return _build_profile(
            STEP_ROUNDTABLE, None, [], "",
            "No domain", effective.get("context_selection_reason", "fallback"),
            [], ["summary", "strengths", "typical_tasks"], "viewpoints", effective,
        )
    pack = build_context_pack(primary)
    included = ["summary", "strengths", "typical_tasks"]
    excluded = ["methods", "interaction_style", "not_for"]
    compact = _pack_to_compact(pack, included, MAX_ROUNDTABLE)
    return _build_profile(
        STEP_ROUNDTABLE,
        primary,
        effective.get("selected_secondary_domains") or [],
        compact,
        "viewpoints, collaboration, trade-offs",
        effective.get("context_selection_reason") or "auto",
        included,
        excluded,
        "viewpoints",
        effective,
    )


def build_court_domain_prompt(
    task_id: int,
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """Domain prompt для court: judgement, risk framing. До ~500 символов."""
    effective = get_effective_domain_context(task_id, task_text)
    primary = effective.get("selected_primary_domain")
    if not primary:
        return _build_profile(
            STEP_COURT, None, [], "",
            "No domain", effective.get("context_selection_reason", "fallback"),
            [], ["summary", "strengths", "typical_tasks"], "judgement", effective,
        )
    pack = build_context_pack(primary)
    included = ["summary", "strengths"]
    excluded = ["typical_tasks", "methods", "interaction_style", "not_for"]
    compact = _pack_to_compact(pack, included, MAX_COURT)
    return _build_profile(
        STEP_COURT,
        primary,
        effective.get("selected_secondary_domains") or [],
        compact,
        "judgement, decision rationale, risk framing",
        effective.get("context_selection_reason") or "auto",
        included,
        excluded,
        "judgement",
        effective,
    )


def build_domain_prompt_for_step(
    task_id: int,
    step: str,
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """Единая точка: построить domain prompt профиль для шага."""
    if step == STEP_PIPELINE:
        return build_pipeline_domain_prompt(task_id, task_text)
    if step == STEP_ROUNDTABLE:
        return build_roundtable_domain_prompt(task_id, task_text)
    if step == STEP_COURT:
        return build_court_domain_prompt(task_id, task_text)
    # fallback: pipeline-style
    return build_pipeline_domain_prompt(task_id, task_text)
