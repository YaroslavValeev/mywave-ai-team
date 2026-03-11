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
    """task_get без task_id → error."""
    from app.mcp_server.executor import execute_tool
    text, success = execute_tool("task_get", {})
    assert success is False
    assert "task_id" in text.lower() or "error" in text.lower()
