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
2. CSV: положить `contacts_unique.csv` в `execution/`  
   (или уже есть `parsernews_outreach_contacts_*.csv` с RU).
3. Проверить согласие / сегмент (не слать всем подряд).
4. Рассылка — **вручную** или через согласованный tool; не через боевой TG-бот AI-TEAM без отдельного policy GO.
5. Записать в `send_log.md`: дата, число получателей, канал, результат.
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
