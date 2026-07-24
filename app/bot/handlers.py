# app/bot/handlers.py — intake #TASK, callbacks, кнопки, Smart Intake v0
import asyncio
import io
import logging
import os
import time
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_telegram_config
from app.intake import NormalizeIntakeRequest, normalize_intake, task_brief_to_owner_text
from app.intake.classify import parse_task_id_from_text
from app.intake.schemas import IntakeAttachment, TaskBrief
from app.orchestrator.sync_run import _read_exploration_selected_id, run_sync_orchestration
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.audit import log_audit, log_decision

try:
    from app.canonical_bridge import (
        write_canonical_task_if_enabled,
        get_canonical_task_id,
        write_run_if_enabled,
        write_event_if_enabled,
        write_approval_request_if_enabled,
        write_artifact_if_enabled,
        set_canonical_state,
        should_agents_control_runtime_after_approval,
        apply_owner_decision_hooks_if_enabled,
    )
except Exception:  # ImportError / partial shared_core — не валим бот на старте
    def write_canonical_task_if_enabled(*a, **kw):
        return None

    def get_canonical_task_id(*a, **kw):
        return None

    def write_run_if_enabled(*a, **kw):
        return None

    def write_event_if_enabled(*a, **kw):
        return False

    def write_approval_request_if_enabled(*a, **kw):
        return None

    def write_artifact_if_enabled(*a, **kw):
        return None

    def set_canonical_state(*a, **kw):
        return None

    def should_agents_control_runtime_after_approval():
        return True

    def apply_owner_decision_hooks_if_enabled(*a, **kw):
        return None

from app.bot.notify import send_with_retry
from app.shared.dashboard_link import sign_task_link
from app.owner_memory.delivery import format_owner_delivery_note
from app.business_execution.formatter import format_pack_short
from app.business_execution.execution_engine import apply_action_feedback, ensure_action_instance_blob
from app.business_execution.revenue import create_deal, create_lead, ensure_revenue_fields
from app.business_execution.growth_engine import build_growth_insight, format_growth_insight_telegram

logger = logging.getLogger(__name__)

_CLARIFY_REPLY_CTX: dict[int, tuple[float, dict | None]] = {}
PENDING_TTL_SEC = int(os.getenv("INTAKE_PENDING_TTL_SEC", "900"))


def _dashboard_tasks_url(task_id: int) -> str:
    """Ссылка на HTML-страницу задачи с подписанным ?link= (без X-API-Key в браузере)."""
    base = _get_dashboard_url().rstrip("/")
    tok = sign_task_link(task_id)
    if not tok:
        return f"{base}/tasks/{task_id}"
    return f"{base}/tasks/{task_id}?link={quote(tok, safe='')}"


def _format_mission_gm_footer(task_id: int, task) -> str:
    """
    Короткий «ответный» блок: единый контур с Dashboard + уточнения по рискам (roundtable).
    Текст без Markdown, чтобы не ломать разметку на произвольном summary.
    """
    dash_url = _dashboard_tasks_url(task_id)
    lines = [
        "—",
        "Отчёт по контуру: миссия прошла разбор → конвейер → совещание → суд в одном хранилище.",
        f"Панель (та же лента миссии): {dash_url}",
        "",
        "Возможные уточнения:",
    ]
    risks = task.risk_table_json or []
    added = 0
    if isinstance(risks, list):
        for r in risks[:6]:
            if not isinstance(r, dict):
                continue
            if not r.get("owner_approval_needed"):
                continue
            issue = (r.get("issue") or "").strip()
            rec = (r.get("recommendation") or "").strip()
            if issue:
                lines.append(f"• {issue}")
                added += 1
            if rec and rec != issue:
                lines.append(f"  → {rec}")
    if added == 0:
        lines.append("• Достаточен ли краткий итог для следующего шага?")
        lines.append("• Нужны ли дополнительные вложения или уточнение формулировки миссии?")
    lines.append("")
    lines.append("Telegram и панель — два входа в одну миссию.")
    return "\n".join(lines)


def build_owner_buttons(task_id: int) -> InlineKeyboardBuilder:
    cfg = get_telegram_config()
    btns = cfg.get("buttons", {})
    b = InlineKeyboardBuilder()
    b.button(text=btns.get("approve", "✅ Утвердить"), callback_data=f"a:{task_id}")
    b.button(text=btns.get("rework", "🔁 Доработать"), callback_data=f"r:{task_id}")
    b.button(text=btns.get("clarify", "❓ Уточнить"), callback_data=f"c:{task_id}")
    b.button(text=btns.get("full", "📄 Полный отчёт"), callback_data=f"f:{task_id}")
    b.button(text=btns.get("llm_cloud", "🧠 OpenAI (EU)"), callback_data=f"llm:c:{task_id}")
    b.button(text=btns.get("llm_local", "🏠 Локально"), callback_data=f"llm:l:{task_id}")
    b.adjust(2, 2, 2)
    b.row(InlineKeyboardButton(text=btns.get("dashboard", "📊 Панель"), url=_dashboard_tasks_url(task_id)))
    return b


def build_owner_buttons_with_merged(task_id: int) -> InlineKeyboardBuilder:
    """Кнопки + подтверждение merge (v0.2)."""
    cfg = get_telegram_config()
    btns = cfg.get("buttons", {})
    b = InlineKeyboardBuilder()
    b.button(text=btns.get("approve", "✅ Утвердить"), callback_data=f"a:{task_id}")
    b.button(text=btns.get("rework", "🔁 Доработать"), callback_data=f"r:{task_id}")
    b.button(text=btns.get("clarify", "❓ Уточнить"), callback_data=f"c:{task_id}")
    b.button(text=btns.get("merged", "✅ Я смержил"), callback_data=f"m:{task_id}")
    b.button(text=btns.get("full", "📄 Полный отчёт"), callback_data=f"f:{task_id}")
    b.button(text=btns.get("llm_cloud", "🧠 OpenAI (EU)"), callback_data=f"llm:c:{task_id}")
    b.button(text=btns.get("llm_local", "🏠 Локально"), callback_data=f"llm:l:{task_id}")
    b.adjust(2, 2, 1, 2)
    b.row(InlineKeyboardButton(text=btns.get("dashboard", "📊 Панель"), url=_dashboard_tasks_url(task_id)))
    return b


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


def is_owner(chat_id: int) -> bool:
    cfg = get_telegram_config()
    owner_id = cfg.get("owner_chat_id")
    if not owner_id:
        return True  # Если не задан — разрешаем всем (dev)
    try:
        return str(chat_id) == str(owner_id)
    except Exception:
        return False


def _pending_put(payload: dict) -> str:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return repo.put_intake_draft(payload, ttl_sec=PENDING_TTL_SEC)


def _pending_peek(pid: str) -> dict | None:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return repo.peek_intake_draft(pid)


def _pending_pop(pid: str) -> dict | None:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        return repo.pop_intake_draft(pid)


def _reply_context_from_message(message: Message) -> dict | None:
    rm = message.reply_to_message
    if not rm or not (rm.text or rm.caption):
        return None
    parent = (rm.text or rm.caption or "").strip()
    tid = parse_task_id_from_text(parent)
    out: dict = {"raw": {"parent_text": parent}}
    if tid is not None:
        out["task_id"] = tid
    return out


async def transcribe_voice_openai(bot: Bot, message: Message) -> str | None:
    if not message.voice:
        return None
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        import httpx

        buf = io.BytesIO()
        await bot.download(message.voice, destination=buf)
        raw = buf.getvalue()
        if not raw:
            return None
        r = httpx.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": ("voice.ogg", raw, "application/octet-stream")},
            data={"model": "whisper-1"},
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("text") or "").strip() or None
    except Exception as exc:
        logger.warning("Whisper STT failed: %s", exc)
        return None


def _is_task_command_after_strip(text: str) -> tuple[bool, str]:
    """True, если после lstrip это #TASK / #task / # TASK — иначе Smart Intake."""
    s = (text or "").lstrip()
    u = s.upper()
    if u.startswith("# TASK"):
        return True, s
    if u.startswith("#TASK"):
        return True, s
    return False, s


async def create_mission_and_run(
    owner_text: str,
    chat_id: int,
    bot: Bot,
    *,
    source: str = "telegram",
    project_id: int | None = None,
    business_meta: dict | None = None,
):
    """Создать задачу и запустить тот же оркестратор, что и для #TASK."""
    from app.orchestrator.llm_tier import detect_tier_tag_in_text, merge_llm_tier_into_business_action, resolve_llm_tier

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text=owner_text, project_id=project_id)
        ba: dict = {}
        if business_meta:
            raw_ba = business_meta.get("business_action")
            if isinstance(raw_ba, dict):
                ba.update(raw_ba)
            gm_snap = business_meta.get("gm_decision")
            if isinstance(gm_snap, dict) and gm_snap:
                ba["gm_decision"] = gm_snap
                gm_pack = gm_snap.get("execution_pack") if isinstance(gm_snap.get("execution_pack"), dict) else None
                if gm_pack:
                    ba["execution_pack"] = gm_pack
            direct_pack = business_meta.get("execution_pack")
            if isinstance(direct_pack, dict) and direct_pack:
                ba["execution_pack"] = direct_pack
            for key in ("business_unit", "business_goal_hint", "intake_title"):
                val = business_meta.get(key)
                if val:
                    ba[str(key)] = val
        tagged = detect_tier_tag_in_text(owner_text)
        tier = tagged or resolve_llm_tier(owner_text=owner_text, business_action=ba)
        ba = merge_llm_tier_into_business_action(ba, tier)
        repo.update_task(
            task.id,
            business_type=(business_meta or {}).get("business_type") or None,
            impact_level=(business_meta or {}).get("impact_level") or None,
            impact_score=(business_meta or {}).get("impact_score"),
            business_action_json=ba,
            business_outcome=(business_meta or {}).get("business_outcome") or None,
        )
        task_id = task.id
        write_canonical_task_if_enabled(
            legacy_task_id=task_id,
            owner_text=owner_text,
            origin_channel=source or "telegram",
        )
        log_audit(
            repo,
            "task_created",
            task_id=task_id,
            payload={
                "owner_text_len": len(owner_text),
                "mission_id": task_id,
                "source": source,
                "business_type": (business_meta or {}).get("business_type"),
                "impact_level": (business_meta or {}).get("impact_level"),
                "llm_tier": ba.get("llm_tier"),
            },
        )
    tier_note = ""
    if ba.get("llm_tier") == "cloud":
        tier_note = " Режим: OpenAI через EU."
    elif ba.get("llm_tier") == "local":
        tier_note = " Режим: локальная модель."
    await send_with_retry(
        bot,
        chat_id,
        f"Принято. Миссия #{task_id} в работе.{tier_note} Итог пришлю сюда; полная лента — в панели.",
    )
    logger.info("TELEGRAM_ORCHESTRATION_SCHEDULED task_id=%s chat_id=%s source=%s", task_id, chat_id, source)
    asyncio.create_task(_run_orchestration(task_id, chat_id, bot))


async def handle_task_intake(message: Message):
    """Обработка сообщения #TASK — создание задачи и запуск оркестрации."""
    if not is_owner(message.chat.id):
        await message.answer("Доступ только для владельца.")
        return
    ok, stripped = _is_task_command_after_strip(message.text or "")
    await create_mission_and_run(stripped if ok else (message.text or ""), message.chat.id, message.bot, source="telegram")


async def _process_smart_normalize(message: Message, text: str, attachments: list[IntakeAttachment] | None = None):
    """Smart Intake: нормализация и UX (без немедленного create)."""
    atts = attachments or []
    chat_id = message.chat.id
    rc = _reply_context_from_message(message)
    now = time.monotonic()
    if chat_id in _CLARIFY_REPLY_CTX:
        exp, saved = _CLARIFY_REPLY_CTX.pop(chat_id)
        if now < exp and saved is not None:
            rc = saved if rc is None else rc

    req = NormalizeIntakeRequest(
        text=text or "",
        attachments=atts,
        source="telegram",
        user_id=str(message.from_user.id) if message.from_user else "",
        reply_context=rc,
    )
    parent_txt = None
    if message.reply_to_message:
        parent_txt = message.reply_to_message.text or message.reply_to_message.caption
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        resp = normalize_intake(req, parent_message_text=parent_txt, repo=repo)

    gm = resp.gm_decision

    if resp.decision == "reject":
        await message.answer("Принял, задачу не создаю.")
        return

    # GM: справочный ответ без миссии и без оркестрации
    if gm and gm.action == "answer" and gm.execution_mode == "quick":
        msg_lines = [
            f"📌 Режим директора: {gm.execution_mode} · действие: {gm.action} · риск: {gm.risk_level}",
            "",
            gm.explanation or "Справочный режим без создания миссии.",
            "",
            gm.next_step
            or "Если нужен документ или работа команды — отправьте #TASK или уточните запрос.",
        ]
        await message.answer("\n".join(msg_lines).strip())
        return

    if resp.decision == "clarify" or (gm and gm.action == "clarify"):
        lines = list(resp.clarifying_questions)[:3]
        if not lines and gm and gm.explanation:
            lines = [gm.explanation]
        body = "\n".join(f"• {q}" for q in lines) if lines else "Уточни, пожалуйста, что именно нужно сделать."
        extra = f"\n\n({gm.next_step})" if gm and gm.next_step and gm.action == "clarify" else ""
        await message.answer(f"Нужно уточнение:\n{body}{extra}\n\nОтветь одним сообщением.")
        _CLARIFY_REPLY_CTX[chat_id] = (time.monotonic() + PENDING_TTL_SEC, rc)
        return

    if resp.decision == "attach":
        tid = req.reply_task_id() or resp.matched_task_id or resp.task_brief.related_task_id
        if tid is None and isinstance(rc, dict) and rc.get("task_id") is not None:
            try:
                tid = int(rc["task_id"])
            except (TypeError, ValueError):
                tid = None
        if tid is None:
            await message.answer(
                "Не удалось определить номер миссии для вложения. "
                "Ответьте реплаем на сообщение с «Миссия #N» или создайте задачу через #TASK."
            )
            return
        block = f"[SmartIntake attach]\n{resp.task_brief.input_summary.strip()}"
        pid = _pending_put({"kind": "attach", "task_id": tid, "block": block, "reply_ctx": rc})
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Да, к этой миссии", callback_data=f"si:ay:{pid}")
        kb.button(text="🆕 Новая задача", callback_data=f"si:an:{pid}")
        kb.adjust(2)
        head = f"Похоже на продолжение миссии #{tid}"
        if resp.task_brief.project_name:
            head += f" ({resp.task_brief.project_name})"
        summary = f"{head}.\n\n{resp.task_brief.input_summary[:1200]}"
        await message.answer(summary, reply_markup=kb.as_markup())
        return

    brief = resp.task_brief
    original_input = (text or "").strip()
    pid = _pending_put(
        {
            "kind": "create",
            "brief": brief.model_dump(),
            "original_input": original_input,
            "reply_ctx": rc,
            "confidence": resp.confidence,
            "business_action": resp.business_action.model_dump() if resp.business_action else None,
            "gm_decision": resp.gm_decision.model_dump() if resp.gm_decision else None,
        }
    )
    preview = f"Черновик миссии:\n\n{brief.title}\n\n{brief.input_summary[:1500]}"
    if brief.project_name:
        preview += f"\n\nПроект: {brief.project_name}"
    if resp.business_action:
        preview += (
            f"\n\nБизнес-действие: {resp.business_action.action_type}"
            f" · impact: {resp.business_action.impact_level}"
            f"\nОжидаемый результат: {resp.business_action.expected_outcome[:180]}"
        )
    if gm:
        preview += (
            f"\n\nДиректор: режим {gm.execution_mode} · {gm.action} · риск {gm.risk_level}"
            + (f"\nАгенты: {', '.join(gm.agents_plan)}" if gm.agents_plan else "")
        )
        if gm.explanation:
            preview += f"\n{gm.explanation[:400]}"
        if getattr(gm, "business_value_hint", ""):
            preview += f"\n\nБизнес-ценность: {gm.business_value_hint[:420]}"
        if getattr(gm, "next_business_step", ""):
            preview += f"\nСледующий бизнес-шаг: {gm.next_business_step[:420]}"
        if getattr(gm, "execution_pack", None):
            ep = gm.execution_pack
            preview += f"\nExecution Pack: {(ep.action_title or ep.pack_type)[:220]}"
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Создать", callback_data=f"si:y:{pid}")
    kb.button(text="❓ Уточнить", callback_data=f"si:q:{pid}")
    kb.button(text="🚫 Отмена", callback_data=f"si:n:{pid}")
    kb.adjust(2, 1)
    await message.answer(preview + f"\n\nуверенность: {resp.confidence:.2f}", reply_markup=kb.as_markup())


async def handle_smart_intake_text(message: Message):
    if not is_owner(message.chat.id):
        return
    t = message.text or ""
    ok, stripped = _is_task_command_after_strip(t)
    if ok:
        # Сообщение с #TASK не с первого символа (переносы/пробелы) не ловит фильтр handle_task_intake.
        await create_mission_and_run(stripped, message.chat.id, message.bot, source="telegram")
        return
    await _process_smart_normalize(message, t, [])


async def handle_smart_intake_voice(message: Message):
    if not is_owner(message.chat.id):
        return
    txt = await transcribe_voice_openai(message.bot, message)
    if not txt:
        await message.answer("Голос не распознан. Пришлите текстом или проверьте настройку распознавания речи.")
        return
    await _process_smart_normalize(message, txt, [])


async def handle_smart_intake_photo(message: Message):
    if not is_owner(message.chat.id):
        return
    cap = (message.caption or "").strip()
    if not cap:
        await message.answer("Добавьте подпись к фото — по ней сформируем миссию (vision в v0 не используется).")
        return
    await _process_smart_normalize(message, cap, [])


async def handle_smart_intake_callback(cb: CallbackQuery):
    """Короткие callback si:* (лимит Telegram 64 байта)."""
    if not cb.message or not is_owner(cb.message.chat.id):
        await cb.answer("Доступ только для владельца.", show_alert=True)
        return
    data = cb.data or ""
    if not data.startswith("si:"):
        return
    parts = data.split(":")
    if len(parts) != 3:
        await cb.answer("Кнопка устарела.", show_alert=True)
        return
    _, code, pid = parts
    chat_id = cb.message.chat.id

    if code == "n":
        _pending_pop(pid)
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_with_retry(cb.bot, chat_id, "Отменено.")
        await cb.answer()
        return

    p = _pending_peek(pid)
    if not p:
        await cb.answer("Сессия истекла. Отправьте текст снова.", show_alert=True)
        return

    if code == "q":
        _CLARIFY_REPLY_CTX[chat_id] = (time.monotonic() + PENDING_TTL_SEC, p.get("reply_ctx"))
        await send_with_retry(
            cb.bot,
            chat_id,
            "Напишите уточнение одним сообщением (контекст реплая сохранён, если был).",
        )
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer()
        return

    if code == "y":
        p = _pending_pop(pid)
        if not p or p.get("kind") != "create":
            await cb.answer("Сессия истекла.", show_alert=True)
            return
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        brief = TaskBrief(**p["brief"])
        owner_text = task_brief_to_owner_text(brief, original_input=p.get("original_input") or "")
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(
                repo,
                "smart_intake_confirmed",
                payload={"source": "telegram", "owner_text_len": len(owner_text)},
            )
        await cb.answer("Создаю миссию…")
        await create_mission_and_run(
            owner_text,
            chat_id,
            cb.bot,
            source="telegram_smart_intake",
            project_id=brief.project_id,
            business_meta={
                "business_type": brief.business_type,
                "impact_level": (p.get("business_action") or {}).get("impact_level"),
                "impact_score": 0.9 if (p.get("business_action") or {}).get("impact_level") == "high" else 0.6,
                "business_action": p.get("business_action"),
                "business_outcome": (p.get("business_action") or {}).get("expected_outcome"),
                "gm_decision": p.get("gm_decision"),
                "business_unit": brief.business_unit,
                "business_goal_hint": (brief.business_goal_hint or "").strip() or None,
                "intake_title": (brief.title or "").strip() or None,
            },
        )
        return

    if code == "ay":
        p = _pending_pop(pid)
        if not p or p.get("kind") != "attach":
            await cb.answer("Сессия истекла.", show_alert=True)
            return
        tid = int(p["task_id"])
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            updated = repo.append_owner_context(tid, p["block"])
            if not updated:
                await cb.answer("Миссия не найдена.", show_alert=True)
                return
            log_audit(
                repo,
                "smart_intake_attach",
                task_id=tid,
                payload={"source": "telegram", "block_len": len(p.get("block") or "")},
            )
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_with_retry(
            cb.bot,
            chat_id,
            f"Контекст добавлен к миссии #{tid}. Автозапуск не выполнялся — при необходимости используйте #TASK или панель.",
        )
        await cb.answer()
        return

    if code == "an":
        p = _pending_pop(pid)
        if not p or p.get("kind") != "attach":
            await cb.answer("Сессия истекла.", show_alert=True)
            return
        block = (p.get("block") or "").strip()
        brief = TaskBrief(
            title="Новая миссия (из дополнения)",
            goal="Выполнить запрос владельца",
            input_summary=block or "(пусто)",
            desired_outcome="Готовый план/артефакты по контуру AI Office",
            requires_owner_approval=True,
        )
        npid = _pending_put(
            {
                "kind": "create",
                "brief": brief.model_dump(),
                "original_input": block,
                "reply_ctx": None,
                "confidence": 0.75,
            }
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Создать", callback_data=f"si:y:{npid}")
        kb.button(text="❓ Уточнить", callback_data=f"si:q:{npid}")
        kb.button(text="🚫 Отмена", callback_data=f"si:n:{npid}")
        kb.adjust(2, 1)
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_with_retry(cb.bot, chat_id, "Оформим как новую миссию:", reply_markup=kb.as_markup())
        await cb.answer()
        return

    await cb.answer("Неизвестное действие.", show_alert=True)


async def _run_orchestration(task_id: int, chat_id: int, bot: Bot):
    """Полный цикл: triage → pipeline → roundtable → court (тот же путь, что и API)."""
    logger.info("TELEGRAM_ORCHESTRATION_BEGIN task_id=%s chat_id=%s", task_id, chat_id)
    Session = get_session_factory()
    try:
        with Session() as session:
            repo = TaskRepository(session)
            result = run_sync_orchestration(repo, task_id, source="telegram")
            if result is None:
                await send_with_retry(bot, chat_id, f"Ошибка: миссия #{task_id} не найдена.")
                return

            final_status = result["status"]
            summary = result["summary"]
            task = repo.get_task(task_id)
            footer = _format_mission_gm_footer(task_id, task) if task else ""
            delivery_note = format_owner_delivery_note(repo)

            if final_status == "EXECUTION_READY":
                msg = f"{summary}\n\n{footer}".strip()
                if delivery_note:
                    msg += delivery_note
                growth = build_growth_insight(repo.get_all_tasks())
                insight_line = format_growth_insight_telegram(growth)
                if insight_line:
                    msg += insight_line
                await send_with_retry(bot, chat_id, msg, reply_markup=None)
                return

            exec_pack = None
            if task and isinstance(task.business_action_json, dict):
                exec_pack = task.business_action_json.get("execution_pack")
            real_exec_line = ""
            if task and isinstance(task.business_action_json, dict):
                exr = task.business_action_json.get("execution_from_scenario")
                if isinstance(exr, dict) and exr.get("project_structure"):
                    real_exec_line = "\n\nСистема подготовила исполнение. Можно запускать через Cursor."
            exec_pack_line = ""
            next_action_line = ""
            if isinstance(exec_pack, dict) and exec_pack:
                try:
                    from app.business_execution.schemas import ExecutionPack

                    pack_obj = ExecutionPack.model_validate(exec_pack)
                    next_action_line = f"\n\nЧто делать сейчас:\n→ {pack_obj.action_title}"
                    exec_pack_line = (
                        "\n\nГотово к действию:\n→ открыть пакет исполнения в панели\n"
                        f"→ {format_pack_short(pack_obj)}"
                    )
                except Exception:
                    exec_pack_line = ""
                    next_action_line = ""

            growth = build_growth_insight(repo.get_all_tasks())
            insight_line = format_growth_insight_telegram(growth)
            checklist_reminder = "\n\nНа сегодня:\n1) Выполнил шаг?\n2) Записал результат (даже если «ничего»)?"

            if final_status == "WAIT_OWNER":
                exploration_kb = None
                exploration_pending = False
                if task and isinstance(task.business_action_json, dict):
                    ex = task.business_action_json.get("exploration")
                    sel = _read_exploration_selected_id(task) if task else ""
                    if isinstance(ex, dict) and ex.get("exploration_mode") and not sel:
                        exploration_pending = True
                        opts = ex.get("options") if isinstance(ex.get("options"), list) else []
                        if opts:
                            exploration_kb = build_scenario_buttons(task_id, opts).as_markup()
                if exploration_pending:
                    msg = (
                        f"🔎 Миссия #{task_id}: выберите сценарий запуска.\n\n"
                        f"{summary}\n\n{footer}"
                    )
                else:
                    msg = (
                        f"✅ Миссия #{task_id}: результат готов. Нужно ваше утверждение перед исполнением.\n\n"
                        f"{summary}\n\n{footer}"
                    )
                if exec_pack_line:
                    msg += exec_pack_line
                if next_action_line:
                    msg += next_action_line
                if delivery_note:
                    msg += delivery_note
                if insight_line:
                    msg += insight_line
                if real_exec_line:
                    msg += real_exec_line
                msg += checklist_reminder
                ep_kb = None
                if exec_pack_line:
                    kb = InlineKeyboardBuilder()
                    kb.button(text="✅ Да", callback_data=f"ep:y:{task_id}")
                    kb.button(text="❌ Нет", callback_data=f"ep:n:{task_id}")
                    kb.adjust(2)
                    ep_kb = kb.as_markup()
                await send_with_retry(
                    bot,
                    chat_id,
                    msg,
                    reply_markup=exploration_kb or ep_kb or build_owner_buttons(task_id).as_markup(),
                )
            else:
                msg = f"✅ Миссия #{task_id} выполнена.\n\n{summary}"
                if exec_pack_line:
                    msg += exec_pack_line
                if next_action_line:
                    msg += next_action_line
                if footer:
                    msg += f"\n\n{footer}"
                else:
                    msg += f"\n\n📊 Панель: {_dashboard_tasks_url(task_id)}"
                if delivery_note:
                    msg += delivery_note
                if insight_line:
                    msg += insight_line
                if real_exec_line:
                    msg += real_exec_line
                msg += checklist_reminder
                ep_kb = None
                if exec_pack_line:
                    kb = InlineKeyboardBuilder()
                    kb.button(text="✅ Да", callback_data=f"ep:y:{task_id}")
                    kb.button(text="❌ Нет", callback_data=f"ep:n:{task_id}")
                    kb.adjust(2)
                    ep_kb = kb.as_markup()
                await send_with_retry(bot, chat_id, msg, reply_markup=ep_kb)

    except Exception as e:
        logger.exception("Orchestration failed for task %s", task_id)
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, "orchestration_error", task_id=task_id, payload={"error": str(e)})
        await send_with_retry(bot, chat_id, f"Ошибка по миссии #{task_id}: {str(e)}")

def _get_dashboard_url() -> str:
    from app.config import get_dashboard_config
    return os.getenv("DASHBOARD_URL") or get_dashboard_config().get("base_url", "http://localhost:8080")


def _load_full_report_text(task) -> str:
    """Текст полного отчёта: файл court/final_report если есть, иначе summary."""
    from pathlib import Path

    chunks: list[str] = []
    path_raw = (getattr(task, "report_path", None) or "").strip()
    if path_raw:
        p = Path(path_raw)
        if not p.is_file():
            # относительный путь от корня репо / контейнера
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
    text = "\n\n".join(chunks)
    # Telegram hard limit ~4096; оставляем запас под заголовок
    return text


async def _send_long_telegram(bot, chat_id: int, header: str, body: str) -> None:
    """Отправить длинный текст частями (лимит Telegram ~4096)."""
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
    """Обработка кнопок Утвердить / Доработать / Уточнить / Полный отчёт."""
    if not is_owner(cb.message.chat.id if cb.message else 0):
        await cb.answer("Доступ только для владельца.", show_alert=True)
        return

    parts = cb.data.split(":", 1)
    if len(parts) != 2:
        await cb.answer("Неверная кнопка.")
        return
    code, tid = parts[0], parts[1]
    try:
        task_id = int(tid)
    except ValueError:
        await cb.answer("Неверный номер миссии.")
        return

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            await cb.answer("Миссия не найдена.", show_alert=True)
            return

        if code == "f":
            report = _load_full_report_text(task)
            await _send_long_telegram(
                cb.bot,
                cb.message.chat.id,
                f"📄 Полный отчёт по миссии #{task_id}:",
                report,
            )
            await cb.answer()
            return

        if code == "m":
            log_decision(repo, task_id, decision="merged", owner_approval=True)
            log_audit(repo, "OWNER_MERGED", task_id=task_id, payload={"decision": "i_merged"})
            repo.update_task(task_id, status="DONE")
            await send_with_retry(cb.bot, cb.message.chat.id, f"✅ Миссия #{task_id}: слияние подтверждено. Задача закрыта.")
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

        has_pr = bool(task.pr_url)
        if code == "a":
            new_status = "APPROVED_WAIT_MERGE" if has_pr else "DONE"
        elif code == "r":
            new_status = "REWORK"
        else:
            new_status = "NEED_INFO"
        repo.update_task(task_id, status=new_status)
        try:
            from app.canonical_bridge import apply_owner_decision_hooks_if_enabled

            apply_owner_decision_hooks_if_enabled(
                task_id,
                code,
                approved_by="telegram_owner",
                terminal_on_approve=(code == "a" and new_status == "DONE"),
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "canonical approval resolution hook failed task_id=%s", task_id
            )

        if code == "a":
            if has_pr:
                await send_with_retry(cb.bot, cb.message.chat.id, f"✅ Миссия #{task_id} одобрена. Смержите PR в GitHub, затем нажмите «Я смержил».")
            else:
                await send_with_retry(cb.bot, cb.message.chat.id, f"✅ Миссия #{task_id} утверждена.")
        elif code == "r":
            await send_with_retry(cb.bot, cb.message.chat.id, f"🔁 Миссия #{task_id}: запрошена доработка. Запускаю повторный цикл…")
            asyncio.create_task(_run_orchestration(task_id, cb.message.chat.id, cb.bot))
        else:
            await send_with_retry(cb.bot, cb.message.chat.id, f"❓ Миссия #{task_id}: нужно уточнение. Напишите вопросы новым сообщением с #TASK или #CLARIFY.")

    await cb.answer()


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


async def handle_start(message: Message):
    """Ответ на /start — подсказка, как отправить задачу."""
    await message.answer(
        "Привет! Можно так:\n\n"
        "• #TASK <описание> — сразу в работу\n"
        "• Свободный текст — умный приём (сначала подтверждение кнопками)\n"
        "• Голос — если настроено распознавание речи\n"
        "• Фото с подписью — как текст задачи\n\n"
        "Пример: #TASK написать тесты для API"
    )


def register_handlers(dp: Dispatcher):
    dp.message.register(handle_start, Command("start"))
    # Регистр не важен: #TASK, #task, # TASK, # task
    dp.message.register(
        handle_task_intake,
        F.text & (
            F.text.startswith("#TASK") | F.text.startswith("#task") | F.text.startswith("#Task")
            | F.text.startswith("# TASK") | F.text.startswith("# task") | F.text.startswith("# Task")
        ),
    )
    dp.message.register(handle_smart_intake_voice, F.voice)
    dp.message.register(handle_smart_intake_photo, F.photo)
    dp.message.register(handle_smart_intake_text, F.text)
    dp.callback_query.register(handle_smart_intake_callback, F.data.startswith("si:"))
    dp.callback_query.register(handle_scenario_callback, F.data.startswith("sc:"))
    dp.callback_query.register(handle_llm_tier_callback, F.data.startswith("llm:"))
    dp.callback_query.register(handle_owner_callback, F.data.startswith(("a:", "r:", "c:", "f:", "m:")))
    dp.callback_query.register(handle_execution_pack_callback, F.data.startswith("ep:"))
    dp.callback_query.register(handle_revenue_result_callback, F.data.startswith("rv:"))






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
