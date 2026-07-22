# agents-http-client

Тонкий HTTP-клиент к **Agents Control API** (Governance Layer).

Используется:

- Personal_Helper (product shell) — create / list / approve
- Molt (runtime) — health / task status / execution-events (read) при необходимости governance sync

**Не** дублирует SoT. SoT остаётся в Agents store (+ shared-core canonical path).

## Env

| Переменная | Пример |
|------------|--------|
| `AGENTS_CONTROL_API_URL` | `https://agm.mywavewake.ru` или `http://127.0.0.1:8088` |
| `AGENTS_API_KEY` / `OWNER_API_KEY` | тот же ключ, что `X-API-Key` |

## Использование

```python
from agents_http_client import AgentsControlClient

client = AgentsControlClient.from_env()
health = client.health()
task = client.create_task(owner_text="#TASK from Personal_Helper")
client.approve(task["id"])
```

## Установка в umbrella

```text
PYTHONPATH=.../MyWave_AI_TEAM_Presets_v1_1/packages/agents-http-client;...
```

или скопировать пакет в `AI-Team/packages/agents-http-client` (mirror).
