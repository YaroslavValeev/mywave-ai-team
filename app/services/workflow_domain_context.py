# app/services/workflow_domain_context.py — Phase 10.1: effective domain context for workflow and override
from __future__ import annotations

from typing import Any, Optional

from app.services.domain_triage import select_context_for_task, build_task_domain_metadata
from app.services.domain_context_packs import build_context_pack
from app.services.domain_registry import get_domain
from app.services.domain_override_store import get_override, set_override

DOMAIN_CONTEXT_VERSION = "1.0"
COMPACT_CONTEXT_MAX = 1500


def _build_compact_for_domain(domain_key: str) -> str:
    """Собрать compact context для одного домена (для override)."""
    pack = build_context_pack(domain_key)
    if not pack:
        return ""
    summary = (pack.get("summary") or "")[:400]
    strengths = (pack.get("strengths") or [])[:5]
    name = pack.get("canonical_name", domain_key)
    parts = [f"[{name}] {summary}"]
    if strengths:
        parts.append("Ключевые слова: " + ", ".join(strengths[:5]))
    return "\n".join(parts)[:COMPACT_CONTEXT_MAX]


def build_workflow_domain_context(
    task_text: str,
    task_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Собрать полный workflow domain context (auto или с учётом override).
    Если task_id задан и есть override — используется override primary.
    """
    override = get_override(task_id) if task_id is not None else None
    if override and override.get("override_active"):
        primary = override.get("new_primary_domain")
        compact = _build_compact_for_domain(primary) if primary else ""
        return {
            "selected_primary_domain": primary,
            "selected_secondary_domains": [],
            "selected_context_pack_keys": [primary] if primary else [],
            "compact_context": compact,
            "context_selection_reason": override.get("override_reason") or "Owner override",
            "context_selection_source": "override",
            "domain_override": True,
            "domain_override_source": override.get("override_source", ""),
            "domain_override_reason": override.get("override_reason") or "",
            "domain_context_version": DOMAIN_CONTEXT_VERSION,
        }
    sel = select_context_for_task(task_text or "")
    primary = sel.get("primary_domain_key")
    secondary = sel.get("selected_context_packs", [])[1:3] if isinstance(sel.get("selected_context_packs"), list) else []
    if primary and primary in secondary:
        secondary = [k for k in secondary if k != primary]
    return {
        "selected_primary_domain": primary,
        "selected_secondary_domains": secondary[:2],
        "selected_context_pack_keys": sel.get("selected_context_packs", []),
        "compact_context": (sel.get("compact_context") or "")[:COMPACT_CONTEXT_MAX],
        "context_selection_reason": sel.get("reason", ""),
        "context_selection_source": "auto" if primary else "fallback",
        "domain_override": False,
        "domain_override_source": "",
        "domain_override_reason": "",
        "domain_context_version": DOMAIN_CONTEXT_VERSION,
    }


def select_domain_context_for_workflow(
    task_text: str,
    task_id: Optional[int] = None,
) -> dict[str, Any]:
    """Алиас для build_workflow_domain_context (то же поведение)."""
    return build_workflow_domain_context(task_text, task_id)


def apply_domain_override(
    task_id: int,
    primary_domain: str,
    reason: Optional[str] = None,
    actor: str = "owner",
    source: str = "telegram",
) -> dict[str, Any]:
    """
    Установить owner override для задачи. Валидация primary_domain через registry.
    Возвращает запись override или ошибку.
    """
    dom = get_domain(primary_domain)
    if not dom:
        return {"success": False, "error": "unknown_domain", "message": f"Домен '{primary_domain}' не найден в registry"}
    from app.services.task_domain_store import get_task_domain_metadata
    from app.storage.repositories import get_session_factory, TaskRepository
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
    previous = None
    if task and getattr(task, "owner_text", None):
        meta = get_task_domain_metadata(task_id)
        if meta:
            previous = meta.get("primary_domain")
    rec = set_override(
        task_id=task_id,
        new_primary_domain=primary_domain,
        reason=reason,
        actor=actor,
        source=source,
        previous_primary_domain=previous,
    )
    return {"success": True, "override": rec}


def get_effective_domain_context(
    task_id: Optional[int],
    task_text: Optional[str] = None,
) -> dict[str, Any]:
    """
    Эффективный domain context для задачи (с учётом override).
    Если task_id не передан, task_text обязателен — тогда только auto.
    """
    if task_id is not None and task_text is None:
        from app.storage.repositories import get_session_factory, TaskRepository
        Session = get_session_factory()
        with Session() as session:
            task = TaskRepository(session).get_task(task_id)
        task_text = getattr(task, "owner_text", None) or "" if task else ""
    return build_workflow_domain_context(task_text or "", task_id)


def explain_effective_domain_context(
    task_id: Optional[int] = None,
    task_text: Optional[str] = None,
) -> str:
    """Человекочитаемое объяснение эффективного контекста."""
    ctx = get_effective_domain_context(task_id, task_text)
    primary = ctx.get("selected_primary_domain") or "—"
    source = ctx.get("context_selection_source", "auto")
    override = " (override)" if ctx.get("domain_override") else ""
    reason = (ctx.get("context_selection_reason") or "")[:80]
    return f"Effective domain: {primary}{override}. Source: {source}. {reason}"