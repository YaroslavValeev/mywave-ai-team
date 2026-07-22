# Phase 6: канонические маршруты owner + observability (паритет каналов через единый Control API).


def test_control_api_exposes_owner_and_observability_routes():
    """Все каналы (Telegram→логика, Dashboard form, Office fetch, MCP→api_client) сходятся к /api/*."""
    from app.dashboard.app import app

    route_paths = []
    for r in app.routes:
        p = getattr(r, "path", None)
        if p:
            route_paths.append(p)

    expected_substrings = [
        "/api/tasks/{task_id}/approve",
        "/api/tasks/{task_id}/rework",
        "/api/tasks/{task_id}/clarify",
        "/api/tasks/{task_id}/merged",
        "/api/tasks/{task_id}/runs",
        "/api/tasks/{task_id}/execution-events",
        "/api/tasks/{task_id}/pipeline/run",
        "/api/missions/{mission_id}/scene",
        "/api/missions/{mission_id}/thread",
        "/api/tasks/{task_id}/thread",
        "/api/gateway/catalog",
        "/api/gateway/evaluate",
    ]
    for fragment in expected_substrings:
        assert any(fragment in path for path in route_paths), f"missing route containing {fragment}"


def test_dashboard_html_routes_exist():
    """Формы task_detail дублируют те же действия через POST /tasks/{id}/… (cookie/query api_key)."""
    from app.dashboard.app import app

    paths = [getattr(r, "path", "") for r in app.routes]
    for suffix in ("/tasks/{task_id}/approve", "/tasks/{task_id}/rework", "/tasks/{task_id}/clarify", "/tasks/{task_id}/merged"):
        assert any(p.endswith(suffix) or suffix in p for p in paths), suffix
