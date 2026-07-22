from app.intake import NormalizeIntakeRequest, normalize_intake


def test_business_intent_revenue_classification():
    resp = normalize_intake(
        NormalizeIntakeRequest(
            text="Подготовить стратегию запуска WakeSafari и оффер для спонсоров",
            source="pytest",
        )
    )
    assert resp.business_intent is True
    assert resp.business_action is not None
    assert resp.business_action.action_type in {"revenue", "ops"}


def test_wakesafari_strategy_gm_business_workflow():
    """Сценарий: стратегия запуска WakeSafari → шаблон business + подсказки GM."""
    resp = normalize_intake(
        NormalizeIntakeRequest(
            text="Подготовить стратегию запуска WakeSafari и оффер для спонсоров",
            source="pytest",
        )
    )
    assert resp.gm_decision is not None
    assert resp.gm_decision.workflow_template == "business"
    assert "WakeSafari" in (resp.gm_decision.business_value_hint or "")
    assert resp.gm_decision.next_business_step


def test_business_metrics_endpoint(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK revenue flow")
    repo.update_task(
        t.id,
        status="DONE",
        business_type="revenue",
        impact_level="high",
        impact_score=0.9,
        business_action_json={"action_type": "revenue", "expected_outcome": "sponsor deal"},
    )

    r = client.get("/api/business/metrics", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "project_metrics" in data
    assert data["project_metrics"]["business_effect_tasks"] >= 1
    assert "system_funnel" in data
    assert "execution_feedback" in data
    assert {"actions_started", "actions_completed", "useful_actions", "useless_actions"}.issubset(data["execution_feedback"].keys())
    assert "pack_learning" in data
    assert isinstance(data["pack_learning"], dict)
    assert "revenue_metrics" in data
    rm = data["revenue_metrics"]
    assert {"total_leads", "total_sales", "conversion_rate", "revenue_total", "top_pack_types", "top_actions", "funnel"}.issubset(rm.keys())
    assert "growth_insight" in data
    gi = data["growth_insight"]
    assert {"top_actions", "top_packs", "weak_packs", "recommendations", "pack_priority"}.issubset(gi.keys())
    assert "metrics_7d" in gi and "metrics_30d" in gi and "pack_dynamics" in gi


def test_business_growth_insight_endpoint(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    repo.create_task(owner_text="#TASK growth")
    r = client.get("/api/business/growth/insight", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert {"top_packs_7d", "top_packs_30d", "declining_packs", "emerging_packs", "recommendations"}.issubset(data.keys())


def test_system_data_health_endpoint(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK data-health")
    repo.update_task(
        t.id,
        business_action_json={
            "action_instance": {
                "action_type": "offer_pack",
                "status": "done",
                "created_at": "2026-01-01T10:00:00Z",
                "result_summary": "Есть результат",
            },
            "leads": [{"source_pack_type": "offer_pack"}],
            "deals": [{"status": "won", "amount": "1000", "source_pack_type": "offer_pack"}],
        },
    )
    r = client.get("/api/system/data_health", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert {
        "actions_with_timestamp_pct",
        "actions_with_result_pct",
        "leads_with_source_pct",
        "deals_with_amount_pct",
        "counts",
    }.issubset(data.keys())
    assert "owner_protocol" in data
    op = data["owner_protocol"]
    assert "day_status" in op and "checklist" in op
    assert op["day_status"].get("code") in {"OK", "WARNING", "STOP"}

