# app/services/refinement_exports.py — Phase 10.6: export refinement proposals as change candidates
from __future__ import annotations

from typing import Any, List, Optional

from app.services.refinement_proposal_store import get_proposal, list_proposals


def export_refinement_proposal(proposal_id: str) -> Optional[dict[str, Any]]:
    """Экспорт одного proposal в виде change candidate (human-readable + machine-readable)."""
    p = get_proposal(proposal_id)
    if not p:
        return None
    patch = build_registry_patch_candidate(proposal_id)
    return {
        "proposal_id": proposal_id,
        "proposal": p,
        "patch_candidate": patch,
        "export_format": "refinement_candidate",
    }


def export_pending_refinement_changes(status: str = "accepted") -> List[dict[str, Any]]:
    """Экспорт всех proposals с заданным статусом (обычно accepted) как список change candidates."""
    items = list_proposals(status=status, limit=100)
    out = []
    for p in items:
        pid = p.get("proposal_id")
        if not pid:
            continue
        patch = build_registry_patch_candidate(pid)
        out.append({
            "proposal_id": pid,
            "proposal": p,
            "patch_candidate": patch,
        })
    return out


def _extract_append_value(proposal: dict[str, Any], default: str) -> str:
    """Извлечь значение для append из evidence_summary или reason. Phase 11.8."""
    ev = (proposal.get("evidence_summary") or "")
    if isinstance(ev, list):
        ev = " ".join(str(x) for x in ev)
    rec = (proposal.get("recommended_change") or "")
    for s in (ev, rec, proposal.get("reason", "")):
        if not s or len(s) > 200:
            continue
        s = str(s).strip()
        for prefix in ("keyword:", "alias:", "add ", "добавить "):
            if prefix in s.lower():
                rest = s[s.lower().find(prefix) + len(prefix):].strip().split(",")[0].strip()
                if rest and len(rest) < 80 and " " not in rest:
                    return rest
        if s and len(s) < 50 and " " not in s:
            return s
    return default


def build_registry_patch_candidate(proposal_id: str) -> dict[str, Any]:
    """Построить предложение патча для реестра (YAML/JSON delta или текстовая инструкция). Phase 11.8: + domain_registry, expand_specialization."""
    p = get_proposal(proposal_id)
    if not p:
        return {"error": "proposal not found", "proposal_id": proposal_id}
    ptype = p.get("proposal_type", "")
    target_layer = p.get("target_layer", "")
    target_key = p.get("target_key", "")
    domain_key = p.get("domain_key") or (target_key.split(":")[0] if target_key else "")
    workflow_step = p.get("workflow_step") or (target_key.split(":")[-1] if ":" in (target_key or "") else "")

    if ptype == "add_specialization_profile" and target_layer == "specializations":
        key = f"{domain_key}_{workflow_step}" if domain_key and workflow_step else (target_key or "new_entry")
        yaml_suggestion = f"""
# Add to app/data/agent_specializations/specializations.yaml under 'specializations:'
  {key}:
    specialization_key: {key}
    domain_key: {domain_key or 'DOMAIN'}
    workflow_step: {workflow_step or 'pipeline'}
    profile_name: {domain_key or 'Domain'} {workflow_step or 'pipeline'}
    summary: "Add description based on evidence: { (p.get('evidence_summary') or '')[:80]}"
    execution_focus: "focus here"
    expected_output_type: "handoff_summary"
    guardrails: []
    selection_keywords: []
"""
        return {
            "target_file": "app/data/agent_specializations/specializations.yaml",
            "action": "add_entry",
            "target_key": key,
            "yaml_suggestion": yaml_suggestion.strip(),
            "human_instruction": f"Добавить в specializations.yaml запись для domain={domain_key}, step={workflow_step}. Причина: {p.get('reason', '')[:120]}",
        }

    if ptype == "expand_specialization_profile" and target_layer == "specializations":
        spec_key = target_key or f"{domain_key}_{workflow_step}"
        rec = (p.get("recommended_change") or "").lower()
        ev = str(p.get("evidence_summary") or "")
        if "keyword" in rec or "selection" in rec:
            val = _extract_append_value(p, domain_key or "keyword")
            return {
                "target_file": "app/data/agent_specializations/specializations.yaml",
                "action": "append_specialization_keyword",
                "target_key": spec_key,
                "append_value": val,
                "human_instruction": f"Добавить selection_keyword '{val}' в {spec_key}. {p.get('reason', '')[:100]}",
            }
        if "guardrail" in rec or "guard" in rec:
            val = _extract_append_value(p, "review before production")
            return {
                "target_file": "app/data/agent_specializations/specializations.yaml",
                "action": "append_guardrail_note",
                "target_key": spec_key,
                "append_value": val,
                "human_instruction": f"Добавить guardrail в {spec_key}. {p.get('reason', '')[:100]}",
            }
        if "summary" in rec:
            val = (ev or p.get("reason", ""))[:200]
            return {
                "target_file": "app/data/agent_specializations/specializations.yaml",
                "action": "update_summary_minor",
                "target_key": spec_key,
                "append_value": val or "Updated from refinement",
                "human_instruction": f"Обновить summary в {spec_key}. {p.get('reason', '')[:100]}",
            }
        return {
            "target_file": "app/data/agent_specializations/specializations.yaml",
            "action": "append_specialization_keyword",
            "target_key": spec_key,
            "append_value": _extract_append_value(p, domain_key or "keyword"),
            "human_instruction": f"Расширить профиль {spec_key}. {p.get('reason', '')[:100]}",
        }

    if ptype == "adjust_routing_keywords" and target_layer == "domain_registry":
        dk = target_key or domain_key or "general"
        val = _extract_append_value(p, dk)
        return {
            "target_file": "app/data/domain_registry/domain_registry.yaml",
            "action": "append_routing_keyword",
            "target_key": dk,
            "append_value": val,
            "human_instruction": f"Добавить routing_keyword '{val}' в домен {dk}. {p.get('reason', '')[:100]}",
        }

    if ptype == "add_alias" and target_layer == "domain_registry":
        dk = target_key or domain_key or "general"
        val = _extract_append_value(p, dk)
        return {
            "target_file": "app/data/domain_registry/domain_registry.yaml",
            "action": "add_alias",
            "target_key": dk,
            "append_value": val,
            "human_instruction": f"Добавить alias '{val}' в домен {dk}. {p.get('reason', '')[:100]}",
        }

    if ptype == "review_domain_mapping":
        return {
            "target_file": None,
            "action": "manual_review",
            "target_key": target_key or p.get("project_key"),
            "human_instruction": f"Просмотреть причины override по задачам/проекту. Причина: {p.get('reason', '')[:120]}",
        }
    return {
        "target_file": None,
        "action": "manual_review",
        "target_key": target_key,
        "human_instruction": p.get("reason", "")[:200],
    }
