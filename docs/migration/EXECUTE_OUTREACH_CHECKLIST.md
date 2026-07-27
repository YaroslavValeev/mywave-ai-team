# EXECUTE after Owner approve — checklist (MEDIA outreach)

Статус: operational (minimal pack)  
Дата: 2026-07-27  
Связано: task #30/#32/#33, OPEN_BACKLOG EX, `app/orchestrator/execution_pack.py`

## Когда

После Telegram **✅ Утвердить** на `content_pipeline` / MEDIA (или API approve):

1. Статус → **`EXECUTION_READY`** (не DONE, пока не отметите завершение рассылки).
2. Пишется пакет в `app/artifacts/tasks/task_N/execution/`:
   - `EXECUTE_PACK.md` — инструкция
   - `message_to_send.txt` — текст из deliverable
   - `send_log.md` — шаблон лога (пусто)
3. В TG приходит путь к пакету. **Авторассылки нет.**

## Шаги (человек + Cursor)

1. Открыть `EXECUTE_PACK.md` / `message_to_send.txt`.
2. Финализировать prep (копия CSV + сегменты, **без отправки**):
   ```bash
   python3 scripts/finalize_outreach_prep.py --task-id N
   # или в контейнере:
   docker compose exec app python scripts/finalize_outreach_prep.py --task-id N
   ```
   Появятся: `contacts_unique.csv`, `segment_inventory.md`, `segment_emails_pilot.csv`, `segment_telegram_hold.csv`, обновлённый `send_log.md`.
3. Проверить согласие / сегмент (не слать всем подряд). Telegram-hold = HOLD.
4. Рассылка — **вручную** или через согласованный tool; не через боевой TG-бот AI-TEAM без отдельного policy GO.
5. После реальной отправки дописать в `send_log.md`: дата, число, канал, результат.
6. Закрыть миссию:
   ```bash
   docker compose exec app python scripts/prepare_outreach_execute.py --task-id N --mark-done
   ```

## Ручной prepare (если approve был раньше / pack потерян)

```bash
docker compose exec app python scripts/prepare_outreach_execute.py --task-id N
```

## Запрещено без отдельного Owner GO

- Массовая отправка из контейнера AI-TEAM  
- Публикация CSV с PII в git / публичный artifact viewer без redaction  

## Rollback

Удалить CSV с RU; статус можно вернуть через rework; не трогать Sheets.
