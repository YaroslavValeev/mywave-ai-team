# app/services/production_readiness.py — Phase 12.2: production hardening checks
"""Единый слой проверок эксплуатационной готовности."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
_REGISTRY_BASE = Path(__file__).resolve().parents[2] / "app" / "config"


def _check(name: str, ok: bool, reason: str = "") -> dict[str, Any]:
    return {"check_name": name, "ok": ok, "reason": reason or ("ok" if ok else "failed")}


def check_critical_flows() -> list[dict[str, Any]]:
    """Проверка критичных потоков: owner dashboard, API, action center, collaboration, tuning, domain/project."""
    results = []
    # owner_dashboard
    try:
        from app.services.owner_dashboard import get_dashboard_overview
        get_dashboard_overview()
        results.append(_check("owner_dashboard", True))
    except Exception as e:
        results.append(_check("owner_dashboard", False, str(e)[:200]))

    # action_center
    try:
        from app.services.action_center import list_available_actions
        list_available_actions("owner")
        results.append(_check("action_center", True))
    except Exception as e:
        results.append(_check("action_center", False, str(e)[:200]))

    # collaboration_execution
    try:
        from app.services.collaboration_execution import list_collaboration_executions
        list_collaboration_executions(limit=1)
        results.append(_check("collaboration_execution", True))
    except Exception as e:
        results.append(_check("collaboration_execution", False, str(e)[:200]))

    # tuning_refinement_patch
    try:
        from app.services.refinement_proposals import list_refinement_proposals
        list_refinement_proposals(limit=1)
        results.append(_check("tuning_refinement_patch", True))
    except Exception as e:
        results.append(_check("tuning_refinement_patch", False, str(e)[:200]))

    # domain_project_portfolio
    try:
        from app.services.project_queries import list_projects
        list_projects(limit=1)
        results.append(_check("domain_project_portfolio", True))
    except Exception as e:
        results.append(_check("domain_project_portfolio", False, str(e)[:200]))

    try:
        from app.services.domain_registry import list_domains
        list_domains()
        results.append(_check("domain_registry", True))
    except Exception as e:
        results.append(_check("domain_registry", False, str(e)[:200]))

    return results


def check_runtime_entrypoints() -> list[dict[str, Any]]:
    """Проверка конфигурации entrypoints: OWNER_API_KEY, TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID."""
    results = []
    key = os.getenv("OWNER_API_KEY") or os.getenv("DASHBOARD_API_KEY")
    results.append(_check("owner_api_key", bool(key), "set" if key else "not set"))

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    results.append(_check("telegram_bot_token", bool(token), "set" if token else "not set"))

    owner_id = os.getenv("OWNER_CHAT_ID")
    results.append(_check("owner_chat_id", bool(owner_id), "set" if owner_id else "not set (dev: all allowed)"))

    return results


def check_store_health() -> list[dict[str, Any]]:
    """Проверка stores: main DB, registry YAML."""
    results = []
    # main_db
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            _ = repo.get_all_tasks()[:1]
        results.append(_check("main_db", True))
    except Exception as e:
        results.append(_check("main_db", False, str(e)[:200]))

    # registry yaml
    for fname in ("domain_registry", "specializations", "routing", "policy"):
        path = _CONFIG_DIR / f"{fname}.yaml"
        if not path.exists():
            results.append(_check(f"registry_{fname}", True, "optional, not found"))
            continue
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                yaml.safe_load(f)
            results.append(_check(f"registry_{fname}", True))
        except Exception as e:
            results.append(_check(f"registry_{fname}", False, str(e)[:120]))

    return results


def check_backup_readiness() -> list[dict[str, Any]]:
    """Проверка backup: registry backup dir, postgres backup script."""
    results = []
    try:
        from app.services.registry_backups import get_backup_dir
        d = get_backup_dir()
        d.mkdir(parents=True, exist_ok=True)
        test_file = d / ".readiness_test"
        try:
            test_file.write_text("ok")
            test_file.unlink(missing_ok=True)
            results.append(_check("registry_backup_dir", True))
        except Exception as e:
            results.append(_check("registry_backup_dir", False, str(e)[:120]))
    except Exception as e:
        results.append(_check("registry_backup_dir", False, str(e)[:120]))

    root = Path(__file__).resolve().parents[2]
    backup_script = root / "scripts" / "backup_postgres.sh"
    results.append(_check("postgres_backup_script", backup_script.exists(), "exists" if backup_script.exists() else "not found"))

    return results


def check_patch_and_outcome_paths() -> list[dict[str, Any]]:
    """Проверка patch/outcome: registry_backups, collaboration outcome persist."""
    results = []
    try:
        from app.services.registry_backups import create_snapshot, get_backup_dir
        d = get_backup_dir()
        results.append(_check("registry_backups_module", True))
    except Exception as e:
        results.append(_check("registry_backups_module", False, str(e)[:120]))

    try:
        from app.services.collaboration_outcomes import list_collaboration_outcomes
        list_collaboration_outcomes(limit=1)
        results.append(_check("collaboration_outcome_persist", True))
    except Exception as e:
        results.append(_check("collaboration_outcome_persist", False, str(e)[:120]))

    return results


def run_production_readiness_checks() -> dict[str, Any]:
    """Запустить все проверки и вернуть raw results."""
    flows = check_critical_flows()
    entrypoints = check_runtime_entrypoints()
    stores = check_store_health()
    backups = check_backup_readiness()
    patch_outcome = check_patch_and_outcome_paths()

    all_checks = flows + entrypoints + stores + backups + patch_outcome
    failed = [c for c in all_checks if not c.get("ok")]
    critical_failures = [
        c for c in failed
        if c.get("check_name") in ("main_db", "owner_api_key", "owner_dashboard", "action_center")
    ]

    if critical_failures:
        level = "not_ready"
    elif failed:
        level = "degraded"
    else:
        level = "ready"

    attention = []
    for c in failed[:5]:
        attention.append(f"{c.get('check_name', '?')}: {c.get('reason', '')[:60]}")
    if len(failed) > 5:
        attention.append(f"... и ещё {len(failed) - 5}")

    return {
        "ready": level == "ready",
        "level": level,
        "failed_checks": [{"check_name": c["check_name"], "reason": c.get("reason", "")} for c in failed],
        "degraded_checks": [] if level == "ready" else [{"check_name": c["check_name"], "reason": c.get("reason", "")} for c in failed],
        "attention_items": attention[:3],
        "checks": all_checks,
        "counts": {"total": len(all_checks), "passed": len(all_checks) - len(failed), "failed": len(failed)},
    }


def get_production_readiness_summary() -> dict[str, Any]:
    """Компактный summary для owner surface."""
    raw = run_production_readiness_checks()
    return {
        "ready": raw["ready"],
        "level": raw["level"],
        "failed_checks": raw["failed_checks"],
        "attention_items": raw["attention_items"],
        "counts": raw["counts"],
    }
