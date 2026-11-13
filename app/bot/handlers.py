# app/bot/handlers.py — intake #TASK, callbacks, кнопки
import asyncio
import logging
import os
from typing import Callable, Awaitable

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_telegram_config, get_policy
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.audit import log_audit, log_decision
try:
    from app.canonical_bridge import (
        write_canonical_task_if_enabled,
        get_canonical_task_id,
        write_run_if_enabled,
        write_event_if_enabled,
        write_approval_request_if_enabled,
        write_approval_resolution_if_enabled,
        write_artifact_if_enabled,
        set_canonical_state,
        get_canonical_state,
        should_agents_control_runtime_after_approval,
        handle_rework_via_molt_if_enabled,
    )
except ImportError:
    def write_canonical_task_if_enabled(*a, **kw): return None
    def get_canonical_task_id(*a, **kw): return None
    def write_run_if_enabled(*a, **kw): return None
    def write_event_if_enabled(*a, **kw): return False
    def write_approval_request_if_enabled(*a, **kw): return None
    def write_approval_resolution_if_enabled(*a, **kw): return False
    def write_artifact_if_enabled(*a, **kw): return None
    def set_canonical_state(*a, **kw): return None
    def get_canonical_state(*a, **kw): return {}
    def should_agents_control_runtime_after_approval(): return True
    def handle_rework_via_molt_if_enabled(*a, **kw): return None
from app.shared.redaction import redact
from app.services.owner_queries import (
    get_system_status_summary,
    get_active_tasks,
    get_task_card,
    get_pending_approvals,
    get_recent_artifacts,
    get_runs_summary,
    _molt_health_check,
)
from app.owner_summary import build_short_summary, build_detailed_summary
from app.services.owner_insights import (
    get_weekly_digest,
    get_blockers_summary,
    get_awaiting_decisions_summary,
    get_completed_recently_summary,
    get_project_activity_summary,
    get_rework_signal_summary,
    get_degraded_signal_summary,
    get_long_running_summary,
)
from app.presenters.owner_presenters import (
    format_summary,
    format_task_card,
    format_approvals_list,
    format_artifacts_list,
    format_tasks_list,
    format_runs_list,
    format_detailed_summary,
)
from app.presenters.owner_insight_presenters import (
    format_weekly_digest,
    format_blockers_summary,
    format_awaiting_decisions_summary,
    format_completed_recently_summary,
    format_project_activity_summary,
    format_rework_signal_summary,
    format_degraded_signal_summary,
    format_long_running_summary,
)
from app.services.owner_recommendations import (
    get_next_actions,
    get_decision_queue,
    get_project_health_summary,
    get_risk_signals,
    get_strategic_weekly_digest,
    get_monthly_digest_baseline,
)
from app.presenters.owner_recommendation_presenters import (
    format_next_actions as format_next_actions_msg,
    format_decision_queue as format_decision_queue_msg,
    format_project_health_summary as format_project_health_msg,
    format_risk_signals as format_risk_signals_msg,
    format_strategic_weekly_digest as format_strategic_weekly_msg,
    format_monthly_digest_baseline as format_monthly_digest_msg,
)
from app.services.project_queries import (
    list_projects,
    get_project_overview,
    get_project_health,
    get_project_tasks,
    get_project_pending_approvals,
    get_project_recent_artifacts,
    get_project_risks,
    get_project_decision_queue,
)
from app.presenters.project_presenters import (
    present_project_list,
    present_project_overview,
    present_project_health,
    present_project_tasks,
    present_project_approvals,
    present_project_artifacts,
    present_project_risks,
    present_project_decision_queue,
    format_project_list_text,
    format_project_card_text,
)
from app.services.collaboration_flows import (
    get_collaboration_hotspots,
    get_collaboration_recommendations,
    get_cross_role_handoffs,
    get_project_handoff_signals,
    get_role_collaboration_summary,
)
from app.presenters.collaboration_presenters import (
    format_collaboration_telegram,
    format_handoffs_telegram,
    format_project_handoffs_telegram,
    format_role_collaboration_telegram,
    present_project_handoff_signals,
    present_role_collaboration_summary,
)
from app.services.owner_portfolio import (
    get_portfolio_overview,
    get_portfolio_focus_list,
    get_rework_hotspots,
    get_degraded_hotspots,
    get_approvals_backlog_by_project,
)
from app.presenters.owner_portfolio_presenters import (
    present_portfolio_overview,
    present_portfolio_focus_list,
    present_approvals_backlog_by_project,
    present_rework_hotspots,
    present_degraded_hotspots,
    format_portfolio_overview_text,
    format_focus_list_text,
    format_hotspots_text,
    format_approvals_backlog_text,
)
from app.services.role_views import get_owner_view, get_operator_view, get_executor_view, get_reviewer_view
from app.presenters.role_presenters import (
    format_owner_view_text,
    format_operator_view_text,
    format_executor_view_text,
    format_reviewer_view_text,
)
from app.services.action_center import list_available_actions, can_execute_action, execute_action
from app.services.role_access import (
    resolve_actor_role,
    deny_or_fallback_role,
    resolve_and_log,
    check_action_access_and_log,
)
from app.presenters.action_presenters import format_action_list, format_action_result, format_action_error
from app.presenters.role_access_presenters import format_access_denied_message
from app.services.production_readiness import get_production_readiness_summary
from app.presenters.production_readiness_presenters import format_readiness_telegram
from app.services.domain_registry import list_domains, get_domain
from app.services.expert_routing import suggest_domains_for_task
from app.presenters.domain_presenters import (
    format_domain_list_text,
    format_domain_card_text,
    format_routing_result_text,
)
from app.orchestrator.triage import run_triage
from app.orchestrator.pipeline import run_pipeline
from app.orchestrator.roundtable import run_roundtable
from app.orchestrator.court import run_court
from app.shared.critical_flags import check_critical_execute, infer_flags_from_task

logger = logging.getLogger(__name__)


def build_owner_buttons(task_id: int) -> InlineKeyboardBuilder:
    cfg = get_telegram_config()
    btns = cfg.get("buttons", {})
    b = InlineKeyboardBuilder()
    b.button(text=btns.get("approve", "✅ Approve"), callback_data=f"a:{task_id}")
    b.button(text=btns.get("rework", "🔁 Rework"), callback_data=f"r:{task_id}")
    b.button(text=btns.get("clarify", "❓ Clarify"), callback_data=f"c:{task_id}")
    b.button(text=btns.get("full", "📄 Full report"), callback_data=f"f:{task_id}")
    b.adjust(2, 2)
    return b


def build_owner_buttons_with_merged(task_id: int) -> InlineKeyboardBuilder:
    """Кнопки + I merged (v0.2)."""
    cfg = get_telegram_config()
    btns = cfg.get("buttons", {})
    b = InlineKeyboardBuilder()
    b.button(text=btns.get("approve", "✅ Approve"), callback_data=f"a:{task_id}")
    b.button(text=btns.get("rework", "🔁 Rework"), callback_data=f"r:{task_id}")
    b.button(text=btns.get("clarify", "❓ Clarify"), callback_data=f"c:{task_id}")
    b.button(text="✅ I merged", callback_data=f"m:{task_id}")
    b.button(text=btns.get("full", "📄 Full report"), callback_data=f"f:{task_id}")
    b.adjust(2, 2, 1)
    return b


def is_owner(chat_id: int) -> bool:
    cfg = get_telegram_config()
    owner_id = cfg.get("owner_chat_id")
    if not owner_id:
        return True  # Если не задан — разрешаем всем (dev)
    try:
        return str(chat_id) == str(owner_id)
    except Exception:
        return False


async def handle_task_intake(message: Message):
    """Обработка сообщения #TASK — создание задачи и запуск оркестрации."""
    logger.info("handle_task_intake chat_id=%s text=%r", message.chat.id, (message.text or "")[:120])
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return

    text = message.text or ""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text=text)
        task_id = task.id
        log_audit(repo, "task_created", task_id=task_id, payload={"owner_text_len": len(text)})
        write_canonical_task_if_enabled(legacy_task_id=task_id, owner_text=text, origin_channel="telegram")
    max_chars = get_policy().get("limits", {}).get("telegram_summary_max_chars", 1200)
    await message.answer(f"Принято. Task #{task_id} в работе. Итог пришлю с кнопками.")

    # Запуск оркестрации в фоне
    asyncio.create_task(_run_orchestration(task_id, message.chat.id, message.bot))


async def _run_orchestration(task_id: int, chat_id: int, bot: Bot, pre_created_run_id: str | None = None):
    """Полный цикл: triage → pipeline → roundtable → court. pre_created_run_id: при rework через Molt run уже создан."""
    Session = get_session_factory()
    max_chars = get_policy().get("limits", {}).get("telegram_summary_max_chars", 1200)
    try:
        with Session() as session:
            repo = TaskRepository(session)
            task = repo.get_task(task_id)
            if not task:
                await bot.send_message(chat_id, f"Ошибка: Task #{task_id} не найден.")
                return

            # TRIAGE
            triage_result = run_triage(task.owner_text)
            repo.update_task(
                task_id,
                status="TRIAGED",
                domain=triage_result.get("domain"),
                task_type=triage_result.get("task_type"),
                criticality=triage_result.get("criticality"),
                plan_or_execute=triage_result.get("plan_or_execute"),
            )
            log_audit(repo, "triage_done", task_id=task_id, payload=triage_result)
            try:
                from app.services.domain_triage import build_task_domain_metadata
                domain_meta = build_task_domain_metadata(task.owner_text)
                log_audit(repo, "domain_triage", task_id=task_id, payload=domain_meta)
            except Exception:
                pass
            try:
                from app.services.workflow_domain_context import get_effective_domain_context
                wf_ctx = get_effective_domain_context(task_id, task.owner_text)
                triage_result["workflow_domain_context"] = wf_ctx
                log_audit(repo, "domain_context_used", task_id=task_id, payload={
                    "primary_domain": wf_ctx.get("selected_primary_domain"),
                    "source": wf_ctx.get("context_selection_source"),
                    "override": wf_ctx.get("domain_override", False),
                })
            except Exception:
                pass

            # Canonical: Run + run_started (при rework через Molt run уже создан — pre_created_run_id)
            canonical_task_id = get_canonical_task_id(task_id)
            if canonical_task_id:
                run_id = pre_created_run_id if pre_created_run_id else write_run_if_enabled(canonical_task_id)
                if run_id:
                    set_canonical_state(
                        task_id,
                        canonical_task_id=canonical_task_id,
                        run_id=run_id,
                        status="run_started",
                        last_event="run_started",
                        clear_approval=True,
                    )
                    write_event_if_enabled(run_id, "run_started")

            # PIPELINE
            repo.update_task(task_id, status="IN_PIPELINE")
            pipeline_result = run_pipeline(task_id, triage_result, repo)
            log_audit(repo, "pipeline_done", task_id=task_id, payload={"steps": len(pipeline_result.get("handoffs", []))})

            # ROUNDTABLE
            repo.update_task(task_id, status="IN_ROUNDTABLE")
            roundtable_result = run_roundtable(task_id, triage_result, pipeline_result, repo)
            log_audit(repo, "roundtable_done", task_id=task_id, payload={"risks": len(roundtable_result.get("risk_table", []))})

            # COURT
            repo.update_task(task_id, status="IN_COURT")
            court_result = run_court(task_id, triage_result, pipeline_result, roundtable_result, repo)
            report_path = court_result.get("report_path")
            summary = court_result.get("summary", "")[:max_chars]

            flags = infer_flags_from_task(
                domain=triage_result.get("domain", ""),
                task_type=triage_result.get("task_type", ""),
                execute_gate=triage_result.get("execute_gate", ""),
                plan_or_execute=triage_result.get("plan_or_execute", ""),
            )
            needs_approval = check_critical_execute(flags)

            if needs_approval:
                repo.update_task(task_id, status="WAIT_OWNER", report_path=report_path, summary=summary)
                state = get_canonical_state(task_id)
                if state.get("run_id") and state.get("canonical_task_id"):
                    approval_id = write_approval_request_if_enabled(
                        state["canonical_task_id"], state["run_id"], "execute_gate", requested_by="telegram_owner"
                    )
                    if approval_id:
                        set_canonical_state(
                            task_id,
                            approval_id=approval_id,
                            status="waiting_approval",
                            last_event="approval_requested",
                        )
                        write_event_if_enabled(state["run_id"], "run_waiting_approval", {"approval_id": approval_id})
                msg = f"✅ Task #{task_id}: результат готов. Нужен апрув для EXECUTE.\n\n{summary}"
                await bot.send_message(
                    chat_id,
                    redact(msg),
                    reply_markup=build_owner_buttons(task_id).as_markup(),
                )
            else:
                repo.update_task(task_id, status="DONE", report_path=report_path, summary=summary)
                state = get_canonical_state(task_id)
                if state.get("run_id"):
                    write_event_if_enabled(state["run_id"], "run_succeeded", {"summary": summary[:200]})
                    if state.get("canonical_task_id") and report_path:
                        write_artifact_if_enabled(
                            state["canonical_task_id"], "report", report_path or "",
                            run_id=state.get("run_id"), title=f"Task #{task_id} report",
                        )
                    set_canonical_state(task_id, status="succeeded", last_event="run_succeeded")
                dashboard_url = _get_dashboard_url()
                msg = f"✅ Task #{task_id} выполнен.\n\n{summary}"
                if dashboard_url:
                    msg += f"\n\n📊 [Dashboard]({dashboard_url}/tasks/{task_id})"
                await bot.send_message(chat_id, redact(msg))

    except Exception as e:
        logger.exception("Orchestration failed for task %s", task_id)
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, "orchestration_error", task_id=task_id, payload={"error": str(e)})
        await bot.send_message(chat_id, redact(f"Ошибка по Task #{task_id}: {str(e)}"))


def _get_dashboard_url() -> str:
    from app.config import get_dashboard_config
    return os.getenv("DASHBOARD_URL") or get_dashboard_config().get("base_url", "http://localhost:8080")


def _load_full_report_text(task) -> str:
    """Текст полного отчёта: файл court/final_report если есть, иначе summary.

    Live runtime helper — restored during reconcile (used by tests/Telegram full report).
    """
    from pathlib import Path

    chunks: list[str] = []
    path_raw = (getattr(task, "report_path", None) or "").strip()
    if path_raw:
        p = Path(path_raw)
        if not p.is_file():
            cand = Path.cwd() / path_raw
            if cand.is_file():
                p = cand
        if p.is_file():
            try:
                body = p.read_text(encoding="utf-8", errors="replace").strip()
                if body:
                    chunks.append(body)
            except OSError:
                pass
    if not chunks and getattr(task, "summary", None):
        chunks.append(str(task.summary).strip())
    if not chunks:
        return "(отчёт ещё не сформирован)"
    return "\n\n".join(chunks)


async def _send_long_telegram(bot, chat_id: int, header: str, body: str) -> None:
    """Отправить длинный текст частями (лимит Telegram ~4096)."""
    from app.bot.notify import send_with_retry

    limit = 3500
    full = f"{header}\n\n{body}".strip()
    if len(full) <= 4000:
        await send_with_retry(bot, chat_id, full)
        return
    await send_with_retry(bot, chat_id, f"{header}\n\n(ниже частями)")
    start = 0
    part = 1
    while start < len(body):
        chunk = body[start : start + limit]
        await send_with_retry(bot, chat_id, f"📄 Часть {part}:\n\n{chunk}")
        start += limit
        part += 1


async def handle_owner_callback(cb: CallbackQuery):
    """Обработка кнопок Approve/Rework/Clarify/Full report."""
    if not is_owner(cb.message.chat.id if cb.message else 0):
        await cb.answer("Доступ только для Owner.", show_alert=True)
        return

    parts = cb.data.split(":", 1)
    if len(parts) != 2:
        await cb.answer("Неверный callback.")
        return
    code, tid = parts[0], parts[1]
    try:
        task_id = int(tid)
    except ValueError:
        await cb.answer("Неверный task_id.")
        return

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            await cb.answer("Задача не найдена.", show_alert=True)
            return

        if code == "f":
            report = task.summary or task.report_path or "(нет)"
            if task.report_path:
                report = f"Отчёт: {task.report_path}\n\n{task.summary or ''}"
            await cb.message.answer(redact(f"📄 Full report Task #{task_id}:\n\n{report}"))
            await cb.answer()
            return

        if code == "m":
            log_decision(repo, task_id, decision="merged", owner_approval=True)
            log_audit(repo, "OWNER_MERGED", task_id=task_id, payload={"decision": "i_merged"})
            repo.update_task(task_id, status="DONE")
            state = get_canonical_state(task_id)
            if state.get("approval_id") and state.get("run_id"):
                write_approval_resolution_if_enabled(
                    state["approval_id"], state["run_id"], approved=True,
                    approved_by="telegram_owner", comment="merged",
                    terminal_on_approve=True,
                )
                set_canonical_state(task_id, status="succeeded", last_event="approval_merged")
            if state.get("run_id") and should_agents_control_runtime_after_approval():
                write_event_if_enabled(state["run_id"], "run_succeeded", {"decision": "merged"})
            await cb.message.answer(redact(f"✅ Task #{task_id}: merge подтверждён. Задача закрыта."))
            await cb.answer()
            return

        owner_approval = code == "a"
        log_decision(repo, task_id, decision=code, owner_approval=owner_approval)
        state = get_canonical_state(task_id)
        rework_new_run_id = None
        if state.get("approval_id") and state.get("run_id"):
            if code == "r" and state.get("canonical_task_id"):
                rework_new_run_id = handle_rework_via_molt_if_enabled(
                    task_id,
                    state["canonical_task_id"],
                    state["run_id"],
                    state["approval_id"],
                    approved_by="telegram_owner",
                    comment="rework",
                )
            if rework_new_run_id is None:
                write_approval_resolution_if_enabled(
                    state["approval_id"], state["run_id"],
                    approved=(code == "a"),
                    approved_by="telegram_owner",
                    comment="rework" if code == "r" else ("clarify" if code == "c" else "approve"),
                    terminal_on_approve=(code == "a"),
                )
                status_after = "succeeded" if code == "a" else ("resumed" if code == "r" else "clarify")
                set_canonical_state(task_id, status=status_after, last_event=f"approval_{code}")
        if code == "a" and state.get("run_id"):
            if should_agents_control_runtime_after_approval():
                write_event_if_enabled(state["run_id"], "run_succeeded", {"decision": "approve"})
            if state.get("canonical_task_id") and task.report_path:
                write_artifact_if_enabled(
                    state["canonical_task_id"], "report", task.report_path or "",
                    run_id=state.get("run_id"), title=f"Task #{task_id} report",
                )
        if code == "a":
            log_audit(repo, "OWNER_APPROVED", task_id=task_id, payload={"decision": "approve"})
        elif code == "r":
            log_audit(repo, "OWNER_REWORK", task_id=task_id, payload={"decision": "rework"})
        else:
            log_audit(repo, "OWNER_CLARIFY", task_id=task_id, payload={"decision": "clarify"})

        has_pr = bool(task.pr_url)
        if code == "a":
            new_status = "APPROVED_WAIT_MERGE" if has_pr else "DONE"
        elif code == "r":
            new_status = "REWORK"
        else:
            new_status = "NEED_INFO"
        repo.update_task(task_id, status=new_status)

        if code == "a":
            if has_pr:
                await cb.message.answer(redact(f"✅ Task #{task_id} одобрен. Смерджи PR в GitHub, затем нажми «I merged»."))
            else:
                await cb.message.answer(redact(f"✅ Task #{task_id} утверждён."))
        elif code == "r":
            await cb.message.answer(redact(f"🔁 Task #{task_id}: запрошен rework. Запускаю повторный цикл..."))
            asyncio.create_task(_run_orchestration(task_id, cb.message.chat.id, cb.bot, pre_created_run_id=rework_new_run_id))
        else:
            await cb.message.answer(redact(f"❓ Task #{task_id}: нужно уточнение. Напиши вопросы в новом сообщении с #TASK или #CLARIFY."))

    await cb.answer()


async def handle_start(message: Message):
    """Ответ на /start — подсказка, как отправить задачу."""
    await message.answer(
        "Привет! Отправь задачу в формате:\n\n#TASK <описание задачи>\n\n"
        "Пример: #TASK написать тесты для API"
    )


# --- Phase 9.0: owner operational commands ---

async def handle_owner_help(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    await message.answer(
        "Команды:\n"
        "/help — эта справка\n"
        "/status — сводка системы\n"
        "/tasks — список задач\n"
        "/task <id> — карточка задачи\n"
        "/approvals — ожидающие approve\n"
        "/artifacts — последние результаты\n"
        "/runs — активные run\n"
        "/health — статус Molt\n"
        "/summary — развёрнутая сводка\n\n"
        "/digest — weekly management digest\n"
        "/blockers — что тормозит\n"
        "/decisions — что ждёт решения owner\n"
        "/done — что завершилось недавно\n"
        "/insights — project/activity/rework/degraded/long-running\n\n"
        "/next — следующие шаги (3–5)\n"
        "/decisions_queue — приоритетная очередь решений\n"
        "/health_projects — здоровье по группам\n"
        "/risks — риски и рекомендации\n"
        "/weekly_digest — стратегическая недельная сводка\n"
        "/monthly_digest — месячная сводка (30 дней)\n\n"
        "/projects — список проектов (health)\n"
        "/project <key> — карточка проекта (например /project general)\n"
        "/project_domain <key> — domain profile проекта\n"
        "/role_domains — domain recommendations по ролям\n"
        "/domain_pressure — сводка domain pressure по ролям\n\n"
        "/portfolio — обзор портфеля (cross-project)\n"
        "/focus — focus list (top 5 проектов для внимания)\n"
        "/hotspots — rework и degraded hotspots\n"
        "/approvals_backlog — approvals backlog по проектам\n\n"
        "Role views (Phase 9.7):\n"
        "/view_owner — компактный owner summary\n"
        "/view_operator — runtime, stuck, blockers\n"
        "/view_executor — active tasks, artifacts, blockers\n"
        "/view_reviewer — pending approvals, decision queue\n\n"
        "Actions (Phase 9.8):\n"
        "/actions — доступные действия\n"
        "/do <action> — выполнить действие\n"
        "/refresh — обновить статус\n"
        "/recheck — проверить Molt\n"
        "/smoke — smoke-check\n"
        "/readiness — production readiness summary (Phase 12.2)\n"
        "/digest_now — отправить digest сейчас\n"
        "/defer_intervention <id> — отложить intervention 24ч (Phase 12.3)\n\n"
        "💬 Можно писать обычным языком: «что важно», «проблемные проекты», «что делать» и т.д.\n\n"
        "Domain expertise (Phase 9.9/10.1):\n"
        "/domains — список доменов экспертизы\n"
        "/domain <key> — карточка домена\n"
        "/route <текст> — подбор домена по тексту задачи\n"
        "/task_domain <id> — effective domain задачи\n"
        "/set_task_domain <id> <domain_key> [причина] — override домена задачи\n"
        "/clear_task_domain <id> — снять override\n"
        "/task_specialization <id> — профиль специализации по шагам (Phase 10.4)\n"
        "Phase 10.5 — analytics:\n"
        "/domain_analytics [дней] — override summary и hotspots\n"
        "/specialization_analytics [дней] — fallback summary и hotspots\n"
        "/refinement_backlog [дней] — backlog улучшений\n"
        "Phase 10.6 — proposals:\n"
        "/refinement_proposals [generate] — список / сгенерировать из backlog\n"
        "/refinement_proposal <id> — карточка proposal\n"
        "/patch_refinement <id> — patch candidate\n"
        "/dry_run_patch <id> — dry-run\n"
        "/apply_patch <id> — применить safe patch\n"
        "/project_lifecycle <key> — domain lifecycle проекта\n"
        "/domain_lifecycle [дней] — дрифт / нестабильные проекты\n"
        "/review_refinement <id> accept|reject [note] — ревью\n\n"
        "Phase 11.0 — Explanation:\n"
        "/explain_task <id> — почему система так считает по задаче\n"
        "/explain_project <key> — почему по проекту\n"
        "/explain_portfolio — почему focus list\n"
        "/explain_refinement [proposal_id] — почему refinement\n"
        "/explain_collaboration [project_key] — почему collaboration\n\n"
        "Phase 11.1 — Action suggestions:\n"
        "/suggestions — collaboration action suggestions\n"
        "/project_suggestions <key> — suggestions по проекту\n"
        "/role_suggestions <role> — suggestions по роли\n"
        "/decision_support — decision support (options, preferred, risk)\n\n"
        "Phase 11.2 — Tuning:\n"
        "/tuning_candidates — tuning candidates\n"
        "/tuning_candidate <id> — карточка candidate\n"
        "/review_tuning <id> accept|reject [note]\n"
        "/convert_tuning <id> — в proposal\n"
        "/verify_tuning <id> improved|unchanged|worse [note]\n\n"
        "Phase 11.3 — Tuning patch & outcomes:\n"
        "/patchable_tuning — patchable tuning candidates\n"
        "/tuning_outcomes — verified outcomes summary\n"
        "/tuning_outcome <id> — outcome по candidate\n\n"
        "Phase 11.4 — Collaboration execution:\n"
        "/collaboration_executions — список открытых executions\n"
        "/collaboration_execution <id> — карточка\n"
        "/trigger_collaboration <id> — trigger (+ safe action если есть)\n"
        "/close_collaboration <id> [reason]\n\n"
        "Phase 11.5 — Collaboration outcomes:\n"
        "/collaboration_outcomes — список outcomes в окне\n"
        "/collaboration_outcome <id> [evaluate] — outcome; evaluate — пересчёт\n"
        "/collaboration_followup — кому нужен follow-up\n\n"
        "Phase 11.6 — Cross-layer:\n"
        "/effectiveness_synthesis [дней] — tuning + collaboration synthesis\n\n"
        "Phase 11.7 — Intervention planning:\n"
        "/interventions [дней] — приоритетные вмешательства\n"
        "/project_intervention <key> — intervention plan по проекту\n"
        "/portfolio_intervention [дней] — portfolio bundle\n"
        "/cross_layer_intervention [дней] — cross-layer conflict bundle\n\n"
        "Создать задачу: #TASK <описание>"
    )


async def handle_owner_status(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = build_short_summary()
    await message.answer(redact(format_summary(data)))


async def handle_owner_tasks(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    tasks = get_active_tasks(limit=10)
    await message.answer(redact(format_tasks_list(tasks)))


async def handle_owner_task(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /task <id>")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный id задачи.")
        return
    card = get_task_card(task_id)
    if not card:
        await message.answer("Задача не найдена.")
        return
    await message.answer(redact(format_task_card(card)))


async def handle_task_domain(message: Message):
    """Phase 10.1: /task_domain <id> — показать effective domain и override status."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /task_domain <id>")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный id задачи.")
        return
    card = get_task_card(task_id)
    if not card:
        await message.answer("Задача не найдена.")
        return
    edc = card.get("effective_domain_context")
    if not edc:
        await message.answer(f"Task #{task_id}: доменный контекст недоступен.")
        return
    primary = edc.get("selected_primary_domain") or "—"
    lines = [f"Task #{task_id}", f"Экспертиза: {primary}"]
    if edc.get("domain_override"):
        lines.append("Override: yes (owner)")
        if edc.get("domain_override_reason"):
            lines.append(f"Причина: {edc.get('domain_override_reason')[:100]}")
        lines.append("Снять: /clear_task_domain " + str(task_id))
    else:
        lines.append("Изменить: /set_task_domain " + str(task_id) + " <domain_key> [причина]")
    await message.answer(redact("\n".join(lines)))


async def handle_set_task_domain(message: Message):
    """Phase 10.1: /set_task_domain <id> <domain_key> [reason...] — установить override домена."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Использование: /set_task_domain <id> <domain_key> [причина]")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный id задачи.")
        return
    domain_key = (parts[2] or "").strip()
    reason = (parts[3] or "").strip() if len(parts) > 3 else None
    if not domain_key:
        await message.answer("Укажите domain_key (например legal, code, docs).")
        return
    try:
        from app.services.workflow_domain_context import apply_domain_override
        result = apply_domain_override(task_id, domain_key, reason=reason, actor="owner", source="telegram")
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))
        return
    if not result.get("success"):
        await message.answer(redact(result.get("message", result.get("error", "Не удалось установить override."))))
        return
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, "domain_override", task_id=task_id, payload={
                "new_primary_domain": domain_key,
                "reason": reason,
                "actor": "owner",
                "source": "telegram",
            })
    except Exception:
        pass
    rec = result.get("override", {})
    await message.answer(redact(f"Override установлен. Task #{task_id} → {domain_key}" + (f" ({reason[:50]})" if reason else "")))


async def handle_clear_task_domain(message: Message):
    """Phase 10.2: /clear_task_domain <id> — снять override домена."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /clear_task_domain <id>")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный id задачи.")
        return
    try:
        from app.services.domain_override_store import clear_override, get_override
        had = get_override(task_id)
        cleared = clear_override(task_id)
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))
        return
    if not cleared:
        await message.answer(f"Task #{task_id}: override не был установлен.")
        return
    try:
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, "domain_override_cleared", task_id=task_id, payload={
                "previous_primary_domain": had.get("new_primary_domain") if had else None,
                "actor": "owner",
                "source": "telegram",
            })
    except Exception:
        pass
    await message.answer(redact(f"Override снят. Task #{task_id} — снова используется авто-подбор домена."))


async def handle_task_specialization(message: Message):
    """Phase 10.4: /task_specialization <id> — effective domain + per-step specialization, explainability."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /task_specialization <id>")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный id задачи.")
        return
    try:
        from app.services.agent_specializations import suggest_specialization
        from app.storage.repositories import get_session_factory, TaskRepository
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            task = repo.get_task(task_id)
        if not task:
            await message.answer("Задача не найдена.")
            return
        task_text = getattr(task, "owner_text", None)
        pipeline_sel = suggest_specialization(task_id, "pipeline", task_text)
        roundtable_sel = suggest_specialization(task_id, "roundtable", task_text)
        court_sel = suggest_specialization(task_id, "court", task_text)
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))
        return
    lines = [f"Task #{task_id}", f"Экспертиза: {pipeline_sel.get('effective_domain', '—')}", ""]
    for step, sel in [("Pipeline", pipeline_sel), ("Roundtable", roundtable_sel), ("Court", court_sel)]:
        name = sel.get("profile_name") or (sel.get("selected_specialization") or {}).get("specialization_key", "—")
        fallback = " (fallback)" if sel.get("fallback_used") else ""
        lines.append(f"{step}: {name}{fallback}")
        if sel.get("selection_reason"):
            lines.append(f"  {sel.get('selection_reason')[:80]}")
    await message.answer(redact("\n".join(lines)))


async def handle_domain_analytics(message: Message):
    """Phase 10.5: /domain_analytics [дней] — override summary и hotspots."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 30
    if len(parts) >= 2:
        try:
            window_days = max(7, min(90, int(parts[1])))
        except ValueError:
            pass
    try:
        from app.services.domain_specialization_analytics import get_domain_override_summary, get_override_hotspots
        from app.presenters.domain_specialization_analytics_presenters import (
            format_domain_override_summary_telegram,
            format_override_hotspots_telegram,
        )
        summary = get_domain_override_summary(window_days)
        hotspots = get_override_hotspots(window_days)
        text = format_domain_override_summary_telegram(summary) + "\n\n" + format_override_hotspots_telegram(hotspots)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_specialization_analytics(message: Message):
    """Phase 10.5: /specialization_analytics [дней] — fallback summary и hotspots."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 30
    if len(parts) >= 2:
        try:
            window_days = max(7, min(90, int(parts[1])))
        except ValueError:
            pass
    try:
        from app.services.domain_specialization_analytics import get_specialization_fallback_summary, get_specialization_hotspots
        from app.presenters.domain_specialization_analytics_presenters import (
            format_specialization_fallback_summary_telegram,
            format_specialization_hotspots_telegram,
        )
        summary = get_specialization_fallback_summary(window_days)
        hotspots = get_specialization_hotspots(window_days)
        text = format_specialization_fallback_summary_telegram(summary) + "\n\n" + format_specialization_hotspots_telegram(hotspots)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_refinement_backlog(message: Message):
    """Phase 10.5: /refinement_backlog [дней] — backlog улучшений domain/specialization."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 30
    if len(parts) >= 2:
        try:
            window_days = max(7, min(90, int(parts[1])))
        except ValueError:
            pass
    try:
        from app.services.domain_specialization_analytics import get_refinement_backlog
        from app.presenters.domain_specialization_analytics_presenters import format_refinement_backlog_telegram
        backlog = get_refinement_backlog(window_days)
        text = format_refinement_backlog_telegram(backlog)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_refinement_proposals(message: Message):
    """Phase 10.6: /refinement_proposals [generate] — список proposals; generate создаёт из backlog."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) >= 2 and parts[1].lower() == "generate":
        try:
            from app.services.refinement_proposals import generate_refinement_proposals
            created = generate_refinement_proposals(window_days=30)
            await message.answer(redact(f"Создано proposals: {len(created)}. /refinement_proposals — список."))
        except Exception as e:
            await message.answer(redact(f"Ошибка: {e!s}"))
        return
    try:
        from app.services.refinement_proposals import list_refinement_proposals
        from app.presenters.refinement_proposal_presenters import format_refinement_proposal_list_telegram
        items = list_refinement_proposals(limit=15)
        text = format_refinement_proposal_list_telegram(items)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_refinement_proposal(message: Message):
    """Phase 10.6: /refinement_proposal <id> — карточка proposal."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /refinement_proposal <id>")
        return
    proposal_id = parts[1].strip()
    try:
        from app.services.refinement_proposals import get_refinement_proposal
        from app.presenters.refinement_proposal_presenters import format_refinement_proposal_card_telegram
        p = get_refinement_proposal(proposal_id)
        text = format_refinement_proposal_card_telegram(p)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_review_refinement(message: Message):
    """Phase 10.6: /review_refinement <id> accept|reject [note] — ревью proposal."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Использование: /review_refinement <id> accept|reject [заметка]")
        return
    proposal_id = parts[1].strip()
    decision = parts[2].strip().lower()
    notes = parts[3].strip() if len(parts) > 3 else None
    try:
        from app.services.refinement_proposals import review_refinement_proposal
        updated = review_refinement_proposal(proposal_id, decision, reviewer="telegram", notes=notes)
        if updated:
            await message.answer(redact(f"Proposal {proposal_id}: {updated.get('status')}"))
        else:
            await message.answer("Proposal не найден или неверный decision (accept/reject).")
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))


async def handle_patch_refinement(message: Message):
    """Phase 10.7: /patch_refinement <proposal_id> — patch candidate для proposal."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите id: /patch_refinement <proposal_id>")
        return
    proposal_id = parts[1].strip()
    try:
        from app.services.registry_patch_builder import build_patch_candidate
        from app.presenters.registry_patch_presenters import format_patch_candidate_telegram
        patch = build_patch_candidate(proposal_id)
        text = format_patch_candidate_telegram(patch)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_dry_run_patch(message: Message):
    """Phase 10.7: /dry_run_patch <proposal_id> — dry-run без записи."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите id: /dry_run_patch <proposal_id>")
        return
    proposal_id = parts[1].strip()
    try:
        from app.services.registry_patch_apply import dry_run_patch
        from app.presenters.registry_patch_presenters import format_patch_dry_run_telegram
        result = dry_run_patch(proposal_id)
        text = format_patch_dry_run_telegram(result)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_apply_patch(message: Message):
    """Phase 10.7: /apply_patch <proposal_id> — применить safe patch (только accepted, safe type)."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите id: /apply_patch <proposal_id>")
        return
    proposal_id = parts[1].strip()
    try:
        from app.services.registry_patch_apply import apply_patch_candidate
        from app.presenters.registry_patch_presenters import format_patch_apply_telegram
        result = apply_patch_candidate(proposal_id, actor="telegram")
        text = format_patch_apply_telegram(result)
        if not result.get("success") and result.get("error"):
            text += "\n" + (result.get("error") or "")
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_project_lifecycle(message: Message):
    """Phase 10.8/11.9: /project_lifecycle <key> — lifecycle + evolution refinement (owner answer)."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите проект: /project_lifecycle <project_key>")
        return
    project_key = parts[1].strip()
    try:
        from app.services.project_domain_lifecycle import get_project_domain_lifecycle
        from app.presenters.project_domain_lifecycle_presenters import format_project_lifecycle_telegram
        from app.services.project_domain_evolution_refinement import get_project_domain_evolution_refinement
        from app.presenters.project_domain_evolution_presenters import format_evolution_refinement_telegram
        lc = get_project_domain_lifecycle(project_key, window_days=30)
        text = format_project_lifecycle_telegram(lc)
        ref = get_project_domain_evolution_refinement(project_key, window_days=30)
        if ref.get("owner_answer"):
            text += "\n\n" + format_evolution_refinement_telegram(ref)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_domain_lifecycle(message: Message):
    """Phase 10.8/11.9: /domain_lifecycle [days] — сводка lifecycle + evolution attention."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 30
    if len(parts) >= 2 and parts[1].isdigit():
        window_days = min(90, max(7, int(parts[1])))
    try:
        from app.services.project_domain_lifecycle import get_cross_project_domain_lifecycle_summary
        from app.presenters.project_domain_lifecycle_presenters import format_domain_lifecycle_telegram
        from app.services.project_domain_evolution_refinement import get_project_domain_transition_summary
        from app.presenters.project_domain_evolution_presenters import format_evolution_transition_summary_telegram
        summary = get_cross_project_domain_lifecycle_summary(window_days=window_days)
        text = format_domain_lifecycle_telegram(summary, window_days=window_days)
        ev_summary = get_project_domain_transition_summary(window_days=window_days)
        if ev_summary.get("attention_items_count", 0) > 0:
            text += "\n\n" + format_evolution_transition_summary_telegram(ev_summary, window_days=window_days)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_explain_task(message: Message):
    """Phase 11.0: /explain_task <id> — почему система так считает по задаче."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /explain_task <id>")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный id задачи.")
        return
    try:
        from app.services.explanation_assist import explain_task
        from app.presenters.explanation_presenters import format_task_explanation_telegram
        raw = explain_task(task_id)
        text = format_task_explanation_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_explain_project(message: Message):
    """Phase 11.0: /explain_project <key> — почему система так считает по проекту."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите ключ: /explain_project <project_key>")
        return
    project_key = parts[1].strip()
    try:
        from app.services.explanation_assist import explain_project
        from app.presenters.explanation_presenters import format_project_explanation_telegram
        raw = explain_project(project_key)
        text = format_project_explanation_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_explain_portfolio(message: Message):
    """Phase 11.0: /explain_portfolio — почему проекты в focus list."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 7
    if len(parts) >= 2 and parts[1].isdigit():
        window_days = min(90, max(1, int(parts[1])))
    try:
        from app.services.explanation_assist import explain_portfolio
        from app.presenters.explanation_presenters import format_portfolio_explanation_telegram
        raw = explain_portfolio(window_days=window_days)
        text = format_portfolio_explanation_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_explain_refinement(message: Message):
    """Phase 11.0: /explain_refinement [proposal_id] — почему refinement."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    proposal_id = parts[1].strip() if len(parts) >= 2 else None
    try:
        from app.services.explanation_assist import explain_refinement
        from app.presenters.explanation_presenters import format_refinement_explanation_telegram
        raw = explain_refinement(proposal_id=proposal_id, window_days=30)
        text = format_refinement_explanation_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_explain_collaboration(message: Message):
    """Phase 11.0: /explain_collaboration [project_key] — почему collaboration."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    project_key = parts[1].strip() if len(parts) >= 2 else None
    try:
        from app.services.explanation_assist import explain_collaboration
        from app.presenters.explanation_presenters import format_collaboration_explanation_telegram
        raw = explain_collaboration(project_key=project_key, window_days=7)
        text = format_collaboration_explanation_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_suggestions(message: Message):
    """Phase 11.1: /suggestions — collaboration action suggestions."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 7
    if len(parts) >= 2 and parts[1].isdigit():
        window_days = min(90, max(1, int(parts[1])))
    try:
        from app.services.collaboration_action_suggestions import get_collaboration_action_suggestions
        from app.presenters.action_suggestion_presenters import format_suggestions_telegram
        raw = get_collaboration_action_suggestions(window_days=window_days)
        text = format_suggestions_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_project_suggestions(message: Message):
    """Phase 11.1: /project_suggestions <key> — suggestions по проекту."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите ключ: /project_suggestions <project_key>")
        return
    project_key = parts[1].strip()
    try:
        from app.services.collaboration_action_suggestions import get_project_action_suggestions
        from app.presenters.action_suggestion_presenters import format_project_suggestions_telegram
        raw = get_project_action_suggestions(project_key, window_days=7)
        text = format_project_suggestions_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_role_suggestions(message: Message):
    """Phase 11.1: /role_suggestions <role> — suggestions по роли."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите роль: /role_suggestions <owner|operator|executor|reviewer>")
        return
    role_key = parts[1].strip().lower()
    if role_key not in ("owner", "operator", "executor", "reviewer"):
        await message.answer("Роль: owner, operator, executor, reviewer")
        return
    try:
        from app.services.collaboration_action_suggestions import get_role_action_suggestions
        from app.presenters.action_suggestion_presenters import format_role_suggestions_telegram
        raw = get_role_action_suggestions(role_key, window_days=7)
        text = format_role_suggestions_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_decision_support(message: Message):
    """Phase 11.1: /decision_support — decision support (options, preferred, risk)."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    scope_type = "portfolio"
    scope_key = None
    window_days = 7
    if len(parts) >= 2:
        scope_type = parts[1].lower()
    if len(parts) >= 3:
        scope_key = parts[2].strip()
    if len(parts) >= 4 and parts[3].isdigit():
        window_days = min(90, max(1, int(parts[3])))
    try:
        from app.services.collaboration_action_suggestions import get_decision_support
        from app.presenters.action_suggestion_presenters import format_decision_support_telegram
        raw = get_decision_support(scope_type=scope_type, scope_key=scope_key, window_days=window_days)
        text = format_decision_support_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_tuning_candidates(message: Message):
    """Phase 11.2: /tuning_candidates — specialization tuning candidates."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    status = parts[1] if len(parts) >= 2 and parts[1] in ("pending_review", "accepted", "converted") else None
    window_days = 30
    if len(parts) >= 2 and parts[-1].isdigit():
        window_days = min(90, max(7, int(parts[-1])))
    try:
        from app.services.agent_tuning_workflows import get_tuning_candidates
        from app.presenters.agent_tuning_presenters import format_tuning_candidates_telegram
        raw = get_tuning_candidates(window_days=window_days, status=status)
        text = format_tuning_candidates_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_tuning_candidate(message: Message):
    """Phase 11.2: /tuning_candidate <id> — карточка candidate."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /tuning_candidate <id>")
        return
    candidate_id = parts[1].strip()
    try:
        from app.services.agent_tuning_workflows import get_tuning_candidate
        from app.presenters.agent_tuning_presenters import format_tuning_candidate_telegram
        raw = get_tuning_candidate(candidate_id)
        text = format_tuning_candidate_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_review_tuning(message: Message):
    """Phase 11.2: /review_tuning <id> accept|reject [note]."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Использование: /review_tuning <id> accept|reject [заметка]")
        return
    candidate_id, decision = parts[1], parts[2]
    notes = parts[3] if len(parts) >= 4 else None
    try:
        from app.services.agent_tuning_workflows import mark_tuning_candidate_reviewed
        updated = mark_tuning_candidate_reviewed(candidate_id, decision=decision, notes=notes, reviewer="telegram")
        text = f"Tuning {candidate_id}: {decision}" if updated else "Неверное решение или candidate не найден"
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_convert_tuning(message: Message):
    """Phase 11.2: /convert_tuning <id> — конвертировать в refinement proposal."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите id: /convert_tuning <id>")
        return
    candidate_id = parts[1].strip()
    try:
        from app.services.agent_tuning_workflows import convert_tuning_candidate_to_proposal
        p = convert_tuning_candidate_to_proposal(candidate_id)
        text = f"Proposal: {p.get('proposal_id', '')}" if p else "Candidate не accepted или уже converted"
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_verify_tuning(message: Message):
    """Phase 11.2: /verify_tuning <id> improved|unchanged|worse|insufficient_data [note]."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Использование: /verify_tuning <id> improved|unchanged|worse|insufficient_data [заметка]")
        return
    candidate_id, outcome = parts[1], parts[2]
    notes = parts[3] if len(parts) >= 4 else None
    try:
        from app.services.agent_tuning_workflows import mark_tuning_candidate_verified
        updated = mark_tuning_candidate_verified(candidate_id, outcome=outcome, notes=notes)
        text = f"Tuning {candidate_id}: verified {outcome}" if updated else "Неверный outcome или candidate не найден"
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_patchable_tuning(message: Message):
    """Phase 11.3: /patchable_tuning — patchable tuning candidates."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 30
    if len(parts) >= 2 and parts[-1].isdigit():
        window_days = min(90, max(7, int(parts[-1])))
    try:
        from app.services.tuning_patch_integration import list_patchable_tuning_candidates
        from app.presenters.tuning_patch_presenters import format_patchable_tuning_telegram

        raw = list_patchable_tuning_candidates(window_days=window_days, limit=12)
        text = format_patchable_tuning_telegram(raw.get("items", []))
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_tuning_outcomes(message: Message):
    """Phase 11.3: /tuning_outcomes — list outcomes + summary."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    window_days = 30
    if len(parts) >= 2 and parts[-1].isdigit():
        window_days = min(90, max(7, int(parts[-1])))
    try:
        from app.services.tuning_outcomes import list_tuning_outcomes, get_tuning_outcome_summary
        from app.presenters.tuning_patch_presenters import format_tuning_outcomes_telegram

        summary = get_tuning_outcome_summary(window_days=window_days)
        lo = list_tuning_outcomes(window_days=window_days, limit=10)
        head = (
            f"Summary: improved={summary.get('improved_count')}, worse={summary.get('worse_count')}, "
            f"pending={summary.get('pending_measurement_count')}\n"
        )
        text = head + format_tuning_outcomes_telegram(lo.get("items", []))
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_tuning_outcome(message: Message):
    """Phase 11.3: /tuning_outcome <id> — one outcome; optional: evaluate."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите: /tuning_outcome <candidate_id> [evaluate]")
        return
    candidate_id = parts[1].strip()
    do_eval = len(parts) >= 3 and parts[2].lower() == "evaluate"
    try:
        from app.services.tuning_outcomes import get_tuning_outcome, evaluate_tuning_outcome
        from app.presenters.tuning_patch_presenters import format_tuning_outcome_card_telegram

        rec = evaluate_tuning_outcome(candidate_id, window_days=30) if do_eval else get_tuning_outcome(candidate_id)
        text = format_tuning_outcome_card_telegram(rec or {})
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_collaboration_executions(message: Message):
    """Phase 11.4: /collaboration_executions — pending executions."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    try:
        from app.services.collaboration_execution import get_pending_collaboration_executions
        from app.presenters.collaboration_execution_presenters import format_collaboration_executions_telegram

        pe = get_pending_collaboration_executions(window_days=14, limit=15)
        text = format_collaboration_executions_telegram(pe.get("items", []))
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_collaboration_execution(message: Message):
    """Phase 11.4: /collaboration_execution <id>."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите: /collaboration_execution <execution_id>")
        return
    eid = parts[1].strip()
    try:
        from app.services.collaboration_execution import get_collaboration_execution
        from app.presenters.collaboration_execution_presenters import format_collaboration_execution_card_telegram

        ex = get_collaboration_execution(eid)
        text = format_collaboration_execution_card_telegram(ex or {})
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_trigger_collaboration(message: Message):
    """Phase 11.4: /trigger_collaboration <id> — explicit trigger."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите: /trigger_collaboration <execution_id>")
        return
    eid = parts[1].strip()
    try:
        from app.services.collaboration_execution import trigger_collaboration_execution
        from app.presenters.collaboration_execution_presenters import format_collaboration_execution_card_telegram

        ex = trigger_collaboration_execution(eid, actor="telegram", run_safe_action=True)
        text = format_collaboration_execution_card_telegram(ex or {}) if ex else "Execution не найден или закрыт"
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_close_collaboration(message: Message):
    """Phase 11.4: /close_collaboration <id> [reason]."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Укажите: /close_collaboration <execution_id> [reason]")
        return
    eid = parts[1].strip()
    reason = parts[2] if len(parts) >= 3 else "telegram_close"
    try:
        from app.services.collaboration_execution import mark_collaboration_execution_closed
        from app.presenters.collaboration_execution_presenters import format_collaboration_execution_card_telegram

        ex = mark_collaboration_execution_closed(eid, actor="telegram", reason=reason)
        text = format_collaboration_execution_card_telegram(ex or {}) if ex else "Execution не найден"
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_collaboration_outcomes(message: Message):
    """Phase 11.5: /collaboration_outcomes — краткий список outcomes."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    try:
        from app.services.collaboration_outcomes import list_collaboration_outcomes, get_collaboration_effectiveness_summary
        from app.presenters.collaboration_outcome_presenters import (
            format_collaboration_outcomes_list_telegram,
            format_collaboration_effectiveness_summary_telegram,
        )

        lo = list_collaboration_outcomes(window_days=30, limit=12)
        su = get_collaboration_effectiveness_summary(window_days=30)
        text = format_collaboration_effectiveness_summary_telegram(su) + "\n\n" + format_collaboration_outcomes_list_telegram(lo.get("items", []))
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_collaboration_outcome(message: Message):
    """Phase 11.5: /collaboration_outcome <id> [evaluate]."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите: /collaboration_outcome <execution_id> [evaluate]")
        return
    eid = parts[1].strip()
    do_eval = len(parts) >= 3 and parts[2].lower() == "evaluate"
    try:
        from app.services.collaboration_outcomes import get_collaboration_execution_outcome, evaluate_collaboration_execution_outcome
        from app.presenters.collaboration_outcome_presenters import format_collaboration_outcome_card_telegram

        rec = evaluate_collaboration_execution_outcome(eid, window_days=7) if do_eval else get_collaboration_execution_outcome(eid)
        text = format_collaboration_outcome_card_telegram(rec or {})
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_collaboration_followup(message: Message):
    """Phase 11.5: /collaboration_followup — follow-up по outcomes."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    try:
        from app.services.collaboration_outcomes import get_followup_needed_executions
        from app.presenters.collaboration_outcome_presenters import format_followup_needed_telegram

        raw = get_followup_needed_executions(window_days=30, limit=15)
        text = format_followup_needed_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_effectiveness_synthesis(message: Message):
    """Phase 11.6: /effectiveness_synthesis [дней] — cross-layer tuning + collaboration."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    try:
        wd = int(parts[1]) if len(parts) >= 2 else 30
    except (ValueError, IndexError):
        wd = 30
    try:
        from app.services.cross_layer_effectiveness import synthesize_cross_layer_summary
        from app.presenters.cross_layer_effectiveness_presenters import format_cross_layer_synthesis_telegram

        raw = synthesize_cross_layer_summary(window_days=wd)
        text = format_cross_layer_synthesis_telegram(raw)
    except Exception as e:
        text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_defer_intervention(message: Message):
    """Phase 12.3: /defer_intervention <intervention_id> — отложить intervention на 24ч."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    intervention_id = (parts[1] if len(parts) > 1 else "").strip()
    if not intervention_id:
        await message.answer(
            "Укажите intervention_id: /defer_intervention iv_portfolio_x_0\n"
            "(ID можно взять из /interventions или web /owner/interventions)"
        )
        return
    try:
        from app.services.intervention_acceptance import record_intervention_response
        actor = "telegram:%s" % message.chat.id
        result = record_intervention_response(intervention_id, response="deferred", actor=actor)
        if result.get("success"):
            await message.answer("✅ Отложено на 24ч. В do_now не попадёт.")
        else:
            await message.answer(redact(f"Ошибка: {result.get('error', 'unknown')}"))
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))


async def handle_interventions(message: Message):
    """Phase 11.7/12.0: /interventions [дней] — компактно: что делать, safe action если есть."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    try:
        wd = int(parts[1]) if len(parts) >= 2 else 30
    except (ValueError, IndexError):
        wd = 30
    try:
        from app.services.adaptive_decision_support import list_top_decision_support_items
        from app.presenters.adaptive_decision_support_presenters import format_top_items_telegram

        raw = list_top_decision_support_items(window_days=wd, limit=8)
        text = format_top_items_telegram(raw)
    except Exception as e:
        try:
            from app.services.intervention_planning import list_priority_interventions
            from app.presenters.intervention_presenters import format_priority_interventions_telegram
            raw = list_priority_interventions(window_days=wd, limit=8)
            text = format_priority_interventions_telegram(raw)
        except Exception:
            text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_project_intervention(message: Message):
    """Phase 11.7/12.0: /project_intervention <key> — компактно: главная проблема, действие."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Укажите project key: /project_intervention <key>")
        return
    key = parts[1]
    try:
        from app.services.adaptive_decision_support import get_project_decision_support
        from app.presenters.adaptive_decision_support_presenters import format_adaptive_decision_support_telegram

        raw = get_project_decision_support(key, window_days=30)
        text = format_adaptive_decision_support_telegram(raw)
    except Exception as e:
        try:
            from app.services.intervention_planning import get_intervention_bundle
            from app.presenters.intervention_presenters import format_intervention_bundle_telegram
            bundle = get_intervention_bundle("project", scope_key=key, window_days=30)
            text = format_intervention_bundle_telegram(bundle)
        except Exception:
            text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_portfolio_intervention(message: Message):
    """Phase 11.7/12.0: /portfolio_intervention [дней] — компактно: что делать, safe action."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    try:
        wd = int(parts[1]) if len(parts) >= 2 else 30
    except (ValueError, IndexError):
        wd = 30
    try:
        from app.services.adaptive_decision_support import get_portfolio_decision_support
        from app.presenters.adaptive_decision_support_presenters import format_adaptive_decision_support_telegram

        raw = get_portfolio_decision_support(window_days=wd)
        text = format_adaptive_decision_support_telegram(raw)
    except Exception as e:
        try:
            from app.services.intervention_planning import get_intervention_bundle
            from app.presenters.intervention_presenters import format_intervention_bundle_telegram
            bundle = get_intervention_bundle("portfolio", window_days=wd)
            text = format_intervention_bundle_telegram(bundle)
        except Exception:
            text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_cross_layer_intervention(message: Message):
    """Phase 11.7/12.0: /cross_layer_intervention [дней] — компактно: конфликт слоёв."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split()
    try:
        wd = int(parts[1]) if len(parts) >= 2 else 30
    except (ValueError, IndexError):
        wd = 30
    try:
        from app.services.adaptive_decision_support import get_cross_layer_decision_support
        from app.presenters.adaptive_decision_support_presenters import format_adaptive_decision_support_telegram

        raw = get_cross_layer_decision_support(window_days=wd)
        text = format_adaptive_decision_support_telegram(raw)
    except Exception as e:
        try:
            from app.services.intervention_planning import get_intervention_bundle
            from app.presenters.intervention_presenters import format_intervention_bundle_telegram
            bundle = get_intervention_bundle("cross_layer", window_days=wd)
            text = format_intervention_bundle_telegram(bundle)
        except Exception:
            text = redact(f"Ошибка: {e!s}")
    await message.answer(redact(text))


async def handle_owner_approvals(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    tasks = get_pending_approvals(limit=10)
    await message.answer(redact(format_approvals_list(tasks)))


async def handle_owner_artifacts(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    tasks = get_recent_artifacts(limit=10)
    await message.answer(redact(format_artifacts_list(tasks)))


async def handle_owner_runs(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    runs = get_runs_summary(limit=10)
    await message.answer(redact(format_runs_list(runs)))


async def handle_owner_health(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    ok, msg = _molt_health_check()
    mode = os.environ.get("MOLT_TRANSPORT_MODE", "local").lower()
    if mode != "http":
        await message.answer(f"Molt: in-process ({mode})")
    else:
        await message.answer(f"Molt: {msg}")


async def handle_owner_summary(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = build_detailed_summary()
    await message.answer(redact(format_detailed_summary(data)))


async def handle_owner_digest(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_weekly_digest(limit=5)
    await message.answer(redact(format_weekly_digest(data)))


async def handle_owner_blockers(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_blockers_summary(limit=10)
    await message.answer(redact(format_blockers_summary(data)))


async def handle_owner_decisions(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_awaiting_decisions_summary(limit=10)
    await message.answer(redact(format_awaiting_decisions_summary(data)))


async def handle_owner_done(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_completed_recently_summary(limit=10)
    await message.answer(redact(format_completed_recently_summary(data)))


async def handle_owner_insights(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    project = get_project_activity_summary(limit=5)
    rework = get_rework_signal_summary(limit=5)
    degraded = get_degraded_signal_summary(limit=5)
    long_running = get_long_running_summary(limit=5)
    text = "\n\n".join([
        format_project_activity_summary(project),
        format_rework_signal_summary(rework),
        format_degraded_signal_summary(degraded),
        format_long_running_summary(long_running),
    ])
    await message.answer(redact(text))


async def handle_owner_next(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_next_actions(limit=5)
    await message.answer(redact(format_next_actions_msg(data)))


async def handle_owner_decisions_queue(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_decision_queue(limit=10)
    await message.answer(redact(format_decision_queue_msg(data)))


async def handle_owner_health_projects(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_project_health_summary(limit=10)
    await message.answer(redact(format_project_health_msg(data)))


async def handle_owner_risks(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_risk_signals(limit=5)
    await message.answer(redact(format_risk_signals_msg(data)))


async def handle_owner_weekly_digest(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_strategic_weekly_digest()
    await message.answer(redact(format_strategic_weekly_msg(data)))


async def handle_owner_monthly_digest(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_monthly_digest_baseline()
    await message.answer(redact(format_monthly_digest_msg(data)))


async def handle_owner_projects(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    raw = list_projects(limit=50)
    data = present_project_list(raw)
    await message.answer(redact(format_project_list_text(data)))


async def handle_owner_project(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите ключ проекта: /project <key>. Например: /project general. Список: /projects")
        return
    project_key = parts[1].strip()
    overview_raw = get_project_overview(project_key)
    health_raw = get_project_health(project_key)
    risks_raw = get_project_risks(project_key, limit=5)
    queue_raw = get_project_decision_queue(project_key, limit=5)
    overview = present_project_overview(overview_raw)
    health = present_project_health(health_raw)
    risks = present_project_risks(risks_raw)
    decision_queue = present_project_decision_queue(queue_raw)
    card_data = {
        "overview": overview,
        "health": health,
        "risks": risks,
        "decision_queue": decision_queue,
        "project_key": project_key,
    }
    await message.answer(redact(format_project_card_text(card_data)))


async def handle_project_domain(message: Message):
    """Phase 10.3: /project_domain <key> — domain profile проекта."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите ключ: /project_domain <key>. Список: /projects")
        return
    project_key = parts[1].strip()
    try:
        from app.services.project_domain_mapping import get_project_domain_profile
        from app.presenters.project_domain_presenters import format_project_domain_telegram
        profile = get_project_domain_profile(project_key)
        await message.answer(redact(format_project_domain_telegram(profile)))
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))


async def handle_role_domains(message: Message):
    """Phase 10.3: /role_domains — domain recommendations по ролям."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    try:
        from app.services.role_domain_recommendations import get_role_domain_recommendations
        from app.presenters.role_domain_presenters import format_role_domain_telegram
        lines = []
        for role in ("owner", "operator", "executor", "reviewer"):
            rec = get_role_domain_recommendations(role, limit_domains=3)
            lines.append(format_role_domain_telegram(rec))
        await message.answer(redact("\n\n".join(lines)))
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))


async def handle_domain_pressure(message: Message):
    """Phase 10.3: /domain_pressure — сводка domain pressure по ролям."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    try:
        from app.services.role_domain_recommendations import (
            get_owner_domain_recommendations,
            get_operator_domain_recommendations,
            get_executor_domain_recommendations,
            get_reviewer_domain_recommendations,
        )
        from app.presenters.role_domain_presenters import format_domain_pressure_telegram
        recs = [
            get_owner_domain_recommendations(3),
            get_operator_domain_recommendations(3),
            get_executor_domain_recommendations(3),
            get_reviewer_domain_recommendations(3),
        ]
        await message.answer(redact(format_domain_pressure_telegram(recs)))
    except Exception as e:
        await message.answer(redact(f"Ошибка: {e!s}"))


async def handle_owner_portfolio(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    raw = get_portfolio_overview()
    data = present_portfolio_overview(raw)
    await message.answer(redact(format_portfolio_overview_text(data)))


async def handle_owner_focus(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    raw = get_portfolio_focus_list(limit=5)
    data = present_portfolio_focus_list(raw)
    await message.answer(redact(format_focus_list_text(data)))


async def handle_owner_hotspots(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    rework_raw = get_rework_hotspots(limit=5)
    degraded_raw = get_degraded_hotspots(limit=5)
    rework = present_rework_hotspots(rework_raw)
    degraded = present_degraded_hotspots(degraded_raw)
    await message.answer(redact(format_hotspots_text(rework, degraded)))


async def handle_owner_approvals_backlog(message: Message):
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    raw = get_approvals_backlog_by_project(limit=15)
    data = present_approvals_backlog_by_project(raw)
    await message.answer(redact(format_approvals_backlog_text(data)))


async def handle_collaboration(message: Message):
    """Phase 10.9: collaboration overview — hotspots + recommendations."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    hotspots = get_collaboration_hotspots(window_days=7, limit=10)
    recs = get_collaboration_recommendations(window_days=7, limit=8)
    text = format_collaboration_telegram(hotspots, recs)
    await message.answer(redact(text))


async def handle_handoffs(message: Message):
    """Phase 10.9: cross-role handoffs."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    handoffs = get_cross_role_handoffs(window_days=7, limit=15)
    text = format_handoffs_telegram(handoffs)
    await message.answer(redact(text))


async def handle_project_handoffs(message: Message):
    """Phase 10.9: /project_handoffs <key> — handoff signals по проекту."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    project_key = (parts[1].strip() if len(parts) > 1 else "").strip() or "general"
    raw = get_project_handoff_signals(project_key)
    presented = present_project_handoff_signals(raw)
    text = format_project_handoffs_telegram(presented)
    await message.answer(redact(text))


async def handle_role_collaboration(message: Message):
    """Phase 10.9: /role_collaboration <role> — collaboration summary для роли."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    role_key = (parts[1].strip().lower() if len(parts) > 1 else "").strip() or "owner"
    if role_key not in ("owner", "reviewer", "executor", "operator"):
        role_key = "owner"
    raw = get_role_collaboration_summary(role_key)
    presented = present_role_collaboration_summary(raw)
    text = format_role_collaboration_telegram(presented)
    await message.answer(redact(text))


async def handle_view_owner(message: Message):
    """Phase 9.7: компактный owner view summary."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_owner_view()
    await message.answer(redact(format_owner_view_text(data)))


async def handle_view_operator(message: Message):
    """Phase 9.7: operator view — runtime, stuck, blockers."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_operator_view()
    await message.answer(redact(format_operator_view_text(data)))


async def handle_view_executor(message: Message):
    """Phase 9.7: executor view — active tasks, artifacts, blockers."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_executor_view()
    await message.answer(redact(format_executor_view_text(data)))


async def handle_view_reviewer(message: Message):
    """Phase 9.7: reviewer view — pending approvals, decision queue."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    data = get_reviewer_view()
    await message.answer(redact(format_reviewer_view_text(data)))


def _telegram_role(chat_id: int) -> str:
    """Phase 9.8 / 12.1: resolve role via role_access; baseline — owner по chat_id."""
    resolved = resolve_actor_role("telegram", {"chat_id": chat_id, "is_owner": is_owner(chat_id)})
    return deny_or_fallback_role(resolved) or ""


def _telegram_deny_message() -> str:
    """Phase 12.1: human-readable denial when role not resolved."""
    return format_access_denied_message(reason="Доступ только для Owner.")


async def handle_actions(message: Message):
    """Phase 9.8 / 12.1: список доступных действий для роли."""
    role = _telegram_role(message.chat.id)
    if not role:
        await message.answer(redact(_telegram_deny_message()))
        return
    actions = list_available_actions(role)
    await message.answer(redact(format_action_list(actions, role)))


async def handle_do_action(message: Message):
    """Phase 9.8 / 12.1: выполнить действие /do <action_name>."""
    actor = "telegram:%s" % message.chat.id
    role = resolve_and_log("telegram", {"chat_id": message.chat.id, "is_owner": is_owner(message.chat.id)}, actor=actor)
    if not role:
        await message.answer(redact(_telegram_deny_message()))
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите действие: /do <action_name>")
        return
    action_name = parts[1].strip().lower()
    if not check_action_access_and_log(role, action_name, actor=actor):
        await message.answer(redact(format_access_denied_message(
            reason="Роль не позволяет выполнить это действие.", action=action_name
        )))
        return
    result = execute_action(action_name, role, actor=actor)
    await message.answer(redact(format_action_result(result)))


async def handle_refresh(message: Message):
    """Phase 9.8 / 12.1: /refresh — refresh_status."""
    role = _telegram_role(message.chat.id)
    if not role:
        await message.answer(redact(_telegram_deny_message()))
        return
    actor = "telegram:%s" % message.chat.id
    if not check_action_access_and_log(role, "refresh_status", actor=actor):
        await message.answer(redact(format_access_denied_message(reason="Роль не позволяет.", action="refresh_status")))
        return
    result = execute_action("refresh_status", role, actor=actor)
    await message.answer(redact(format_action_result(result)))


async def handle_recheck(message: Message):
    """Phase 9.8 / 12.1: /recheck — recheck_molt_health."""
    role = _telegram_role(message.chat.id)
    if not role:
        await message.answer(redact(_telegram_deny_message()))
        return
    actor = "telegram:%s" % message.chat.id
    if not check_action_access_and_log(role, "recheck_molt_health", actor=actor):
        await message.answer(redact(format_access_denied_message(reason="Роль не позволяет.", action="recheck_molt_health")))
        return
    result = execute_action("recheck_molt_health", role, actor=actor)
    await message.answer(redact(format_action_result(result)))


async def handle_smoke(message: Message):
    """Phase 9.8 / 12.1: /smoke — run_smoke_check."""
    role = _telegram_role(message.chat.id)
    if not role:
        await message.answer(redact(_telegram_deny_message()))
        return
    actor = "telegram:%s" % message.chat.id
    if not check_action_access_and_log(role, "run_smoke_check", actor=actor):
        await message.answer(redact(format_access_denied_message(reason="Роль не позволяет.", action="run_smoke_check")))
        return
    result = execute_action("run_smoke_check", role, actor=actor)
    await message.answer(redact(format_action_result(result)))


async def handle_readiness(message: Message):
    """Phase 12.2: /readiness — production readiness summary."""
    if not is_owner(message.chat.id):
        await message.answer(redact(_telegram_deny_message()))
        return
    summary = get_production_readiness_summary()
    text = format_readiness_telegram(summary)
    await message.answer(redact(text))


async def handle_digest_now(message: Message):
    """Phase 9.8 / 12.1: /digest_now — send_digest_now (owner)."""
    role = _telegram_role(message.chat.id)
    if not role:
        await message.answer(redact(_telegram_deny_message()))
        return
    actor = "telegram:%s" % message.chat.id
    if not check_action_access_and_log(role, "send_digest_now", actor=actor):
        await message.answer(redact(format_access_denied_message(reason="Роль не позволяет.", action="send_digest_now")))
        return
    result = execute_action("send_digest_now", role, actor=actor)
    await message.answer(redact(format_action_result(result)))


# --- Phase 9.9: domain expertise (owner-facing) ---
async def handle_domains(message: Message):
    """Phase 9.9: /domains — список доменов экспертизы из know_proff registry."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    domains = list_domains()
    text = format_domain_list_text(domains)
    await message.answer(redact(text))


async def handle_domain(message: Message):
    """Phase 9.9: /domain <key> — карточка домена по ключу или алиасу."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    key = (parts[1] if len(parts) > 1 else "").strip()
    if not key:
        await message.answer("Укажите ключ: /domain <domain_key>")
        return
    domain = get_domain(key)
    text = format_domain_card_text(domain)
    await message.answer(redact(text))


async def handle_route(message: Message):
    """Phase 9.9: /route <текст> — подбор домена по тексту задачи (explainable)."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return
    parts = (message.text or "").strip().split(maxsplit=1)
    task_text = (parts[1] if len(parts) > 1 else "").strip()
    if not task_text:
        await message.answer("Укажите текст задачи: /route проверить договор с поставщиком")
        return
    suggestions = suggest_domains_for_task(task_text, limit=5)
    text = format_routing_result_text(suggestions, task_preview=task_text[:150])
    await message.answer(redact(text))


# --- Telegram NL interface: intent routing to existing handlers ---
_NL_COMMAND_HANDLERS = {
    "/status": handle_owner_status,
    "/next": handle_owner_next,
    "/blockers": handle_owner_blockers,
    "/approvals": handle_owner_approvals,
    "/done": handle_owner_done,
    "/focus": handle_owner_focus,
    "/portfolio": handle_owner_portfolio,
    "/health_projects": handle_owner_health_projects,
    "/risks": handle_owner_risks,
    "/decisions_queue": handle_owner_decisions_queue,
    "/interventions": handle_interventions,
    "/readiness": handle_readiness,
    "/handoffs": handle_handoffs,
    "/tuning_outcomes": handle_tuning_outcomes,
    "/explain_portfolio": handle_explain_portfolio,
    "/explain_project": handle_explain_project,
    "/defer_intervention": handle_defer_intervention,
}


async def handle_nl_message(message: Message):
    """NL interface: свободный русский запрос → intent → существующий handler."""
    if not is_owner(message.chat.id):
        await message.answer(redact(_telegram_deny_message()))
        return
    text = (message.text or "").strip()
    if not text or text.upper().startswith(("#TASK", "# TASK")):
        return
    from app.services.telegram_nl_router import resolve_intent
    route = resolve_intent(text)
    if route.clarification:
        await message.answer(redact(route.clarification))
        return
    cmd = route.synthetic_command.strip()
    if not cmd:
        await message.answer(redact("Не удалось определить запрос. Напишите /help для списка команд."))
        return
    base = cmd.split()[0] if cmd else ""
    handler = _NL_COMMAND_HANDLERS.get(base)
    if not handler:
        await message.answer(redact("Пока не умею отвечать на такой запрос. Используйте /help."))
        return
    # Адаптер: подменяем message.text на synthetic_command
    class _Adapter:
        chat = message.chat
        text = cmd
        answer = message.answer
    await handler(_Adapter())




# --- live runtime callbacks (reconcile graft) ---
def build_scenario_buttons(task_id: int, options: list[dict]) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for opt in options[:3]:
        oid = str(opt.get("id") or "").strip()
        title = str(opt.get("title") or "Вариант").strip()
        if not oid:
            continue
        b.button(text=title[:40], callback_data=f"sc:{task_id}:{oid}")
    if options:
        b.adjust(1)
    return b


async def handle_llm_tier_callback(cb: CallbackQuery):
    """Owner: перезапуск миссии на cloud (EU OpenAI) или local (Ollama)."""
    if not cb.message or not is_owner(cb.message.chat.id):
        await cb.answer("Доступ только для владельца.", show_alert=True)
        return
    parts = (cb.data or "").split(":")
    # llm:c:123 or llm:l:123
    if len(parts) != 3 or parts[0] != "llm":
        await cb.answer("Неверная кнопка.")
        return
    mode, tid = parts[1], parts[2]
    tier = "cloud" if mode == "c" else "local" if mode == "l" else ""
    if not tier:
        await cb.answer("Неверный режим LLM.")
        return
    try:
        task_id = int(tid)
    except ValueError:
        await cb.answer("Неверный номер миссии.")
        return

    from app.orchestrator.llm_tier import merge_llm_tier_into_business_action

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            await cb.answer("Миссия не найдена.", show_alert=True)
            return
        ba = merge_llm_tier_into_business_action(
            dict(task.business_action_json or {}) if isinstance(task.business_action_json, dict) else {},
            tier,
        )
        repo.update_task(task_id, business_action_json=ba, status="REWORK")
        log_audit(
            repo,
            "OWNER_LLM_TIER",
            task_id=task_id,
            payload={"llm_tier": tier, "decision": "rerun"},
        )
    label = "OpenAI через EU" if tier == "cloud" else "локальная модель"
    await send_with_retry(
        cb.bot,
        cb.message.chat.id,
        f"🧠 Миссия #{task_id}: перезапуск на {label}…",
    )
    await cb.answer()
    asyncio.create_task(_run_orchestration(task_id, cb.message.chat.id, cb.bot))


async def handle_scenario_callback(cb: CallbackQuery):
    if not cb.message or not is_owner(cb.message.chat.id):
        await cb.answer("Доступ только для владельца.", show_alert=True)
        return
    data = cb.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "sc":
        await cb.answer("Неверная кнопка.")
        return
    try:
        task_id = int(parts[1])
    except ValueError:
        await cb.answer("Неверный номер миссии.", show_alert=True)
        return
    option_id = str(parts[2]).strip()
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            await cb.answer("Миссия не найдена.", show_alert=True)
            return
        ba = dict(task.business_action_json or {})
        ex = dict(ba.get("exploration") or {})
        ex["selected_option_id"] = option_id
        ba["exploration"] = ex
        repo.update_task(task_id, business_action_json=ba, status="TRIAGED")
        log_audit(repo, "exploration_option_selected", task_id=task_id, payload={"option_id": option_id, "source": "telegram"})
    await send_with_retry(cb.bot, cb.message.chat.id, f"✅ Миссия #{task_id}: выбран сценарий {option_id}. Запускаю исполнение…")
    asyncio.create_task(_run_orchestration(task_id, cb.message.chat.id, cb.bot))
    await cb.answer()


async def handle_execution_pack_callback(cb: CallbackQuery):
    if not cb.message or not is_owner(cb.message.chat.id):
        await cb.answer("Доступ только для владельца.", show_alert=True)
        return
    data = cb.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "ep":
        await cb.answer("Неверная кнопка.")
        return
    verdict = parts[1]
    try:
        task_id = int(parts[2])
    except ValueError:
        await cb.answer("Неверный номер миссии.", show_alert=True)
        return

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            await cb.answer("Миссия не найдена.", show_alert=True)
            return
        ba0 = dict(task.business_action_json or {})
        if getattr(task, "status", None) == "EXECUTION_READY" or ba0.get("execution_ready"):
            try:
                if cb.message:
                    await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await cb.answer("Пробный режим: отзыв по кнопкам отключён. Запускайте исполнение в Cursor.", show_alert=False)
            return
        project = repo.get_project(task.project_id) if task.project_id else None
        tracked = ensure_action_instance_blob(task, project)
        if not tracked:
            await cb.answer("Пакет исполнения не найден.", show_alert=True)
            return

        if verdict == "y":
            updated = apply_action_feedback(
                tracked,
                status="done",
                owner_feedback="выполнено",
                result_summary="Подтверждено владельцем в Telegram",
                result_type="lead",
                result_value="owner_confirmed",
            )
            text = f"✅ Отмечено: действие по миссии #{task_id} выполнено."
            rk = InlineKeyboardBuilder()
            rk.button(text="Нет", callback_data=f"rv:n:{task_id}")
            rk.button(text="Лид", callback_data=f"rv:l:{task_id}")
            rk.button(text="Продажа", callback_data=f"rv:s:{task_id}")
            rk.adjust(3)
        else:
            updated = apply_action_feedback(
                tracked,
                status="skipped",
                owner_feedback="не сработало",
                result_summary="Владелец отметил, что действие не дало результата",
                result_type="lead",
                result_value="no_result",
            )
            text = f"📝 Отмечено: действие по миссии #{task_id} не сработало. Система учтёт отзыв."

        repo.update_task(task_id, business_action_json=updated)
        refreshed = repo.get_task(task_id)
        if refreshed:
            enriched = ensure_action_instance_blob(refreshed, project, all_tasks=repo.get_all_tasks())
            if enriched:
                repo.update_task(task_id, business_action_json=enriched)
        repo.add_audit_event(
            "telegram_execution_feedback",
            task_id=task_id,
            payload={"verdict": verdict},
        )
    if verdict == "y":
        await send_with_retry(cb.bot, cb.message.chat.id, "Это дало результат?", reply_markup=rk.as_markup())
    await send_with_retry(cb.bot, cb.message.chat.id, text)
    await cb.answer()


async def handle_revenue_result_callback(cb: CallbackQuery):
    if not cb.message or not is_owner(cb.message.chat.id):
        await cb.answer("Доступ только для владельца.", show_alert=True)
        return
    data = cb.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "rv":
        await cb.answer("Неверная кнопка.")
        return
    tag = parts[1]
    try:
        task_id = int(parts[2])
    except ValueError:
        await cb.answer("Неверный номер миссии.", show_alert=True)
        return

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            await cb.answer("Миссия не найдена.", show_alert=True)
            return
        project = repo.get_project(task.project_id) if task.project_id else None
        tracked = ensure_action_instance_blob(task, project, all_tasks=repo.get_all_tasks())
        if not tracked:
            await cb.answer("Пакет исполнения не найден.", show_alert=True)
            return
        tracked = ensure_revenue_fields(tracked)
        action = tracked.get("action_instance") if isinstance(tracked.get("action_instance"), dict) else {}
        pack = tracked.get("execution_pack") if isinstance(tracked.get("execution_pack"), dict) else {}
        action_id = str(action.get("action_id") or "")
        pack_type = str(pack.get("pack_type") or action.get("action_type") or "generic_pack")

        if tag == "l":
            tracked = create_lead(
                tracked,
                project_id=task.project_id,
                action_id=action_id,
                pack_type=pack_type,
                channel="telegram",
                notes="Lead отмечен в Telegram",
                value_estimate="",
            )
            msg = f"💡 Лид привязан к действию #{task_id}."
        elif tag == "s":
            tracked = create_deal(
                tracked,
                project_id=task.project_id,
                action_id=action_id,
                pack_type=pack_type,
                amount="0",
                notes="Продажа отмечена в Telegram (уточните сумму в панели)",
            )
            msg = "💰 Продажа записана. Уточните сумму в панели."
        else:
            msg = "Принято: результата в деньгах пока нет."

        repo.update_task(task_id, business_action_json=tracked)
        repo.add_audit_event("telegram_revenue_feedback", task_id=task_id, payload={"result": tag})

    await send_with_retry(cb.bot, cb.message.chat.id, msg)
    await cb.answer()


def register_handlers(dp: Dispatcher):
    # live runtime (execution / scenario / llm tier)
    dp.callback_query.register(handle_scenario_callback, F.data.startswith("sc:"))
    dp.callback_query.register(handle_llm_tier_callback, F.data.startswith("llm:"))
    dp.callback_query.register(handle_execution_pack_callback, F.data.startswith("ep:"))
    dp.callback_query.register(handle_revenue_result_callback, F.data.startswith("rv:"))

    dp.message.register(handle_start, Command("start"))
    dp.message.register(handle_owner_help, Command("help"))
    dp.message.register(handle_owner_status, Command("status"))
    dp.message.register(handle_owner_tasks, Command("tasks"))
    dp.message.register(handle_owner_task, Command("task"))
    dp.message.register(handle_owner_approvals, Command("approvals"))
    dp.message.register(handle_owner_artifacts, Command("artifacts"))
    dp.message.register(handle_owner_runs, Command("runs"))
    dp.message.register(handle_owner_health, Command("health"))
    dp.message.register(handle_owner_summary, Command("summary"))
    dp.message.register(handle_owner_digest, Command("digest"))
    dp.message.register(handle_owner_blockers, Command("blockers"))
    dp.message.register(handle_owner_decisions, Command("decisions"))
    dp.message.register(handle_owner_done, Command("done"))
    dp.message.register(handle_owner_insights, Command("insights"))
    dp.message.register(handle_owner_next, Command("next"))
    dp.message.register(handle_owner_decisions_queue, Command("decisions_queue"))
    dp.message.register(handle_owner_health_projects, Command("health_projects"))
    dp.message.register(handle_owner_risks, Command("risks"))
    dp.message.register(handle_owner_weekly_digest, Command("weekly_digest"))
    dp.message.register(handle_owner_monthly_digest, Command("monthly_digest"))
    dp.message.register(handle_owner_projects, Command("projects"))
    dp.message.register(handle_owner_project, Command("project"))
    dp.message.register(handle_project_domain, Command("project_domain"))
    dp.message.register(handle_role_domains, Command("role_domains"))
    dp.message.register(handle_domain_pressure, Command("domain_pressure"))
    dp.message.register(handle_owner_portfolio, Command("portfolio"))
    dp.message.register(handle_owner_focus, Command("focus"))
    dp.message.register(handle_owner_hotspots, Command("hotspots"))
    dp.message.register(handle_owner_approvals_backlog, Command("approvals_backlog"))
    dp.message.register(handle_collaboration, Command("collaboration"))
    dp.message.register(handle_handoffs, Command("handoffs"))
    dp.message.register(handle_project_handoffs, Command("project_handoffs"))
    dp.message.register(handle_role_collaboration, Command("role_collaboration"))
    dp.message.register(handle_view_owner, Command("view_owner"))
    dp.message.register(handle_view_operator, Command("view_operator"))
    dp.message.register(handle_view_executor, Command("view_executor"))
    dp.message.register(handle_view_reviewer, Command("view_reviewer"))
    dp.message.register(handle_actions, Command("actions"))
    dp.message.register(handle_do_action, Command("do"))
    dp.message.register(handle_refresh, Command("refresh"))
    dp.message.register(handle_recheck, Command("recheck"))
    dp.message.register(handle_smoke, Command("smoke"))
    dp.message.register(handle_readiness, Command("readiness"))
    dp.message.register(handle_digest_now, Command("digest_now"))
    dp.message.register(handle_domains, Command("domains"))
    dp.message.register(handle_domain, Command("domain"))
    dp.message.register(handle_route, Command("route"))
    dp.message.register(handle_task_domain, Command("task_domain"))
    dp.message.register(handle_set_task_domain, Command("set_task_domain"))
    dp.message.register(handle_clear_task_domain, Command("clear_task_domain"))
    dp.message.register(handle_task_specialization, Command("task_specialization"))
    dp.message.register(handle_domain_analytics, Command("domain_analytics"))
    dp.message.register(handle_specialization_analytics, Command("specialization_analytics"))
    dp.message.register(handle_refinement_backlog, Command("refinement_backlog"))
    dp.message.register(handle_refinement_proposals, Command("refinement_proposals"))
    dp.message.register(handle_refinement_proposal, Command("refinement_proposal"))
    dp.message.register(handle_review_refinement, Command("review_refinement"))
    dp.message.register(handle_patch_refinement, Command("patch_refinement"))
    dp.message.register(handle_dry_run_patch, Command("dry_run_patch"))
    dp.message.register(handle_apply_patch, Command("apply_patch"))
    dp.message.register(handle_project_lifecycle, Command("project_lifecycle"))
    dp.message.register(handle_domain_lifecycle, Command("domain_lifecycle"))
    dp.message.register(handle_explain_task, Command("explain_task"))
    dp.message.register(handle_explain_project, Command("explain_project"))
    dp.message.register(handle_explain_portfolio, Command("explain_portfolio"))
    dp.message.register(handle_explain_refinement, Command("explain_refinement"))
    dp.message.register(handle_explain_collaboration, Command("explain_collaboration"))
    dp.message.register(handle_suggestions, Command("suggestions"))
    dp.message.register(handle_project_suggestions, Command("project_suggestions"))
    dp.message.register(handle_role_suggestions, Command("role_suggestions"))
    dp.message.register(handle_decision_support, Command("decision_support"))
    dp.message.register(handle_tuning_candidates, Command("tuning_candidates"))
    dp.message.register(handle_tuning_candidate, Command("tuning_candidate"))
    dp.message.register(handle_review_tuning, Command("review_tuning"))
    dp.message.register(handle_convert_tuning, Command("convert_tuning"))
    dp.message.register(handle_verify_tuning, Command("verify_tuning"))
    dp.message.register(handle_patchable_tuning, Command("patchable_tuning"))
    dp.message.register(handle_tuning_outcomes, Command("tuning_outcomes"))
    dp.message.register(handle_tuning_outcome, Command("tuning_outcome"))
    dp.message.register(handle_collaboration_executions, Command("collaboration_executions"))
    dp.message.register(handle_collaboration_execution, Command("collaboration_execution"))
    dp.message.register(handle_trigger_collaboration, Command("trigger_collaboration"))
    dp.message.register(handle_close_collaboration, Command("close_collaboration"))
    dp.message.register(handle_collaboration_outcomes, Command("collaboration_outcomes"))
    dp.message.register(handle_collaboration_outcome, Command("collaboration_outcome"))
    dp.message.register(handle_collaboration_followup, Command("collaboration_followup"))
    dp.message.register(handle_effectiveness_synthesis, Command("effectiveness_synthesis"))
    dp.message.register(handle_defer_intervention, Command("defer_intervention"))
    dp.message.register(handle_interventions, Command("interventions"))
    dp.message.register(handle_project_intervention, Command("project_intervention"))
    dp.message.register(handle_portfolio_intervention, Command("portfolio_intervention"))
    dp.message.register(handle_cross_layer_intervention, Command("cross_layer_intervention"))
    # Регистр не важен: #TASK, #task, # TASK, # task
    dp.message.register(
        handle_task_intake,
        F.text & (
            F.text.startswith("#TASK") | F.text.startswith("#task") | F.text.startswith("#Task")
            | F.text.startswith("# TASK") | F.text.startswith("# task") | F.text.startswith("# Task")
        ),
    )
    dp.callback_query.register(handle_owner_callback, F.data.startswith(("a:", "r:", "c:", "f:", "m:")))
    # NL interface: plain text (not command, not #TASK) → intent routing
    dp.message.register(handle_nl_message, F.text & ~F.text.startswith("/"))
