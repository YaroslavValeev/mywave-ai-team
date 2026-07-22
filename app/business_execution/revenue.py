from __future__ import annotations

import time
from collections import Counter
from typing import Any


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def ensure_revenue_fields(blob: dict[str, Any]) -> dict[str, Any]:
    out = dict(blob)
    if not isinstance(out.get("leads"), list):
        out["leads"] = []
    if not isinstance(out.get("deals"), list):
        out["deals"] = []
    if not isinstance(out.get("revenue_warnings"), list):
        out["revenue_warnings"] = []
    return out


def create_lead(
    blob: dict[str, Any],
    *,
    project_id: int | None,
    action_id: str,
    pack_type: str,
    channel: str,
    notes: str,
    value_estimate: str,
    status: str = "new",
) -> dict[str, Any]:
    out = ensure_revenue_fields(blob)
    if not action_id:
        out["revenue_warnings"].append("lead без source_action_id")
        return out
    lead_id = f"lead-{int(time.time() * 1000)}"
    out["leads"].append(
        {
            "lead_id": lead_id,
            "project_id": project_id,
            "source_action_id": action_id,
            "source_pack_type": pack_type or "generic_pack",
            "created_at": _now_iso(),
            "channel": (channel or "unknown")[:80],
            "status": status,
            "value_estimate": (value_estimate or "")[:120],
            "notes": (notes or "")[:1000],
        }
    )
    return out


def create_deal(
    blob: dict[str, Any],
    *,
    project_id: int | None,
    action_id: str,
    pack_type: str,
    amount: str,
    notes: str,
    lead_id: str = "",
    status: str = "won",
) -> dict[str, Any]:
    out = ensure_revenue_fields(blob)
    if not action_id:
        out["revenue_warnings"].append("sale без source_action_id")
        return out
    amt = _safe_float(amount)
    if amt <= 0:
        out["revenue_warnings"].append("sale без суммы")

    resolved_lead = lead_id
    if not resolved_lead:
        # create lightweight attributed lead automatically
        out = create_lead(
            out,
            project_id=project_id,
            action_id=action_id,
            pack_type=pack_type,
            channel="sale",
            notes="auto-created from sale",
            value_estimate=str(amount or "0"),
            status="converted",
        )
        if out.get("leads"):
            resolved_lead = out["leads"][-1].get("lead_id", "")

    out["deals"].append(
        {
            "deal_id": f"deal-{int(time.time() * 1000)}",
            "lead_id": resolved_lead,
            "project_id": project_id,
            "amount": str(amount or "0"),
            "status": status,
            "closed_at": _now_iso(),
            "notes": (notes or "")[:1000],
            "source_action_id": action_id,
            "source_pack_type": pack_type or "generic_pack",
        }
    )
    return out


def task_revenue_summary(blob: dict[str, Any]) -> dict[str, Any]:
    b = ensure_revenue_fields(blob)
    leads = [x for x in b.get("leads", []) if isinstance(x, dict)]
    deals = [x for x in b.get("deals", []) if isinstance(x, dict)]
    total = sum(_safe_float(d.get("amount")) for d in deals if str(d.get("status") or "").lower() == "won")
    return {
        "leads": len(leads),
        "sales": len([d for d in deals if str(d.get("status") or "").lower() == "won"]),
        "revenue_total": round(total, 2),
        "warnings": b.get("revenue_warnings", []),
    }


def compute_revenue_metrics_from_tasks(tasks: list[Any]) -> dict[str, Any]:
    total_actions = 0
    total_leads = 0
    total_sales = 0
    revenue_total = 0.0
    pack_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()

    for t in tasks:
        ba = getattr(t, "business_action_json", None)
        if not isinstance(ba, dict):
            continue
        action = ba.get("action_instance") if isinstance(ba.get("action_instance"), dict) else {}
        action_id = str(action.get("action_id") or "")
        if action_id:
            total_actions += 1

        leads = ba.get("leads") if isinstance(ba.get("leads"), list) else []
        deals = ba.get("deals") if isinstance(ba.get("deals"), list) else []

        for l in leads:
            if not isinstance(l, dict):
                continue
            if not l.get("source_action_id"):
                continue
            total_leads += 1
            pack_counter[str(l.get("source_pack_type") or "generic_pack")] += 1
            action_counter[str(l.get("source_action_id") or "unknown")] += 1

        for d in deals:
            if not isinstance(d, dict):
                continue
            if str(d.get("status") or "").lower() != "won":
                continue
            total_sales += 1
            revenue_total += _safe_float(d.get("amount"))
            pack_counter[str(d.get("source_pack_type") or "generic_pack")] += 1
            action_counter[str(d.get("source_action_id") or "unknown")] += 1

    conversion_rate = round((total_sales / total_leads), 2) if total_leads else 0.0
    top_pack_types = [{"pack_type": k, "count": v} for k, v in pack_counter.most_common(5)]
    top_actions = [{"action_id": k, "count": v} for k, v in action_counter.most_common(5)]
    return {
        "total_actions": total_actions,
        "total_leads": total_leads,
        "total_sales": total_sales,
        "conversion_rate": conversion_rate,
        "revenue_total": round(revenue_total, 2),
        "top_pack_types": top_pack_types,
        "top_actions": top_actions,
        "funnel": {
            "actions": total_actions,
            "leads": total_leads,
            "deals": total_sales,
        },
    }
