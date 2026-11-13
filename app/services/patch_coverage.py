# app/services/patch_coverage.py — Phase 11.8: patch coverage summary (patchable vs manual-only)
from __future__ import annotations

from typing import Any

from app.services.refinement_exports import export_pending_refinement_changes
from app.services.registry_patch_builder import build_patch_candidate, SAFE_PATCH_TYPES


def get_patch_coverage_summary(status: str = "accepted", limit: int = 100) -> dict[str, Any]:
    """Сводка: patchable vs manual-only по accepted proposals. Phase 11.8."""
    items = export_pending_refinement_changes(status=status)[:limit]
    patchable = 0
    manual_only = 0
    by_type: dict[str, dict[str, int]] = {}
    patchable_types: list[str] = []

    for p in items:
        pid = p.get("proposal_id")
        if not pid:
            continue
        patch = build_patch_candidate(pid)
        ptype = patch.get("patch_type", "manual_review")
        apply_allowed = bool(patch.get("apply_allowed"))
        by_type.setdefault(ptype, {"patchable": 0, "manual": 0})
        if apply_allowed and ptype in SAFE_PATCH_TYPES:
            patchable += 1
            by_type[ptype]["patchable"] += 1
            if ptype not in patchable_types:
                patchable_types.append(ptype)
        else:
            manual_only += 1
            by_type[ptype]["manual"] += 1

    return {
        "patchable_count": patchable,
        "manual_only_count": manual_only,
        "total_accepted": len(items),
        "by_type": by_type,
        "patchable_types": patchable_types,
        "safe_patch_types": list(SAFE_PATCH_TYPES),
    }
