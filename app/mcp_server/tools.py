# app/mcp_server/tools.py — определения MCP tools
# Регистрация инструментов: tasks, artifacts, pipeline, PR, logs, health.

TOOLS_SPEC = [
    {
        "name": "tasks_list",
        "description": "Получить список задач",
        "inputSchema": {"type": "object", "properties": {}},
    },
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
        "name": "task_mark_merged",
        "description": "Подтвердить ручной merge задачи Owner'ом",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "task_approve",
        "description": "Owner approve (паритет Telegram/Dashboard POST /api/tasks/{id}/approve)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "task_rework",
        "description": "Owner rework (POST /api/tasks/{id}/rework)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "task_clarify",
        "description": "Owner clarify (POST /api/tasks/{id}/clarify)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "runs_list",
        "description": "Персистентные проходы оркестрации (GET /api/tasks/{id}/runs)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "execution_events_list",
        "description": "События исполнения SoT (GET /api/tasks/{id}/execution-events)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "task_get",
        "description": "Получить задачу по task_id или mission_id (одинаковые идентификаторы)",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "mission_id": {"type": "string"}, "raw": {"type": "boolean"}},
            "anyOf": [{"required": ["task_id"]}, {"required": ["mission_id"]}],
        },
    },
    {
        "name": "mission_thread",
        "description": "Единая нить миссии: audit + чат + handoffs (GET /api/missions/{id}/thread)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mission_id": {"type": "string"},
                "task_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "anyOf": [{"required": ["task_id"]}, {"required": ["mission_id"]}],
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
    {
        "name": "gateway_catalog",
        "description": "OpenClaw-style каталог capabilities (без секретов): какие интеграции сконфигурированы",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
