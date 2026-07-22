# tests/test_mcp_tools_http.py — MCP tools через api_client (mock)
import os
import pytest
from unittest.mock import patch

# Mock BASE_URL чтобы не ходить в сеть
os.environ.setdefault("MYWAVE_BASE_URL", "http://localhost:9999")
os.environ.setdefault("OWNER_API_KEY", "test_key")


def test_mcp_executor_health_with_mock():
    """health tool с mock — возвращает ok при 200."""
    with patch("app.shared.api_client.health") as mock_health:
        mock_health.return_value = (True, "ok")
        from app.mcp_server.executor import execute_tool
        text, success = execute_tool("health", {})
        assert success is True
        assert "ok" in text.lower() or "true" in text.lower()


def test_mcp_executor_task_create_with_mock():
    """task_create через api_client (mock)."""
    with patch("app.shared.api_client.task_create") as mock:
        mock.return_value = ({"id": 1, "status": "NEW"}, None)
        from app.mcp_server.executor import execute_tool
        text, success = execute_tool("task_create", {"domain": "PRODUCT_DEV", "task_type": "general"})
        assert success is True
        mock.assert_called_once()
        call_kw = mock.call_args
        assert call_kw[0][0] == "PRODUCT_DEV"
        assert call_kw[0][1] == "general"


def test_mcp_executor_task_get_error_without_task_id():
    """task_get без task_id/mission_id → error."""
    from app.mcp_server.executor import execute_tool
    text, success = execute_tool("task_get", {})
    assert success is False
    assert "task_id" in text.lower() or "mission_id" in text.lower() or "error" in text.lower()


def test_mcp_executor_task_get_with_mission_id_mock():
    with patch("app.shared.api_client.task_get") as mock:
        mock.return_value = ({"id": 5, "mission_id": 5}, None)
        from app.mcp_server.executor import execute_tool

        text, success = execute_tool("task_get", {"mission_id": "5"})
        assert success is True
        mock.assert_called_once_with(5, raw=False)


def test_mcp_executor_mission_thread_with_mock():
    with patch("app.shared.api_client.mission_thread_get") as mock:
        mock.return_value = ({"mission": {"mission_id": 1}, "items": [], "count": 0}, None)
        from app.mcp_server.executor import execute_tool

        text, success = execute_tool("mission_thread", {"mission_id": "1", "limit": 50})
        assert success is True
        mock.assert_called_once_with(1, limit=50)


def test_mcp_executor_tasks_list_with_mock():
    """tasks_list возвращает список задач через api_client."""
    with patch("app.shared.api_client.tasks_list") as mock:
        mock.return_value = ([{"id": 1, "status": "NEW"}], None)
        from app.mcp_server.executor import execute_tool
        text, success = execute_tool("tasks_list", {})
        assert success is True
        assert '"id": 1' in text
        mock.assert_called_once()


def test_mcp_executor_task_mark_merged_with_mock():
    """task_mark_merged вызывает api_client.task_mark_merged."""
    with patch("app.shared.api_client.task_mark_merged") as mock:
        mock.return_value = ({"id": 1, "status": "DONE"}, None)
        from app.mcp_server.executor import execute_tool
        text, success = execute_tool("task_mark_merged", {"task_id": "1"})
        assert success is True
        assert "DONE" in text
        mock.assert_called_once_with(1)


def test_mcp_executor_task_approve_with_mock():
    with patch("app.shared.api_client.task_approve") as mock:
        mock.return_value = ({"id": 1, "status": "DONE"}, None)
        from app.mcp_server.executor import execute_tool

        text, success = execute_tool("task_approve", {"task_id": "1"})
        assert success is True
        mock.assert_called_once_with(1)


def test_mcp_executor_runs_list_with_mock():
    with patch("app.shared.api_client.task_runs_list") as mock:
        mock.return_value = ({"task_id": 1, "runs": []}, None)
        from app.mcp_server.executor import execute_tool

        text, success = execute_tool("runs_list", {"task_id": "2"})
        assert success is True
        assert "runs" in text
        mock.assert_called_once_with(2)


def test_mcp_executor_execution_events_with_mock():
    with patch("app.shared.api_client.task_execution_events_list") as mock:
        mock.return_value = ({"task_id": 1, "events": []}, None)
        from app.mcp_server.executor import execute_tool

        text, success = execute_tool("execution_events_list", {"task_id": "3", "limit": 50})
        assert success is True
        mock.assert_called_once_with(3, limit=50)


def test_mcp_executor_gateway_catalog_with_mock():
    with patch("app.shared.api_client.gateway_catalog") as mock:
        mock.return_value = ({"model": "gateway-v1", "capabilities": []}, None)
        from app.mcp_server.executor import execute_tool

        text, success = execute_tool("gateway_catalog", {})
        assert success is True
        assert "gateway" in text.lower()
        mock.assert_called_once()
