# app/presenters/refinement_proposal_presenters.py — Phase 10.6: proposal view-models
from __future__ import annotations

from typing import Any, List


def present_refinement_proposal_list(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Список proposals для web: compact view."""
    return {
        "items": [
            {
                "proposal_id": p.get("proposal_id"),
                "proposal_type": p.get("proposal_type"),
                "target_layer": p.get("target_layer"),
                "target_key": p.get("target_key"),
                "reason": (p.get("reason") or "")[:150],
                "severity": p.get("severity"),
                "status": p.get("status"),
                "created_at": p.get("created_at"),
            }
            for p in items
        ],
        "count": len(items),
    }


def present_refinement_proposal_card(p: dict[str, Any]) -> dict[str, Any]:
    """Одна карточка proposal для web."""
    if not p:
        return {}
    return {
        "proposal_id": p.get("proposal_id"),
        "proposal_type": p.get("proposal_type"),
        "target_layer": p.get("target_layer"),
        "target_key": p.get("target_key"),
        "reason": p.get("reason"),
        "evidence_summary": p.get("evidence_summary"),
        "recommended_change": p.get("recommended_change"),
        "source_signals": p.get("source_signals"),
        "severity": p.get("severity"),
        "status": p.get("status"),
        "created_at": p.get("created_at"),
        "reviewed_at": p.get("reviewed_at"),
        "applied_at": p.get("applied_at"),
        "reviewer": p.get("reviewer"),
        "notes": p.get("notes"),
        "domain_key": p.get("domain_key"),
        "workflow_step": p.get("workflow_step"),
        "project_key": p.get("project_key"),
        "source_tuning_candidate_id": p.get("source_tuning_candidate_id"),
    }


def present_refinement_review_result(updated: dict[str, Any] | None) -> dict[str, Any]:
    """Результат review (accept/reject)."""
    if not updated:
        return {"success": False, "message": "Proposal not found or invalid"}
    return {
        "success": True,
        "proposal_id": updated.get("proposal_id"),
        "status": updated.get("status"),
        "reviewer": updated.get("reviewer"),
    }


def present_refinement_export(export_data: dict[str, Any] | None) -> dict[str, Any]:
    """Экспорт proposal (patch candidate) для web."""
    if not export_data:
        return {"success": False, "message": "Export failed"}
    return {
        "success": True,
        "proposal_id": export_data.get("proposal_id"),
        "proposal": present_refinement_proposal_card(export_data.get("proposal") or {}),
        "patch_candidate": export_data.get("patch_candidate"),
        "export_format": export_data.get("export_format", "refinement_candidate"),
    }


def format_refinement_proposal_list_telegram(items: List[dict[str, Any]], limit: int = 10) -> str:
    """Краткий текст списка для Telegram."""
    if not items:
        return "Refinement proposals: пусто. Сгенерируйте: /refinement_proposals generate"
    lines = ["Refinement proposals:"]
    for p in items[:limit]:
        lines.append(f"  {p.get('proposal_id', '')[:20]} [{p.get('status')}] {p.get('proposal_type', '')} — {(p.get('reason') or '')[:50]}")
    return "\n".join(lines)


def format_refinement_proposal_card_telegram(p: dict[str, Any]) -> str:
    """Одна карточка для Telegram."""
    if not p:
        return "Proposal не найден."
    lines = [
        f"Proposal: {p.get('proposal_id', '')}",
        f"Type: {p.get('proposal_type')} | Status: {p.get('status')}",
        f"Target: {p.get('target_layer')} / {p.get('target_key')}",
        f"Reason: {(p.get('reason') or '')[:200]}",
    ]
    if p.get("evidence_summary"):
        lines.append(f"Evidence: {(p.get('evidence_summary') or '')[:120]}")
    lines.append("Review: /review_refinement <id> accept|reject [note]")
    return "\n".join(lines)
