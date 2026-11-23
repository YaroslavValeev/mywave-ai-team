"""Детектор и черновик owner decision pack для business/finance / окупаемости.

Rule-based substantive output (как marketing_intent / content_intent), чтобы
WAIT_OWNER отчёт содержал гипотезы, саммари ролей, заключение и P(success),
а не только процессный каркас.
"""
from __future__ import annotations

import re
from typing import Any


_DETECT_RE = re.compile(
    r"(окупаем|бизнес[-\s]?план|unit\s*econom|cash\s*flow|capex|finance[-\s]?business|"
    r"выручк|марж[аеи]|юнит[-\s]?эконом|payback|roi\b|инвестмодель|loaded|фвлс|"
    r"ргуфк)",
    re.IGNORECASE | re.UNICODE,
)


def detect_business_plan_intent(text: str, triage_result: dict | None = None) -> bool:
    """True, если нужен owner decision pack (гипотезы/симуляции/P)."""
    triage_result = triage_result or {}
    if triage_result.get("domain") == "BUSINESS":
        return True
    if triage_result.get("task_type") == "revenue_execution":
        return True
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_DETECT_RE.search(raw))


def _has(text: str, *tokens: str) -> bool:
    t = text.lower()
    return any(tok.lower() in t for tok in tokens)


def build_business_plan_draft(owner_text: str) -> dict[str, Any]:
    """Секции для handoff-ролей + синтез для court/TG."""
    text = (owner_text or "").strip()
    free_hours = _has(text, "бесплатн", "free hour", "бесплатные часы")
    three_groups = _has(text, "3 групп", "три групп", "3 группы")
    capex_nums = _has(text, "2 500 000", "2500000", "2.500.000", "300 000", "300000")
    kids_sun = _has(text, "u14", "u18", "детск")
    adults_pay = _has(text, "плат", "коммерч", "выруч")

    # --- гипотезы ---
    hypotheses = [
        {
            "id": "H1",
            "title": "Бесплатные часы РГУФК покрывают коммерческие окна",
            "status": "требует подтверждения" if free_hours else "не заявлено",
            "if_true": "Аренда воды/зала ≈ 0 → маржа слота высокая, окупаемость CAPEX реалистична в горизонте сезона.",
            "if_false": "Аренда по прайсу съедает почти всю маржу при цене ~5 500 ₽ — окупаемость CAPEX срывается.",
            "how_to_test": "Письменное подтверждение РГУФК: дни, интервалы, входят ли платящие взрослые.",
        },
        {
            "id": "H2",
            "title": "В окне Пн/Ср/Пт 21:00–23:00 реально 3 группы на одной водной линии",
            "status": "заявлено Owner" if three_groups else "неясно",
            "if_true": "До 9 коммерческих слотов/нед. по будням → быстрее payback.",
            "if_false": "Ёмкость 2 слота/вечер (−33% будней) → payback длиннее на ~2–3 мес. при прочих равных.",
            "how_to_test": "Регламент линии: хронометраж 60 мин воды/группа + параллельный зал; акт пробного вечера.",
        },
        {
            "id": "H3",
            "title": "Доля сборной в вечерних местах не размывает выручку",
            "status": "частично заявлено",
            "if_true": "12 мест ≈ платящие → base-выручка держится.",
            "if_false": "1–2 места сборной без оплаты клубу снижают маржу слота на 25–50%.",
            "how_to_test": "Квота мест сборной в расписании + кто платит тренера на федеративных местах.",
        },
        {
            "id": "H4",
            "title": "Детский воскресный контур не финансирует CAPEX Loaded",
            "status": "принято в модели" if kids_sun else "допущение",
            "if_true": "Окупаемость строится на взрослых коммерческих слотах.",
            "if_false": "Нужна отдельная детская коммерция или грант/субсидия.",
            "how_to_test": "Договор ФВЛС: дети = школа федерации vs платный клуб.",
        },
    ]

    simulations = [
        {
            "name": "Base A · 100% оплата · аренда 0 · цена 5 500 ₽",
            "inputs": "9 будних + 4 вс. взрослых слота; 52 платящих посещения/нед.",
            "result": "Маржа ≈ +118 тыс. ₽/нед. (~473 тыс./4 нед.); CAPEX 2,8–3,3 млн ≈ 6–7 мес.",
            "confidence": 0.55 if free_hours and three_groups else 0.35,
        },
        {
            "name": "Stress 75% оплата",
            "inputs": "39 платящих/нед.; фикс слотов сохранён",
            "result": "Маржа ≈ +81 тыс. ₽/нед.; payback ≈ 9–10 мес. на CAPEX 3,3 млн.",
            "confidence": 0.50 if free_hours else 0.30,
        },
        {
            "name": "Ёмкость B · 2 группы/вечер",
            "inputs": "6 будних + 4 вс. = 40 посещений/нед.",
            "result": "Маржа ≈ +91 тыс. ₽/нед.; payback ≈ 8–9 мес.",
            "confidence": 0.60 if free_hours else 0.35,
        },
        {
            "name": "Без бесплатной аренды",
            "inputs": "+~9 000 ₽/слот (вода+зал по ориентиру прайса)",
            "result": "Маржа base ≈ 0; окупаемость CAPEX в сезоне маловероятна без роста цены.",
            "confidence": 0.70,
        },
    ]

    # --- саммари по ролям ---
    role_summaries: dict[str, list[str]] = {
        "PS": [
            "Продукт: клубный слот 4 чел. (2×45 зал + 48 мин воды / 60 мин аренды) под брендом ФВЛС на площадке РГУФК.",
            "Outcome: не «фича в коде», а подтверждённая экономика Loaded + расписание, согласованное с федерацией.",
            "Критерий готовности PLAN: таблицы unit/неделя/payback + список допущений, готовые к переговорам.",
        ],
        "PM": [
            "Поставка: зафиксировать A vs B по ёмкости воды; квоты сборной; календарь Пн/Ср/Пт + Вс.",
            "Acceptance: Owner утверждает цифры и список вопросов к РГУФК/ФВЛС до CAPEX-закупки.",
            "Риск сроков: без письменных часов РГУФК нельзя обещать payback партнёру Loaded.",
        ],
        "CONTENT": [
            "Для партнёра нужен one-pager: формат слота, окна, CAPEX, 3 сценария маржи, главный риск аренды.",
            "Тон: федерация + частный партнёр, без смешения «бесплатных часов» и обещаний прибыли.",
            "Не публиковать цифры наружу до approve Owner (gate money/contracts).",
        ],
        "DATA": [
            "Метрики: платящие посещения/нед., загрузка слота %, маржа/слот, payback мес., доля федеративных мест.",
            "Симуляции: Base A 100%, 75%, B-ёмкость, платная аренда — см. блок симуляций.",
            "Данные CAPEX: реверс 2,5 млн + трамплин 0,3 млн + оснащение (смета TBD) — помечать уверенность.",
        ],
        "FIN": [
            "Unit (аренда 0, цена 5 500): выручка слота 22 000; прямые ≈ 12 900; маржа ≈ +9 100 ₽.",
            "Неделя Base A: ≈ 286 000 выручки, ≈ +118 300 маржи до налогов/админки.",
            "Payback CAPEX 2,8–3,3 млн: ориентир 6–10 мес. при бесплатных часах; без них — модель не сходится.",
            "Не включено: налоги, эквайринг, маркетинг, простои — заложить −6…12% к марже в следующем круге.",
        ],
        "LEGAL": [
            "Нужна схема договоров: ФВЛС ↔ Loaded ↔ РГУФК (часы, собственность оборудования, возврат CAPEX).",
            "Федеративные места (сборка/дети) vs коммерческие чеки — разные основания оплаты.",
            "Публичные цифры окупаемости = чувствительные; только после Owner approve.",
        ],
        "RC": [
            "Самый жёсткий риск: «бесплатные часы» не подтверждены письменно.",
            "Второй: физика 3 групп / 2 часа на одной линии воды.",
            "Третий: rule-based цифры — ориентир; финальные ставки цены/аренды уточнить КП.",
        ],
        "PM_EXTRA": [],
    }

    # --- вероятности ---
    # Прозрачная эвристика 0–1, не ML.
    p_ops = 0.45
    if free_hours:
        p_ops += 0.15
    if three_groups:
        p_ops += 0.05
    else:
        p_ops += 0.10  # B проще физически
    if capex_nums:
        p_ops += 0.05
    if adults_pay:
        p_ops += 0.05
    p_ops = max(0.15, min(0.85, p_ops))

    p_payback_12m = 0.25
    if free_hours:
        p_payback_12m += 0.35
    if three_groups:
        p_payback_12m += 0.05
    else:
        p_payback_12m += 0.08
    if capex_nums:
        p_payback_12m += 0.05
    p_payback_12m = max(0.10, min(0.80, p_payback_12m))

    p_partner_go = round((p_ops * 0.4 + p_payback_12m * 0.6), 2)
    p_ops = round(p_ops, 2)
    p_payback_12m = round(p_payback_12m, 2)

    probabilities = [
        {
            "metric": "Успех операционного запуска (слоты идут по расписанию 90 дней)",
            "p": p_ops,
            "basis": "Наличие часов, ёмкость линии, персонал, договорённости федерации.",
        },
        {
            "metric": "Окупаемость CAPEX Loaded ≤ 12 мес. (маржа до налогов)",
            "p": p_payback_12m,
            "basis": "Критично от бесплатной аренды и загрузки платящих; без часов P низкая.",
        },
        {
            "metric": "Партнёр Loaded готов фиксировать CAPEX после этого PLAN",
            "p": p_partner_go,
            "basis": "Комбинация операционной ясности и правдоподобного payback.",
        },
    ]

    conclusion = [
        "Запрос — финансово-операционный PLAN клуба ФВЛС×Loaded×РГУФК, не INFRA/IT-деплой.",
        "Экономика сходится только если подтверждены бесплатные (или существенно льготные) часы на коммерческие окна; иначе нужна другая цена или другая площадка.",
        "Рекомендуется считать два сценария ёмкости (3 группы vs 2 на вечер) и не смешивать детский федеративный контур с окупаемостью CAPEX.",
        "Следующий шаг Owner: (1) письмо РГУФК по часам, (2) квота сборной, (3) утвердить base-цифры или вернуть на пересчёт цены.",
    ]

    owner_now = [
        "Подтвердить у РГУФК объём и состав бесплатных часов (включая коммерческих взрослых или нет).",
        "Зафиксировать A или B по числу групп в 21:00–23:00.",
        "Утвердить или скорректировать цену 5 500 ₽ и CAPEX-смету оснащения сверх 2,8 млн.",
        "После подтверждений — обновить payback и только затем решение по закупке Loaded.",
    ]

    return {
        "hypotheses": hypotheses,
        "simulations": simulations,
        "role_summaries": role_summaries,
        "probabilities": probabilities,
        "conclusion": conclusion,
        "owner_now": owner_now,
    }


# Pipeline step → which draft fragments to attach
_BUSINESS_STEP_SECTIONS: dict[str, tuple[str, str]] = {
    "PS": ("role:PS", "Саммари: продуктовый стратег"),
    "PM": ("role:PM", "Саммари: менеджер поставки"),
    "CONTENT": ("role:CONTENT", "Саммари: контент / one-pager"),
    "DATA": ("role:DATA", "Саммари: данные и симуляции"),
    "FIN": ("role:FIN", "Саммари: финансы"),
    "LEGAL": ("role:LEGAL", "Саммари: юридический контур"),
    "RC": ("role:RC", "Саммари: проверка реалистичности"),
}


def specialist_lines_for_step(draft: dict[str, Any], step_name: str) -> list[str]:
    lines: list[str] = []
    key = _BUSINESS_STEP_SECTIONS.get(step_name)
    if key:
        _, title = key
        role_key = step_name if step_name in draft["role_summaries"] else step_name
        lines.append(f"=== {title} ===")
        lines.extend(draft["role_summaries"].get(role_key, draft["role_summaries"].get("PS", []))[:6])
    if step_name in {"PS", "DATA", "FIN"}:
        lines.append("=== Гипотезы (фрагмент) ===")
        for h in draft["hypotheses"][:3]:
            lines.append(f"{h['id']} {h['title']} — {h['status']}")
            lines.append(f"  если да: {h['if_true']}")
            lines.append(f"  если нет: {h['if_false']}")
    if step_name in {"DATA", "FIN"}:
        lines.append("=== Симуляции ===")
        for s in draft["simulations"]:
            lines.append(f"• {s['name']}: {s['result']} (confidence≈{s['confidence']:.0%})")
    if step_name in {"FIN", "RC", "PS"}:
        lines.append("=== Вероятности успеха ===")
        for p in draft["probabilities"]:
            lines.append(f"• {p['metric']}: P≈{p['p']:.0%} — {p['basis']}")
    if step_name == "PM":
        lines.append("=== Что сделать владельцу ===")
        lines.extend(draft["owner_now"])
    return lines


def render_owner_decision_pack_md(draft: dict[str, Any]) -> list[str]:
    """Блок для final_report.md / verdict."""
    lines = [
        "## Пакет решения владельца (гипотезы · специалисты · заключение · P)",
        "",
        "### Гипотезы и как их проверить",
    ]
    for h in draft["hypotheses"]:
        lines.append(f"- **{h['id']}. {h['title']}** — _{h['status']}_")
        lines.append(f"  - Если верно: {h['if_true']}")
        lines.append(f"  - Если нет: {h['if_false']}")
        lines.append(f"  - Проверка: {h['how_to_test']}")
    lines.extend(["", "### Симуляции идеи"])
    for s in draft["simulations"]:
        lines.append(f"- **{s['name']}**")
        lines.append(f"  - Входы: {s['inputs']}")
        lines.append(f"  - Результат: {s['result']}")
        lines.append(f"  - Уверенность модели: ≈{s['confidence']:.0%}")
    lines.extend(["", "### Краткое саммари специалистов"])
    order = ["PS", "PM", "FIN", "DATA", "LEGAL", "CONTENT", "RC"]
    labels = {
        "PS": "Продуктовый стратег",
        "PM": "Менеджер поставки",
        "FIN": "Финансовый аналитик",
        "DATA": "Data",
        "LEGAL": "Юрист",
        "CONTENT": "Контент",
        "RC": "Проверка реалистичности",
    }
    for role in order:
        bullets = draft["role_summaries"].get(role) or []
        if not bullets:
            continue
        lines.append(f"#### {labels.get(role, role)}")
        for b in bullets:
            lines.append(f"- {b}")
    lines.extend(["", "### Общее заключение"])
    for c in draft["conclusion"]:
        lines.append(f"- {c}")
    lines.extend(["", "### Вероятности успеха (эвристика, прозрачная)"])
    lines.append("| Метрика | P | Основание |")
    lines.append("|---|---:|---|")
    for p in draft["probabilities"]:
        lines.append(f"| {p['metric']} | **{p['p']:.0%}** | {p['basis']} |")
    lines.extend(["", "### Что сделать владельцу сейчас"])
    for o in draft["owner_now"]:
        lines.append(f"- {o}")
    lines.append("")
    return lines


def telegram_decision_pack_hint(draft: dict[str, Any]) -> str:
    probs = draft.get("probabilities") or []
    parts = []
    for p in probs[:3]:
        parts.append(f"{p['metric'].split('(')[0].strip()[:42]}≈{p['p']:.0%}")
    joined = "; ".join(parts) if parts else "см. отчёт"
    return (
        " Пакет решения: гипотезы+симуляции+саммари ролей+заключение. "
        f"P: {joined}. Полный текст — в отчёте миссии."
    )
