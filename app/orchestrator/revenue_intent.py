"""Детектор явного revenue/sales intent для triage override (приоритет над CrewAI)."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Многословные конструкции — не опираются на \b после морфемы «оплат-» / «деньг-».
_PHRASES = (
    r"(?:получить\s+(?:первую|первый|первые)?\s*(?:оплат\w*|деньг\w*|выручк\w*))"
    r"|(?:найти\s+\d*\s*клиент\w*)"
    r"|(?:привести\s+клиент\w*)"
    r"|(?:закрыть\s+клиент\w*)"
    r"|(?:привлечь\s+клиент\w*)"
)

# Слова и корни: \w* для падежей (клиентов, оплату, деньгами).
_WORDS = (
    r"(?:^|(?<=[\s,.:;!?()«»\"'\-]))"
    r"(?:клиент\w*|оплат\w*|деньг\w*|выручк\w*|revenue|sales?|payments?|paying|"
    r"продаж\w*|сделк\w*|лид\w*|покупател\w*|монетиз\w*|спонсор\w*|коммерц\w*)"
    r"(?=(?:$|[\s,.:;!?()«»\"'\-])|\w)"
)

_REVENUE_INTENT_RE = re.compile(
    rf"(?:{_PHRASES}|{_WORDS})",
    re.IGNORECASE | re.UNICODE,
)


def detect_revenue_intent(text: str) -> bool:
    """True, если в тексте задачи явно фигурируют деньги/клиенты/продажи (жёсткий override triage)."""
    raw = (text or "").strip()
    if not raw:
        logger.info("REVENUE_INTENT_CHECK: text empty, result=False")
        return False
    result = bool(_REVENUE_INTENT_RE.search(raw))
    # Лог для прод-отладки: длина + начало строки (полный текст может быть в DEBUG при необходимости).
    preview = raw[:1200].replace("\n", "\\n")
    logger.info(
        "REVENUE_INTENT_CHECK: len=%s result=%s text_head=%r",
        len(raw),
        result,
        preview[:400] + ("…" if len(preview) > 400 else ""),
    )
    return result
