from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

# Anti-noise v1.1
MIN_SAMPLES_FOR_SIGNAL = 4
MIN_SAMPLES_FOR_CONFIDENCE = 8
# Разница priority для growth_override: при «полном» сигнале мягче, при 4–7 выборках — жёстче
PRIORITY_DELTA_FULL_SIGNAL = 0.22
PRIORITY_DELTA_LOW_CONFIDENCE = 0.36
PRIORITY_MIN_BEST_FOR_OVERRIDE = 0.35
TREND_EPS = 0.04
logger = logging.getLogger(__name__)
_MISSING_TS_WARNED: set[str] = set()


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_iso_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return _ensure_utc(val)
    if not isinstance(val, str):
        return None
    s = val.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return _ensure_utc(datetime.fromisoformat(s))
    except ValueError:
        return None


def _task_reference_dt(task: Any) -> datetime | None:
    ba = getattr(task, "business_action_json", None)
    if isinstance(ba, dict):
        ai = ba.get("action_instance")
        if isinstance(ai, dict):
            for key in ("completed_at", "started_at", "created_at"):
                dt = _parse_iso_dt(ai.get(key))
                if dt:
                    return dt
    for attr in ("updated_at", "created_at"):
        v = getattr(task, attr, None)
        if isinstance(v, datetime):
            return _ensure_utc(v)
    return None


def _filter_tasks_in_window(tasks: list[Any], *, days: int, ref_now: datetime) -> list[Any]:
    cutoff = _ensure_utc(ref_now) - timedelta(days=days)
    out: list[Any] = []
    for t in tasks:
        d = _task_reference_dt(t)
        if d is None:
            task_id = str(getattr(t, "id", "unknown"))
            if task_id not in _MISSING_TS_WARNED:
                logger.warning("growth_window_missing_timestamp task_id=%s", task_id)
                _MISSING_TS_WARNED.add(task_id)
            continue
        if d >= cutoff:
            out.append(t)
    return out


def _enrich_row(row: dict[str, Any]) -> dict[str, Any]:
    g = int(row.get("generated") or 0)
    conf = round(min(1.0, g / float(MIN_SAMPLES_FOR_CONFIDENCE)), 4)
    if g < MIN_SAMPLES_FOR_SIGNAL:
        level = "none"
    elif g < MIN_SAMPLES_FOR_CONFIDENCE:
        level = "low"
    else:
        level = "full"
    row = dict(row)
    row["confidence"] = conf
    row["signal_level"] = level
    gen = max(g, 1)
    row["rolling_conversion_rate"] = round(float(row.get("sales", 0) or 0) / gen, 4)
    row["rolling_success_rate"] = row["rolling_conversion_rate"]
    row["rolling_revenue"] = round(_safe_float(row.get("revenue")), 2)
    return row


def compute_pack_performance_with_revenue(tasks: list[Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}

    def ensure(pt: str) -> dict[str, Any]:
        if pt not in rows:
            rows[pt] = {
                "pack_type": pt,
                "generated": 0,
                "started": 0,
                "completed": 0,
                "sales": 0,
                "leads": 0,
                "revenue": 0.0,
                "success_rate": 0.0,
                "completion_rate": 0.0,
                "revenue_contribution": 0.0,
                "priority_score": 0.0,
                "explainability": "",
            }
        return rows[pt]

    total_revenue = 0.0
    for t in tasks:
        ba = getattr(t, "business_action_json", None)
        if not isinstance(ba, dict):
            continue
        pack = ba.get("execution_pack") if isinstance(ba.get("execution_pack"), dict) else {}
        action = ba.get("action_instance") if isinstance(ba.get("action_instance"), dict) else {}
        deals = ba.get("deals") if isinstance(ba.get("deals"), list) else []
        leads = ba.get("leads") if isinstance(ba.get("leads"), list) else []

        pt = str(pack.get("pack_type") or action.get("action_type") or "generic_pack")
        cur = ensure(pt)
        cur["generated"] += 1
        status = str(action.get("status") or "pending")
        if action.get("started_at") or status in {"in_progress", "done", "skipped"}:
            cur["started"] += 1
        if status in {"done", "skipped"}:
            cur["completed"] += 1

        for l in leads:
            if isinstance(l, dict) and str(l.get("source_pack_type") or pt) == pt:
                cur["leads"] += 1

        for d in deals:
            if not isinstance(d, dict):
                continue
            if str(d.get("source_pack_type") or pt) != pt:
                continue
            if str(d.get("status") or "").lower() == "won":
                cur["sales"] += 1
                amt = _safe_float(d.get("amount"))
                cur["revenue"] += amt
                total_revenue += amt

    for pt, cur in rows.items():
        gen = max(cur["generated"], 1)
        cur["success_rate"] = round(cur["sales"] / gen, 2)
        cur["completion_rate"] = round(cur["completed"] / gen, 2)

    for pt, cur in rows.items():
        cur["revenue_contribution"] = round((cur["revenue"] / total_revenue), 2) if total_revenue > 0 else 0.0
        priority = (cur["success_rate"] * 0.5) + (cur["revenue_contribution"] * 0.3) + (cur["completion_rate"] * 0.2)
        cur["priority_score"] = round(priority, 3)
        cur["explainability"] = (
            f"{cur['generated']} запусков, {cur['sales']} продаж, revenue={round(cur['revenue'],2)}"
        )

    return rows


def _metrics_map_enriched(tasks: list[Any]) -> dict[str, dict[str, Any]]:
    raw = compute_pack_performance_with_revenue(tasks)
    return {k: _enrich_row(dict(v)) for k, v in raw.items()}


def _pack_trend(pack: str, m7: dict[str, dict[str, Any]], m30: dict[str, dict[str, Any]]) -> str:
    r7 = m7.get(pack) or {}
    r30 = m30.get(pack) or {}
    g7 = int(r7.get("generated") or 0)
    g30 = int(r30.get("generated") or 0)
    p7 = float(r7.get("priority_score") or 0)
    p30 = float(r30.get("priority_score") or 0)
    if g7 < 2 and g30 < MIN_SAMPLES_FOR_SIGNAL:
        return "stable"
    if g30 >= MIN_SAMPLES_FOR_SIGNAL:
        diff = p7 - p30
        if diff > TREND_EPS:
            return "improving"
        if diff < -TREND_EPS:
            return "declining"
        return "stable"
    if g7 >= 2:
        if p7 > p30 + 0.06:
            return "improving"
        if p7 < p30 - 0.06:
            return "declining"
    return "stable"


def _pack_row_for_api(pack: str, row: dict[str, Any], trend: str) -> dict[str, Any]:
    return {
        "pack_type": pack,
        "priority_score": float(row.get("priority_score") or 0),
        "generated": int(row.get("generated") or 0),
        "sales": int(row.get("sales") or 0),
        "revenue": round(_safe_float(row.get("revenue")), 2),
        "trend": trend,
        "confidence": float(row.get("confidence") or 0),
        "signal_level": str(row.get("signal_level") or "none"),
        "rolling_conversion_rate": float(row.get("rolling_conversion_rate") or 0),
        "rolling_revenue": float(row.get("rolling_revenue") or 0),
        "rolling_success_rate": float(row.get("rolling_success_rate") or 0),
    }


def compute_top_actions(tasks: list[Any]) -> list[dict[str, Any]]:
    action_sales: Counter[str] = Counter()
    for t in tasks:
        ba = getattr(t, "business_action_json", None)
        if not isinstance(ba, dict):
            continue
        deals = ba.get("deals") if isinstance(ba.get("deals"), list) else []
        for d in deals:
            if not isinstance(d, dict):
                continue
            if str(d.get("status") or "").lower() != "won":
                continue
            aid = str(d.get("source_action_id") or "unknown")
            action_sales[aid] += 1
    return [{"action_id": k, "sales": v} for k, v in action_sales.most_common(5)]


def recommend_next_actions(
    tasks: list[Any],
    *,
    m7: dict[str, dict[str, Any]] | None = None,
    m30: dict[str, dict[str, Any]] | None = None,
    mall: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    perf = mall or compute_pack_performance_with_revenue(tasks)
    m7 = m7 or _metrics_map_enriched(_filter_tasks_in_window(tasks, days=7, ref_now=datetime.now(timezone.utc)))
    m30 = m30 or _metrics_map_enriched(_filter_tasks_in_window(tasks, days=30, ref_now=datetime.now(timezone.utc)))
    if not perf:
        return ["Недостаточно данных: начните с offer_pack и фиксируйте лиды/продажи."]

    ranked = sorted(perf.values(), key=lambda x: x.get("priority_score", 0), reverse=True)
    recs: list[str] = []

    def _strong(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [r for r in rows.values() if int(r.get("generated") or 0) >= MIN_SAMPLES_FOR_SIGNAL],
            key=lambda x: x.get("priority_score", 0),
            reverse=True,
        )[:2]

    for r in _strong(m7):
        recs.append(
            f"[7d] Усилить {r['pack_type']}: priority={r.get('priority_score')} "
            f"(n={r.get('generated')}, conf={r.get('confidence')})."
        )
    for r in _strong(m30):
        if r["pack_type"] not in {x.get("pack_type") for x in _strong(m7)}:
            recs.append(
                f"[30d] Опора на {r['pack_type']}: устойчивый сигнал (n={r.get('generated')})."
            )

    weak = [r for r in ranked if int(r.get("generated") or 0) >= MIN_SAMPLES_FOR_SIGNAL and r.get("priority_score", 0) < 0.2][:2]
    for r in weak:
        recs.append(f"[всё время] Ограничить {r['pack_type']}: низкая отдача ({r['explainability']})")

    if any(r.get("pack_type") == "partner_outreach_pack" and r.get("priority_score", 0) < 0.2 for r in ranked):
        recs.append("Избегать partner_outreach без CRM/реальных контактов.")

    return recs[:8]


def build_growth_insight(tasks: list[Any], *, ref_now: datetime | None = None) -> dict[str, Any]:
    ref = ref_now or datetime.now(timezone.utc)
    tasks_7d = _filter_tasks_in_window(tasks, days=7, ref_now=ref)
    tasks_30d = _filter_tasks_in_window(tasks, days=30, ref_now=ref)
    m_all = _metrics_map_enriched(tasks)
    m7 = _metrics_map_enriched(tasks_7d)
    m30 = _metrics_map_enriched(tasks_30d)

    ranked = sorted(m_all.values(), key=lambda x: x.get("priority_score", 0), reverse=True)
    top = [{"pack_type": r["pack_type"], "sales": r["sales"], "priority_score": r["priority_score"]} for r in ranked[:3]]
    weak = [
        {"pack_type": r["pack_type"], "sales": r["sales"], "priority_score": r["priority_score"]}
        for r in ranked
        if r.get("priority_score", 0) < 0.2
    ][:3]

    all_pack_types = set(m_all) | set(m7) | set(m30)
    pack_dynamics: list[dict[str, Any]] = []
    for pt in sorted(all_pack_types):
        trend = _pack_trend(pt, m7, m30)
        row = m_all.get(pt) or m30.get(pt) or m7.get(pt) or {"pack_type": pt, "generated": 0, "priority_score": 0.0}
        pack_dynamics.append(_pack_row_for_api(pt, dict(row), trend))

    declining = [p for p in pack_dynamics if p["trend"] == "declining" and p["generated"] >= MIN_SAMPLES_FOR_SIGNAL]
    emerging = [
        p
        for p in pack_dynamics
        if p["trend"] == "improving"
        and int(m7.get(p["pack_type"], {}).get("generated") or 0) >= 2
        and int(m30.get(p["pack_type"], {}).get("generated") or 0) < MIN_SAMPLES_FOR_CONFIDENCE
    ]

    return {
        "top_actions": compute_top_actions(tasks),
        "top_packs": top,
        "weak_packs": weak,
        "recommendations": recommend_next_actions(tasks, m7=m7, m30=m30, mall=m_all),
        "pack_priority": {r["pack_type"]: r["priority_score"] for r in ranked},
        "metrics_7d": m7,
        "metrics_30d": m30,
        "metrics_all_time": m_all,
        "pack_dynamics": pack_dynamics,
        "declining_packs": declining,
        "emerging_packs": emerging,
        "thresholds": {
            "min_samples_for_signal": MIN_SAMPLES_FOR_SIGNAL,
            "min_samples_for_confidence": MIN_SAMPLES_FOR_CONFIDENCE,
        },
    }


def build_growth_api_insight(tasks: list[Any], *, ref_now: datetime | None = None) -> dict[str, Any]:
    """Формат ответа GET /api/business/growth/insight."""
    ref = ref_now or datetime.now(timezone.utc)
    m7 = _metrics_map_enriched(_filter_tasks_in_window(tasks, days=7, ref_now=ref))
    m30 = _metrics_map_enriched(_filter_tasks_in_window(tasks, days=30, ref_now=ref))
    m_all = _metrics_map_enriched(tasks)

    def _tops(rows: dict[str, dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
        ranked_local = sorted(rows.values(), key=lambda x: x.get("priority_score", 0), reverse=True)
        out: list[dict[str, Any]] = []
        for r in ranked_local[:n]:
            pt = str(r.get("pack_type") or "")
            tr = _pack_trend(pt, m7, m30)
            out.append(_pack_row_for_api(pt, dict(r), tr))
        return out

    all_pts = set(m_all) | set(m7) | set(m30)
    dynamics: list[dict[str, Any]] = []
    for pt in sorted(all_pts):
        trend = _pack_trend(pt, m7, m30)
        row = m_all.get(pt) or m30.get(pt) or m7.get(pt) or {"pack_type": pt, "generated": 0, "priority_score": 0.0}
        dynamics.append(_pack_row_for_api(pt, dict(row), trend))

    declining_packs = [p for p in dynamics if p["trend"] == "declining" and p["generated"] >= MIN_SAMPLES_FOR_SIGNAL]
    emerging_packs = [
        p
        for p in dynamics
        if p["trend"] == "improving"
        and int(m7.get(p["pack_type"], {}).get("generated") or 0) >= 2
        and int(m30.get(p["pack_type"], {}).get("generated") or 0) < MIN_SAMPLES_FOR_CONFIDENCE
    ]

    return {
        "top_packs_7d": _tops(m7, 5),
        "top_packs_30d": _tops(m30, 5),
        "declining_packs": declining_packs,
        "emerging_packs": emerging_packs,
        "recommendations": recommend_next_actions(tasks, m7=m7, m30=m30, mall=m_all),
        "pack_dynamics": dynamics,
        "metrics_all_time": m_all,
    }


def format_growth_insight_telegram(growth: dict[str, Any]) -> str:
    """Краткий Insight для Telegram с акцентом на 7d."""
    lines: list[str] = []
    m7 = growth.get("metrics_7d") if isinstance(growth.get("metrics_7d"), dict) else {}
    strong7 = sorted(
        [dict(v) for v in m7.values() if isinstance(v, dict) and int(v.get("generated") or 0) >= MIN_SAMPLES_FOR_SIGNAL],
        key=lambda x: float(x.get("priority_score") or 0),
        reverse=True,
    )
    weak7 = sorted(
        [dict(v) for v in m7.values() if isinstance(v, dict) and int(v.get("generated") or 0) >= MIN_SAMPLES_FOR_SIGNAL],
        key=lambda x: float(x.get("priority_score") or 0),
    )
    if strong7:
        best = strong7[0]
        lines.append(f"За последние 7 дней лучше: {best.get('pack_type')} (priority={best.get('priority_score')}).")
    if weak7 and strong7 and weak7[0].get("pack_type") != strong7[0].get("pack_type"):
        w = weak7[0]
        if int(w.get("generated") or 0) >= MIN_SAMPLES_FOR_SIGNAL:
            lines.append(f"За 7 дней слабее: {w.get('pack_type')} (priority={w.get('priority_score')}).")
    if not lines and growth.get("top_packs"):
        packs = ", ".join(str(p.get("pack_type")) for p in growth.get("top_packs", [])[:2])
        lines.append(f"За всё время сильнее: {packs} (мало свежих событий для окна 7d).")
    recs = growth.get("recommendations") or []
    if recs:
        lines.append(f"Рекомендация: {recs[0]}")
    if not lines:
        return ""
    return "\n\nInsight (рост):\n" + "\n".join(f"→ {ln}" for ln in lines)


def growth_override_allowed(
    *,
    base_priority: float,
    best_priority: float,
    base_generated: int,
    best_generated: int,
) -> bool:
    """Правило anti-noise для смены pack в сторону более сильного."""
    if best_generated < MIN_SAMPLES_FOR_SIGNAL or base_generated < MIN_SAMPLES_FOR_SIGNAL:
        return False
    if best_priority < PRIORITY_MIN_BEST_FOR_OVERRIDE:
        return False
    full_conf = base_generated >= MIN_SAMPLES_FOR_CONFIDENCE and best_generated >= MIN_SAMPLES_FOR_CONFIDENCE
    need_delta = PRIORITY_DELTA_FULL_SIGNAL if full_conf else PRIORITY_DELTA_LOW_CONFIDENCE
    return best_priority >= (base_priority + need_delta)
