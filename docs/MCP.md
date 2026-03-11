# MCP — подключение Tools к Cursor/агентам

Private MCP Server для MyWave AI-TEAM. Инструменты: tasks, artifacts, pipeline, PR, logs, health.

## Что это даёт

Cursor-агенты работают с AI-TEAM напрямую через MCP tools, а не через копипаст. Создание задач, получение артефактов, запуск пайплайна, PR — всё как инструменты.

## Tools (список)

| Tool | Описание |
|------|----------|
| `task_create` | Создать задачу (domain, task_type, payload) |
| `task_update` | Обновить задачу (status, decisions) |
| `task_get` | Получить задачу по task_id |
| `artifacts_list` | Список артефактов по task_id |
| `artifacts_get` | Содержимое артефакта |
| `pipeline_run` | Запустить пайплайн |
| `pr_create` | Создать PR (через gateway) |
| `logs_get` | Логи по task_id (без секретов) |
| `health` | Статус окружения |

## Подключение в Cursor

1. Добавить MCP-сервер в настройки Cursor (MCP config).
2. Transport: stdio.
3. Command: `python -m app.mcp_server.server` (из корня репо).

Пример конфига Cursor MCP (v0.2):

```json
{
  "mcpServers": {
    "mywave-ai-team": {
      "command": "python",
      "args": ["-m", "app.mcp_server.server"],
      "cwd": "/path/to/mywave-ai-team",
      "env": {
        "OWNER_API_KEY": "<твой ключ>",
        "MYWAVE_BASE_URL": "https://agm.mywavetreaning.ru"
      }
    }
  }
}
```

MCP tools вызывают HTTPS API сервера. Без `OWNER_API_KEY` и `MYWAVE_BASE_URL` запросы не пройдут.

## Безопасность

- `app/config/mcp_tools.yaml` — конфиг tools и security.
- Требуется API key.
- Секреты не передаются в tools (redaction).
- Gateway выдаёт только capabilities.
