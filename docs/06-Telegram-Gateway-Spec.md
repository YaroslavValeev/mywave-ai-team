# Telegram-шлюз (v1.1)

## Компоненты
- aiogram bot (private chat)
- orchestrator (CrewAI runtime)
- state store (PostgreSQL)
- artifact store (disk/S3)
- audit logging (JSON) + redaction

## Кнопки (по умолчанию)
- ✅ Approve (a:{task_id})
- 🔁 Rework (r:{task_id})
- ❓ Clarify (c:{task_id})
- 📄 Full report (f:{task_id})

Ограничение callback_data: до 64 байт → используем короткие коды.

## Режимы сообщений
- Short summary (<=1200 chars)
- Full report as file (md/pdf)
- Evidence pack as zip (опционально)

## Ошибки и ретраи
- Telegram send fail → 3 ретрая (экспонента)
- Agent timeout → 1 ретрай, затем fallback или “частичный результат”
- DB fail → стоп + уведомление Owner
