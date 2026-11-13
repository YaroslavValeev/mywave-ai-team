# app/presenters/registry_patch_presenters.py — Phase 10.7: patch workflow view-models
from __future__ import annotations

from typing import Any


def present_patch_candidate(patch: dict[str, Any]) -> dict[str, Any]:
    """Patch candidate для web: target_file, patch_type, risk, diff_summary, apply_allowed."""
    if not patch:
        return {}
    if patch.get("error"):
        return {"error": patch.get("error"), "proposal_id": patch.get("proposal_id"), "apply_allowed": False}
    return {
        "patch_id": patch.get("patch_id"),
        "proposal_id": patch.get("proposal_id"),
        "target_file": patch.get("target_file"),
        "target_layer": patch.get("target_layer"),
        "patch_type": patch.get("patch_type"),
        "patch_scope": patch.get("patch_scope"),
        "risk_level": patch.get("risk_level"),
        "diff_summary": patch.get("diff_summary"),
        "apply_allowed": patch.get("apply_allowed", False),
        "rollback_supported": patch.get("rollback_supported", False),
        "validation_status": patch.get("validation_status"),
    }


def present_patch_dry_run(result: dict[str, Any]) -> dict[str, Any]:
    """Результат dry-run для web."""
    return {
        "proposal_id": result.get("proposal_id"),
        "diff_summary": result.get("diff_summary"),
        "validation_preview": result.get("validation_preview"),
        "apply_allowed": result.get("apply_allowed", False),
        "reason": result.get("reason"),
    }


def present_patch_validation(result: dict[str, Any]) -> dict[str, Any]:
    """Результат валидации для web."""
    return {
        "proposal_id": result.get("proposal_id"),
        "validation_status": result.get("validation_status"),
        "validation_errors": result.get("validation_errors", []),
        "reason": result.get("reason"),
    }


def present_patch_apply_result(result: dict[str, Any]) -> dict[str, Any]:
    """Результат apply для web."""
    return {
        "success": result.get("success", False),
        "proposal_id": result.get("proposal_id"),
        "patch_id": result.get("patch_id"),
        "target_file": result.get("target_file"),
        "backup_ref": result.get("backup_ref"),
        "applied_by": result.get("applied_by"),
        "error": result.get("error"),
    }


def present_patch_error(error: str, proposal_id: str = None, **extra: Any) -> dict[str, Any]:
    """Ошибка патча для web."""
    out = {"success": False, "error": error, **extra}
    if proposal_id is not None:
        out["proposal_id"] = proposal_id
    return out


def format_patch_candidate_telegram(patch: dict[str, Any]) -> str:
    """Краткий текст patch candidate для Telegram."""
    if patch.get("error"):
        return f"Patch: ошибка — {patch.get('error')}"
    lines = [
        f"Patch: {patch.get('patch_type')} → {patch.get('target_file', '')}",
        f"Risk: {patch.get('risk_level')} | Apply: {'да' if patch.get('apply_allowed') else 'нет'}",
        (patch.get("diff_summary") or "")[:200],
    ]
    return "\n".join(lines)


def format_patch_dry_run_telegram(result: dict[str, Any]) -> str:
    """Результат dry-run для Telegram."""
    lines = [f"Dry-run {result.get('proposal_id', '')}: apply_allowed={result.get('apply_allowed')}"]
    if result.get("reason"):
        lines.append(result["reason"])
    if result.get("validation_preview"):
        v = result["validation_preview"]
        if v.get("status") == "error":
            lines.append("Validation: " + "; ".join((v.get("errors") or [])[:2]))
    return "\n".join(lines)


def format_patch_apply_telegram(result: dict[str, Any]) -> str:
    """Результат apply для Telegram."""
    if result.get("success"):
        return f"Apply OK: {result.get('patch_id', '')} → {result.get('target_file', '')}"
    return f"Apply failed: {result.get('error', 'unknown')}"
