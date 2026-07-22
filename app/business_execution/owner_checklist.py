from __future__ import annotations

from typing import Any

# Пороги v1 — синхронно с docs/OWNER-PRODUCTION-CHECKLIST-V1.md
STOP_ACTIONS_TS_PCT = 70.0
STOP_ACTIONS_RESULT_PCT = 50.0
STOP_LEADS_SOURCE_PCT = 80.0
STOP_DEALS_AMOUNT_PCT = 70.0


def compute_data_health(tasks: list[Any]) -> dict[str, Any]:
    """Проценты качества данных по задачам (без привязки к HTTP)."""
    action_total = 0
    action_with_timestamp = 0
    action_with_result = 0
    leads_total = 0
    leads_with_source = 0
    deals_total = 0
    deals_with_amount = 0

    for t in tasks:
        ba = t.business_action_json if isinstance(getattr(t, "business_action_json", None), dict) else {}
        ai = ba.get("action_instance") if isinstance(ba.get("action_instance"), dict) else None
        if isinstance(ai, dict):
            action_total += 1
            has_ts = bool(ai.get("created_at") or ai.get("started_at") or ai.get("completed_at"))
            if has_ts:
                action_with_timestamp += 1
            has_result = bool(str(ai.get("result_summary") or "").strip())
            if not has_result:
                snaps = ba.get("result_snapshots") if isinstance(ba.get("result_snapshots"), list) else []
                has_result = any(bool(str((s or {}).get("result_value") or "").strip()) for s in snaps if isinstance(s, dict))
            if has_result:
                action_with_result += 1

        leads = ba.get("leads") if isinstance(ba.get("leads"), list) else []
        for lead in leads:
            if not isinstance(lead, dict):
                continue
            leads_total += 1
            if lead.get("source_pack_type") or lead.get("source_action_id"):
                leads_with_source += 1

        deals = ba.get("deals") if isinstance(ba.get("deals"), list) else []
        for deal in deals:
            if not isinstance(deal, dict):
                continue
            deals_total += 1
            try:
                amount_ok = float(deal.get("amount")) > 0
            except (TypeError, ValueError):
                amount_ok = False
            if amount_ok:
                deals_with_amount += 1

    def _pct(part: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round((part / total) * 100.0, 2)

    return {
        "actions_with_timestamp_pct": _pct(action_with_timestamp, action_total),
        "actions_with_result_pct": _pct(action_with_result, action_total),
        "leads_with_source_pct": _pct(leads_with_source, leads_total),
        "deals_with_amount_pct": _pct(deals_with_amount, deals_total),
        "counts": {
            "actions_total": action_total,
            "actions_with_timestamp": action_with_timestamp,
            "actions_with_result": action_with_result,
            "leads_total": leads_total,
            "leads_with_source": leads_with_source,
            "deals_total": deals_total,
            "deals_with_amount": deals_with_amount,
        },
    }


def _growth_has_full_signal(growth_insight: dict[str, Any] | None) -> bool:
    if not growth_insight:
        return False
    mall = growth_insight.get("metrics_all_time")
    if not isinstance(mall, dict):
        return False
    for row in mall.values():
        if not isinstance(row, dict):
            continue
        if int(row.get("generated") or 0) >= 8:
            return True
    return False


def _growth_has_low_only(growth_insight: dict[str, Any] | None) -> bool:
    """Есть действия, но ни один тип не набрал «полный» объём."""
    if not growth_insight:
        return False
    mall = growth_insight.get("metrics_all_time")
    if not isinstance(mall, dict) or not mall:
        return False
    return not _growth_has_full_signal(growth_insight)


def _growth_has_unstable_band(growth_insight: dict[str, Any] | None) -> bool:
    if not growth_insight:
        return False
    mall = growth_insight.get("metrics_all_time")
    if not isinstance(mall, dict):
        return False
    for row in mall.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("signal_level") or "") == "low":
            return True
    return False


def classify_owner_day_status(
    health: dict[str, Any],
    growth_insight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    OK / WARNING / STOP — простыми словами для Owner.
    STOP только если есть данные в категории и они ниже порога.
    """
    counts = health.get("counts") if isinstance(health.get("counts"), dict) else {}
    at = int(counts.get("actions_total") or 0)
    lt = int(counts.get("leads_total") or 0)
    dt = int(counts.get("deals_total") or 0)

    ts_pct = float(health.get("actions_with_timestamp_pct") or 0)
    res_pct = float(health.get("actions_with_result_pct") or 0)
    lead_pct = float(health.get("leads_with_source_pct") or 0)
    deal_pct = float(health.get("deals_with_amount_pct") or 0)

    stop_reasons: list[str] = []
    if at > 0 and ts_pct < STOP_ACTIONS_TS_PCT:
        stop_reasons.append("мало отметок времени у выполненных шагов")
    if at > 0 and res_pct < STOP_ACTIONS_RESULT_PCT:
        stop_reasons.append("мало записанных итогов по шагам")
    if lt > 0 and lead_pct < STOP_LEADS_SOURCE_PCT:
        stop_reasons.append("лиды почти без указания источника")
    if dt > 0 and deal_pct < STOP_DEALS_AMOUNT_PCT:
        stop_reasons.append("сделки почти без суммы")

    if stop_reasons:
        return {
            "code": "STOP",
            "title": "Стоп",
            "message": "Сначала поправьте данные — иначе подсказки будут вводить в заблуждение.",
            "details": stop_reasons,
        }

    warn_bits: list[str] = []
    if at >= 1 and _growth_has_low_only(growth_insight):
        warn_bits.append("мало повторений по шагам — подсказки роста осторожные")
    if _growth_has_unstable_band(growth_insight):
        warn_bits.append("есть шаги на «среднем» объёме данных — не полагайтесь вслепую")
    m7 = (growth_insight or {}).get("metrics_7d") if isinstance((growth_insight or {}).get("metrics_7d"), dict) else {}
    g7 = sum(int((v or {}).get("generated") or 0) for v in m7.values() if isinstance(v, dict))
    if g7 < 4 and at >= 1:
        warn_bits.append("мало свежих шагов за последнюю неделю — тренд не ясен")

    if warn_bits:
        return {
            "code": "WARNING",
            "title": "Осторожно",
            "message": "Работать можно, но проверяйте решения здравым смыслом.",
            "details": warn_bits,
        }

    return {
        "code": "OK",
        "title": "Всё в порядке",
        "message": "Можно планировать шаги на день.",
        "details": [],
    }


def owner_daily_checklist_bullets() -> list[str]:
    """Короткий протокол без жаргона (5–7 строк)."""
    return [
        "Утром: посмотрите статус ниже — зелёный, жёлтый или красный.",
        "Выберите не больше одного–трёх шагов на день — что реально доведёте до конца.",
        "Одна задача — одно действие — одно завершение.",
        "После шага обязательно отметьте итог: ничего / лид / продажа; у продажи укажите сумму.",
        "Не держите итог «в голове» — только записанный итог считается.",
        "Если подсказки роста странные или данных мало — берите базовый план, не «усиление».",
        "Вечером: хотя бы один шаг завершён и один итог записан.",
    ]


def owner_protocol_for_dashboard(tasks: list[Any], growth_insight: dict[str, Any] | None) -> dict[str, Any]:
    health = compute_data_health(tasks)
    status = classify_owner_day_status(health, growth_insight)
    return {
        "health": health,
        "status": status,
        "checklist": owner_daily_checklist_bullets(),
    }
