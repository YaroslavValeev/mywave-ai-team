# GM / Director Layer — решает режим исполнения и план агентов, не выполняет работу.
from __future__ import annotations

import logging
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from app.intake.schemas import GMDirectorDecision, NormalizeIntakeResponse, TaskBrief

logger = logging.getLogger(__name__)

# Ключи Owner Memory, при которых на исполнении ожидается контроль владельца (уровень 1).
OWNER_APPROVAL_KEYS = frozenset(
    {
        "security_requires_owner_approval",
        "strategy_change_requires_owner",
        "idea_scenario_change_requires_owner",
        "critical_execution_requires_owner",
        "public_publish_requires_owner",
        "no_auto_merge",
    }
)

# Риск для уровня 2: действие в проде / секреты / деньги / правовые последствия.
_RISK_HIGH = re.compile(
    r"\b(deploy|deployment|production|\bprod\b|rollback|kubectl|terraform|"
    r"password|secret|token|api[_\s]?key|credential|"
    r"оплат|платеж|billing|gdpr|персональн|юрид|legal|contract|"
    r"git\s+push|force\s+push|merge\s+to\s+main|release|опубликовать|публикац)\b",
    re.IGNORECASE,
)

_ACTION_VERBS = re.compile(
    r"\b(сделать|сделай|нужно|надо|исправить|добавить|внедрить|реализовать|deploy|fix|implement|"
    r"напиши|создай|подключи|миграт|refactor)\b",
    re.IGNORECASE,
)

# Справочные формулировки («что это за ошибка?») — не считаем заказом работы.
_DIAGNOSTIC_QUESTION = re.compile(
    r"что\s+(это\s+за|означает|значит)\b|почему\s+так|в\s+чём\s+(ошибка|проблема)\b",
    re.IGNORECASE,
)

_DOC_WORKFLOW_HINT = re.compile(
    r"техбриф|спецификац|документ|markdown|сохрани\s+в\s+файл|\bbrief\b|prd|описание\s+api",
    re.IGNORECASE,
)
_RESEARCH_WORKFLOW_HINT = re.compile(
    r"исслед|research|обзор\s+рынк|сравни\s+вариант|benchmark|альтернатив",
    re.IGNORECASE,
)
_CONTINUATION_HINT = re.compile(r"продолж|continuation|дополни\s+миссию", re.IGNORECASE)
_DEBUG_HINT = re.compile(r"debug|дебаг|ошибк|stack\s*trace|repro|воспроизвед", re.IGNORECASE)
# Стратегия / монетизация / ивенты — отдельный шаблон цепочки (не заменяет approve владельца).
_BUSINESS_WORKFLOW_HINT = re.compile(
    r"\b(стратег|gtm|go-?to-?market|монетиз|спонсор|партнёр|оффер|"
    r"wakesafari|snowpolia|ивент|выручк|воронк|запуск\s+продукта|business\s+workflow)\b",
    re.IGNORECASE,
)


def gm_director_enabled() -> bool:
    return os.getenv("GM_DIRECTOR_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def _suggest_workflow_template(text: str, risk: str) -> str | None:
    """Эвристика выбора шаблона (planner может переопределить по task_type позже)."""
    if _BUSINESS_WORKFLOW_HINT.search(text):
        return "business"
    if _DOC_WORKFLOW_HINT.search(text):
        return "document"
    if _RESEARCH_WORKFLOW_HINT.search(text):
        return "research"
    if risk == "high" or _RISK_HIGH.search(text):
        return "execution_safe"
    if _DEBUG_HINT.search(text):
        return "debug"
    if _CONTINUATION_HINT.search(text):
        return "continuation"
    return None


class GMDirectorInput(BaseModel):
    """Контекст для GM (после Smart Intake + Project Memory + Owner Memory)."""

    task_brief: dict[str, Any] = Field(default_factory=dict)
    memory_bundle: dict[str, Any] = Field(default_factory=dict)
    owner_rules_bundle: dict[str, Any] = Field(default_factory=dict)
    intake_decision: str = ""
    confidence: float = 0.0
    intent_type: str = "task"
    needs_clarification: bool = False
    owner_hard_block_intake: bool = False
    business_action: dict[str, Any] = Field(default_factory=dict)


class ScenarioOption(BaseModel):
    id: str
    title: str
    what: str
    result: str
    risk: str


def _text_mass(brief: TaskBrief) -> tuple[int, int]:
    raw = f"{brief.title}\n{brief.goal}\n{brief.input_summary}\n{brief.desired_outcome}\n{brief.context_summary}"
    att_n = len(brief.attachments or [])
    return len(raw), att_n


def _risk_from_text(s: str) -> str:
    if not s or len(s.strip()) < 4:
        return "low"
    if _RISK_HIGH.search(s):
        return "high"
    if _ACTION_VERBS.search(s) and len(s) > 200:
        return "medium"
    return "low"


def _owner_keys_bundle(bundle: dict[str, Any]) -> list[str]:
    keys = bundle.get("owner_rule_keys_applied") or bundle.get("rule_keys") or []
    if isinstance(keys, list):
        return [str(k) for k in keys if k]
    return []


def _business_hints(brief: TaskBrief, business_type: str, combined_text: str) -> tuple[str, str]:
    """Кратко: зачем это бизнесу и что логично сделать после артефакта (без автодействий)."""
    unit = (brief.business_unit or "").strip().lower()
    bt = (business_type or brief.business_type or "").strip().lower()
    tl = combined_text.lower()

    value_chunks: list[str] = []
    if unit == "wakesafari":
        value_chunks.append("WakeSafari: выручка и узнаваемость через ивенты и партнёрства.")
    elif unit == "snowpolia":
        value_chunks.append("SnowPolia: монетизация и удержание игровой аудитории.")
    elif unit in {"media", "mywave"}:
        value_chunks.append("Контент/MyWave: усиление бренда и воронка интереса.")
    elif unit == "platform":
        value_chunks.append("AI-платформа: спонсоры, аналитика и масштабирование предложения.")
    elif unit == "training":
        value_chunks.append("Сайт и тренировки: конверсия в регистрации и доверие к бренду.")

    if bt == "marketing":
        value_chunks.append("Маркетинг: охват и конверсия в следующий шаг воронки.")
    elif bt == "product":
        value_chunks.append("Продукт: скорость поставки ценности и качество UX.")
    elif bt == "revenue":
        value_chunks.append("Выручка: сделки, спонсоры, партнёрства и условия.")
    elif bt == "ops":
        value_chunks.append("Операции: предсказуемая доставка без срывов сроков и качества.")

    if not value_chunks:
        value_chunks.append("Связать работу с измеримым бизнес-эффектом (метрику фиксирует Owner).")

    business_value_hint = " ".join(value_chunks)

    if "wakesafari" in tl or unit == "wakesafari":
        next_business_step = (
            "После артефакта: согласовать оффер и пакет для партнёров с Owner; "
            "публикации и платные активности — только после явного approve."
        )
    elif "стратег" in tl or "gtm" in tl or "go-to-market" in tl:
        next_business_step = (
            "Зафиксировать гипотезы и оффер; согласовать список партнёров/каналов с Owner до любых публикаций."
        )
    elif bt == "revenue":
        next_business_step = (
            "Собрать короткий список контактов и условий; исходящие коммуникации и сделки — после approve Owner."
        )
    elif bt == "marketing":
        next_business_step = (
            "Согласовать тексты и площадки; автопост и платное продвижение — только после approve Owner."
        )
    elif bt == "product":
        next_business_step = "Согласовать scope и критерии готовности; изменения в проде — по политике Owner."
    elif bt == "ops":
        next_business_step = "Зафиксировать ответственных и сроки; внешние обязательства — с контролем Owner."
    else:
        next_business_step = (
            "Согласовать следующий шаг с Owner, если затрагиваются публикации, деньги или персональные данные."
        )

    return business_value_hint, next_business_step


def decide_gm_director(inp: GMDirectorInput) -> GMDirectorDecision:
    """
    Уровни: Owner rules → Risk → Complexity → Confidence.
    Не вызывает LLM и не запускает агентов.
    """
    brief = TaskBrief.model_validate(inp.task_brief)
    combined_text = f"{brief.title}\n{brief.input_summary}\n{brief.context_summary}"
    owner_keys = _owner_keys_bundle(inp.owner_rules_bundle)
    if not owner_keys and inp.owner_rules_bundle:
        owner_keys = _owner_keys_bundle({"owner_rule_keys_applied": inp.owner_rules_bundle.get("keys", [])})

    mass, att_n = _text_mass(brief)
    mem_used = bool(inp.memory_bundle.get("used"))
    risk = _risk_from_text(combined_text)
    if risk == "low" and mem_used and mass > 3000:
        risk = "medium"

    owner_approval_signal = bool(OWNER_APPROVAL_KEYS & set(owner_keys))
    business_type = str(inp.business_action.get("action_type") or brief.business_type or "").strip().lower()
    if business_type == "revenue" and risk == "low":
        risk = "medium"
    requires_approval = owner_approval_signal or risk == "high"

    explanation_parts: list[str] = []
    if owner_approval_signal:
        explanation_parts.append("Правила владельца: нужен контроль на исполнении (security/strategy/execution).")
    if risk == "high":
        explanation_parts.append("Повышенный риск: прод, секреты, публикация или необратимые действия.")
    elif risk == "medium":
        explanation_parts.append("Средний риск или объёмный контекст.")
    if business_type:
        explanation_parts.append(f"Бизнес-класс: {business_type}.")
    if business_type in {"revenue", "ops"}:
        requires_approval = True

    business_value_hint, next_business_step = _business_hints(brief, business_type, combined_text)

    # Уровень 4: низкая уверенность → clarify
    if inp.owner_hard_block_intake:
        return GMDirectorDecision(
            execution_mode="quick",
            action="clarify",
            requires_approval=True,
            agents_plan=[],
            risk_level="high" if risk == "high" else "medium",
            explanation="; ".join(explanation_parts) if explanation_parts else "Блокирующее правило владельца на intake.",
            next_step="Сформулируйте запрос явнее или снимите блокировку правилом владельца.",
            business_value_hint=business_value_hint,
            next_business_step=next_business_step,
        )

    if inp.confidence < 0.42 and inp.intake_decision in ("create", "attach"):
        return GMDirectorDecision(
            execution_mode="quick",
            action="clarify",
            requires_approval=False,
            agents_plan=[],
            risk_level=risk if risk != "high" else "medium",
            explanation="Низкая уверенность intake — лучше уточнить перед миссией.",
            next_step="Ответьте на уточняющие вопросы одним сообщением.",
            business_value_hint=business_value_hint,
            next_business_step=next_business_step,
        )

    # Отклонение шума
    if inp.intake_decision == "reject":
        return GMDirectorDecision(
            execution_mode="quick",
            action="reject",
            requires_approval=False,
            agents_plan=[],
            risk_level="low",
            explanation="Ввод классифицирован как шум или тривиальное подтверждение — задача не создаётся.",
            next_step="При необходимости отправьте полноценное описание задачи.",
            business_value_hint="",
            next_business_step="",
        )

    # Вложение в существующую миссию
    if inp.intake_decision == "attach":
        mode = "full" if risk == "high" or mass > 4000 else "light"
        agents = _agents_for_mode(mode, risk, mass, att_n, wants_devil=owner_approval_signal or risk != "low")
        wtpl = _suggest_workflow_template(combined_text, risk) or "continuation"
        return GMDirectorDecision(
            execution_mode=mode,
            action="attach",
            requires_approval=requires_approval,
            agents_plan=agents,
            risk_level=risk,
            explanation="; ".join(explanation_parts) if explanation_parts else "Дополнение к существующей миссии.",
            next_step="Контекст будет добавлен к задаче; оркестрацию запускайте отдельно при необходимости.",
            business_value_hint=business_value_hint,
            next_business_step=next_business_step,
            workflow_template=wtpl,
        )

    # Уже запрошено уточнение на intake (decision=clarify)
    if inp.intake_decision == "clarify":
        # Информационный вопрос без явной работы — quick answer без миссии
        summary = brief.input_summary
        q_like = "?" in summary and (
            not _ACTION_VERBS.search(summary) or bool(_DIAGNOSTIC_QUESTION.search(summary))
        )
        if inp.intent_type in ("question", "analysis") and inp.confidence >= 0.48 and q_like:
            return GMDirectorDecision(
                execution_mode="quick",
                action="answer",
                requires_approval=False,
                agents_plan=["synthesizer"] if mass > 800 else [],
                risk_level="low",
                explanation="Похоже на справочный вопрос — ответ без полной миссии и без оркестрации.",
                next_step="Кратко ответьте в чате или переведите в миссию (#TASK), если нужен артефакт.",
                business_value_hint=business_value_hint,
                next_business_step=next_business_step,
            )
        return GMDirectorDecision(
            execution_mode="quick",
            action="clarify",
            requires_approval=False,
            agents_plan=[],
            risk_level=risk,
            explanation="; ".join(explanation_parts) if explanation_parts else "Нужно уточнение намерения перед созданием миссии.",
            next_step="Соберите ответы на вопросы — затем intake сможет создать задачу.",
            business_value_hint=business_value_hint,
            next_business_step=next_business_step,
        )

    # create (новая миссия)
    if mass > 3500 or att_n > 2 or risk == "high":
        mode = "full"
    elif mass > 900 or att_n > 0 or inp.intent_type == "analysis":
        mode = "light"
    else:
        mode = "light"

    if risk == "high" or owner_approval_signal:
        mode = "full"

    agents = _agents_for_mode(mode, risk, mass, att_n, wants_devil=owner_approval_signal or risk != "low")
    wtpl = _suggest_workflow_template(combined_text, risk)

    return GMDirectorDecision(
        execution_mode=mode,
        action="create_task",
        requires_approval=requires_approval,
        agents_plan=agents,
        risk_level=risk,
        explanation="; ".join(explanation_parts)
        if explanation_parts
        else f"Режим {mode}: миссия по сложности/риску; агенты: {', '.join(agents) or 'по умолчанию pipeline'}.",
        next_step="Подтвердите черновик миссии или уточните запрос.",
        business_value_hint=business_value_hint,
        next_business_step=next_business_step,
        workflow_template=wtpl,
    )


def _agents_for_mode(
    mode: str,
    risk: str,
    mass: int,
    att_n: int,
    *,
    wants_devil: bool,
) -> list[str]:
    """Порядок: synthesizer → analyst → devil_advocate → adapter (подмножество по режиму)."""
    out: list[str] = []
    if mode in ("light", "full") and (mass > 800 or att_n > 0):
        out.append("synthesizer")
    if mode in ("light", "full"):
        out.append("analyst")
    if mode == "full" and (wants_devil or risk == "high"):
        out.append("devil_advocate")
    if mode == "full":
        out.append("adapter")
    # дедуп с сохранением порядка
    seen: set[str] = set()
    unique = []
    for a in out:
        if a not in seen:
            seen.add(a)
            unique.append(a)
    return unique


def build_gm_input_from_normalize(resp: NormalizeIntakeResponse) -> GMDirectorInput:
    """Собирает вход GM из ответа normalize (в т.ч. owner_rule_keys_applied на resp)."""
    return GMDirectorInput(
        task_brief=resp.task_brief.model_dump(),
        memory_bundle={
            "used": resp.memory_used,
            "refs": list(resp.task_brief.memory_refs or []),
        },
        owner_rules_bundle={"owner_rule_keys_applied": list(resp.owner_rule_keys_applied or [])},
        intake_decision=resp.decision,
        confidence=resp.confidence,
        intent_type=resp.intent_type,
        needs_clarification=resp.needs_clarification,
        owner_hard_block_intake=resp.owner_hard_block_intake,
        business_action=resp.business_action.model_dump() if resp.business_action else {},
    )


def apply_gm_layer(resp: NormalizeIntakeResponse) -> NormalizeIntakeResponse:
    """Вычисляет gm_decision и пишет структурированный лог (без побочных эффектов)."""
    if not gm_director_enabled():
        return resp.model_copy(update={"gm_decision": None})

    inp = build_gm_input_from_normalize(resp)
    gm = decide_gm_director(inp)
    try:
        from app.business_execution.execution_engine import build_execution_pack_from_gm
        from app.dashboard.business_view import owner_workstream_from_intake_brief

        ws = owner_workstream_from_intake_brief(resp.task_brief, resp.business_action)
        pack = build_execution_pack_from_gm(
            next_business_step=gm.next_business_step,
            business_value_hint=gm.business_value_hint,
            owner_workstream=ws,
            business_type=(resp.task_brief.business_type or ""),
            business_unit=(resp.task_brief.business_unit or ""),
            workflow_template=(gm.workflow_template or ""),
            expected_outcome=(resp.business_action.expected_outcome if resp.business_action else ""),
            project_name=(resp.task_brief.project_name or ""),
            project_goal=(resp.task_brief.business_goal_hint or ""),
            owner_text=resp.task_brief.input_summary or resp.task_brief.title,
        )
        gm = gm.model_copy(update={"owner_workstream": ws, "execution_pack": pack})
    except Exception:
        pass
    logger.info(
        "gm_decision",
        extra={
            "execution_mode": gm.execution_mode,
            "action": gm.action,
            "requires_approval": gm.requires_approval,
            "risk_level": gm.risk_level,
            "agents_selected": gm.agents_plan,
            "reason": (gm.explanation or "")[:500],
            "intake_decision": resp.decision,
            "confidence": resp.confidence,
            "workflow_template": gm.workflow_template,
            "business_value_hint": (gm.business_value_hint or "")[:300],
            "next_business_step": (gm.next_business_step or "")[:300],
            "owner_workstream": (getattr(gm, "owner_workstream", None) or "")[:120],
            "execution_pack_type": (
                (gm.execution_pack.pack_type if getattr(gm, "execution_pack", None) else "")[:80]
            ),
        },
    )
    return resp.model_copy(update={"gm_decision": gm})


def build_exploration_scenarios(owner_text: str) -> dict[str, Any]:
    raw = (owner_text or "").strip()
    options = [
        ScenarioOption(
            id="s1",
            title="MVP по одной стране",
            what="Пилот по 1 стране: собрать источники, создать 1 страницу и 1 канал лидов.",
            result="Первый валидированный спрос и базовая воронка лидов.",
            risk="Сигнал может быть шумным из-за узкого охвата.",
        ).model_dump(),
        ScenarioOption(
            id="s2",
            title="Агрегатор с партнёрской витриной",
            what="Подключить 10-20 источников и собрать витрину предложений.",
            result="Более широкий входящий поток и основа для коммерческих переговоров.",
            risk="Больше зависимости от качества источников и синхронизации данных.",
        ).model_dump(),
        ScenarioOption(
            id="s3",
            title="Контентный запуск + SEO",
            what="Сделать структуру стран, контент и SEO-страницы.",
            result="Устойчивый органический поток и основа для долгого роста.",
            risk="Дольше до первых денег по сравнению с MVP-пилотом.",
        ).model_dump(),
    ]
    return {
        "exploration_mode": True,
        "owner_prompt": raw[:200] if raw else "Новая идея проекта",
        "options": options,
        "recommended_option_id": "s1",
        "recommendation": "Начать с s1 (MVP): минимальная стоимость ошибки и быстрый цикл learning -> execution.",
    }
