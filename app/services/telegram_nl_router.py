# app/services/telegram_nl_router.py — Telegram natural-language owner interface
"""Тонкий conversational facade: NL intent → existing services/handlers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Intent groups
INTENT_STATUS = "status"
INTENT_PORTFOLIO = "portfolio"
INTENT_INTERVENTIONS = "interventions"
INTENT_READINESS = "readiness"
INTENT_COLLABORATION = "collaboration"
INTENT_TUNING_OUTCOMES = "tuning_outcomes"
INTENT_EXPLANATION = "explanation"
INTENT_DEFER = "defer"
INTENT_NEXT_ACTIONS = "next_actions"
INTENT_BLOCKERS = "blockers"
INTENT_APPROVALS = "approvals"
INTENT_DONE = "done"
INTENT_UNKNOWN = "unknown"

# Mapping: (keywords_lower, intent, synthetic_command, needs_param)
# keywords: any of these in user text → intent
# needs_param: intent requires extraction (project_key, intervention_id, etc.)
_INTENT_PATTERNS: list[tuple[list[str], str, str, bool]] = [
    # status / summary
    (["что важно", "самое важное", "сводка", "общая картинка", "статус системы"], INTENT_STATUS, "/status", False),
    (["что сделать сегодня", "что делать сегодня", "что мне сделать", "что сделать сейчас", "следующие шаги"], INTENT_NEXT_ACTIONS, "/next", False),
    (["что тормозит", "блокеры", "что блокирует"], INTENT_BLOCKERS, "/blockers", False),
    (["ожидают одобрения", "approvals", "что ждёт approve", "одобрить"], INTENT_APPROVALS, "/approvals", False),
    (["что завершилось", "что сделано", "что закрыли", "завершённые"], INTENT_DONE, "/done", False),
    (["риски", "какие риски"], INTENT_PORTFOLIO, "/risks", False),
    (["очередь решений", "решения ждут"], INTENT_PORTFOLIO, "/decisions_queue", False),
    # portfolio / projects
    (["проблемные проекты", "какие проекты проблемные", "фокус", "focus", "портфель", "portfolio"], INTENT_PORTFOLIO, "/focus", False),
    (["проекты", "список проектов", "все проекты"], INTENT_PORTFOLIO, "/portfolio", False),
    (["здоровье проектов", "health проектов"], INTENT_PORTFOLIO, "/health_projects", False),
    # interventions
    (["что делать", "что надо сделать", "interventions", "вмешательства", "можно отложить", "отложить вмешательства"], INTENT_INTERVENTIONS, "/interventions", False),
    # readiness
    (["readiness", "готовность", "что по readiness", "production readiness"], INTENT_READINESS, "/readiness", False),
    # collaboration / bottleneck
    (["bottleneck", "узкое место", "где bottleneck", "handoffs", "хендоффы", "сотрудничество", "collaboration"], INTENT_COLLABORATION, "/handoffs", False),
    # tuning / outcomes
    (["tuning сработал", "tuning сработало", "улучшилось за", "что реально улучшилось", "tuning outcomes", "outcomes"], INTENT_TUNING_OUTCOMES, "/tuning_outcomes", False),
    # explanation / why
    (["почему проект", "почему горит", "объясни проект", "почему этот проект", "почему в фокусе"], INTENT_EXPLANATION, "/explain_portfolio", True),
    (["почему система считает", "объясни портфель"], INTENT_EXPLANATION, "/explain_portfolio", False),
    # defer
    (["отложи intervention", "отложи вот этот", "отложить intervention", "отложи на сутки", "отложить на сутки"], INTENT_DEFER, "/defer_intervention", True),
]

# Pattern to extract intervention_id from text (iv_xxx_xxx_xxx or iv_xxx_x_0)
_INTERVENTION_ID_RE = re.compile(r"\biv_[a-z0-9_]+", re.I)
# Pattern to extract project key (single word after "проект" or similar)
_PROJECT_KEY_RE = re.compile(r"(?:проект[ау]?|project)\s+([a-z0-9_-]+)", re.I)


@dataclass
class NLRouteResult:
    """Результат роутинга: intent, синтетическая команда, извлечённые параметры."""
    intent: str
    synthetic_command: str
    param: Optional[str] = None
    clarification: Optional[str] = None


def resolve_intent(text: str) -> NLRouteResult:
    """
    Определить intent по тексту пользователя.
    Returns NLRouteResult. Если clarification — задать уточняющий вопрос.
    """
    t = (text or "").strip()
    if not t or len(t) < 3:
        return NLRouteResult(INTENT_UNKNOWN, "", clarification="Напишите запрос или используйте /help для списка команд.")

    lower = t.lower()

    # Extract intervention_id if present (for defer)
    intervention_id = None
    m_iv = _INTERVENTION_ID_RE.search(t)
    if m_iv:
        intervention_id = m_iv.group(0)

    # Extract project_key if present
    project_key = None
    m_proj = _PROJECT_KEY_RE.search(t)
    if m_proj:
        project_key = m_proj.group(1).strip()

    for keywords, intent, cmd, needs_param in _INTENT_PATTERNS:
        if any(kw in lower for kw in keywords):
            if intent == INTENT_DEFER:
                if intervention_id:
                    return NLRouteResult(intent, f"{cmd} {intervention_id}", param=intervention_id)
                return NLRouteResult(
                    intent, "",
                    clarification="Укажите intervention_id (например iv_portfolio_x_0). Список: /interventions"
                )
            if intent == INTENT_EXPLANATION and needs_param and project_key:
                return NLRouteResult(intent, f"/explain_project {project_key}", param=project_key)
            if intent == INTENT_EXPLANATION and needs_param and not project_key:
                # "почему этот проект горит" без ключа → explain_portfolio
                return NLRouteResult(intent, "/explain_portfolio", param=None)
            return NLRouteResult(intent, cmd)

    return NLRouteResult(
        INTENT_UNKNOWN, "",
        clarification="Не понял запрос. Попробуйте: «что важно сейчас», «проблемные проекты», «что делать» — или /help."
    )


def get_handler_for_route(route: NLRouteResult) -> Optional[str]:
    """Возвращает имя handler-функции для вызова, или None если нужен clarification."""
    if route.clarification:
        return None
    if not route.synthetic_command:
        return None
    # Mapping command -> handler name (для справки; фактически вызываем по synthetic_command)
    return route.synthetic_command.strip().split()[0]
