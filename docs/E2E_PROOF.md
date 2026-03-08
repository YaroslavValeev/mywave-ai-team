# E2E Proof — сквозной сценарий (MW-AITEAM-v0.2.1)

Один воспроизводимый сценарий: MCP task_create → pipeline_run → local runner PR → Telegram PR ready → Approve → ручной merge → I merged → DONE.

**Секреты в документе отсутствуют.**

---

## Сценарий

### 1. MCP task_create

Cursor (с подключённым MCP mywave-ai-team) вызывает tool `task_create`:
- domain: PRODUCT_DEV
- task_type: feature_delivery
- payload: { "title": "Add X" }

Результат: `{"id": 1, "status": "NEW", "domain": "PRODUCT_DEV"}`

### 2. MCP pipeline_run

Tool `pipeline_run` с task_id=1.

Результат: `{"ok": true, "status": "WAIT_OWNER", "report_path": "..."}`

### 3. Local Runner PR

```bash
# На машине Owner (локально)
cd /path/to/mywave-ai-team
# .env.local содержит OWNER_API_KEY, GH_TOKEN, MYWAVE_BASE_URL

python -c "
import asyncio
from app.runners.cursor_runner.pr_loop import run_pr_loop
r = asyncio.run(run_pr_loop(task_id=1, workspace_path='.', mode='manual'))
print(r)
"
```

Результат: `{success: true, pr_url: "https://github.com/.../pull/2", commit_sha: "abc123", ci_url: "https://.../actions?query=..."}`

### 4. Telegram PR ready

Owner получает сообщение:
- task_id, summary
- PR URL, Dashboard URL
- Кнопки: Approve, Rework, Clarify, I merged

### 5. Approve

Owner нажимает **Approve** → статус `APPROVED_WAIT_MERGE`.
Сообщение: «Смерджи PR в GitHub, затем нажми I merged».

### 6. Ручной merge

Owner открывает PR в GitHub UI → Merge pull request → Confirm merge.

### 7. I merged

Owner нажимает **I merged** в Telegram → статус `DONE`.

---

## Audit trail (пример, без секретов)

```
event_type=mcp_tool_invoke payload={"tool_name":"task_create","actor":"mcp","status":"ok","latency_ms":120,"request_id":"a1b2c3-..."}
event_type=api_request payload={"actor":"owner","route":"/api/tasks","task_id":null,"status_code":201,"latency_ms":45,"request_id":"a1b2c3-..."}
event_type=mcp_tool_invoke payload={"tool_name":"pipeline_run","actor":"mcp","status":"ok","latency_ms":350,"request_id":"d4e5f6-..."}
event_type=api_request payload={"actor":"owner","route":"/api/tasks/1/pipeline/run","task_id":1,"status_code":200,"latency_ms":320,"request_id":"d4e5f6-..."}
event_type=OWNER_APPROVED payload={"decision":"approve"}
event_type=OWNER_MERGED payload={"decision":"i_merged"}
```

Корреляция: `request_id` связывает `mcp_tool_invoke` с соответствующим `api_request`.

---

## Проверка

1. `pytest -q` — все тесты проходят
2. Token scan — CI не находит паттерны токенов
3. Ручной прогон по шагам 1–7
