from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.knowledge_intake.models import (
    ClaimKind,
    Classification,
    ConfidenceAssessment,
    ExtractedClaim,
    KnowledgeSource,
    Material,
)
from app.knowledge_intake.workflow import KnowledgeIntakeCase
from app.shared.audit import log_audit


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _sentences(material: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", material.strip())]
    return [part for part in parts if len(part) >= 4][:12]


def create_knowledge_draft(
    repo,
    task_id: int,
    *,
    material: str,
    title: str,
    source_locator: str,
    category: str = "project",
) -> dict[str, Any]:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError("Миссия не найдена.")
    statements = _sentences(material)
    if not statements:
        raise ValueError("Материал не содержит извлекаемого знания.")

    source_id = f"source-{uuid4().hex[:10]}"
    case = KnowledgeIntakeCase.start(
        Material(material_id=f"material-{uuid4().hex[:10]}", content=material, origin=source_locator)
    )
    claims = tuple(
        ExtractedClaim(
            claim_id=f"claim-{index + 1}",
            statement=statement,
            kind=ClaimKind.FACT_CANDIDATE,
            source_ids=(source_id,),
        )
        for index, statement in enumerate(statements)
    )
    case = (
        case.record_extraction(claims)
        .record_classification(
            Classification(category=category, knowledge_type="owner_supplied_source", tags=("draft",))
        )
        .record_entities(())
        .record_relations(())
        .record_sources(
            (
                KnowledgeSource(
                    source_id=source_id,
                    locator=source_locator,
                    title=title,
                    source_type="owner_material",
                    excerpt=material[:500],
                ),
            )
        )
        .record_confidence(
            tuple(
                ConfidenceAssessment(
                    claim_id=claim.claim_id,
                    score=0.55,
                    rationale="Извлечено из указанного владельцем источника; требует Owner approval.",
                )
                for claim in claims
            )
        )
        .create_draft(title=title, summary=f"Извлечено утверждений: {len(claims)}")
        .submit_for_owner_approval()
    )
    draft = _json_safe(asdict(case.draft))
    business_action = dict(task.business_action_json or {})
    business_action["knowledge_intake"] = draft
    repo.update_task(task_id, business_action_json=business_action)
    log_audit(
        repo,
        "knowledge_draft_created",
        task_id=task_id,
        payload={"draft_id": draft["draft_id"], "claims": len(claims), "status_after": draft["status"]},
    )
    return draft


def approve_knowledge_draft(repo, task_id: int, *, owner_id: str = "owner", note: str = "") -> dict[str, Any]:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError("Миссия не найдена.")
    business_action = dict(task.business_action_json or {})
    draft = business_action.get("knowledge_intake")
    if not isinstance(draft, dict) or draft.get("status") != "pending_owner_approval":
        raise ValueError("Нет черновика, ожидающего подтверждения владельца.")
    if not task.project_id:
        raise ValueError("Миссия не связана с проектом; публикация знания заблокирована.")

    published_at = datetime.utcnow().isoformat()
    canonical = {
        "record_id": uuid4().hex,
        "draft_id": draft.get("draft_id"),
        "title": draft.get("title"),
        "summary": draft.get("summary"),
        "claims": draft.get("claims") or [],
        "classification": draft.get("classification") or {},
        "sources": draft.get("sources") or [],
        "confidence": draft.get("confidence") or [],
        "approved_by": owner_id,
        "approval_note": note,
        "published_at": published_at,
    }
    entry = repo.add_memory_entry(
        project_id=task.project_id,
        task_id=task_id,
        scope="knowledge_base",
        content=json.dumps(canonical, ensure_ascii=False, indent=2),
        source_ref=str((draft.get("material") or {}).get("origin") or f"task:{task_id}"),
    )
    draft = {**draft, "status": "published", "approved_by": owner_id, "published_at": published_at, "memory_entry_id": entry.id}
    business_action["knowledge_intake"] = draft
    repo.update_task(task_id, business_action_json=business_action)
    log_audit(
        repo,
        "knowledge_published",
        task_id=task_id,
        payload={"draft_id": draft.get("draft_id"), "memory_entry_id": entry.id, "status_after": "published"},
    )
    return draft


def reject_knowledge_draft(repo, task_id: int, *, reason: str) -> dict[str, Any]:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError("Миссия не найдена.")
    business_action = dict(task.business_action_json or {})
    draft = business_action.get("knowledge_intake")
    if not isinstance(draft, dict) or draft.get("status") != "pending_owner_approval":
        raise ValueError("Нет черновика, ожидающего решения владельца.")
    draft = {**draft, "status": "rejected", "rejection_reason": reason.strip() or "Отклонено владельцем."}
    business_action["knowledge_intake"] = draft
    repo.update_task(task_id, business_action_json=business_action)
    log_audit(
        repo,
        "knowledge_rejected",
        task_id=task_id,
        payload={"draft_id": draft.get("draft_id"), "status_after": "rejected"},
    )
    return draft
