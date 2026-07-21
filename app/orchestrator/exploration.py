from __future__ import annotations

import logging
import re
from typing import Any

from app.gm_director import build_exploration_scenarios

logger = logging.getLogger(__name__)

_EXPLORATION_HINTS = (
    "я бы хотел",
    "идея",
    "создать проект",
    "новое направление",
    "запустить направление",
    "проверить гипотез",
    "гипотез",
    "предложите варианты",
    "варианты реализации",
    "mvp",
    "new project",
    "new direction",
    "explore",
)

_EXPLORATION_PHRASES_RE = re.compile(
    r"(запуст(ить|им)\s+направлен\w*|провер(ить|им)\s+гипотез\w*|предлож(и|ите)\s+вариант\w*|mvp)",
    re.IGNORECASE,
)

# Не использовать слишком широкое «клиент»: цели вроде «первых клиентов после проверки гипотезы»
# относятся к exploration, а не к немедленному revenue-run.
_EXECUTION_SIGNALS = re.compile(
    r"(оплат\w*|деньг\w*|"
    r"найти\s+\d+\s+клиент\w*|"
    r"\d+\s+клиент\w*\s+и\s+оплат\w*|"
    r"сделк\w*|лид\w*|ship|deploy|выполнить\s+сейчас|сделай\s+сейчас|"
    r"сегодня\s+сделай|до\s+\d{1,2}[./-]\d{1,2})",
    re.IGNORECASE,
)


def detect_exploration_intent(owner_text: str) -> bool:
    raw = (owner_text or "").strip()
    if not raw:
        logger.info("EXPLORATION_INTENT_CHECK: text empty, result=False")
        return False
    lowered = raw.lower()
    hint_hit = any(h in lowered for h in _EXPLORATION_HINTS) or bool(_EXPLORATION_PHRASES_RE.search(raw))
    if not hint_hit:
        logger.info("EXPLORATION_INTENT_CHECK: len=%s hint_hit=False result=False", len(raw))
        return False
    # Exploration включаем только если нет явного сигнала «сразу делаем».
    result = not bool(_EXECUTION_SIGNALS.search(raw))
    logger.info(
        "EXPLORATION_INTENT_CHECK: len=%s hint_hit=%s result=%s text_head=%r",
        len(raw),
        hint_hit,
        result,
        (raw[:240] + ("…" if len(raw) > 240 else "")),
    )
    return result


def build_default_scenarios(owner_text: str) -> dict[str, Any]:
    return build_exploration_scenarios(owner_text)
