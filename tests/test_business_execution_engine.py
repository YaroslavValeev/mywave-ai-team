from app.business_execution.execution_engine import apply_action_feedback, build_execution_pack_from_gm, ensure_action_instance_blob
from app.business_execution.learning_hooks import build_pack_learning_hints
from app.business_execution.growth_engine import build_growth_insight, compute_pack_performance_with_revenue, growth_override_allowed
from app.business_execution.learning_hooks import apply_learning_to_pack_builder
from app.business_execution.pack_builder import build_pack
from app.business_execution.schemas import ExecutionContext
from app.intake import NormalizeIntakeRequest, normalize_intake


def test_execution_pack_offer_from_next_step():
    pack = build_execution_pack_from_gm(
        next_business_step="Подготовить оффер WakeSafari для партнёров",
        business_value_hint="Рост первых продаж",
        business_type="revenue",
        business_unit="wakesafari",
        expected_outcome="первые заявки",
    )
    assert pack is not None
    assert pack.pack_type == "offer_pack"
    assert pack.action_title


def test_execution_pack_launch_plan_from_step():
    pack = build_execution_pack_from_gm(
        next_business_step="Собрать план запуска проекта",
        workflow_template="business",
        expected_outcome="готовность к запуску",
    )
    assert pack is not None
    assert pack.pack_type == "launch_plan_pack"


def test_gm_response_contains_execution_pack():
    resp = normalize_intake(
        NormalizeIntakeRequest(
            text="Подготовить стратегию запуска WakeSafari и оффер для спонсоров",
            source="pytest",
        )
    )
    assert resp.gm_decision is not None
    assert resp.gm_decision.execution_pack is not None
    assert resp.gm_decision.execution_pack.action_title


def test_pack_builder_applies_learning_fallback_for_weak_pack():
    tasks = []
    for i in range(4):
        tasks.append(
            type(
                "_T",
                (),
                {
                    "business_action_json": {
                        "execution_pack": {"pack_type": "partner_outreach_pack"},
                        "action_instance": {
                            "status": "skipped",
                            "owner_feedback": "не сработало",
                            "result_summary": "",
                        },
                        "result_snapshots": [],
                        "execution_scoring": {"actionability": 0.2, "result_probability": 0.1},
                    }
                },
            )()
        )

    hints = {"partner_outreach_pack": build_pack_learning_hints("partner_outreach_pack", tasks)}
    ctx = ExecutionContext(
        next_business_step="Сделать outreach партнёрам",
        owner_text="нужны контакты спонсоров",
        business_type="revenue",
    )
    pack = build_pack(ctx, learning_hints=hints)
    assert pack.pack_type == "generic_pack"
    assert any("входных данных" in s.lower() for s in pack.ready_steps)


def test_growth_engine_priority_prefers_revenue_pack():
    tasks = [
        type(
            "_T",
            (),
            {
                "business_action_json": {
                    "execution_pack": {"pack_type": "offer_pack"},
                    "action_instance": {"status": "done", "action_type": "offer_pack", "started_at": "x"},
                    "deals": [{"status": "won", "amount": "100000", "source_pack_type": "offer_pack", "source_action_id": "a1"}],
                    "leads": [{"source_pack_type": "offer_pack", "source_action_id": "a1"}],
                }
            },
        )(),
        type(
            "_T",
            (),
            {
                "business_action_json": {
                    "execution_pack": {"pack_type": "partner_outreach_pack"},
                    "action_instance": {"status": "skipped", "action_type": "partner_outreach_pack"},
                    "deals": [],
                    "leads": [],
                }
            },
        )(),
    ]
    perf = compute_pack_performance_with_revenue(tasks)
    assert perf["offer_pack"]["priority_score"] > perf["partner_outreach_pack"]["priority_score"]
    insight = build_growth_insight(tasks)
    assert insight["top_packs"]
    assert "metrics_7d" in insight and "pack_dynamics" in insight


def test_growth_override_blocked_without_min_samples():
    assert not growth_override_allowed(
        base_priority=0.1,
        best_priority=0.9,
        base_generated=2,
        best_generated=8,
    )
    assert growth_override_allowed(
        base_priority=0.1,
        best_priority=0.55,
        base_generated=8,
        best_generated=8,
    )


def test_apply_learning_no_override_when_low_n():
    hints = {
        "offer_pack": {"priority_score": 0.6, "recommended_mode": "normal_generate", "growth_generated": 8},
        "partner_outreach_pack": {
            "priority_score": 0.05,
            "recommended_mode": "normal_generate",
            "growth_generated": 2,
        },
    }
    out = apply_learning_to_pack_builder({"base_pack_type": "partner_outreach_pack"}, hints)
    assert out["selected_pack_type"] == "partner_outreach_pack"
    assert out["recommended_mode"] != "growth_override"


def test_action_instance_has_created_timestamp():
    task = type(
        "_Task",
        (),
        {
            "id": 101,
            "project_id": 1,
            "business_action_json": {
                "execution_pack": {
                    "pack_type": "offer_pack",
                    "action_title": "Собрать оффер",
                    "why": "Рост выручки",
                    "expected_result": "1 лид",
                    "ready_steps": ["Шаг 1"],
                    "how_to_execute": "Сделать шаг 1",
                    "checklist": ["готово"],
                }
            },
        },
    )()
    blob = ensure_action_instance_blob(task, project=None, all_tasks=None)
    assert isinstance(blob, dict)
    action = blob.get("action_instance") or {}
    assert action.get("created_at")
    out = apply_action_feedback(blob, status="in_progress")
    assert (out.get("action_instance") or {}).get("created_at")
