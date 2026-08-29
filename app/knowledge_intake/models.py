"""Immutable domain models for draft-first knowledge intake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.knowledge_intake.errors import CanonicalizationError, DomainValidationError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise DomainValidationError(f"{field_name} must not be empty")
    return cleaned


class IntakeStage(str, Enum):
    MATERIAL = "material"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    ENTITIES = "entities"
    RELATIONS = "relations"
    SOURCE = "source"
    CONFIDENCE = "confidence"
    DRAFT = "draft"
    PENDING_OWNER_APPROVAL = "pending_owner_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class ClaimKind(str, Enum):
    FACT_CANDIDATE = "fact_candidate"
    ASSUMPTION = "assumption"


class DraftStatus(str, Enum):
    DRAFT = "draft"
    PENDING_OWNER_APPROVAL = "pending_owner_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Material:
    material_id: str
    content: str
    origin: str
    received_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "material_id", _required(self.material_id, "material_id"))
        object.__setattr__(self, "content", _required(self.content, "content"))
        object.__setattr__(self, "origin", _required(self.origin, "origin"))
        if self.received_at.tzinfo is None:
            raise DomainValidationError("received_at must be timezone-aware")


@dataclass(frozen=True)
class ExtractedClaim:
    claim_id: str
    statement: str
    kind: ClaimKind
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _required(self.claim_id, "claim_id"))
        object.__setattr__(self, "statement", _required(self.statement, "statement"))
        if not isinstance(self.kind, ClaimKind):
            raise DomainValidationError("kind must be a ClaimKind")
        source_ids = tuple(_required(item, "source_id") for item in self.source_ids)
        if len(source_ids) != len(set(source_ids)):
            raise DomainValidationError(f"claim {self.claim_id} contains duplicate source_ids")
        object.__setattr__(self, "source_ids", source_ids)


@dataclass(frozen=True)
class Classification:
    category: str
    knowledge_type: str
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", _required(self.category, "category"))
        object.__setattr__(self, "knowledge_type", _required(self.knowledge_type, "knowledge_type"))
        tags = tuple(_required(tag, "tag") for tag in self.tags)
        if len(tags) != len(set(tags)):
            raise DomainValidationError("classification contains duplicate tags")
        object.__setattr__(self, "tags", tags)


@dataclass(frozen=True)
class Entity:
    entity_id: str
    name: str
    entity_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_id", _required(self.entity_id, "entity_id"))
        object.__setattr__(self, "name", _required(self.name, "name"))
        object.__setattr__(self, "entity_type", _required(self.entity_type, "entity_type"))


@dataclass(frozen=True)
class Relation:
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _required(self.relation_id, "relation_id"))
        object.__setattr__(self, "subject_entity_id", _required(self.subject_entity_id, "subject_entity_id"))
        object.__setattr__(self, "predicate", _required(self.predicate, "predicate"))
        object.__setattr__(self, "object_entity_id", _required(self.object_entity_id, "object_entity_id"))


@dataclass(frozen=True)
class KnowledgeSource:
    source_id: str
    locator: str
    title: str
    source_type: str = "document"
    excerpt: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _required(self.source_id, "source_id"))
        object.__setattr__(self, "locator", _required(self.locator, "locator"))
        object.__setattr__(self, "title", _required(self.title, "title"))
        object.__setattr__(self, "source_type", _required(self.source_type, "source_type"))


@dataclass(frozen=True)
class ConfidenceAssessment:
    claim_id: str
    score: float
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _required(self.claim_id, "claim_id"))
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise DomainValidationError("confidence score must be numeric")
        if not 0.0 <= float(self.score) <= 1.0:
            raise DomainValidationError("confidence score must be between 0 and 1")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "rationale", _required(self.rationale, "rationale"))


@dataclass(frozen=True)
class OwnerApproval:
    owner_id: str
    note: str
    approved_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _required(self.owner_id, "owner_id"))
        if self.approved_at.tzinfo is None:
            raise DomainValidationError("approved_at must be timezone-aware")


@dataclass(frozen=True)
class KnowledgeDraft:
    draft_id: str
    case_id: str
    title: str
    summary: str
    material: Material
    claims: tuple[ExtractedClaim, ...]
    classification: Classification
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    sources: tuple[KnowledgeSource, ...]
    confidence: tuple[ConfidenceAssessment, ...]
    status: DraftStatus = DraftStatus.DRAFT
    created_at: datetime = field(default_factory=utc_now)
    approval: OwnerApproval | None = None
    rejection_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "draft_id", _required(self.draft_id, "draft_id"))
        object.__setattr__(self, "case_id", _required(self.case_id, "case_id"))
        object.__setattr__(self, "title", _required(self.title, "title"))
        object.__setattr__(self, "summary", _required(self.summary, "summary"))
        if not isinstance(self.status, DraftStatus):
            raise DomainValidationError("status must be a DraftStatus")
        if self.created_at.tzinfo is None:
            raise DomainValidationError("created_at must be timezone-aware")
        if self.status is DraftStatus.APPROVED and self.approval is None:
            raise DomainValidationError("approved draft must contain owner approval")
        if self.status is not DraftStatus.APPROVED and self.approval is not None:
            raise DomainValidationError("only an approved draft may contain owner approval")
        if self.status is DraftStatus.REJECTED and not self.rejection_reason.strip():
            raise DomainValidationError("rejected draft must contain a reason")
        if self.status is not DraftStatus.REJECTED and self.rejection_reason:
            raise DomainValidationError("only a rejected draft may contain a rejection reason")


@dataclass(frozen=True)
class CanonicalFact:
    claim_id: str
    statement: str
    source_ids: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class LabeledAssumption:
    claim_id: str
    statement: str
    source_ids: tuple[str, ...]


_CANONICAL_FACTORY_TOKEN = object()


@dataclass(frozen=True, init=False)
class CanonicalKnowledgeRecord:
    record_id: str
    draft_id: str
    title: str
    summary: str
    facts: tuple[CanonicalFact, ...]
    assumptions: tuple[LabeledAssumption, ...]
    classification: Classification
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    sources: tuple[KnowledgeSource, ...]
    approved_by: str
    approved_at: datetime
    published_at: datetime

    def __init__(
        self,
        *,
        record_id: str = "",
        draft_id: str = "",
        title: str = "",
        summary: str = "",
        facts: tuple[CanonicalFact, ...] = (),
        assumptions: tuple[LabeledAssumption, ...] = (),
        classification: Classification | None = None,
        entities: tuple[Entity, ...] = (),
        relations: tuple[Relation, ...] = (),
        sources: tuple[KnowledgeSource, ...] = (),
        approved_by: str = "",
        approved_at: datetime | None = None,
        published_at: datetime | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _CANONICAL_FACTORY_TOKEN:
            raise CanonicalizationError("canonical records can only be created from an approved draft")
        if classification is None or approved_at is None or published_at is None:
            raise CanonicalizationError("approved draft data is incomplete")
        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "draft_id", draft_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "assumptions", assumptions)
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "entities", entities)
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "approved_by", approved_by)
        object.__setattr__(self, "approved_at", approved_at)
        object.__setattr__(self, "published_at", published_at)

    @classmethod
    def _from_approved_draft(
        cls,
        draft: KnowledgeDraft,
        *,
        record_id: str,
        published_at: datetime,
    ) -> CanonicalKnowledgeRecord:
        if draft.status is not DraftStatus.APPROVED or draft.approval is None:
            raise CanonicalizationError("only an owner-approved draft can become canonical")

        confidence_by_claim = {item.claim_id: item.score for item in draft.confidence}
        facts = tuple(
            CanonicalFact(
                claim_id=claim.claim_id,
                statement=claim.statement,
                source_ids=claim.source_ids,
                confidence=confidence_by_claim[claim.claim_id],
            )
            for claim in draft.claims
            if claim.kind is ClaimKind.FACT_CANDIDATE
        )
        assumptions = tuple(
            LabeledAssumption(
                claim_id=claim.claim_id,
                statement=claim.statement,
                source_ids=claim.source_ids,
            )
            for claim in draft.claims
            if claim.kind is ClaimKind.ASSUMPTION
        )
        return cls(
            record_id=record_id,
            draft_id=draft.draft_id,
            title=draft.title,
            summary=draft.summary,
            facts=facts,
            assumptions=assumptions,
            classification=draft.classification,
            entities=draft.entities,
            relations=draft.relations,
            sources=draft.sources,
            approved_by=draft.approval.owner_id,
            approved_at=draft.approval.approved_at,
            published_at=published_at,
            _factory_token=_CANONICAL_FACTORY_TOKEN,
        )
