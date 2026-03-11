# app/mcp_server/tools.py — определения MCP tools
# Регистрация инструментов: tasks, artifacts, pipeline, PR, logs, health.

TOOLS_SPEC = [
    {
        "name": "task_create",
        "description": "Создать задачу в AI-TEAM (task_id, domain, task_type, payload)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "task_type": {"type": "string"},
                "payload": {"type": "object"},
                "criticality": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            },
            "required": ["domain", "task_type"],
        },
    },
    {
        "name": "task_update",
        "description": "Обновить задачу (task_id, status, decisions, artifacts)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "status": {"type": "string"},
                "decisions": {"type": "array"},
                "artifacts": {"type": "object"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "task_get",
        "description": "Получить задачу по task_id",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "artifacts_list",
        "description": "Список артефактов по task_id",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "artifacts_get",
        "description": "Получить содержимое артефакта (artifact_id = handoff id)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "artifact_id": {"type": "integer"}},
            "required": ["task_id", "artifact_id"],
        },
    },
    {
        "name": "pipeline_run",
        "description": "Запустить пайплайн для task_id",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "pr_create",
        "description": "Создать PR (через gateway, с минимальными правами)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "branch": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["branch", "title"],
        },
    },
    {
        "name": "logs_get",
        "description": "Получить логи по task_id (без секретов)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "health",
        "description": "Статус окружения (DB, dashboard, gateway)",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
