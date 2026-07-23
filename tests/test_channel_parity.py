# Phase 6: канонические маршруты owner + observability (паритет каналов через единый Control API).
#
# Assert via OpenAPI paths — FastAPI 0.139+ nests include_router under _IncludedRouter,
# so flat `app.routes` + getattr(path) misses /api/* (CI red). Prod routes still exist.


def test_control_api_exposes_owner_and_observability_routes():
    """Все каналы (Telegram→логика, Dashboard form, Office fetch, MCP→api_client) сходятся к /api/*."""
    from app.dashboard.app import app

    route_paths = list(app.openapi()["paths"].keys())

    expected = [
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
    for path in expected:
        assert path in route_paths, f"missing OpenAPI path {path}"


def test_dashboard_html_routes_exist():
    """Формы task_detail дублируют те же действия через POST /tasks/{id}/… (cookie/query api_key)."""
    from app.dashboard.app import app

    paths = list(app.openapi()["paths"].keys())
    for suffix in (
        "/tasks/{task_id}/approve",
        "/tasks/{task_id}/rework",
        "/tasks/{task_id}/clarify",
        "/tasks/{task_id}/merged",
    ):
        assert any(p.endswith(suffix) or p == suffix for p in paths), suffix
