# app/bot/handlers.py — intake #TASK, callbacks, кнопки
import asyncio
import logging
import os
from typing import Callable, Awaitable

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_telegram_config, get_policy
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.audit import log_audit, log_decision
from app.shared.redaction import redact
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
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для Owner.")
        return

    text = message.text or ""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text=text)
        log_audit(repo, "task_created", task_id=task.id, payload={"owner_text_len": len(text)})

    task_id = task.id
    max_chars = get_policy().get("limits", {}).get("telegram_summary_max_chars", 1200)
    await message.answer(f"Принято. Task #{task_id} в работе. Итог пришлю с кнопками.")

    # Запуск оркестрации в фоне
    asyncio.create_task(_run_orchestration(task_id, message.chat.id, message.bot))


async def _run_orchestration(task_id: int, chat_id: int, bot: Bot):
    """Полный цикл: triage → pipeline → roundtable → court."""
    Session = get_session_factory()
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
                msg = f"✅ Task #{task_id}: результат готов. Нужен апрув для EXECUTE.\n\n{summary}"
                await bot.send_message(
                    chat_id,
                    redact(msg),
                    reply_markup=build_owner_buttons(task_id).as_markup(),
                )
            else:
                repo.update_task(task_id, status="DONE", report_path=report_path, summary=summary)
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

        owner_approval = code == "a"
        log_decision(repo, task_id, decision=code, owner_approval=owner_approval)
        if code == "a":
            log_audit(repo, "OWNER_APPROVED", task_id=task_id, payload={"decision": "approve"})
        elif code == "r":
            log_audit(repo, "OWNER_REWORK", task_id=task_id, payload={"decision": "rework"})
        else:
            log_audit(repo, "OWNER_CLARIFY", task_id=task_id, payload={"decision": "clarify"})
        repo.update_task(task_id, status="DONE" if code == "a" else "IN_PIPELINE")

        if code == "a":
            await cb.message.answer(redact(f"✅ Task #{task_id} утверждён."))
        elif code == "r":
            await cb.message.answer(redact(f"🔁 Task #{task_id}: запрошен rework. Запускаю повторный цикл..."))
            asyncio.create_task(_run_orchestration(task_id, cb.message.chat.id, cb.bot))
        else:
            await cb.message.answer(redact(f"❓ Task #{task_id}: нужно уточнение. Напиши вопросы в новом сообщении с #TASK или #CLARIFY."))

    await cb.answer()


def register_handlers(dp: Dispatcher):
    dp.message.register(handle_task_intake, F.text & (F.text.startswith("# TASK") | F.text.startswith("#TASK")))
    dp.callback_query.register(handle_owner_callback, F.data.startswith(("a:", "r:", "c:", "f:")))
