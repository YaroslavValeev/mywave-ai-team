"""Ordered aggregate for the draft-first knowledge intake lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from app.knowledge_intake.errors import DomainValidationError, InvalidStageTransition
from app.knowledge_intake.models import (
    CanonicalKnowledgeRecord,
    ClaimKind,
    Classification,
    ConfidenceAssessment,
    DraftStatus,
    Entity,
    ExtractedClaim,
    IntakeStage,
    KnowledgeDraft,
    KnowledgeSource,
    Material,
    OwnerApproval,
    Relation,
    utc_now,
)


def _unique_by_id(items: tuple[object, ...], attribute: str, label: str) -> None:
    values = [getattr(item, attribute) for item in items]
    if len(values) != len(set(values)):
        raise DomainValidationError(f"{label} ids must be unique")


@dataclass(frozen=True)
class _CaseState:
    case_id: str
    stage: IntakeStage
    material: Material
    claims: tuple[ExtractedClaim, ...] = ()
    classification: Classification | None = None
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    sources: tuple[KnowledgeSource, ...] = ()
    confidence: tuple[ConfidenceAssessment, ...] = ()
    draft: KnowledgeDraft | None = None
    canonical_record: CanonicalKnowledgeRecord | None = None


class KnowledgeIntakeCase:
    """Immutable aggregate that permits only the prescribed lifecycle order."""

    __slots__ = ("_state",)

    def __init__(self) -> None:
        raise TypeError("use KnowledgeIntakeCase.start()")

    @classmethod
    def _from_state(cls, state: _CaseState) -> KnowledgeIntakeCase:
        instance = object.__new__(cls)
        instance._state = state
        return instance

    @classmethod
    def start(cls, material: Material, *, case_id: str | None = None) -> KnowledgeIntakeCase:
        resolved_case_id = (case_id or uuid4().hex).strip()
        if not resolved_case_id:
            raise DomainValidationError("case_id must not be empty")
        return cls._from_state(
            _CaseState(case_id=resolved_case_id, stage=IntakeStage.MATERIAL, material=material)
        )

    @property
    def case_id(self) -> str:
        return self._state.case_id

    @property
    def stage(self) -> IntakeStage:
        return self._state.stage

    @property
    def material(self) -> Material:
        return self._state.material

    @property
    def claims(self) -> tuple[ExtractedClaim, ...]:
        return self._state.claims

    @property
    def draft(self) -> KnowledgeDraft | None:
        return self._state.draft

    @property
    def canonical_record(self) -> CanonicalKnowledgeRecord | None:
        return self._state.canonical_record

    def _require_stage(self, expected: IntakeStage) -> None:
        if self.stage is not expected:
            raise InvalidStageTransition(
                f"expected stage {expected.value}, current stage is {self.stage.value}"
            )

    def _advance(self, stage: IntakeStage, **changes: object) -> KnowledgeIntakeCase:
        return self._from_state(replace(self._state, stage=stage, **changes))

    def record_extraction(self, claims: tuple[ExtractedClaim, ...]) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.MATERIAL)
        claims = tuple(claims)
        if not claims:
            raise DomainValidationError("extraction must contain at least one claim")
        _unique_by_id(claims, "claim_id", "claim")
        return self._advance(IntakeStage.EXTRACTION, claims=claims)

    def record_classification(self, classification: Classification) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.EXTRACTION)
        return self._advance(IntakeStage.CLASSIFICATION, classification=classification)

    def record_entities(self, entities: tuple[Entity, ...]) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.CLASSIFICATION)
        entities = tuple(entities)
        _unique_by_id(entities, "entity_id", "entity")
        return self._advance(IntakeStage.ENTITIES, entities=entities)

    def record_relations(self, relations: tuple[Relation, ...]) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.ENTITIES)
        relations = tuple(relations)
        _unique_by_id(relations, "relation_id", "relation")
        entity_ids = {entity.entity_id for entity in self._state.entities}
        for relation in relations:
            referenced_ids = {relation.subject_entity_id, relation.object_entity_id}
            missing = referenced_ids - entity_ids
            if missing:
                raise DomainValidationError(
                    f"relation {relation.relation_id} references unknown entities: {sorted(missing)}"
                )
        return self._advance(IntakeStage.RELATIONS, relations=relations)

    def record_sources(self, sources: tuple[KnowledgeSource, ...]) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.RELATIONS)
        sources = tuple(sources)
        _unique_by_id(sources, "source_id", "source")
        source_ids = {source.source_id for source in sources}
        factual_claims = [claim for claim in self.claims if claim.kind is ClaimKind.FACT_CANDIDATE]
        if not factual_claims:
            raise DomainValidationError("a draft must contain at least one factual candidate")
        for claim in self.claims:
            missing = set(claim.source_ids) - source_ids
            if missing:
                raise DomainValidationError(
                    f"claim {claim.claim_id} references unknown sources: {sorted(missing)}"
                )
            if claim.kind is ClaimKind.FACT_CANDIDATE and not claim.source_ids:
                raise DomainValidationError(
                    f"factual candidate {claim.claim_id} must reference at least one source"
                )
        return self._advance(IntakeStage.SOURCE, sources=sources)

    def record_confidence(
        self,
        assessments: tuple[ConfidenceAssessment, ...],
    ) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.SOURCE)
        assessments = tuple(assessments)
        _unique_by_id(assessments, "claim_id", "confidence assessment")
        claim_ids = {claim.claim_id for claim in self.claims}
        assessment_ids = {assessment.claim_id for assessment in assessments}
        unknown = assessment_ids - claim_ids
        if unknown:
            raise DomainValidationError(f"confidence references unknown claims: {sorted(unknown)}")
        required = {
            claim.claim_id for claim in self.claims if claim.kind is ClaimKind.FACT_CANDIDATE
        }
        missing = required - assessment_ids
        if missing:
            raise DomainValidationError(
                f"factual candidates are missing confidence assessments: {sorted(missing)}"
            )
        return self._advance(IntakeStage.CONFIDENCE, confidence=assessments)

    def create_draft(
        self,
        *,
        title: str,
        summary: str,
        draft_id: str | None = None,
        created_at: datetime | None = None,
    ) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.CONFIDENCE)
        if self._state.classification is None:
            raise DomainValidationError("classification is missing")
        draft = KnowledgeDraft(
            draft_id=draft_id or uuid4().hex,
            case_id=self.case_id,
            title=title,
            summary=summary,
            material=self.material,
            claims=self.claims,
            classification=self._state.classification,
            entities=self._state.entities,
            relations=self._state.relations,
            sources=self._state.sources,
            confidence=self._state.confidence,
            created_at=created_at or utc_now(),
        )
        return self._advance(IntakeStage.DRAFT, draft=draft)

    def submit_for_owner_approval(self) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.DRAFT)
        if self.draft is None:
            raise DomainValidationError("draft is missing")
        draft = replace(self.draft, status=DraftStatus.PENDING_OWNER_APPROVAL)
        return self._advance(IntakeStage.PENDING_OWNER_APPROVAL, draft=draft)

    def approve(
        self,
        *,
        owner_id: str,
        note: str = "",
        approved_at: datetime | None = None,
    ) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.PENDING_OWNER_APPROVAL)
        if self.draft is None:
            raise DomainValidationError("draft is missing")
        approval = OwnerApproval(
            owner_id=owner_id,
            note=note,
            approved_at=approved_at or utc_now(),
        )
        draft = replace(self.draft, status=DraftStatus.APPROVED, approval=approval)
        return self._advance(IntakeStage.APPROVED, draft=draft)

    def reject(self, *, reason: str) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.PENDING_OWNER_APPROVAL)
        if self.draft is None:
            raise DomainValidationError("draft is missing")
        reason = reason.strip()
        if not reason:
            raise DomainValidationError("rejection reason must not be empty")
        draft = replace(self.draft, status=DraftStatus.REJECTED, rejection_reason=reason)
        return self._advance(IntakeStage.REJECTED, draft=draft)

    def publish(
        self,
        *,
        record_id: str | None = None,
        published_at: datetime | None = None,
    ) -> KnowledgeIntakeCase:
        self._require_stage(IntakeStage.APPROVED)
        if self.draft is None:
            raise DomainValidationError("draft is missing")
        record = CanonicalKnowledgeRecord._from_approved_draft(
            self.draft,
            record_id=record_id or uuid4().hex,
            published_at=published_at or utc_now(),
        )
        return self._advance(IntakeStage.PUBLISHED, canonical_record=record)
