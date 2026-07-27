"""Tests for ADR-007 agent_cluster mapping."""

from app.orchestrator.agent_clusters import agent_cluster_for_domain, attach_agent_cluster
from app.orchestrator.triage import run_triage


def test_agent_cluster_for_known_domains():
    assert agent_cluster_for_domain("MEDIA_OPS") == "MEDIA"
    assert agent_cluster_for_domain("PRODUCT_DEV") == "STRATEGY"
    assert agent_cluster_for_domain("EVENTS") == "EVENTS"
    assert agent_cluster_for_domain("RUZA") == "KNOWLEDGE"
    assert agent_cluster_for_domain("nope") == "UNKNOWN"


def test_attach_agent_cluster():
    out = attach_agent_cluster({"domain": "MEDIA_OPS", "task_type": "content_pipeline"})
    assert out["agent_cluster"] == "MEDIA"


def test_run_triage_stamps_media_cluster():
    result = run_triage("#TASK короткий контент-анонс для канала MyWave")
    assert result.get("domain") == "MEDIA_OPS"
    assert result.get("task_type") == "content_pipeline"
    assert result.get("agent_cluster") == "MEDIA"


def test_content_pipeline_payload_has_deliverable(db_session, tmp_path, monkeypatch):
    from app.storage.repositories import TaskRepository
    from app.orchestrator import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setenv("ORCHESTRATION_ENGINE", "rule_based")

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="#TASK контент анонс клуба MyWave")
    triage_result = {
        "domain": "MEDIA_OPS",
        "task_type": "content_pipeline",
        "criticality": "HIGH",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PUBLISH",
        "agent_cluster": "MEDIA",
        "route": ["CONTENT", "PROMPT", "DATA", "ARCH"],
    }
    result = pipeline_module.run_pipeline(task.id, triage_result, repo)
    first = result["handoffs"][0]["payload"]
    assert first.get("agent_cluster") == "MEDIA"
    assert isinstance(first.get("deliverable"), dict)
    assert first["deliverable"].get("kind") == "message_draft"
    assert any("Привет" in str(x) for x in first["deliverable"].get("body_lines") or [])
