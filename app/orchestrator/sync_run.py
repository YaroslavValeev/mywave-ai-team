# app/orchestrator/sync_run.py — единый синхронный цикл оркестрации (API + Telegram).
from __future__ import annotations

import logging
from typing import Any

from app.config import get_policy
from app.business_execution.execution_runner import (
    build_cursor_prompts,
    build_execution_tasks,
    create_project_structure,
)
from app.business_execution.execution_engine import ensure_action_instance_blob, ensure_execution_pack_for_task
from app.governance.owner_flow import on_orchestration_awaiting_owner
from app.orchestrator.court import run_court
from app.orchestrator.exploration import build_default_scenarios, detect_exploration_intent
from app.orchestrator.pipeline import run_pipeline
from app.orchestrator.roundtable import run_roundtable
from app.orchestrator.triage import run_triage
from app.shared.audit import log_audit
from app.shared.critical_flags import check_critical_execute, infer_flags_from_task
from app.intake.memory_writer import write_task_memory_after_orchestration
from app.owner_memory.schemas import ExecutionRuleContext
from app.owner_memory.rules_engine import apply_rules_to_execution, explain_rule_effects
from app.owner_memory.service import OwnerMemoryService, owner_memory_enabled
from app.storage.repositories import TaskRepository
from app.orchestrator.triage_snapshot import persist_triage_snapshot, resync_triage_dict_from_store

logger = logging.getLogger(__name__)


def _read_exploration_selected_id_from_dict(exploration: dict[str, Any] | None) -> str:
    """Нормализованный id выбранного сценария (API/Telegram могли писать разные ключи)."""
    if not isinstance(exploration, dict):
        return ""
    for key in ("selected_option_id", "selected_option", "scenario_id", "option_id"):
        val = exploration.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _read_exploration_selected_id(task: Any) -> str:
    if not task:
        return ""
    ba = task.business_action_json if isinstance(getattr(task, "business_action_json", None), dict) else {}
    ex = ba.get("exploration")
    return _read_exploration_selected_id_from_dict(ex if isinstance(ex, dict) else None)


def _exploration_waiting_without_selection(task: Any) -> bool:
    """Уже WAIT_OWNER из-за exploration и сценарий ещё не выбран (повторный API/Telegram run не должен идти в court)."""
    if not task or getattr(task, "status", None) != "WAIT_OWNER":
        return False
    ba = task.business_action_json if isinstance(getattr(task, "business_action_json", None), dict) else {}
    ex = ba.get("exploration")
    if not isinstance(ex, dict) or not ex.get("exploration_mode"):
        return False
    return not _read_exploration_selected_id(task)


def _execution_ready_summary(task_id: int, exr: dict[str, Any]) -> str:
    """Текст для Telegram/API после dry-run execution из сценария (без pipeline/court)."""
    n_dirs = len(exr.get("project_structure") or []) if isinstance(exr.get("project_structure"), list) else 0
    n_tasks = len(exr.get("agent_tasks") or []) if isinstance(exr.get("agent_tasks"), list) else 0
    n_prompts = len(exr.get("cursor_prompts") or []) if isinstance(exr.get("cursor_prompts"), list) else 0
    lines = [
        "🧠 Execution готов",
        "",
        f"📁 Структура проекта создана ({n_dirs} элементов)",
        f"⚙️ Задачи агентам собраны ({n_tasks})",
        f"💬 Cursor-промпты готовы ({n_prompts})",
        "",
        "👉 Следующий шаг:",
        "Запусти execution через Cursor",
        "",
        f"Миссия #{task_id}: сценарий «{(exr.get('selected_option') or {}).get('title') or 'выбранный'}».",
    ]
    return "\n".join(lines)


def _execution_ready_idempotent_return(
    repo: TaskRepository, task_id: int, source: str, limit: int, *, reason: str
) -> dict[str, Any]:
    task = repo.get_task(task_id)
    ba = dict(task.business_action_json or {}) if task else {}
    exr = ba.get("execution_from_scenario") if isinstance(ba.get("execution_from_scenario"), dict) else {}
    summary = _execution_ready_summary(task_id, exr)[:limit]
    logger.info(
        "EXECUTION_READY_EARLY_RETURN task_id=%s source=%s reason=%s",
        task_id,
        source,
        reason,
    )
    log_audit(
        repo,
        "execution_ready_early_return",
        task_id=task_id,
        payload={"source": source, "reason": reason},
    )
    return {
        "ok": True,
        "status": "EXECUTION_READY",
        "report_path": None,
        "summary": summary,
        "reason": "execution_ready",
    }


def _exploration_summary(bundle: dict[str, Any], task_id: int) -> str:
    options = bundle.get("options") if isinstance(bundle.get("options"), list) else []
    lines = [f"Exploration для миссии #{task_id}: выберите сценарий запуска."]
    for opt in options[:3]:
        lines.append(f"- {opt.get('id')}: {opt.get('title')} — {opt.get('result')}")
    rec = (bundle.get("recommendation") or "").strip()
    if rec:
        lines.append(f"Рекомендация: {rec}")
    return "\n".join(lines)


def _ensure_exploration_bundle(repo: TaskRepository, task_id: int, owner_text: str, triage_result: dict[str, Any]) -> dict[str, Any]:
    task = repo.get_task(task_id)
    ba = dict(task.business_action_json or {}) if task else {}
    existing = ba.get("exploration") if isinstance(ba.get("exploration"), dict) else {}
    if not existing:
        existing = build_default_scenarios(owner_text)
    existing["exploration_mode"] = True
    existing["triage_domain"] = triage_result.get("domain")
    existing["triage_task_type"] = triage_result.get("task_type")
    ba["exploration"] = existing
    repo.update_task(task_id, business_action_json=ba)
    logger.info("EXPLORATION_MODE_ON task_id=%s options=%s", task_id, len(existing.get("options") or []))
    return existing


def _run_execution_from_scenario(repo: TaskRepository, task_id: int, triage_result: dict[str, Any]) -> None:
    task = repo.get_task(task_id)
    if not task:
        return
    base = dict(task.business_action_json or {})
    exploration = base.get("exploration") if isinstance(base.get("exploration"), dict) else {}
    selected_id = _read_exploration_selected_id_from_dict(exploration)
    options = exploration.get("options") if isinstance(exploration.get("options"), list) else []
    selected = next((o for o in options if str(o.get("id")) == selected_id), None)
    if not isinstance(selected, dict):
        return
    logger.info("SCENARIO_SELECTED task_id=%s option_id=%s", task_id, selected_id)
    log_audit(
        repo,
        "SCENARIO_SELECTED",
        task_id=task_id,
        payload={"selected_option_id": selected_id},
    )
    logger.info("REAL_EXECUTION_STARTED task_id=%s", task_id)
    project_structure = create_project_structure(task, selected)
    logger.info("PROJECT_STRUCTURE_CREATED task_id=%s dirs=%s", task_id, len(project_structure))
    execution_tasks = build_execution_tasks(task, selected)
    logger.info("EXECUTION_TASKS_BUILT task_id=%s tasks=%s", task_id, len(execution_tasks))
    cursor_prompts = build_cursor_prompts(task, selected, execution_tasks)
    logger.info("CURSOR_PROMPTS_GENERATED task_id=%s prompts=%s", task_id, len(cursor_prompts))
    execution_from_scenario = {
        "selected_option": selected,
        "project_structure": project_structure,
        "agent_tasks": execution_tasks,
        "sources_seed": [],
        "cursor_prompts": cursor_prompts,
        "auto_run": False,
        "system_note": "Система подготовила execution. Можно запускать через Cursor.",
        "cursor_prompt": f"Выполни сценарий {selected.get('title')} для задачи #{task_id}: "
        "создай структуру проекта и подготовь артефакты по первой стране.",
        "triage_domain": triage_result.get("domain"),
        "triage_task_type": triage_result.get("task_type"),
    }
    base["execution_from_scenario"] = execution_from_scenario
    base["execution_ready"] = True
    repo.update_task(task_id, business_action_json=base)
    logger.info("EXECUTION_FROM_SCENARIO task_id=%s option_id=%s", task_id, selected_id)
    log_audit(
        repo,
        "EXECUTION_FROM_SCENARIO",
        task_id=task_id,
        payload={"selected_option_id": selected_id, "auto_run": False},
    )
    log_audit(
        repo,
        "exploration_execution_started",
        task_id=task_id,
        payload={"selected_option_id": selected_id, "selected_title": selected.get("title")},
    )


def _apply_revenue_gm_after_triage(repo: TaskRepository, task_id: int, owner_text: str | None, triage_result: dict[str, Any]) -> None:
    """Для #TASK без Smart Intake: дозаполнить gm_decision при revenue override."""
    if not triage_result.get("revenue_intent_override"):
        return
    task = repo.get_task(task_id)
    if not task:
        return
    ba = dict(task.business_action_json or {})
    gm = dict(ba.get("gm_decision") or {})
    raw = (owner_text or task.owner_text or "").strip()
    gm.setdefault("execution_mode", "full")
    gm.setdefault("action", "create_task")
    gm.setdefault("requires_approval", True)
    if not gm.get("risk_level"):
        gm["risk_level"] = "high"
    if not gm.get("agents_plan"):
        gm["agents_plan"] = ["BD", "FIN", "LEGAL"]
    gm["workflow_template"] = "business"
    gm["owner_workstream"] = "revenue"
    gm["business_value_hint"] = raw[:400] if raw else "Коммерческий результат: клиенты, лиды, оплата."
    gm["next_business_step"] = raw[:500] if raw else "Сформулировать измеримый шаг к первой оплате."
    ba["gm_decision"] = gm
    prev_score = float(task.impact_score or 0.0)
    repo.update_task(
        task_id,
        business_action_json=ba,
        business_type="revenue",
        impact_level="high",
        impact_score=max(prev_score, 0.85),
    )


def _summary_limit(max_chars: int | None) -> int:
    if max_chars is not None:
        return max_chars
    return int(get_policy().get("limits", {}).get("telegram_summary_max_chars", 1200))


def run_sync_orchestration(
    repo: TaskRepository,
    task_id: int,
    *,
    source: str = "api",
    control: Any = None,
    summary_max_chars: int | None = None,
) -> dict[str, Any] | None:
    """
    Triage → pipeline → roundtable → court с едиными audit/governance шагами.

    Возвращает dict с ключами ok, status, report_path, summary или None, если задача не найдена.
    """
    task = repo.get_task(task_id)
    if not task:
        return None

    limit = _summary_limit(summary_max_chars)

    if getattr(task, "status", None) == "EXECUTION_READY":
        return _execution_ready_idempotent_return(repo, task_id, source, limit, reason="repeat_execution_ready")

    # Повторный вызов (Dashboard /api/tasks/{id}/pipeline/run, фон, дубль Telegram) при уже выданных сценариях
    # не должен снова гонять triage → pipeline → court.
    if _exploration_waiting_without_selection(task):
        ba = dict(task.business_action_json or {})
        bundle = ba.get("exploration") if isinstance(ba.get("exploration"), dict) else {}
        summary = _exploration_summary(bundle, task_id)[:limit]
        logger.info(
            "EXPLORATION_EARLY_RETURN task_id=%s source=%s reason=repeat_wait_owner exploration_mode=True selected_option_id=%s",
            task_id,
            source,
            None,
        )
        log_audit(
            repo,
            "exploration_early_return",
            task_id=task_id,
            payload={"source": source, "reason": "repeat_wait_owner"},
        )
        return {"ok": True, "status": "WAIT_OWNER", "report_path": None, "summary": summary}

    if control:
        control.set_phase("triage", message="Координатор определяет маршрут и тип задачи.", current_step="COORDINATOR")
        control.check_cancelled()
    triage_result = run_triage(task.owner_text)
    logger.info(
        "triage_result domain=%s task_type=%s revenue_override=%s",
        triage_result.get("domain"),
        triage_result.get("task_type"),
        triage_result.get("revenue_intent_override"),
    )
    triage_updates = {
        key: triage_result.get(key)
        for key in ("domain", "task_type", "criticality", "plan_or_execute")
        if triage_result.get(key) is not None
    }
    repo.update_task(task_id, status="TRIAGED", **triage_updates)
    _apply_revenue_gm_after_triage(repo, task_id, task.owner_text, triage_result)
    persist_triage_snapshot(repo, task_id, triage_result)
    triage_result = resync_triage_dict_from_store(repo, task_id, triage_result)
    # Колонки Task = SoT для court/дашборда; resync уже канонизировал dict (в т.ч. revenue-lock).
    td = triage_result.get("domain")
    tt = triage_result.get("task_type")
    tc = triage_result.get("criticality")
    tp = triage_result.get("plan_or_execute")
    repo.update_task(
        task_id,
        domain=td,
        task_type=tt,
        criticality=tc,
        plan_or_execute=tp,
    )
    st = repo.get_task(task_id)
    logger.info(
        "TASK_AFTER_TRIAGE domain=%s task_type=%s revenue_override=%s",
        triage_result.get("domain"),
        triage_result.get("task_type"),
        triage_result.get("revenue_intent_override"),
    )
    logger.info(
        "TASK_STORED domain=%s task_type=%s triage_meta.domain=%s",
        getattr(st, "domain", None),
        getattr(st, "task_type", None),
        ((st.business_action_json or {}).get("triage_meta") or {}).get("domain") if st and isinstance(st.business_action_json, dict) else None,
    )
    owner_for_detect = (getattr(st, "owner_text", None) or task.owner_text or "").strip()
    exploration_detect = detect_exploration_intent(owner_for_detect)
    selected_preflight = _read_exploration_selected_id(st)
    exploration_on = bool(triage_result.get("exploration_mode")) or exploration_detect
    logger.info(
        "SYNC_RUN_INPUT task_id=%s exploration_mode_triage=%s exploration_mode_detect=%s exploration_on=%s selected_option_id=%s",
        task_id,
        triage_result.get("exploration_mode"),
        exploration_detect,
        exploration_on,
        selected_preflight or None,
    )
    log_audit(repo, "triage_done", task_id=task_id, payload={**triage_result, "source": source})

    if exploration_on:
        bundle = _ensure_exploration_bundle(repo, task_id, task.owner_text or "", triage_result)
        fresh = repo.get_task(task_id)
        selected_option_id = _read_exploration_selected_id(fresh) or str(bundle.get("selected_option_id") or "").strip()
        if not selected_option_id:
            repo.update_task(task_id, status="WAIT_OWNER")
            summary = _exploration_summary(bundle, task_id)[:limit]
            logger.info(
                "EXPLORATION_EARLY_RETURN task_id=%s source=%s reason=no_selection exploration_on=True selected_option_id=%s",
                task_id,
                source,
                None,
            )
            log_audit(
                repo,
                "exploration_early_return",
                task_id=task_id,
                payload={"source": source, "reason": "no_selection"},
            )
            log_audit(
                repo,
                "exploration_options_ready",
                task_id=task_id,
                payload={"options": bundle.get("options"), "recommended_option_id": bundle.get("recommended_option_id")},
            )
            return {"ok": True, "status": "WAIT_OWNER", "report_path": None, "summary": summary}
        _run_execution_from_scenario(repo, task_id, triage_result)
        after_ex = repo.get_task(task_id)
        exr = (
            (after_ex.business_action_json or {}).get("execution_from_scenario")
            if after_ex and isinstance(after_ex.business_action_json, dict)
            else None
        )
        if not isinstance(exr, dict):
            logger.warning(
                "EXECUTION_FROM_SCENARIO_MISSING task_id=%s exploration_selected=%s",
                task_id,
                _read_exploration_selected_id(after_ex) if after_ex else None,
            )
            fail_summary = (
                "Не удалось собрать execution по выбранному сценарию. "
                "Проверьте, что option_id есть в списке exploration."
            )[:limit]
            repo.update_task(task_id, status="WAIT_OWNER")
            log_audit(
                repo,
                "execution_ready_failed",
                task_id=task_id,
                payload={"source": source, "reason": "scenario_payload_missing"},
            )
            return {"ok": True, "status": "WAIT_OWNER", "report_path": None, "summary": fail_summary}
        ba = dict(after_ex.business_action_json or {})
        ba["execution_ready"] = True
        repo.update_task(task_id, business_action_json=ba, status="EXECUTION_READY")
        summary = _execution_ready_summary(task_id, exr)[:limit]
        logger.info(
            "EXPLORATION_EXECUTION_READY_RETURN task_id=%s source=%s reason=execution_ready",
            task_id,
            source,
        )
        log_audit(
            repo,
            "exploration_execution_ready",
            task_id=task_id,
            payload={"source": source, "reason": "execution_ready", "auto_run": False},
        )
        return {
            "ok": True,
            "status": "EXECUTION_READY",
            "report_path": None,
            "summary": summary,
            "reason": "execution_ready",
        }

    logger.info("pipeline_input domain=%s task_type=%s", triage_result.get("domain"), triage_result.get("task_type"))
    if control:
        control.set_phase("pipeline", message="AI-Team запускает рабочий pipeline.", current_step="PM")
        control.check_cancelled()
    repo.update_task(task_id, status="IN_PIPELINE")
    log_audit(repo, "pipeline_start", task_id=task_id, payload={"source": source, "status_after": "IN_PIPELINE"})
    pipeline_result = run_pipeline(task_id, triage_result, repo, control=control)
    log_audit(
        repo,
        "pipeline_done",
        task_id=task_id,
        payload={"steps": len(pipeline_result.get("handoffs", [])), "source": source, "status_after": "IN_PIPELINE"},
    )

    if control:
        control.set_phase("roundtable", message="Совет обсуждает риски и ограничения.", current_step="RC")
        control.check_cancelled()
    repo.update_task(task_id, status="IN_ROUNDTABLE")
    roundtable_result = run_roundtable(task_id, triage_result, pipeline_result, repo, control=control)
    log_audit(
        repo,
        "roundtable_done",
        task_id=task_id,
        payload={"risks": len(roundtable_result.get("risk_table", [])), "source": source, "status_after": "IN_ROUNDTABLE"},
    )

    if control:
        control.set_phase("court", message="Суд формирует финальный verdict.", current_step="JUDGE")
        control.check_cancelled()
    repo.update_task(task_id, status="IN_COURT")
    court_result = run_court(task_id, triage_result, pipeline_result, roundtable_result, repo, control=control)
    report_path = court_result.get("report_path")
    summary = court_result.get("summary", "")[:limit]

    if control:
        control.set_phase(
            "execution_pack_generation",
            message="Система формирует готовый execution pack для следующего бизнес-шага.",
            current_step="GM",
        )
        control.check_cancelled()

    latest_task = repo.get_task(task_id)
    if latest_task:
        project = repo.get_project(latest_task.project_id) if latest_task.project_id else None
        all_tasks = repo.get_all_tasks()
        pack = ensure_execution_pack_for_task(latest_task, project, all_tasks=all_tasks)
        if pack:
            base_json = latest_task.business_action_json if isinstance(latest_task.business_action_json, dict) else {}
            merged_json = dict(base_json)
            merged_json["execution_pack"] = pack.model_dump()
            gm = merged_json.get("gm_decision")
            if isinstance(gm, dict):
                gm = dict(gm)
                gm["execution_pack"] = pack.model_dump()
                merged_json["gm_decision"] = gm
            repo.update_task(task_id, business_action_json=merged_json)
            log_audit(
                repo,
                "execution_pack_generated",
                task_id=task_id,
                payload={"pack_type": pack.pack_type, "source": source},
            )

        refreshed = repo.get_task(task_id)
        if refreshed:
            tracked = ensure_action_instance_blob(refreshed, project, all_tasks=all_tasks)
            if tracked:
                repo.update_task(task_id, business_action_json=tracked)

    flags = infer_flags_from_task(
        domain=triage_result.get("domain", ""),
        task_type=triage_result.get("task_type", ""),
        execute_gate=triage_result.get("execute_gate", ""),
        plan_or_execute=triage_result.get("plan_or_execute", ""),
    )
    needs_approval = check_critical_execute(flags) or any(
        risk.get("owner_approval_needed") for risk in roundtable_result.get("risk_table", [])
    )
    owner_exec_payload: dict = {}
    if owner_memory_enabled():
        svc = OwnerMemoryService(repo)
        owner_bundle = svc.build_owner_rules_bundle(
            context_scopes=["execution", "governance", "global"],
            target_scope="task",
            target_id=str(task_id),
        )
        exec_ctx = ExecutionRuleContext(
            plan_or_execute=str(triage_result.get("plan_or_execute") or ""),
            domain=str(triage_result.get("domain") or ""),
            task_type=str(triage_result.get("task_type") or ""),
            execute_gate=str(triage_result.get("execute_gate") or ""),
            flags=flags,
            needs_approval_base=needs_approval,
            task_id=task_id,
        )
        needs_approval, owner_eng = apply_rules_to_execution(exec_ctx, bundle=owner_bundle)
        owner_exec_payload = explain_rule_effects(owner_eng)

    final_status = "WAIT_OWNER" if needs_approval else "DONE"

    if control:
        control.set_phase(
            "finalize",
            message="Система фиксирует итоговый статус задачи.",
            current_step="OWNER" if needs_approval else "JUDGE",
        )
        control.check_cancelled()
    repo.update_task(task_id, status=final_status, report_path=report_path, summary=summary)
    on_orchestration_awaiting_owner(repo, task_id, final_status)
    od_payload = {
        "report_path": report_path,
        "final_status": final_status,
        "source": source,
        "status_after": final_status,
    }
    if owner_exec_payload:
        od_payload["owner_memory_execution"] = owner_exec_payload
    log_audit(repo, "orchestration_done", task_id=task_id, payload=od_payload)
    write_task_memory_after_orchestration(repo, task_id)
    return {"ok": True, "status": final_status, "report_path": report_path, "summary": summary}
