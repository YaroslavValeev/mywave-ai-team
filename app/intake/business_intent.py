from __future__ import annotations

import re

from app.intake.schemas import BusinessAction, NormalizeIntakeResponse

_MARKETING_RE = re.compile(
    r"\b(контент|пост|reels|smm|продвиж|реклама|маркетинг|охват|лид|таргет|воронк)\b",
    re.IGNORECASE,
)
_PRODUCT_RE = re.compile(
    r"\b(фича|frontend|backend|api|ux|ui|лендинг|landing|приложени|сайт|dashboard|платформ)\b",
    re.IGNORECASE,
)
_REVENUE_RE = re.compile(
    r"\b(продаж|выручк|монетизац|спонсор|партнер|партнёр|оффер|коммерческ|sponsor|gtm|go-?to-?market|"
    r"клиент|оплат|лид|revenue|sales?|payment|deal|lead)\b",
    re.IGNORECASE,
)
_OPS_RE = re.compile(
    r"\b(логистик|операцион|процесс|организац|ивент|event|площадк|регистрац|билет|команда\s+на\s+месте)\b",
    re.IGNORECASE,
)
_STRATEGY_LAUNCH = re.compile(r"\b(стратеги[яи]\s+запуск|запуск\s+проект|roadmap|план\s+запуск)\b", re.IGNORECASE)

# Реальные направления MyWave (по тексту владельца)
_UNIT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"wakesafari|wake\s*safari", re.IGNORECASE), "wakesafari"),
    (re.compile(r"snowpolia|snow\s*polia", re.IGNORECASE), "snowpolia"),
    (re.compile(r"\bmywave\b|майвейв", re.IGNORECASE), "mywave"),
    (re.compile(r"медиа|media\s*production|контент-продакш|съёмк|youtube|reels", re.IGNORECASE), "media"),
    (re.compile(r"ai\s*платформ|спонсор.*аналит|analytics\s*platform", re.IGNORECASE), "platform"),
    (re.compile(r"тренировк|training|курс|academy", re.IGNORECASE), "training"),
]


def _detect_business_unit(text: str) -> str | None:
    low = text or ""
    for pat, slug in _UNIT_PATTERNS:
        if pat.search(low):
            return slug
    return None


def _guess_type(text: str, unit: str | None) -> str | None:
    t = text or ""
    scores = {
        "marketing": len(_MARKETING_RE.findall(t)),
        "product": len(_PRODUCT_RE.findall(t)),
        "revenue": len(_REVENUE_RE.findall(t)),
        "ops": len(_OPS_RE.findall(t)),
    }
    # Ивенты WakeSafari: часто ops + revenue одновременно — приоритет revenue если спонсор/оффер
    if unit == "wakesafari":
        scores["ops"] += 2
        scores["revenue"] += 1
    if _STRATEGY_LAUNCH.search(t):
        scores["revenue"] += 2
        scores["ops"] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def apply_business_intent(resp: NormalizeIntakeResponse) -> NormalizeIntakeResponse:
    """Business Intent Layer: task -> business action classification."""
    text = f"{resp.task_brief.title}\n{resp.task_brief.input_summary}\n{resp.task_brief.goal}"
    unit = _detect_business_unit(text)
    btype = _guess_type(text, unit)
    if not btype:
        if unit:
            brief = resp.task_brief.model_copy(update={"business_unit": unit})
            return resp.model_copy(update={"task_brief": brief})
        return resp

    impact = "high" if btype == "revenue" else ("medium" if btype in {"product", "ops"} else "low")
    if unit == "wakesafari" and btype in {"ops", "revenue"}:
        impact = "high"
    action = BusinessAction(
        action_type=btype,  # type: ignore[arg-type]
        expected_outcome=(resp.task_brief.desired_outcome or "Измеримый шаг для проекта MyWave")[:400],
        impact_level=impact,  # type: ignore[arg-type]
        time_to_value="short-term" if impact != "high" else "mid-term",
        requires_owner=impact in {"medium", "high"},
    )
    brief = resp.task_brief.model_copy(
        update={
            "business_type": btype,
            "business_unit": unit,
            "business_goal_hint": (resp.task_brief.goal or resp.task_brief.desired_outcome or "")[:400],
        }
    )
    return resp.model_copy(
        update={
            "task_brief": brief,
            "business_action": action,
            "business_intent": True,
        }
    )
