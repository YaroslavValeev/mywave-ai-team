"""Public contracts for the isolated Knowledge Intake domain."""

from app.knowledge_intake.errors import (
    CanonicalizationError,
    DomainValidationError,
    InvalidStageTransition,
    KnowledgeIntakeError,
)
from app.knowledge_intake.models import (
    CanonicalFact,
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
    LabeledAssumption,
    Material,
    OwnerApproval,
    Relation,
)
from app.knowledge_intake.workflow import KnowledgeIntakeCase
from app.knowledge_intake.service import (
    approve_knowledge_draft,
    create_knowledge_draft,
    reject_knowledge_draft,
)

__all__ = [
    "CanonicalFact",
    "CanonicalKnowledgeRecord",
    "CanonicalizationError",
    "ClaimKind",
    "Classification",
    "ConfidenceAssessment",
    "DomainValidationError",
    "DraftStatus",
    "Entity",
    "ExtractedClaim",
    "IntakeStage",
    "InvalidStageTransition",
    "KnowledgeDraft",
    "KnowledgeIntakeCase",
    "KnowledgeIntakeError",
    "KnowledgeSource",
    "LabeledAssumption",
    "Material",
    "OwnerApproval",
    "Relation",
    "approve_knowledge_draft",
    "create_knowledge_draft",
    "reject_knowledge_draft",
]
