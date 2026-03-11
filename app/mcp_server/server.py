# app/mcp_server/server.py — минимальный MCP-сервер (stdio transport)
# Запуск: python -m app.mcp_server.server
# Конфиг: app/config/mcp_tools.yaml

import json
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle_request(req: dict) -> dict:
    """Обработка MCP-запроса (tool call)."""
    method = req.get("method")
    params = req.get("params", {})
    req_id = req.get("id")

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {}) or {}
        if isinstance(args, str):
            import json
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        from app.mcp_server.executor import execute_tool
        text, success = execute_tool(name, args)
        result = {"content": [{"type": "text", "text": text}]}
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "serverInfo": {"name": "mywave-ai-team", "version": "1.2.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "tools/list":
        from app.mcp_server.tools import TOOLS_SPEC
        tools = [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS_SPEC]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}


def main():
    """Чтение JSON-RPC из stdin, ответ в stdout (newline-delimited JSON)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            print(json.dumps(resp), flush=True)
        except Exception as e:
            logger.exception("MCP error: %s", e)
            req_id = None
            try:
                req_id = json.loads(line).get("id") if line else None
            except Exception:
                pass
            err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
            print(json.dumps(err), flush=True)


if __name__ == "__main__":
    main()
