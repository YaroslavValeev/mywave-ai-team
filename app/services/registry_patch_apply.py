# app/services/registry_patch_apply.py — Phase 10.7: dry-run, validate, apply, rollback
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from app.services.registry_backups import create_snapshot, restore_from_backup
from app.services.refinement_exports import build_registry_patch_candidate
from app.services.registry_patch_builder import SAFE_PATCH_TYPES, build_patch_candidate
from app.services.refinement_proposal_store import get_proposal, update_proposal_status
from app.services.registry_validation import (
    check_duplicate_specialization_key,
    validate_domain_registry_structure,
    validate_specializations_structure,
    validate_yaml_content,
)

_PATCHES_META_PATH = Path(__file__).resolve().parents[1] / "data" / "registry_patches.json"


def _get_repo():
    from app.storage.repositories import get_session_factory, TaskRepository
    session = get_session_factory()()
    try:
        return TaskRepository(session)
    finally:
        session.close()


def _audit(event_type: str, **payload: Any) -> None:
    try:
        from app.shared.audit import log_audit
        repo = _get_repo()
        log_audit(repo, event_type, task_id=None, payload=payload)
    except Exception:
        pass


def _load_patches_meta() -> dict:
    if not _PATCHES_META_PATH.exists():
        return {"patches": {}}
    try:
        return json.loads(_PATCHES_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"patches": {}}


def _save_patches_meta(data: dict) -> None:
    _PATCHES_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATCHES_META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _compute_new_specializations_content(target_path: Path, candidate: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Построить новое содержимое specializations.yaml. Phase 11.8: + add_entry, append_*, update_summary."""
    raw = candidate.get("raw_candidate") or build_registry_patch_candidate(candidate.get("proposal_id", ""))
    if raw.get("error"):
        return None, raw.get("error", "unknown")
    ptype = candidate.get("patch_type", "")

    if ptype == "add_specialization_profile":
        return _compute_add_specialization_entry(target_path, raw)
    if ptype in ("append_specialization_keyword", "append_guardrail_note", "update_summary_minor"):
        return _compute_append_specialization(target_path, raw, ptype)
    return None, f"unsupported patch_type for specializations: {ptype}"


def _compute_add_specialization_entry(target_path: Path, raw: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Добавить новую запись в specializations."""
    yaml_suggestion = raw.get("yaml_suggestion")
    target_key = raw.get("target_key")
    if not yaml_suggestion or not target_key:
        return None, "missing yaml_suggestion or target_key"
    if not target_path.exists():
        return None, "target file not found"
    try:
        current = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, str(e)
    if not current or "specializations" not in current:
        return None, "invalid specializations structure"
    wrapped = "specializations:\n" + yaml_suggestion
    try:
        parsed = yaml.safe_load(wrapped)
    except Exception as e:
        return None, f"yaml_suggestion parse: {e}"
    new_entries = (parsed or {}).get("specializations") or {}
    if target_key not in new_entries:
        return None, "target_key not in parsed suggestion"
    if target_key in (current.get("specializations") or {}):
        return None, "duplicate specialization key"
    merged = dict((current.get("specializations") or {}))
    merged[target_key] = new_entries[target_key]
    new_data = {"specializations": merged}
    try:
        out = yaml.safe_dump(new_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return out, None
    except Exception as e:
        return None, str(e)


def _compute_append_specialization(target_path: Path, raw: dict[str, Any], ptype: str) -> tuple[Optional[str], Optional[str]]:
    """Append в selection_keywords/guardrails или update summary. Phase 11.8."""
    target_key = raw.get("target_key")
    append_value = raw.get("append_value")
    if not target_key:
        return None, "missing target_key"
    if not target_path.exists():
        return None, "target file not found"
    try:
        current = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, str(e)
    spec = (current or {}).get("specializations") or {}
    if target_key not in spec:
        return None, f"specialization key not found: {target_key}"
    entry = dict(spec[target_key])
    if ptype == "append_specialization_keyword":
        lst = list(entry.get("selection_keywords") or [])
        if append_value and append_value not in lst:
            lst.append(append_value)
        entry["selection_keywords"] = lst
    elif ptype == "append_guardrail_note":
        lst = list(entry.get("guardrails") or [])
        if append_value and append_value not in lst:
            lst.append(append_value)
        entry["guardrails"] = lst
    elif ptype == "update_summary_minor":
        if append_value:
            entry["summary"] = str(append_value)[:500]
    else:
        return None, f"unsupported: {ptype}"
    spec[target_key] = entry
    new_data = {"specializations": spec}
    try:
        out = yaml.safe_dump(new_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return out, None
    except Exception as e:
        return None, str(e)


def _compute_new_domain_registry_content(target_path: Path, raw: dict[str, Any], ptype: str) -> tuple[Optional[str], Optional[str]]:
    """Append в domain_registry (routing_keywords, typical_requests, aliases). Phase 11.8."""
    target_key = raw.get("target_key")
    append_value = raw.get("append_value")
    if not target_key or not append_value:
        return None, "missing target_key or append_value"
    if not target_path.exists():
        return None, "target file not found"
    try:
        current = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, str(e)
    domains = (current or {}).get("domains") or {}
    if target_key not in domains:
        return None, f"domain key not found: {target_key}"
    entry = dict(domains[target_key])
    if ptype == "append_routing_keyword":
        lst = list(entry.get("routing_keywords") or [])
        if append_value not in lst:
            lst.append(append_value)
        entry["routing_keywords"] = lst
    elif ptype == "append_typical_request":
        lst = list(entry.get("typical_requests") or [])
        if append_value not in lst:
            lst.append(append_value)
        entry["typical_requests"] = lst
    elif ptype == "add_alias":
        lst = list(entry.get("aliases") or [])
        if append_value not in lst:
            lst.append(append_value)
        entry["aliases"] = lst
    else:
        return None, f"unsupported domain patch_type: {ptype}"
    domains[target_key] = entry
    new_data = {"domains": domains}
    try:
        out = yaml.safe_dump(new_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return out, None
    except Exception as e:
        return None, str(e)


def _compute_new_content(target_path: Path, patch: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Dispatcher: specializations vs domain_registry по patch_type. Phase 11.8."""
    ptype = patch.get("patch_type", "")
    raw = patch.get("raw_candidate") or {}
    if ptype in ("add_specialization_profile", "append_specialization_keyword", "append_guardrail_note", "update_summary_minor"):
        return _compute_new_specializations_content(target_path, patch)
    if ptype in ("append_routing_keyword", "append_typical_request", "add_alias"):
        return _compute_new_domain_registry_content(target_path, raw, ptype)
    return None, f"unsupported patch_type: {ptype}"


def dry_run_patch(proposal_id: str) -> dict[str, Any]:
    """Dry-run: diff_summary, validation preview, apply_allowed; файлы не меняются."""
    patch = build_patch_candidate(proposal_id)
    if not patch.get("error"):
        _audit("registry_patch_built", proposal_id=proposal_id, patch_type=patch.get("patch_type"), target_file=patch.get("target_file"), risk_level=patch.get("risk_level"))
    if patch.get("error"):
        _audit("registry_patch_failed", proposal_id=proposal_id, reason=patch.get("error"))
        return {
            "proposal_id": proposal_id,
            "diff_summary": None,
            "validation_preview": {"status": "error", "errors": [patch.get("error")]},
            "apply_allowed": False,
            "reason": patch.get("error"),
        }
    if not patch.get("apply_allowed"):
        _audit("registry_patch_dry_run", proposal_id=proposal_id, apply_allowed=False)
        return {
            "proposal_id": proposal_id,
            "diff_summary": patch.get("diff_summary"),
            "validation_preview": {"status": "skipped", "reason": "not auto-applicable"},
            "apply_allowed": False,
            "reason": "high-risk or unsupported patch type",
        }
    target_path = patch.get("target_path")
    if not target_path:
        target_path = Path(patch.get("target_file") or "")
    if not target_path.is_absolute():
        target_path = Path(__file__).resolve().parents[1] / target_path
    new_content, err = _compute_new_content(target_path, patch)
    if err:
        _audit("registry_patch_failed", proposal_id=proposal_id, reason=err)
        return {
            "proposal_id": proposal_id,
            "diff_summary": patch.get("diff_summary"),
            "validation_preview": {"status": "error", "errors": [err]},
            "apply_allowed": False,
            "reason": err,
        }
    val_status, val_errors, _ = validate_yaml_content(new_content)
    if val_status != "ok":
        _audit("registry_patch_dry_run", proposal_id=proposal_id, apply_allowed=False)
        return {
            "proposal_id": proposal_id,
            "diff_summary": patch.get("diff_summary"),
            "validation_preview": {"status": "error", "errors": val_errors},
            "apply_allowed": False,
            "reason": "validation failed",
        }
    data = yaml.safe_load(new_content)
    ptype = patch.get("patch_type", "")
    if "specializations" in str(patch.get("target_file", "")) or ptype.startswith("add_specialization") or ptype.startswith("append_specialization") or ptype.startswith("append_guardrail") or ptype.startswith("update_summary"):
        struct_ok, struct_errs = validate_specializations_structure(data)
    else:
        struct_ok, struct_errs = validate_domain_registry_structure(data)
    if struct_ok != "ok":
        _audit("registry_patch_dry_run", proposal_id=proposal_id, apply_allowed=False)
        return {
            "proposal_id": proposal_id,
            "diff_summary": patch.get("diff_summary"),
            "validation_preview": {"status": "error", "errors": struct_errs},
            "apply_allowed": False,
            "reason": "structure validation failed",
        }
    _audit("registry_patch_dry_run", proposal_id=proposal_id, diff_summary=patch.get("diff_summary"), apply_allowed=True)
    return {
        "proposal_id": proposal_id,
        "diff_summary": patch.get("diff_summary"),
        "validation_preview": {"status": "ok"},
        "apply_allowed": True,
    }


def validate_patch_candidate(proposal_id: str) -> dict[str, Any]:
    """Валидация кандидата: проверка структуры и дубликатов по «новому» содержимому."""
    patch = build_patch_candidate(proposal_id)
    if patch.get("error"):
        return {"validation_status": "error", "validation_errors": [patch.get("error")], "proposal_id": proposal_id}
    if not patch.get("apply_allowed"):
        return {"validation_status": "skipped", "validation_errors": [], "proposal_id": proposal_id, "reason": "not auto-applicable"}
    target_path = patch.get("target_path") or Path(patch.get("target_file") or "")
    if not isinstance(target_path, Path):
        target_path = Path(target_path)
    if not target_path.is_absolute():
        target_path = Path(__file__).resolve().parents[1] / target_path
    new_content, err = _compute_new_content(target_path, patch)
    if err:
        _audit("registry_patch_validated", proposal_id=proposal_id, validation_status="error")
        return {"validation_status": "error", "validation_errors": [err], "proposal_id": proposal_id}
    val_status, val_errors, _ = validate_yaml_content(new_content)
    if val_status != "ok":
        _audit("registry_patch_validated", proposal_id=proposal_id, validation_status="error")
        return {"validation_status": "error", "validation_errors": val_errors, "proposal_id": proposal_id}
    data = yaml.safe_load(new_content)
    ptype = patch.get("patch_type", "")
    if "specializations" in str(patch.get("target_file", "")) or ptype.startswith("add_specialization") or ptype.startswith("append_specialization") or ptype.startswith("append_guardrail") or ptype.startswith("update_summary"):
        struct_ok, struct_errs = validate_specializations_structure(data)
        if struct_ok != "ok":
            _audit("registry_patch_validated", proposal_id=proposal_id, validation_status="error")
            return {"validation_status": "error", "validation_errors": struct_errs, "proposal_id": proposal_id}
        if ptype == "add_specialization_profile":
            key = (patch.get("raw_candidate") or {}).get("target_key")
            if key and check_duplicate_specialization_key(data, key):
                _audit("registry_patch_validated", proposal_id=proposal_id, validation_status="error")
                return {"validation_status": "error", "validation_errors": [f"duplicate key: {key}"], "proposal_id": proposal_id}
    else:
        struct_ok, struct_errs = validate_domain_registry_structure(data)
        if struct_ok != "ok":
            _audit("registry_patch_validated", proposal_id=proposal_id, validation_status="error")
            return {"validation_status": "error", "validation_errors": struct_errs, "proposal_id": proposal_id}
    _audit("registry_patch_validated", proposal_id=proposal_id, validation_status="ok")
    return {"validation_status": "ok", "validation_errors": [], "proposal_id": proposal_id}


def apply_patch_candidate(proposal_id: str, actor: Optional[str] = None) -> dict[str, Any]:
    """Применить патч только для safe type; перед этим validation и backup."""
    p = get_proposal(proposal_id)
    if not p:
        return {"success": False, "error": "proposal not found", "proposal_id": proposal_id}
    if p.get("status") != "accepted":
        return {"success": False, "error": "proposal not accepted", "proposal_id": proposal_id}
    patch = build_patch_candidate(proposal_id)
    if patch.get("error"):
        _audit("registry_patch_failed", proposal_id=proposal_id, reason=patch.get("error"))
        return {"success": False, "error": patch.get("error"), "proposal_id": proposal_id}
    if not patch.get("apply_allowed") or patch.get("patch_type") not in SAFE_PATCH_TYPES:
        _audit("registry_patch_failed", proposal_id=proposal_id, reason="not auto-applicable")
        return {"success": False, "error": "high-risk or unsupported patch type; manual apply required", "proposal_id": proposal_id}
    val = validate_patch_candidate(proposal_id)
    if val.get("validation_status") != "ok":
        _audit("registry_patch_failed", proposal_id=proposal_id, reason="validation failed", validation_errors=val.get("validation_errors"))
        return {"success": False, "error": "validation failed", "validation_errors": val.get("validation_errors"), "proposal_id": proposal_id}
    target_path = patch.get("target_path") or Path(patch.get("target_file") or "")
    if not isinstance(target_path, Path):
        target_path = Path(target_path)
    if not target_path.is_absolute():
        target_path = Path(__file__).resolve().parents[1] / target_path
    new_content, err = _compute_new_content(target_path, patch)
    if err:
        _audit("registry_patch_failed", proposal_id=proposal_id, reason=err)
        return {"success": False, "error": err, "proposal_id": proposal_id}
    backup_ref, backup_err = create_snapshot(target_path)
    if backup_err:
        _audit("registry_patch_failed", proposal_id=proposal_id, reason=f"backup failed: {backup_err}")
        return {"success": False, "error": f"backup failed: {backup_err}", "proposal_id": proposal_id}
    try:
        target_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        _audit("registry_patch_failed", proposal_id=proposal_id, reason=str(e))
        return {"success": False, "error": str(e), "proposal_id": proposal_id}
    patch_id = patch.get("patch_id", "")
    meta = _load_patches_meta()
    meta.setdefault("patches", {})[patch_id] = {
        "proposal_id": proposal_id,
        "backup_ref": backup_ref,
        "target_file": str(target_path),
        "patch_type": patch.get("patch_type"),
    }
    _save_patches_meta(meta)
    from datetime import datetime, timezone
    update_proposal_status(proposal_id, status="applied", applied_at=datetime.now(timezone.utc).isoformat())
    _audit("registry_patch_applied", proposal_id=proposal_id, patch_id=patch_id, target_file=str(target_path), backup_ref=backup_ref, patch_type=patch.get("patch_type"), actor=actor or "system")
    try:
        from app.services.tuning_outcomes import record_tuning_baseline_on_patch_apply

        record_tuning_baseline_on_patch_apply(proposal_id, patch_id=patch_id, window_days=30)
    except Exception:
        pass
    return {
        "success": True,
        "proposal_id": proposal_id,
        "patch_id": patch_id,
        "target_file": str(target_path),
        "backup_ref": backup_ref,
        "applied_by": actor or "system",
    }


def rollback_patch(patch_id: str, actor: Optional[str] = None) -> dict[str, Any]:
    """Восстановить файл из backup; только для зарегистрированных патчей."""
    meta = _load_patches_meta()
    rec = (meta.get("patches") or {}).get(patch_id)
    if not rec:
        return {"success": False, "error": "patch not found", "patch_id": patch_id}
    backup_ref = rec.get("backup_ref")
    target_file = rec.get("target_file")
    if not backup_ref or not target_file:
        return {"success": False, "error": "missing backup_ref or target_file", "patch_id": patch_id}
    err = restore_from_backup(backup_ref, Path(target_file))
    if err:
        _audit("registry_patch_failed", proposal_id=rec.get("proposal_id"), reason=f"rollback failed: {err}")
        return {"success": False, "error": err, "patch_id": patch_id}
    _audit("registry_patch_rollback", patch_id=patch_id, target_file=target_file, actor=actor or "system")
    return {"success": True, "patch_id": patch_id, "target_file": target_file}


def verify_patch_after_apply(proposal_id: str) -> dict[str, Any]:
    """Проверить, что изменение присутствует в файле (перечитать и проверить ключ)."""
    patch = build_patch_candidate(proposal_id)
    if patch.get("error"):
        return {"verified": False, "error": patch.get("error"), "proposal_id": proposal_id}
    target_path = patch.get("target_path") or Path(patch.get("target_file") or "")
    if not isinstance(target_path, Path):
        target_path = Path(target_path)
    if not target_path.is_absolute():
        target_path = Path(__file__).resolve().parents[1] / target_path
    key = (patch.get("raw_candidate") or {}).get("target_key")
    if not key or not target_path.exists():
        return {"verified": False, "error": "no target key or file", "proposal_id": proposal_id}
    try:
        data = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"verified": False, "error": str(e), "proposal_id": proposal_id}
    spec = (data or {}).get("specializations") or {}
    verified = key in spec
    return {"verified": verified, "proposal_id": proposal_id, "target_key": key}
