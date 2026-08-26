from dataclasses import FrozenInstanceError

import pytest

from app.knowledge_intake import (
    CanonicalKnowledgeRecord,
    CanonicalizationError,
    ClaimKind,
    Classification,
    ConfidenceAssessment,
    DomainValidationError,
    DraftStatus,
    Entity,
    ExtractedClaim,
    IntakeStage,
    InvalidStageTransition,
    KnowledgeIntakeCase,
    KnowledgeSource,
    Material,
    Relation,
)


def _material() -> Material:
    return Material(
        material_id="material-1",
        content="SnowPolia uses a seasonal economy model. Retention may improve.",
        origin="owner-upload:strategy.md",
    )


def _claims() -> tuple[ExtractedClaim, ...]:
    return (
        ExtractedClaim(
            claim_id="claim-fact",
            statement="SnowPolia uses a seasonal economy model.",
            kind=ClaimKind.FACT_CANDIDATE,
            source_ids=("source-1",),
        ),
        ExtractedClaim(
            claim_id="claim-assumption",
            statement="The model may improve retention.",
            kind=ClaimKind.ASSUMPTION,
            source_ids=("source-1",),
        ),
    )


def _case_through_relations(
    claims: tuple[ExtractedClaim, ...] | None = None,
) -> KnowledgeIntakeCase:
    return (
        KnowledgeIntakeCase.start(_material(), case_id="case-1")
        .record_extraction(claims or _claims())
        .record_classification(
            Classification(
                category="product",
                knowledge_type="project_fact",
                tags=("snowpolia", "economy"),
            )
        )
        .record_entities(
            (
                Entity(entity_id="snowpolia", name="SnowPolia", entity_type="project"),
                Entity(entity_id="economy", name="Seasonal economy", entity_type="model"),
            )
        )
        .record_relations(
            (
                Relation(
                    relation_id="relation-1",
                    subject_entity_id="snowpolia",
                    predicate="uses",
                    object_entity_id="economy",
                ),
            )
        )
    )


def _case_through_confidence() -> KnowledgeIntakeCase:
    return _case_through_relations().record_sources(
        (
            KnowledgeSource(
                source_id="source-1",
                locator="uploads/strategy.md",
                title="SnowPolia strategy",
            ),
        )
    ).record_confidence(
        (
            ConfidenceAssessment(
                claim_id="claim-fact",
                score=0.92,
                rationale="The statement is explicit in the owner-provided source.",
            ),
            ConfidenceAssessment(
                claim_id="claim-assumption",
                score=0.35,
                rationale="The expected effect is not supported by outcome data.",
            ),
        )
    )


def test_full_draft_first_lifecycle_publishes_only_after_owner_approval():
    case = _case_through_confidence()
    assert case.stage is IntakeStage.CONFIDENCE

    case = case.create_draft(
        draft_id="draft-1",
        title="SnowPolia economy knowledge",
        summary="A sourced project fact and one explicit assumption.",
    )
    assert case.stage is IntakeStage.DRAFT
    assert case.draft is not None
    assert case.draft.status is DraftStatus.DRAFT
    assert case.canonical_record is None

    case = case.submit_for_owner_approval()
    assert case.stage is IntakeStage.PENDING_OWNER_APPROVAL
    assert case.draft is not None
    assert case.draft.status is DraftStatus.PENDING_OWNER_APPROVAL

    case = case.approve(owner_id="owner-1", note="Sources checked")
    assert case.stage is IntakeStage.APPROVED
    assert case.draft is not None
    assert case.draft.status is DraftStatus.APPROVED

    case = case.publish(record_id="knowledge-1")
    record = case.canonical_record
    assert case.stage is IntakeStage.PUBLISHED
    assert record is not None
    assert record.record_id == "knowledge-1"
    assert record.draft_id == "draft-1"
    assert record.approved_by == "owner-1"


def test_assumption_is_never_promoted_to_canonical_fact():
    record = (
        _case_through_confidence()
        .create_draft(title="Knowledge", summary="Fact and assumption")
        .submit_for_owner_approval()
        .approve(owner_id="owner-1")
        .publish()
        .canonical_record
    )

    assert record is not None
    assert [fact.claim_id for fact in record.facts] == ["claim-fact"]
    assert [assumption.claim_id for assumption in record.assumptions] == ["claim-assumption"]
    assert all(fact.claim_id != "claim-assumption" for fact in record.facts)


def test_workflow_rejects_skipped_or_repeated_stages():
    case = KnowledgeIntakeCase.start(_material())

    with pytest.raises(InvalidStageTransition, match="expected stage extraction"):
        case.record_classification(Classification(category="product", knowledge_type="fact"))

    extracted = case.record_extraction(_claims())
    with pytest.raises(InvalidStageTransition, match="current stage is extraction"):
        extracted.record_extraction(_claims())


def test_relation_must_reference_known_entities():
    case = (
        KnowledgeIntakeCase.start(_material())
        .record_extraction(_claims())
        .record_classification(Classification(category="product", knowledge_type="fact"))
        .record_entities((Entity("snowpolia", "SnowPolia", "project"),))
    )

    with pytest.raises(DomainValidationError, match="unknown entities"):
        case.record_relations(
            (Relation("relation-1", "snowpolia", "uses", "missing-model"),)
        )


def test_factual_candidate_requires_a_declared_source():
    claims = (
        ExtractedClaim(
            claim_id="claim-fact",
            statement="A factual candidate without evidence.",
            kind=ClaimKind.FACT_CANDIDATE,
        ),
    )
    case = _case_through_relations(claims)

    with pytest.raises(DomainValidationError, match="must reference at least one source"):
        case.record_sources(
            (KnowledgeSource("source-1", "uploads/source.md", "Source"),)
        )


def test_claim_cannot_reference_an_unknown_source():
    case = _case_through_relations()

    with pytest.raises(DomainValidationError, match="unknown sources"):
        case.record_sources(
            (KnowledgeSource("different-source", "uploads/source.md", "Source"),)
        )


def test_factual_candidate_requires_confidence_assessment():
    case = _case_through_relations().record_sources(
        (KnowledgeSource("source-1", "uploads/strategy.md", "Strategy"),)
    )

    with pytest.raises(DomainValidationError, match="missing confidence assessments"):
        case.record_confidence(
            (
                ConfidenceAssessment(
                    claim_id="claim-assumption",
                    score=0.3,
                    rationale="This is explicitly uncertain.",
                ),
            )
        )


def test_assumptions_alone_cannot_create_canonical_knowledge():
    claims = (
        ExtractedClaim(
            claim_id="claim-assumption",
            statement="The project may grow next month.",
            kind=ClaimKind.ASSUMPTION,
        ),
    )
    case = _case_through_relations(claims)

    with pytest.raises(DomainValidationError, match="at least one factual candidate"):
        case.record_sources(())


def test_pending_or_rejected_draft_cannot_be_published():
    pending = (
        _case_through_confidence()
        .create_draft(title="Knowledge", summary="Awaiting owner decision")
        .submit_for_owner_approval()
    )
    with pytest.raises(InvalidStageTransition, match="expected stage approved"):
        pending.publish()

    rejected = pending.reject(reason="Source needs verification")
    assert rejected.stage is IntakeStage.REJECTED
    assert rejected.draft is not None
    assert rejected.draft.status is DraftStatus.REJECTED
    with pytest.raises(InvalidStageTransition, match="current stage is rejected"):
        rejected.publish()


def test_canonical_record_cannot_be_constructed_directly():
    with pytest.raises(CanonicalizationError, match="approved draft"):
        CanonicalKnowledgeRecord()


def test_material_and_pipeline_snapshots_are_immutable():
    material = _material()
    case = KnowledgeIntakeCase.start(material).record_extraction(_claims())

    with pytest.raises(FrozenInstanceError):
        material.content = "Changed"  # type: ignore[misc]

    assert case.material.content == _material().content
    assert isinstance(case.claims, tuple)
