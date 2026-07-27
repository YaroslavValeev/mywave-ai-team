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
    result = run_triage("#TASK контент и новости для Telegram канала")
    assert result.get("domain") == "MEDIA_OPS"
    assert result.get("agent_cluster") == "MEDIA"
