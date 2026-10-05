def test_triage_uses_crewai_override_when_enabled(monkeypatch):
    """CrewAI triage может переопределить rule-based результат при включенном флаге."""
    from app.orchestrator import triage as triage_module

    monkeypatch.setattr(
        triage_module,
        "get_orchestration_config",
        lambda: {"engine": "crewai", "allow_fallback": True},
    )
    monkeypatch.setattr(
        triage_module,
        "run_crewai_triage",
        lambda text: {
            "domain": "MEDIA_OPS",
            "task_type": "publish_major",
            "criticality": "CRITICAL",
            "plan_or_execute": "EXECUTE",
            "execute_gate": "OWNER_APPROVAL_ALWAYS",
        },
    )

    result = triage_module.run_triage("# TASK написать большой пост")

    assert result["domain"] == "MEDIA_OPS"
    assert result["task_type"] == "publish_major"
    assert result["plan_or_execute"] == "EXECUTE"


def test_invalid_crewai_route_uses_canonical_fallback_with_provenance(monkeypatch):
    from app.orchestrator import triage as triage_module

    monkeypatch.setattr(triage_module, "get_orchestration_config", lambda: {"engine": "auto", "allow_fallback": True})
    monkeypatch.setattr(
        triage_module,
        "run_crewai_triage",
        lambda text: {"domain": "owner", "task_type": "triage", "execute_gate": "AI-TEAM"},
    )

    result = triage_module.run_triage("# TASK implement a site feature")

    assert result["domain"] == "PRODUCT_DEV"
    assert result["task_type"] == "feature_delivery"
    assert result["agent_cluster"] != "UNKNOWN"
    assert result["triage_source"] == "fallback"
    assert result["triage_validation_status"] == "fallback"
    assert result["triage_validation_errors"]


def test_invalid_crewai_route_fails_in_strict_mode(monkeypatch):
    from app.orchestrator import triage as triage_module

    monkeypatch.setattr(triage_module, "get_orchestration_config", lambda: {"engine": "auto", "allow_fallback": False})
    monkeypatch.setattr(
        triage_module,
        "run_crewai_triage",
        lambda text: {"domain": "owner", "task_type": "triage", "execute_gate": "AI-TEAM"},
    )

    import pytest

    with pytest.raises(RuntimeError, match="semantic validation"):
        triage_module.run_triage("# TASK strict site feature")


def test_pipeline_merge_preserves_llm_provenance():
    from app.orchestrator.pipeline import _merge_payloads

    fallback = {"summary": ["baseline"], "provenance": {"generation_source": "deterministic"}}
    llm = {"summary": ["llm"], "next_action": "ARCH", "provenance": {"generation_source": "llm", "validation_status": "valid"}}
    merged = _merge_payloads(fallback, llm, "ARCH")
    assert merged["provenance"]["generation_source"] == "llm"


def test_pipeline_uses_crewai_payloads_with_fallback(db_session, tmp_path, monkeypatch):
    """CrewAI payload используется, а пропущенные поля добираются из fallback."""
    from app.storage.repositories import TaskRepository
    from app.orchestrator import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline_module,
        "get_orchestration_config",
        lambda: {"engine": "crewai", "allow_fallback": True},
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_crewai_pipeline",
        lambda task_id, steps, context: [
            {
                "summary": ["CrewAI custom summary"],
                "artifacts": ["custom::artifact"],
                "decisions": ["Custom decision"],
                "assumptions": [],
                "risks": [],
                "open_questions": [],
                "next_action": steps[1],
            }
        ]
        + [None] * (len(steps) - 1),
    )

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK реализовать feature delivery")
    triage_result = {
        "domain": "PRODUCT_DEV",
        "task_type": "feature_delivery",
        "criticality": "MEDIUM",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PROD",
    }

    result = pipeline_module.run_pipeline(task.id, triage_result, repo)

    first_payload = result["handoffs"][0]["payload"]
    second_payload = result["handoffs"][1]["payload"]
    assert first_payload["summary"] == ["CrewAI custom summary"]
    assert first_payload["artifacts"] == ["custom::artifact"]
    assert second_payload["summary"]
