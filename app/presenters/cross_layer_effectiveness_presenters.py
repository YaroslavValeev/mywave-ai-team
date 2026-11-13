# app/presenters/cross_layer_effectiveness_presenters.py — Phase 11.6
from __future__ import annotations

from typing import Any, List


def present_cross_layer_synthesis(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_days": raw.get("window_days"),
        "slices": raw.get("slices") or [],
        "alignment_items": raw.get("alignment_items") or [],
        "explainable": raw.get("explainable", True),
        "synthesized_at": raw.get("synthesized_at"),
    }


def format_cross_layer_synthesis_telegram(raw: dict[str, Any], top_align: int = 3) -> str:
    s = present_cross_layer_synthesis(raw)
    lines = [f"Cross-layer effectiveness ({s.get('window_days')}д):"]
    for sl in s.get("slices", []):
        lines.append(f"  {sl.get('layer')}: effective={sl.get('effective_count')}, ineffective={sl.get('ineffective_count')}, followup={sl.get('followup_count')}")
    align = s.get("alignment_items", [])[:top_align]
    if align:
        lines.append("Конфликты:")
        for a in align:
            lines.append(f"  • {a.get('headline')}: {a.get('reason')}")
    else:
        lines.append("Конфликтов нет.")
    return "\n".join(lines)
